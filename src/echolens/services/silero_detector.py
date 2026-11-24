"""VAD de production : Silero, chargé une seule fois au démarrage (D5, C24).

Seul module des services qui importe torch pour la VAD : il n'est importé que si l'extra [ml]
est installé (echolens.services.speech_detection). Le modèle vient du paquet silero-vad, à la
version figée de l'extra [ml] : aucun téléchargement, l'application tourne hors ligne.
"""

from __future__ import annotations

import threading
from importlib.metadata import version

from echolens.core.audio.preprocess_config import VadConfig
from echolens.core.audio.segment import FloatArray, Segment
from echolens.core.models.silero_vad import load_silero_model, silero_speech_segments


class SileroDetector:
    """Silero VAD avec hystérésis, puis le nettoyage des segments de D5."""

    name = "silero"

    def __init__(self, config: VadConfig) -> None:
        self.config = config
        self.model = load_silero_model()
        self.package_version = version("silero-vad")
        # Silero garde une mémoire d'une tranche à l'autre : deux analyses en parallèle (S2)
        # ne doivent pas mélanger leurs tranches dans le même modèle.
        self._lock = threading.Lock()

    def detect(self, signal: FloatArray) -> list[Segment]:
        """Zones de parole selon Silero ; liste vide s'il n'y en a aucune."""
        with self._lock:
            return silero_speech_segments(self.model, signal, self.config)
