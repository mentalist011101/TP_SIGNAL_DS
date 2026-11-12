"""Normalisation du niveau (décision D3) et détection de silence (garde-fou D6).

Le débruitage (D4) et la segmentation (D5) seront ajoutés dans ce module en semaine 1.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float32]

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
