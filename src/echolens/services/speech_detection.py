"""Détection de parole de l'application (D5, C24) : Silero si l'extra [ml] est installé.

Silero (réseau appris sur de la parole) est la VAD de production. Sans torch (mode demo, CI),
webrtcvad sert de secours, avec sa limite connue : il prend des sons continus (pluie,
sinusoïde, bruit blanc) pour de la parole. Le choix est automatique, fait une seule fois au
démarrage et écrit dans les journaux. Toute partie de l'application qui a besoin de la VAD
(émotions, découpage de la transcription, flux micro) passe par le même détecteur.
"""

from __future__ import annotations

import importlib.util
import logging
from typing import Protocol

from echolens.core.audio.preprocess_config import VadConfig
from echolens.core.audio.segment import FloatArray, Segment, detect_speech

logger = logging.getLogger(__name__)
# Modules de l'extra [ml] sans lesquels Silero ne peut pas tourner.
SILERO_MODULES = ("torch", "silero_vad")


class SpeechDetector(Protocol):
    """Ce que doit savoir faire toute VAD de l'application."""

    # « silero » ou « webrtcvad », pour les journaux et les tests.
    name: str

    def detect(self, signal: FloatArray) -> list[Segment]:
        """Zones de parole d'un signal mono 16 kHz ; liste vide s'il n'y en a aucune."""
        ...


class WebrtcvadDetector:
    """VAD de secours sans torch : webrtcvad (D5), limite connue sur les sons continus."""

    name = "webrtcvad"

    def __init__(self, config: VadConfig) -> None:
        self.config = config

    def detect(self, signal: FloatArray) -> list[Segment]:
        """Zones de parole selon webrtcvad, nettoyées comme le prévoit D5."""
        return detect_speech(signal, self.config)


def make_speech_detector(config: VadConfig) -> SpeechDetector:
    """Crée la VAD de l'application : Silero si torch et silero-vad sont installés, sinon
    webrtcvad. Le choix est écrit dans les journaux.

    torch n'est importé que dans le cas Silero, si bien que le mode demo et la CI s'en passent.
    """
    if not silero_is_installed():
        logger.warning(
            "VAD : webrtcvad (secours) — torch ou silero-vad absent (extra [ml]). Limite "
            "connue : des sons continus peuvent être pris pour de la parole."
        )
        return WebrtcvadDetector(config)
    from echolens.services.silero_detector import SileroDetector

    detector = SileroDetector(config)
    logger.info(
        "VAD : Silero (seuil %.2f, fin %.2f), modèle du paquet silero-vad %s",
        config.silero_threshold,
        config.silero_end_threshold,
        detector.package_version,
    )
    return detector


def silero_is_installed() -> bool:
    """Vrai si les modules de l'extra [ml] dont Silero a besoin sont importables."""
    missing = [name for name in SILERO_MODULES if importlib.util.find_spec(name) is None]
    return not missing
