"""Flux micro en direct (EF-14, D8) : du PCM reçu aux fenêtres à analyser, sans modèle.

Le navigateur envoie des morceaux de PCM Int16 mono à 16 kHz. Le tampon garde les W dernières
secondes du son. Toutes les H secondes de son reçu, il rend une fenêtre : les W dernières
secondes. Si le serveur a pris du retard (plusieurs H reçus depuis la dernière fenêtre), il ne
rend que la plus récente et compte les fenêtres sautées : on analyse toujours le son le plus
récent, et la latence reste bornée au lieu de grandir sans fin.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float32]
# Int16 couvre [-32 768, 32 767] : diviser par 32 768 ramène le signal dans [-1, 1).
PCM16_SCALE = 32768.0
BYTES_PER_SAMPLE = 2


def pcm16_to_float32(data: bytes) -> FloatArray:
    """Octets PCM Int16 petit-boutiste (format de D8) → signal float32 dans [-1, 1)."""
    if len(data) % BYTES_PER_SAMPLE != 0:
        raise ValueError("Message PCM tronqué : le nombre d'octets doit être pair (Int16).")
    samples = np.frombuffer(data, dtype="<i2")
    as_float = samples.astype(np.float32)
    scaled: FloatArray = as_float / np.float32(PCM16_SCALE)
    return scaled


@dataclass(frozen=True)
class StreamWindow:
    """Fenêtre prête à analyser : les W dernières secondes du son reçu."""

    signal: FloatArray
    # Fin de la fenêtre, en secondes depuis le début du flux.
    end_s: float
    # Fenêtres sautées juste avant celle-ci, parce que le calcul avait pris du retard.
    skipped: int


class StreamBuffer:
    """Tampon d'une session : garde les W dernières secondes et dit quand rendre une fenêtre."""

    def __init__(self, window_s: float, hop_s: float, sample_rate: int) -> None:
        self.window_samples = round(window_s * sample_rate)
        self.hop_samples = round(hop_s * sample_rate)
        self.sample_rate = sample_rate
        self.total_samples = 0
        self._recent: FloatArray = np.zeros(0, dtype=np.float32)
        # Échantillons reçus depuis la dernière fenêtre rendue.
        self._since_last_window = 0
        self._first_window_sent = False

    def append(self, samples: FloatArray) -> None:
        """Ajoute un morceau de signal et ne garde que les W dernières secondes."""
        joined = np.concatenate([self._recent, samples])
        self._recent = joined[-self.window_samples :]
        self.total_samples += len(samples)
        self._since_last_window += len(samples)

    def next_window(self) -> StreamWindow | None:
        """La fenêtre à analyser maintenant, ou None s'il n'est pas encore temps."""
        # Étape 1 : pas de résultat avant d'avoir une fenêtre pleine (W secondes).
        if self.total_samples < self.window_samples:
            return None
        # Étape 2 : la première fenêtre part dès que W est atteint.
        if not self._first_window_sent:
            self._first_window_sent = True
            self._since_last_window = 0
            return self._current_window(skipped=0)
        # Étape 3 : ensuite, une fenêtre toutes les H secondes. Si plusieurs H sont passés, on
        # ne rend que la plus récente : les autres sont sautées.
        hops_elapsed = self._since_last_window // self.hop_samples
        if hops_elapsed == 0:
            return None
        self._since_last_window -= hops_elapsed * self.hop_samples
        return self._current_window(skipped=hops_elapsed - 1)

    def _current_window(self, skipped: int) -> StreamWindow:
        end_s = self.total_samples / self.sample_rate
        signal = self._recent.copy()
        return StreamWindow(signal=signal, end_s=end_s, skipped=skipped)
