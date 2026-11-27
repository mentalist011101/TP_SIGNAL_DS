"""Cloneurs de voix (EF-18, C35) : ce qui fait dire un texte avec la voix d'un locuteur.

Le reste de l'application ne connaît que l'interface VoiceCloner. Le cloneur est choisi comme
le prédicteur (configs/app.yaml, inference_backend) :
- « demo » : faux cloneur, sans torch ni XTTS : des voyelles de synthèse, pour développer la
  page Cloner et la tester en CI ;
- « models » : XTTS-v2 du registre (echolens.services.xtts_cloner), chargé au premier clonage.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from echolens.config import AppSettings
from echolens.core.inference import FloatArray, VoiceCloningSettings
from echolens.core.models.registry import ModelRegistry, Task

DEMO_MODEL_ID = "demo"
DEMO_MODEL_VERSION = "0"
# Faux cloneur : même fréquence d'échantillonnage que XTTS-v2, environ 15 caractères lus par
# seconde, voyelles à 140 Hz et 4 syllabes par seconde.
DEMO_SAMPLE_RATE = 24_000
DEMO_CHARACTERS_PER_SECOND = 15.0
DEMO_FUNDAMENTAL_HZ = 140.0
DEMO_SYLLABLES_PER_SECOND = 4.0
DEMO_AMPLITUDE = 0.1


class CloningUnavailableError(RuntimeError):
    """Le clonage ne peut pas tourner (licence non acceptée, mémoire, modèle absent) ; le
    message, en français, s'affiche tel quel."""


@dataclass(frozen=True)
class SpeechAudio:
    """Voix produite par un cloneur : échantillons mono et leur fréquence."""

    samples: FloatArray
    sample_rate: int


class VoiceCloner(Protocol):
    """Ce que doit savoir faire tout cloneur, faux ou vrai."""

    model_id: str
    model_version: str

    def check_available(self) -> None:
        """Lève CloningUnavailableError si le clonage ne peut pas tourner (licence)."""
        ...

    def synthesize(self, text: str, references: list[Path]) -> SpeechAudio:
        """Le texte dit avec la voix des extraits de référence (WAV mono 16 kHz)."""
        ...


class DemoVoiceCloner:
    """Faux cloneur : des voyelles de synthèse dont la durée suit la longueur du texte.

    Aucune voix n'est clonée ; model_id « demo » le dit, et la sortie est marquée comme toute
    voix synthétique.
    """

    model_id = DEMO_MODEL_ID
    model_version = DEMO_MODEL_VERSION

    def check_available(self) -> None:
        """Toujours disponible : aucun modèle, aucune licence."""

    def synthesize(self, text: str, references: list[Path]) -> SpeechAudio:
        """Voyelles de synthèse, une seconde pour 15 caractères."""
        # Étape 1 : instants du faux enregistrement.
        duration_s = len(text) / DEMO_CHARACTERS_PER_SECOND
        sample_count = round(duration_s * DEMO_SAMPLE_RATE)
        times = np.arange(sample_count) / DEMO_SAMPLE_RATE
        # Étape 2 : fondamentale et harmoniques, découpées en syllabes.
        voiced = np.zeros_like(times)
        for harmonic in range(1, 15):
            voiced += np.sin(2 * np.pi * DEMO_FUNDAMENTAL_HZ * harmonic * times) / harmonic
        syllables = np.clip(np.sin(2 * np.pi * DEMO_SYLLABLES_PER_SECOND * times), 0, None)
        samples = DEMO_AMPLITUDE * voiced * syllables
        return SpeechAudio(samples=samples.astype(np.float32), sample_rate=DEMO_SAMPLE_RATE)


def make_voice_cloner(
    settings: AppSettings, cloning_settings: VoiceCloningSettings
) -> VoiceCloner | None:
    """Cloneur choisi par inference_backend ; None si le registre n'a pas de modèle de clonage.

    XTTS n'est importé qu'au premier clonage : le serveur démarre sans l'extra [tts].
    """
    if settings.inference_backend == DEMO_MODEL_ID:
        return DemoVoiceCloner()
    from echolens.services.xtts_cloner import XttsCloner

    registry = ModelRegistry.from_yaml(settings.registry_path)
    entries = registry.for_task(Task.VOICE_CLONING)
    if not entries:
        return None
    return XttsCloner(entries[0], cloning_settings, settings.voice_cloning_license_accepted)
