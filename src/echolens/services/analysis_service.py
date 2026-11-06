"""Cycle de vie d'une analyse : import contrôlé, stockage, traitement en arrière-plan (S2, S3, S6).

Les contrôles rapides (extension, décodage, durée, silence) sont faits pendant la requête, avant
de créer l'analyse, pour répondre tout de suite à l'utilisateur. Le traitement long tourne en
arrière-plan (ENF-03) et met à jour le statut en base, que le front interroge.
"""

from __future__ import annotations

import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import soundfile as sf
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from echolens.config import AppSettings
from echolens.core.audio import AudioDecodeError, AudioTooLongError, is_silent, load_audio
from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.services.storage import AnalysisRecord, AnalysisStatus

# Format de l'audio conservé : WAV PCM 16 bits, mono 16 kHz (D2).
CONVERTED_AUDIO_NAME = "audio.wav"
CONVERTED_AUDIO_SUBTYPE = "PCM_16"


class AnalysisRejectedError(ValueError):
    """Le fichier importé ne passe pas un contrôle ; le message s'affiche tel quel."""


class AnalysisNotFoundError(LookupError):
    """Aucune analyse ne porte cet identifiant."""


class AnalysisService:
    """Crée, traite, liste et supprime les analyses ; seul point d'accès à la table analyses."""

    def __init__(self, settings: AppSettings, session_factory: sessionmaker[Session]) -> None:
        self.settings = settings
        self.session_factory = session_factory
        self.executor = ThreadPoolExecutor(max_workers=settings.analysis_workers)

    def create_analysis(
        self, upload: FileStorage, tasks: list[str], profile: str
    ) -> AnalysisRecord:
        """Contrôle le fichier, enregistre l'analyse au statut pending et lance son traitement.

        Lève AnalysisRejectedError (message en français) si un contrôle échoue ; dans ce cas,
        rien n'est enregistré.
        """
        # Étape 1 : nom nettoyé et extension autorisée, avant d'écrire quoi que ce soit (S6).
        filename = secure_filename(upload.filename or "")
        extension = self._check_extension(filename)

        # Étape 2 : copie sur disque, puis contrôles qui demandent de décoder l'audio (D6).
        analysis_id = str(uuid.uuid4())
        folder = self.analysis_dir(analysis_id)
        folder.mkdir(parents=True)
        original = folder / f"original.{extension}"
        upload.save(original)
        try:
            self._check_audio(original)
        except AnalysisRejectedError:
            shutil.rmtree(folder)
            raise

        # Étape 3 : enregistrement au statut pending, puis traitement en arrière-plan (S2).
        record = AnalysisRecord(
            id=analysis_id,
            original_filename=filename,
            status=AnalysisStatus.PENDING,
            tasks=tasks,
            profile=profile,
        )
        with self.session_factory() as session:
            session.add(record)
            session.commit()
        self._submit(analysis_id)
        return self.get_analysis(analysis_id)

    def get_analysis(self, analysis_id: str) -> AnalysisRecord:
        """Renvoie une analyse, ou lève AnalysisNotFoundError."""
        with self.session_factory() as session:
            record = session.get(AnalysisRecord, analysis_id)
        if record is None:
            raise AnalysisNotFoundError(f"Analyse introuvable : {analysis_id}")
        return record

    def list_analyses(self, limit: int, offset: int) -> list[AnalysisRecord]:
        """Historique des analyses, les plus récentes d'abord (EF-08)."""
        query = select(AnalysisRecord)
        query = query.order_by(AnalysisRecord.created_at.desc())
        query = query.limit(limit).offset(offset)
        with self.session_factory() as session:
            records = session.scalars(query).all()
        return list(records)

    def delete_analysis(self, analysis_id: str) -> None:
        """Supprime la ligne en base et le dossier de fichiers de l'analyse."""
        with self.session_factory() as session:
            record = session.get(AnalysisRecord, analysis_id)
            if record is None:
                raise AnalysisNotFoundError(f"Analyse introuvable : {analysis_id}")
            session.delete(record)
            session.commit()
        shutil.rmtree(self.analysis_dir(analysis_id), ignore_errors=True)

    def analysis_dir(self, analysis_id: str) -> Path:
        """Dossier des fichiers d'une analyse : <data_dir>/analyses/<id>/."""
        return self.settings.data_dir / "analyses" / analysis_id

    def converted_audio_path(self, analysis_id: str) -> Path:
        """Chemin de l'audio converti en 16 kHz mono (audio.wav)."""
        return self.analysis_dir(analysis_id) / CONVERTED_AUDIO_NAME

    def _check_extension(self, filename: str) -> str:
        extension = Path(filename).suffix.lower().removeprefix(".")
        if extension in self.settings.allowed_extensions:
            return extension
        allowed = ", ".join(self.settings.allowed_extensions)
        shown_name = filename
        if not shown_name:
            shown_name = "fichier sans nom"
        raise AnalysisRejectedError(
            f"Format non pris en charge : « {shown_name} ». Formats acceptés : {allowed}."
        )

    def _check_audio(self, path: Path) -> None:
        max_seconds = self.settings.max_audio_seconds
        try:
            signal = load_audio(path, max_seconds=max_seconds)
        except AudioTooLongError as error:
            raise AnalysisRejectedError(str(error)) from error
        except AudioDecodeError as error:
            raise AnalysisRejectedError(
                "Fichier audio illisible ou corrompu : impossible de le décoder."
            ) from error
        if is_silent(signal):
            raise AnalysisRejectedError("L'audio est silencieux : aucun son exploitable détecté.")

    def _submit(self, analysis_id: str) -> None:
        if self.settings.run_jobs_synchronously:
            self._process(analysis_id)
            return
        self.executor.submit(self._process, analysis_id)

    def _process(self, analysis_id: str) -> None:
        # Traitement d'une analyse. Les étapes suivantes (spectrogramme, modèles) s'ajouteront
        # après la conversion, dans le même bloc try.
        self._update(analysis_id, status=AnalysisStatus.PROCESSING)
        try:
            duration_s = self._convert_audio(analysis_id)
        except Exception as error:
            # Frontière du thread : toute erreur doit finir en statut failed, sinon elle
            # serait perdue dans le pool et l'analyse resterait « processing » pour toujours.
            message = f"Échec du traitement : {error}"
            self._update(analysis_id, status=AnalysisStatus.FAILED, error_message=message)
            return
        self._update(analysis_id, status=AnalysisStatus.DONE, duration_s=duration_s)

    def _convert_audio(self, analysis_id: str) -> float:
        # Décodage en mono 16 kHz float32 (D1, D2), puis écriture en WAV PCM 16 bits.
        record = self.get_analysis(analysis_id)
        extension = Path(record.original_filename).suffix.lower()
        original = self.analysis_dir(analysis_id) / f"original{extension}"
        signal = load_audio(original, max_seconds=self.settings.max_audio_seconds)
        # Le PCM 16 bits n'accepte que [-1, 1] : on écrête les rares dépassements du décodeur.
        clipped = np.clip(signal, -1.0, 1.0)
        destination = self.converted_audio_path(analysis_id)
        sf.write(destination, clipped, TARGET_SAMPLE_RATE, subtype=CONVERTED_AUDIO_SUBTYPE)
        duration_s = signal.size / TARGET_SAMPLE_RATE
        return duration_s

    def _update(
        self,
        analysis_id: str,
        status: AnalysisStatus,
        error_message: str | None = None,
        duration_s: float | None = None,
    ) -> None:
        with self.session_factory() as session:
            record = session.get(AnalysisRecord, analysis_id)
            # L'analyse a pu être supprimée pendant son traitement : rien à mettre à jour.
            if record is None:
                return
            record.status = status
            record.error_message = error_message
            if duration_s is not None:
                record.duration_s = duration_s
            session.commit()
