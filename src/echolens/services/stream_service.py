"""Flux micro en direct (EF-14, C23, D8) : une session par connexion WebSocket.

La route /ws/stream ne fait que lire et écrire les messages. Ici, la session garde le tampon,
analyse chaque fenêtre en profil temps réel et mesure le temps de calcul (ENF-01, ENF-02).

Si l'utilisateur a choisi d'enregistrer la session et a accepté le consentement (ENF-10), tout
le son reçu est aussi gardé, au plus max_audio_seconds. À l'arrêt, il devient une analyse
ordinaire de l'historique, avec les mêmes contrôles qu'un fichier importé. Sans consentement,
rien n'est gardé : le tampon ne contient que les W dernières secondes, libérées à la fermeture.
"""

from __future__ import annotations

import io
import time
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np
import soundfile as sf
from werkzeug.datastructures import FileStorage

from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.core.inference import FloatArray, StreamSettings
from echolens.core.models.registry import Profile
from echolens.core.stream import StreamBuffer, StreamWindow, level_dbfs, pcm16_to_float32
from echolens.services.analysis_service import AnalysisRejectedError, AnalysisService
from echolens.services.results import build_results, summarize_results

SECONDS_TO_MS = 1000.0
MEDIAN_PERCENT = 50
TAIL_PERCENT = 95
RECORDING_SUBTYPE = "PCM_16"


class StreamError(ValueError):
    """Le flux ne peut pas continuer ; le message, en français, s'affiche tel quel."""


@dataclass(frozen=True)
class StreamOptions:
    """Choix faits avant de démarrer : enregistrer la session, et avec quel consentement."""

    record: bool
    consent_version: str | None


def parse_start(message: dict[str, Any], settings: StreamSettings) -> StreamOptions:
    """Lit le message « start » ; refuse l'enregistrement sans consentement valide (ENF-10).

    Forme attendue : {"type": "start", "record": false}, ou, pour enregistrer,
    {"type": "start", "record": true, "consent": {"accepted": true, "version": "direct-v1"}}.
    """
    if message.get("record") is not True:
        return StreamOptions(record=False, consent_version=None)
    consent = message.get("consent")
    if not isinstance(consent, dict) or consent.get("accepted") is not True:
        raise StreamError(
            "Enregistrement refusé : cochez la case qui dit que vous avez lu et accepté "
            "l'enregistrement de votre voix."
        )
    version = consent.get("version")
    if version != settings.consent_version:
        raise StreamError("Texte de consentement inconnu : rechargez la page, puis réessayez.")
    return StreamOptions(record=True, consent_version=settings.consent_version)


class StreamSession:
    """Une connexion du flux micro : tampon, analyses, mesures et enregistrement éventuel."""

    def __init__(self, service: AnalysisService, options: StreamOptions) -> None:
        self.service = service
        self.options = options
        self.settings = service.result_context.inference_config.stream
        self.buffer = StreamBuffer(self.settings.window_s, self.settings.hop_s, TARGET_SAMPLE_RATE)
        self.max_message_samples = round(self.settings.max_message_s * TARGET_SAMPLE_RATE)
        # Temps de calcul des dernières fenêtres, pour la médiane et le p95 (ENF-01, ENF-02).
        self.compute_times_s: deque[float] = deque(maxlen=self.settings.latency_history)
        self.window_count = 0
        self.skipped_count = 0
        # Son complet de la session, seulement si l'enregistrement est consenti.
        self.max_recording_samples = round(service.settings.max_audio_seconds * TARGET_SAMPLE_RATE)
        self.recorded_pieces: list[FloatArray] = []
        self.recorded_samples = 0
        self.recording_truncated = False

    def ready_message(self) -> dict[str, Any]:
        """Premier message du serveur : les réglages du flux, pour l'affichage."""
        return {
            "type": "ready",
            "window_s": self.settings.window_s,
            "hop_s": self.settings.hop_s,
            "sample_rate": TARGET_SAMPLE_RATE,
            "tasks": self.settings.tasks,
            "record": self.options.record,
        }

    def receive(self, data: bytes) -> None:
        """Ajoute un morceau de PCM Int16 reçu du navigateur."""
        samples = pcm16_to_float32(data)
        if len(samples) > self.max_message_samples:
            raise StreamError(
                "Morceau de son trop long : le navigateur doit envoyer des morceaux courts."
            )
        self.buffer.append(samples)
        if self.options.record:
            self._keep_for_recording(samples)

    def analyze_ready_window(self) -> dict[str, Any] | None:
        """Analyse la fenêtre la plus récente s'il est temps ; None sinon."""
        window = self.buffer.next_window()
        if window is None:
            return None
        # Étape 1 : la fenêtre passe dans la même chaîne qu'un fichier, en profil temps réel
        # (VAD une fois, CRNN des émotions sur la parole, CRNN des événements).
        start = time.perf_counter()
        results = build_results(
            window.signal, self.settings.tasks, Profile.REALTIME, self.service.result_context
        )
        compute_s = time.perf_counter() - start
        # Étape 2 : mesures de la session, puis le message pour le navigateur.
        self.compute_times_s.append(compute_s)
        self.window_count += 1
        self.skipped_count += window.skipped
        return self._window_message(window, results, compute_s)

    def finish(self) -> dict[str, Any] | None:
        """À l'arrêt : enregistre la session dans l'historique si c'était demandé et consenti.

        Renvoie le message « saved » avec l'identifiant de l'analyse, ou None sans
        enregistrement. Lève StreamError si l'audio est refusé (silence, trop court…).
        """
        if not self.options.record or self.recorded_samples == 0:
            return None
        upload = self._recording_upload()
        try:
            record = self.service.create_analysis(
                upload,
                self.settings.recording_tasks,
                self.settings.recording_profile,
                consent_version=self.options.consent_version,
            )
        except AnalysisRejectedError as error:
            raise StreamError(f"Session non enregistrée : {error}") from error
        return {
            "type": "saved",
            "analysis_id": record.id,
            "truncated": self.recording_truncated,
        }

    def _window_message(
        self, window: StreamWindow, results: dict[str, Any], compute_s: float
    ) -> dict[str, Any]:
        # RTF = temps de calcul / durée du son analysé (ENF-01) : il doit rester sous H / W.
        rtf = compute_s / self.settings.window_s
        compute_times = np.array(self.compute_times_s)
        median_s = float(np.percentile(compute_times, MEDIAN_PERCENT))
        tail_s = float(np.percentile(compute_times, TAIL_PERCENT))
        summary = summarize_results(results)
        # Niveau du son reçu : il montre tout de suite si le micro du navigateur est muet.
        level = level_dbfs(window.signal)
        silent = level < self.settings.silent_level_dbfs
        return {
            "type": "window",
            "end_s": round(window.end_s, 3),
            "skipped": window.skipped,
            "results": summary,
            "speech": _has_speech(summary),
            "level_dbfs": round(level, 1),
            "silent": silent,
            "compute_ms": round(compute_s * SECONDS_TO_MS, 1),
            "rtf": round(rtf, 3),
            "compute_p50_ms": round(median_s * SECONDS_TO_MS, 1),
            "compute_p95_ms": round(tail_s * SECONDS_TO_MS, 1),
            "window_count": self.window_count,
            "skipped_count": self.skipped_count,
        }

    def _keep_for_recording(self, samples: FloatArray) -> None:
        # Au-delà de max_audio_seconds (la limite d'un fichier importé, EF-01), on s'arrête.
        room = self.max_recording_samples - self.recorded_samples
        if room <= 0:
            self.recording_truncated = True
            return
        kept = samples[:room]
        if len(kept) < len(samples):
            self.recording_truncated = True
        self.recorded_pieces.append(kept)
        self.recorded_samples += len(kept)

    def _recording_upload(self) -> FileStorage:
        # Le son gardé, en WAV PCM 16 bits mono 16 kHz, présenté comme un fichier importé : il
        # passe par les mêmes contrôles et le même traitement que tout autre fichier.
        signal = np.concatenate(self.recorded_pieces)
        buffer = io.BytesIO()
        sf.write(buffer, signal, TARGET_SAMPLE_RATE, subtype=RECORDING_SUBTYPE, format="WAV")
        buffer.seek(0)
        stamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"direct_{stamp}.wav"
        return FileStorage(stream=buffer, filename=filename, content_type="audio/wav")


def _has_speech(summary: dict[str, Any]) -> bool | None:
    # La VAD a-t-elle trouvé de la parole dans la fenêtre ? On le lit dans le statut de
    # l'émotion ; None si l'émotion n'est pas demandée.
    emotion = summary.get("emotion")
    if emotion is None:
        return None
    return bool(emotion["status"] != "no_speech")
