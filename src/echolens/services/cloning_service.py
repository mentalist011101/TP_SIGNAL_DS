"""Clonage de voix (EF-18, ENF-10, S6, C35) : faire dire un texte à une voix consentante, et
garder chaque extrait, marqué « voix synthétique ».

Contrôles avant tout calcul : le locuteur existe, il a accepté le clonage (seconde case de la
page Locuteurs), le texte n'est ni vide ni trop long. Le calcul tourne en arrière-plan (S2) :
XTTS-v2 sur CPU met plusieurs secondes par phrase. L'extrait est marqué trois fois :
- un bip audible au début (echolens.core.synthetic_marker) ;
- le nom du fichier téléchargé commence par « voix_synthetique » ;
- les métadonnées du WAV (titre et commentaire) le disent.
Il est rangé dans le dossier du locuteur : supprimer le locuteur supprime ses extraits.
"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

import soundfile as sf
from sqlalchemy import select, update
from werkzeug.utils import secure_filename

from echolens.core.synthetic_marker import mark_synthetic
from echolens.services.analysis_service import INTERRUPTED_MESSAGE, AnalysisService
from echolens.services.storage import AnalysisStatus, SynthesisRecord
from echolens.services.voice_cloning import CloningUnavailableError, VoiceCloner

SYNTHESIS_AUDIO_SUBTYPE = "PCM_16"
SYNTHETIC_TITLE = "Voix synthétique (EchoLens)"
SOFTWARE = "EchoLens"


class CloningRejectedError(ValueError):
    """Demande de clonage refusée (texte vide ou trop long) ; message affiché tel quel."""


class CloningForbiddenError(PermissionError):
    """Le locuteur n'a pas accepté que sa voix soit clonée (ENF-10)."""


class SynthesisNotFoundError(LookupError):
    """Aucun extrait synthétique ne porte cet identifiant."""


class CloningService:
    """Crée, liste et supprime les extraits synthétiques ; seul accès à la table syntheses.

    Reprend les locuteurs, le pool de threads et les réglages des analyses.
    """

    def __init__(self, analysis_service: AnalysisService, cloner: VoiceCloner | None) -> None:
        self.analyses = analysis_service
        self.speakers = analysis_service.speakers
        self.session_factory = analysis_service.session_factory
        self.settings = analysis_service.result_context.inference_config.voice_cloning
        self.cloner = cloner
        self._fail_interrupted_syntheses()

    def clone(self, speaker_id: str, text: str) -> SynthesisRecord:
        """Accepte une demande de clonage et lance le calcul en arrière-plan.

        Lève SpeakerNotFoundError, CloningForbiddenError, CloningRejectedError ou
        CloningUnavailableError ; dans ces cas, rien n'est enregistré.
        """
        # Étape 1 : contrôles, du plus grave au plus simple.
        speaker = self.speakers.get_speaker(speaker_id)
        if not speaker.cloning_allowed:
            raise CloningForbiddenError(
                f"{speaker.name} n'a pas accepté que sa voix soit clonée : seule une voix "
                "consentante peut l'être (ENF-10)."
            )
        clean_text = self._check_text(text)
        if self.cloner is None:
            raise CloningUnavailableError("Aucun modèle de clonage dans configs/registry.yaml.")
        self.cloner.check_available()
        # Étape 2 : extrait au statut pending, puis calcul en arrière-plan (S2).
        record = SynthesisRecord(
            id=str(uuid.uuid4()),
            speaker_id=speaker_id,
            text=clean_text,
            status=AnalysisStatus.PENDING,
            model_id=self.cloner.model_id,
            model_version=self.cloner.model_version,
        )
        with self.session_factory() as session:
            session.add(record)
            session.commit()
        self._submit(record.id)
        return self.get_synthesis(record.id)

    def get_synthesis(self, synthesis_id: str) -> SynthesisRecord:
        """Renvoie un extrait synthétique, ou lève SynthesisNotFoundError."""
        with self.session_factory() as session:
            record = session.get(SynthesisRecord, synthesis_id)
        if record is None:
            raise SynthesisNotFoundError(
                f"Aucun extrait synthétique ne porte l'identifiant {synthesis_id}."
            )
        return record

    def list_syntheses(self) -> list[SynthesisRecord]:
        """Tous les extraits synthétiques, les plus récents d'abord."""
        query = select(SynthesisRecord).order_by(SynthesisRecord.created_at.desc())
        with self.session_factory() as session:
            return list(session.scalars(query).unique().all())

    def delete_synthesis(self, synthesis_id: str) -> None:
        """Supprime un extrait et son audio ; lève SynthesisNotFoundError."""
        record = self.get_synthesis(synthesis_id)
        with self.session_factory() as session:
            stored = session.get(SynthesisRecord, synthesis_id)
            session.delete(stored)
            session.commit()
        self.audio_path(record).unlink(missing_ok=True)

    def audio_path(self, record: SynthesisRecord) -> Path:
        """WAV marqué de l'extrait, dans le dossier du locuteur cloné."""
        folder = self.speakers.speaker_dir(record.speaker_id) / "syntheses"
        return folder / f"{record.id}.wav"

    def download_name(self, record: SynthesisRecord) -> str:
        """« voix_synthetique_Awa_2026-11-27.wav » : le nom dit ce qu'est le fichier."""
        name = secure_filename(record.speaker_name) or "locuteur"
        day = record.created_at.strftime("%Y-%m-%d")
        return f"voix_synthetique_{name}_{day}.wav"

    def _check_text(self, text: str) -> str:
        clean_text = text.strip()
        if not clean_text:
            raise CloningRejectedError("Écrivez le texte à faire dire.")
        if len(clean_text) > self.settings.max_text_chars:
            raise CloningRejectedError(
                f"Texte trop long : {self.settings.max_text_chars} caractères au plus."
            )
        return clean_text

    def _submit(self, synthesis_id: str) -> None:
        if self.analyses.settings.run_jobs_synchronously:
            self._process(synthesis_id)
            return
        self.analyses.executor.submit(self._process, synthesis_id)

    def _process(self, synthesis_id: str) -> None:
        record = self.get_synthesis(synthesis_id)
        self._update(synthesis_id, AnalysisStatus.PROCESSING)
        try:
            duration_s, compute_s = self._synthesize(record)
        except CloningUnavailableError as error:
            self._update(synthesis_id, AnalysisStatus.FAILED, error_message=str(error))
            return
        except Exception as error:
            # Frontière du thread : toute erreur finit en statut failed, comme une analyse.
            message = f"Échec du clonage : {error}"
            self._update(synthesis_id, AnalysisStatus.FAILED, error_message=message)
            return
        self._update(synthesis_id, AnalysisStatus.DONE, duration_s=duration_s, compute_s=compute_s)

    def _synthesize(self, record: SynthesisRecord) -> tuple[float, float]:
        if self.cloner is None:
            raise CloningUnavailableError("Aucun modèle de clonage dans configs/registry.yaml.")
        # Étape 1 : la voix, à partir des extraits d'enregistrement du locuteur (C15).
        references = self.speakers.enrollment_audio(record.speaker_id)
        started = time.perf_counter()
        speech = self.cloner.synthesize(record.text, references)
        compute_s = time.perf_counter() - started
        # Étape 2 : bip de marquage, puis WAV avec les métadonnées « voix synthétique ».
        marked = mark_synthetic(speech.samples, speech.sample_rate, self.settings)
        path = self.audio_path(record)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._write_marked_wav(path, marked, speech.sample_rate, record)
        duration_s = len(marked) / speech.sample_rate
        return duration_s, compute_s

    def _write_marked_wav(
        self, path: Path, samples: object, sample_rate: int, record: SynthesisRecord
    ) -> None:
        comment = (
            f"Voix synthétique générée par {record.model_id} à partir de la voix de "
            f"{record.speaker_name}, avec son consentement ({self.settings.consent_version}). "
            "Ce n'est pas un enregistrement réel."
        )
        with sf.SoundFile(
            path, mode="w", samplerate=sample_rate, channels=1, subtype=SYNTHESIS_AUDIO_SUBTYPE
        ) as handle:
            # Les métadonnées sont écrites avant les échantillons (bloc INFO du WAV).
            handle.title = SYNTHETIC_TITLE
            handle.comment = comment
            handle.software = SOFTWARE
            handle.write(samples)

    def _update(
        self,
        synthesis_id: str,
        status: AnalysisStatus,
        error_message: str | None = None,
        duration_s: float | None = None,
        compute_s: float | None = None,
    ) -> None:
        with self.session_factory() as session:
            record = session.get(SynthesisRecord, synthesis_id)
            # Supprimé pendant le calcul (avec son locuteur) : rien à mettre à jour.
            if record is None:
                return
            record.status = status
            record.error_message = error_message
            if duration_s is not None:
                record.duration_s = duration_s
            if compute_s is not None:
                record.compute_s = compute_s
            session.commit()

    def _fail_interrupted_syntheses(self) -> None:
        # Comme pour les analyses : un calcul en cours au redémarrage ne finira jamais.
        unfinished = [AnalysisStatus.PENDING, AnalysisStatus.PROCESSING]
        statement = update(SynthesisRecord).where(SynthesisRecord.status.in_(unfinished))
        statement = statement.values(
            status=AnalysisStatus.FAILED, error_message=INTERRUPTED_MESSAGE
        )
        with self.session_factory() as session:
            session.execute(statement)
            session.commit()
