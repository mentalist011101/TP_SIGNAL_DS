"""Prétraitement du signal : niveau (D3), silence (D6), débruitage (D4), segmentation (D5)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float32]
# Un segment est un couple (début, fin) exprimé en secondes.
Segment = tuple[float, float]

# Plancher numérique pour éviter log(0) et les divisions par zéro.
_EPS = 1e-10


def rms_dbfs(signal: FloatArray) -> float:
    """Niveau RMS du signal en dBFS (0 dBFS = sinusoïde pleine échelle ≈ -3 dB RMS)."""
    rms = float(np.sqrt(np.mean(np.square(signal, dtype=np.float64))))
    return 20.0 * float(np.log10(max(rms, _EPS)))


def rms_normalize(signal: FloatArray, target_dbfs: float = -20.0) -> FloatArray:
    """Applique un gain pour amener le niveau RMS à ``target_dbfs``.

    Gain linéaire : g = 10^((cible - niveau actuel) / 20). Un signal nul est renvoyé tel quel.
    """
    current = rms_dbfs(signal)
    if current <= 20.0 * np.log10(_EPS) + 1.0:
        return np.asarray(signal.copy(), dtype=np.float32)
    gain = np.float32(10.0 ** ((target_dbfs - current) / 20.0))
    normalized: FloatArray = (signal * gain).astype(np.float32)
    return normalized


def peak_limit(signal: FloatArray, ceiling: float = 0.99) -> FloatArray:
    """Écrête le signal à ±``ceiling`` pour éviter toute saturation après le gain."""
    return np.clip(signal, -ceiling, ceiling).astype(np.float32)


def is_silent(signal: FloatArray, threshold_dbfs: float = -60.0) -> bool:
    """Vrai si le niveau RMS global est sous ``threshold_dbfs`` (fichier rejeté)."""
    return rms_dbfs(signal) < threshold_dbfs


def preprocess(signal: FloatArray, target_dbfs: float = -20.0) -> FloatArray:
    """Chaîne de prétraitement commune : normalisation RMS puis écrêtage de sécurité."""
    return peak_limit(rms_normalize(signal, target_dbfs))


def denoise(
    signal: FloatArray,
    sample_rate: int = 16_000,
    stationary: bool = True,
    strength: float = 1.0,
) -> FloatArray:
    """Réduit le bruit de fond par « spectral gating » (décision D4).

    Le bruit est estimé dans chaque case temps-fréquence : ce qui reste sous le seuil est
    atténué, ce qui le dépasse (la parole) est conservé. À réserver à la parole : pour les
    événements sonores le bruit est le signal, et pour les émotions il peut effacer des
    indices prosodiques. ``strength`` (de 0 à 1) règle la part de bruit retirée.
    """
    # Import local : noisereduce fait partie de l'extra [ml], absent de la CI.
    import noisereduce

    cleaned = noisereduce.reduce_noise(
        y=signal, sr=sample_rate, stationary=stationary, prop_decrease=strength
    )
    return np.asarray(cleaned, dtype=np.float32)


@lru_cache(maxsize=1)
def _vad_model() -> Any:
    """Charge Silero VAD une seule fois (le chargement est lent)."""
    from silero_vad import load_silero_vad

    return load_silero_vad()


def detect_speech(signal: FloatArray, sample_rate: int = 16_000) -> list[Segment]:
    """Repère les zones de parole avec Silero VAD (décision D5).

    Renvoie une liste de segments (début, fin) en secondes, vide si aucune parole.
    """
    import torch
    from silero_vad import get_speech_timestamps

    with torch.no_grad():
        timestamps = get_speech_timestamps(
            torch.from_numpy(signal),
            _vad_model(),
            sampling_rate=sample_rate,
            return_seconds=True,
        )
    return [(float(item["start"]), float(item["end"])) for item in timestamps]


def sliding_windows(duration_s: float, window_s: float, hop_s: float) -> list[Segment]:
    """Découpe une durée en fenêtres de ``window_s`` décalées de ``hop_s`` (décisions D5, D8).

    Profil flux micro : fenêtre de 2 s, décalage de 0,5 s. Si la dernière fenêtre ne tombe
    pas pile sur la fin, une fenêtre supplémentaire est alignée sur la fin pour ne rien perdre.
    Un audio plus court qu'une fenêtre donne une seule fenêtre.
    """
    if duration_s <= window_s:
        return [(0.0, duration_s)]
    count = int(np.floor((duration_s - window_s) / hop_s + 1e-9)) + 1
    windows = [(float(i * hop_s), float(i * hop_s + window_s)) for i in range(count)]
    if windows[-1][1] < duration_s - 1e-9:
        windows.append((duration_s - window_s, duration_s))
    return windows
