"""Locuteurs enregistrés (EF-11, S6) : enregistrement avec consentement, liste, suppression.

Enregistrer une voix : un ou plusieurs extraits (micro ou fichiers), la case de consentement
cochée, un nom. La VAD garde les morceaux de parole de 1 à 5 s (comme à l'analyse) ; il en faut
au moins 10 s au total. La voix est la moyenne normée de leurs vecteurs (C15). On garde la voix,
le modèle qui l'a calculée, et l'audio converti en WAV mono 16 kHz (décision de Luciano du
27 nov. 2026) ; supprimer le locuteur supprime tout.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker
from werkzeug.datastructures import FileStorage

from echolens.config import AppSettings
from echolens.core.audio import AudioDecodeError, AudioTooLongError, is_silent, load_audio
from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.core.inference import FloatArray, segment_samples, speaker_windows
from echolens.core.models.registry import Profile, Task
from echolens.core.speaker_id import voice_print
from echolens.services.results import EnrolledVoice, ResultContext
from echolens.services.storage import CloningConsentRecord, SpeakerRecord

MAX_NAME_LENGTH = 80
# Le modèle de locuteur est le même dans les deux profils ; la voix est calculée avec celui du
# profil qualité, et son identifiant est gardé pour ne la comparer qu'à ce modèle.
ENROLLMENT_PROFILE = Profile.QUALITY
ENROLLMENT_AUDIO_SUBTYPE = "PCM_16"


class SpeakerRejectedError(ValueError):
    """La demande d'enregistrement ne passe pas un contrôle ; le message s'affiche tel quel."""


class SpeakerNotFoundError(LookupError):
    """Aucun locuteur ne porte cet identifiant."""


class SpeakerService:
    """Enregistre, liste et supprime les locuteurs ; seul point d'accès à la table speakers."""

    def __init__(
        self,
        settings: AppSettings,
        session_factory: sessionmaker[Session],
        context: ResultContext,
    ) -> None:
        self.settings = settings
        self.session_factory = session_factory
        # Même prédicteur, même VAD et mêmes réglages que les analyses.
        self.context = context

    def enroll(
        self, name: str, consent: bool, uploads: list[FileStorage], cloning_consent: bool = False
    ) -> SpeakerRecord:
        """Enregistre un locuteur ; lève SpeakerRejectedError, sans rien garder, si un contrôle
        échoue. cloning_consent : seconde case, la personne accepte aussi que sa voix soit
        clonée (C35, ENF-10) ; sans elle, la page Cloner ne la propose pas."""
        # Étape 1 : contrôles qui ne demandent pas de lire l'audio.
        clean_name = self._check_request(name, consent, uploads)
        speaker_id = str(uuid.uuid4())
        folder = self.speaker_dir(speaker_id)
        folder.mkdir(parents=True)
        try:
            # Étape 2 : audio de chaque extrait, puis ses morceaux de parole.
            signals = self._read_uploads(uploads, folder)
            pieces = self._speech_pieces(signals)
            # Étape 3 : un vecteur par morceau, puis la voix moyenne (C15).
            vectors = self.context.predictor.embed_voices(ENROLLMENT_PROFILE, pieces)
            voice = voice_print(vectors)
        except SpeakerRejectedError:
            shutil.rmtree(folder)
            raise
        # Étape 4 : enregistrement en base, avec le modèle et la version du consentement.
        info = self.context.predictor.model_info(Task.SPEAKER, ENROLLMENT_PROFILE)
        speech_s = sum(len(piece) for piece in pieces) / TARGET_SAMPLE_RATE
        record = SpeakerRecord(
            id=speaker_id,
            name=clean_name,
            voice=[float(value) for value in voice],
            model_id=info.model_id,
            model_version=info.model_version,
            speech_s=speech_s,
            segment_count=len(pieces),
            audio_count=len(signals),
            consent_version=self.context.inference_config.speaker.consent_version,
        )
        if cloning_consent:
            version = self.context.inference_config.voice_cloning.consent_version
            record.cloning_consent_row = CloningConsentRecord(
                speaker_id=speaker_id, consent_version=version
            )
        with self.session_factory() as session:
            session.add(record)
            session.commit()
        return self.get_speaker(speaker_id)

    def get_speaker(self, speaker_id: str) -> SpeakerRecord:
        """Renvoie un locuteur, ou lève SpeakerNotFoundError."""
        with self.session_factory() as session:
            record = session.get(SpeakerRecord, speaker_id)
        if record is None:
            raise SpeakerNotFoundError(f"Aucun locuteur ne porte l'identifiant {speaker_id}.")
        return record

    def enrollment_audio(self, speaker_id: str) -> list[Path]:
        """Extraits d'enregistrement gardés (WAV mono 16 kHz), dans l'ordre d'envoi."""
        folder = self.speaker_dir(speaker_id)
        return sorted(folder.glob("enrollment_*.wav"))

    def list_speakers(self) -> list[SpeakerRecord]:
        """Tous les locuteurs, par ordre alphabétique de nom."""
        query = select(SpeakerRecord).order_by(SpeakerRecord.name)
        with self.session_factory() as session:
            return list(session.scalars(query).all())

    def delete_speaker(self, speaker_id: str) -> None:
        """Supprime le locuteur, sa voix et son audio ; lève SpeakerNotFoundError."""
        with self.session_factory() as session:
            record = session.get(SpeakerRecord, speaker_id)
            if record is None:
                raise SpeakerNotFoundError(f"Aucun locuteur ne porte l'identifiant {speaker_id}.")
            session.delete(record)
            session.commit()
        shutil.rmtree(self.speaker_dir(speaker_id), ignore_errors=True)

    def enrolled_voices(self) -> list[EnrolledVoice]:
        """Voix de tous les locuteurs, pour la tâche speaker des analyses."""
        voices: list[EnrolledVoice] = []
        for record in self.list_speakers():
            vector = np.array(record.voice, dtype=np.float64)
            voice = EnrolledVoice(
                speaker_id=record.id, name=record.name, voice=vector, model_id=record.model_id
            )
            voices.append(voice)
        return voices

    def speaker_dir(self, speaker_id: str) -> Path:
        """Dossier de l'audio d'enregistrement d'un locuteur."""
        return self.settings.data_dir / "speakers" / speaker_id

    def _check_request(self, name: str, consent: bool, uploads: list[FileStorage]) -> str:
        # Consentement d'abord (S6) : sans lui, on ne lit même pas l'audio.
        if not consent:
            raise SpeakerRejectedError(
                "Consentement requis : cochez la case pour enregistrer cette voix."
            )
        clean_name = name.strip()
        if not clean_name:
            raise SpeakerRejectedError("Donnez un nom au locuteur.")
        if len(clean_name) > MAX_NAME_LENGTH:
            raise SpeakerRejectedError(f"Nom trop long : {MAX_NAME_LENGTH} caractères au plus.")
        if self._name_exists(clean_name):
            raise SpeakerRejectedError(f"Un locuteur s'appelle déjà « {clean_name} ».")
        if not uploads:
            raise SpeakerRejectedError("Ajoutez au moins un extrait de voix.")
        for upload in uploads:
            self._check_extension(upload.filename or "")
        return clean_name

    def _name_exists(self, name: str) -> bool:
        # Comparaison sans tenir compte des majuscules : « Awa » et « awa » sont la même.
        query = select(SpeakerRecord.id).where(func.lower(SpeakerRecord.name) == name.lower())
        with self.session_factory() as session:
            return session.scalar(query) is not None

    def _check_extension(self, sent_name: str) -> None:
        extension = Path(sent_name).suffix.lower().removeprefix(".")
        if extension in self.settings.allowed_extensions:
            return
        allowed = ", ".join(self.settings.allowed_extensions)
        raise SpeakerRejectedError(
            f"Format non pris en charge : « {sent_name} ». Formats acceptés : {allowed}."
        )

    def _read_uploads(self, uploads: list[FileStorage], folder: Path) -> list[FloatArray]:
        # Chaque extrait est décodé en mono 16 kHz (D1, D2) et gardé en WAV ; l'original
        # n'est pas conservé.
        signals: list[FloatArray] = []
        for position, upload in enumerate(uploads, start=1):
            extension = Path(upload.filename or "").suffix.lower()
            original = folder / f"original_{position}{extension}"
            upload.save(original)
            signal = self._decode(original, upload.filename or "")
            original.unlink()
            clipped = np.clip(signal, -1.0, 1.0)
            converted = folder / f"enrollment_{position}.wav"
            sf.write(converted, clipped, TARGET_SAMPLE_RATE, subtype=ENROLLMENT_AUDIO_SUBTYPE)
            signals.append(signal)
        return signals

    def _decode(self, path: Path, sent_name: str) -> FloatArray:
        try:
            signal = load_audio(path, max_seconds=self.settings.max_audio_seconds)
        except AudioTooLongError as error:
            raise SpeakerRejectedError(str(error)) from error
        except AudioDecodeError as error:
            raise SpeakerRejectedError(
                f"Extrait illisible ou corrompu : « {sent_name} »."
            ) from error
        if is_silent(signal):
            raise SpeakerRejectedError(f"Extrait silencieux : « {sent_name} ».")
        return signal

    def _speech_pieces(self, signals: list[FloatArray]) -> list[FloatArray]:
        # Les mêmes morceaux qu'à l'analyse (VAD, 1 à 5 s) : la voix enregistrée et les voix
        # comparées ensuite sont calculées de la même façon.
        settings = self.context.inference_config.speaker
        pieces: list[FloatArray] = []
        for signal in signals:
            speech_segments = self.context.speech_detector.detect(signal)
            for window in speaker_windows(speech_segments, settings):
                pieces.append(segment_samples(signal, window))
        speech_s = sum(len(piece) for piece in pieces) / TARGET_SAMPLE_RATE
        if speech_s < settings.min_enrollment_speech_s:
            found = f"{speech_s:.1f}".replace(".", ",")
            needed = f"{settings.min_enrollment_speech_s:g}".replace(".", ",")
            raise SpeakerRejectedError(
                f"Pas assez de parole : {found} s gardées, il en faut au moins {needed} s. "
                "Parlez plus longtemps ou ajoutez un extrait."
            )
        return pieces
