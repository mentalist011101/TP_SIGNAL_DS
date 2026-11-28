"""Transcription réelle : modèles Whisper du registre, avec faster-whisper (EF-10, C17b).

faster-whisper fait tourner Whisper avec CTranslate2, en int8 sur CPU. Ce module n'est importé
que par le prédicteur réel, à la première transcription ou au préchargement : le mode demo et
la CI se passent de faster-whisper (extra [ml]).

Réglages du décodage (configs/inference.yaml, repris de l'évaluation C17a) : français imposé,
faisceau de 5, pas de VAD interne (la VAD de l'application a déjà découpé la parole), chaque
segment transcrit seul. Les seuils anti-hallucination de faster-whisper (no_speech_threshold,
log_prob_threshold) gardent leurs valeurs par défaut.
"""

from __future__ import annotations

import threading
from pathlib import Path

from faster_whisper import WhisperModel

from echolens.core.inference import FloatArray, TranscriptionSettings
from echolens.core.models.registry import ModelEntry

HF_PREFIX = "hf://"
# Les modèles tournent sur CPU : c'est la machine de référence de l'application (ENF-01).
DEVICE = "cpu"


class TranscriberLoadError(RuntimeError):
    """Un modèle de transcription ne peut pas être chargé ; le message dit pourquoi."""


class WhisperTranscriber:
    """Transcrit des morceaux de parole avec les modèles Whisper du registre."""

    def __init__(self, settings: TranscriptionSettings, models_dir: Path | None) -> None:
        self.settings = settings
        # Dossier local de modèles (<dossier>/<id>/, format CTranslate2) ; None : dépôt
        # Hugging Face du registre, à sa révision figée (cache local).
        self.models_dir = models_dir
        self._models: dict[str, WhisperModel] = {}
        # Deux analyses en parallèle (S2) ne doivent pas charger le même modèle deux fois.
        self._lock = threading.Lock()

    def transcribe(self, entry: ModelEntry, windows: list[FloatArray]) -> list[str]:
        """Un texte par morceau de parole mono 16 kHz, dans le même ordre."""
        model = self.load(entry)
        texts: list[str] = []
        for window in windows:
            text = self._transcribe_window(model, window)
            texts.append(text)
        return texts

    def load(self, entry: ModelEntry) -> WhisperModel:
        """Le modèle prêt à transcrire, chargé une seule fois puis gardé en mémoire (S1)."""
        with self._lock:
            if entry.id not in self._models:
                self._models[entry.id] = self._load_model(entry)
            return self._models[entry.id]

    def _transcribe_window(self, model: WhisperModel, window: FloatArray) -> str:
        settings = self.settings
        # Étape 1 : décodage avec les réglages de C17a ; faster-whisper rend un générateur de
        # phrases, calculées au fur et à mesure qu'on les lit.
        phrases, _ = model.transcribe(
            window,
            language=settings.language,
            beam_size=settings.beam_size,
            vad_filter=settings.vad_filter,
            condition_on_previous_text=settings.condition_on_previous_text,
            temperature=settings.temperature,
        )
        # Étape 2 : le texte du morceau, phrases mises bout à bout.
        parts: list[str] = []
        for phrase in phrases:
            parts.append(phrase.text.strip())
        return " ".join(parts).strip()

    def _load_model(self, entry: ModelEntry) -> WhisperModel:
        if entry.compute_type == "" or entry.cpu_threads is None:
            raise TranscriberLoadError(
                f"{entry.id} : compute_type et cpu_threads manquent dans configs/registry.yaml"
            )
        # Dossier local : les fichiers CTranslate2 du modèle, sans téléchargement.
        if self.models_dir is not None:
            folder = self.models_dir / entry.id
            return WhisperModel(
                str(folder),
                device=DEVICE,
                compute_type=entry.compute_type,
                cpu_threads=entry.cpu_threads,
            )
        if not entry.weights.startswith(HF_PREFIX) or not entry.revision:
            raise TranscriberLoadError(
                f"{entry.id} : ni dossier local de modèles, ni dépôt Hugging Face avec sa "
                "révision dans configs/registry.yaml"
            )
        repo_id = entry.weights.removeprefix(HF_PREFIX)
        return WhisperModel(
            repo_id,
            device=DEVICE,
            compute_type=entry.compute_type,
            cpu_threads=entry.cpu_threads,
            revision=entry.revision,
        )
