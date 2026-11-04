"""Brique 2 : représentations temps-fréquence (STFT, log-Mel, MFCC) calculées avec librosa.

Module unique (décision R5) : le même code calcule les features à l'entraînement sur Kaggle
et à l'inférence dans Flask. Les paramètres viennent de configs/features.yaml et sont tous
passés explicitement à librosa, pour qu'aucune valeur par défaut de la bibliothèque ne change
silencieusement les features d'une version à l'autre.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import librosa
import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field

from echolens.config import load_yaml

FloatArray = npt.NDArray[np.float32]
PadMode = Literal["constant", "edge", "linear_ramp", "reflect", "symmetric", "empty"]


class FeatureConfig(BaseModel):
    """Paramètres des représentations (décisions R1 à R3)."""

    sample_rate: int = Field(default=16_000, gt=0)
    n_fft: int = Field(default=400, gt=0)
    hop_length: int = Field(default=160, gt=0)
    window: str = "hann"
    center: bool = True
    pad_mode: PadMode = "reflect"
    power: float = Field(default=2.0, gt=0)
    n_mels: int = Field(default=64, gt=0)
    f_min: float = Field(default=0.0, ge=0)
    f_max: float = Field(default=8_000.0, gt=0)
    n_mfcc: int = Field(default=40, gt=0)
    top_db: float = Field(default=80.0, gt=0)
    delta_width: int = Field(default=9, ge=3)

    @property
    def frequency_resolution_hz(self) -> float:
        """Résolution fréquentielle Δf = fs / n_fft (40 Hz avec les valeurs par défaut)."""
        return self.sample_rate / self.n_fft

    @classmethod
    def from_yaml(cls, path: Path) -> FeatureConfig:
        """Charge la configuration depuis un fichier YAML."""
        return cls(**load_yaml(path))


def log_mel_spectrogram(signal: FloatArray, config: FeatureConfig) -> FloatArray:
    """Spectrogramme log-Mel en dB, de forme (n_mels, n_frames) (décisions R1, R2).

    R1 : STFT à fenêtre de Hann de 25 ms (n_fft) et pas de 10 ms (hop_length), spectre de
    puissance |X|^power. R2 : banc de n_mels filtres triangulaires sur l'échelle Mel entre
    f_min et f_max, puis passage en dB relatif au maximum du signal, plancher à -top_db.

    Lève ValueError si le signal n'est pas un vecteur mono non vide.
    """
    _check_signal(signal)
    # htk=True et norm=None : la spécification définit l'échelle Mel par la formule HTK
    # m = 2595·log10(1 + f/700) et des filtres triangulaires de hauteur 1. Les valeurs par
    # défaut de librosa (htk=False, norm="slaney") suivent la convention Slaney : échelle
    # linéaire sous 1 kHz et filtres normalisés en aire.
    mel_power = librosa.feature.melspectrogram(
        y=signal,
        sr=config.sample_rate,
        n_fft=config.n_fft,
        hop_length=config.hop_length,
        win_length=config.n_fft,
        window=config.window,
        center=config.center,
        pad_mode=config.pad_mode,
        power=config.power,
        n_mels=config.n_mels,
        fmin=config.f_min,
        fmax=config.f_max,
        htk=True,
        norm=None,
    )
    log_mel = librosa.power_to_db(mel_power, ref=np.max, amin=1e-10, top_db=config.top_db)
    return np.asarray(log_mel, dtype=np.float32)


def mfcc(signal: FloatArray, config: FeatureConfig, with_deltas: bool = True) -> FloatArray:
    """MFCC (décision R3), avec leurs dérivées Δ et ΔΔ par défaut.

    R3 : DCT-II orthonormée du log-Mel en dB (R1, R2), dont on garde les n_mfcc premiers
    coefficients. Les deltas sont des régressions locales sur delta_width trames.
    Forme : (n_mfcc, n_frames), ou (3·n_mfcc, n_frames) avec les deltas, empilés c, Δ, ΔΔ.

    Lève ValueError si le signal n'est pas un vecteur mono non vide.
    """
    log_mel = log_mel_spectrogram(signal, config)
    coefficients = librosa.feature.mfcc(
        S=log_mel,
        n_mfcc=config.n_mfcc,
        dct_type=2,
        norm="ortho",
        lifter=0,
    )
    if not with_deltas:
        return np.asarray(coefficients, dtype=np.float32)
    delta = librosa.feature.delta(
        coefficients, width=config.delta_width, order=1, axis=-1, mode="interp"
    )
    delta2 = librosa.feature.delta(
        coefficients, width=config.delta_width, order=2, axis=-1, mode="interp"
    )
    return np.concatenate([coefficients, delta, delta2], axis=0).astype(np.float32)


def _check_signal(signal: FloatArray) -> None:
    if signal.ndim != 1:
        raise ValueError(f"Le signal doit être mono (1 dimension), reçu {signal.ndim} dimensions")
    if signal.size == 0:
        raise ValueError("Le signal est vide")
