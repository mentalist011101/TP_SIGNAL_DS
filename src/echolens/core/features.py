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
from pydantic import BaseModel, Field, model_validator

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
    db_reference: float = Field(default=1.0, gt=0)
    db_amin: float = Field(default=1e-10, gt=0)
    delta_width: int = Field(default=9, ge=3)
    # U6 : échelle de couleurs fixe de l'image du spectrogramme (présentation seulement).
    display_db_min: float = -80.0
    display_db_max: float = 40.0
    display_colormap: str = "magma"

    @model_validator(mode="after")
    def check_display_range(self) -> FeatureConfig:
        """Refuse une échelle d'affichage vide ou inversée (display_db_min >= display_db_max)."""
        if self.display_db_min >= self.display_db_max:
            raise ValueError(
                f"display_db_min ({self.display_db_min}) doit être inférieur à "
                f"display_db_max ({self.display_db_max})"
            )
        return self

    @property
    def frequency_resolution_hz(self) -> float:
        """Résolution fréquentielle Δf = fs / n_fft (40 Hz avec les valeurs par défaut)."""
        return self.sample_rate / self.n_fft

    @property
    def db_floor(self) -> float:
        """Plancher du log-Mel en dB : 10·log10(amin / ref), soit −100 dB par défaut (R2)."""
        ratio = self.db_amin / self.db_reference
        return float(10.0 * np.log10(ratio))

    @classmethod
    def from_yaml(cls, path: Path) -> FeatureConfig:
        """Charge la configuration depuis un fichier YAML."""
        return cls(**load_yaml(path))


def log_mel_spectrogram(signal: FloatArray, config: FeatureConfig) -> FloatArray:
    """Spectrogramme log-Mel en dB absolus, de forme (n_mels, n_frames) (décisions R1, R2).

    R1 : STFT à fenêtre de Hann de 25 ms (n_fft) et pas de 10 ms (hop_length), spectre de
    puissance |X|^power. R2 : banc de n_mels filtres triangulaires sur l'échelle Mel HTK entre
    f_min et f_max, puis passage en dB absolus avec un plancher fixe (−100 dB).

    Lève ValueError si le signal n'est pas mono, est vide ou dure moins d'une trame.
    """
    _check_signal(signal, config)

    # Étape 1 : STFT puis banc de filtres Mel (R1, R2).
    # htk=True et norm=None : la spécification définit l'échelle Mel par la formule HTK
    # m = 2595·log10(1 + f/700) et des filtres triangulaires de hauteur 1. Les valeurs par
    # défaut de librosa (htk=False, norm="slaney") suivent une autre convention.
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

    # Étape 2 : passage en dB absolus (R2). ref fixe et top_db=None : un silence vaut −100 dB
    # et un même son garde les mêmes valeurs quel que soit ce qui l'entoure dans l'extrait.
    log_mel = librosa.power_to_db(
        mel_power,
        ref=config.db_reference,
        amin=config.db_amin,
        top_db=None,
    )
    return np.asarray(log_mel, dtype=np.float32)


def mfcc(signal: FloatArray, config: FeatureConfig, with_deltas: bool = True) -> FloatArray:
    """MFCC (décision R3), avec leurs dérivées Δ et ΔΔ par défaut.

    R3 : DCT-II orthonormée du log-Mel en dB (R1, R2), dont on garde les n_mfcc premiers
    coefficients. Les deltas sont des régressions locales sur delta_width trames.
    Forme : (n_mfcc, n_frames), ou (3·n_mfcc, n_frames) avec les deltas, empilés c, Δ, ΔΔ.

    Lève ValueError si le signal n'est pas mono, est vide, ou est trop court pour les deltas.
    """
    # Étape 1 : log-Mel, puis DCT-II orthonormée pour décorréler les bandes (R3).
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

    # Étape 2 : deltas sur delta_width trames ; il faut au moins autant de trames que la fenêtre.
    _check_enough_frames_for_deltas(coefficients.shape[1], config)
    delta = librosa.feature.delta(
        coefficients, width=config.delta_width, order=1, axis=-1, mode="interp"
    )
    delta2 = librosa.feature.delta(
        coefficients, width=config.delta_width, order=2, axis=-1, mode="interp"
    )

    # Étape 3 : empilement c, Δ, ΔΔ, soit 3 × n_mfcc valeurs par trame.
    stacked = np.concatenate([coefficients, delta, delta2], axis=0)
    return np.asarray(stacked, dtype=np.float32)


def _check_signal(signal: FloatArray, config: FeatureConfig) -> None:
    """Vérifie que le signal est mono et dure au moins une trame (n_fft échantillons)."""
    if signal.ndim != 1:
        raise ValueError(f"Le signal doit être mono (1 dimension), reçu {signal.ndim} dimensions")
    if signal.size == 0:
        raise ValueError("Le signal est vide")
    if signal.size < config.n_fft:
        minimum_ms = 1000 * config.n_fft / config.sample_rate
        raise ValueError(f"Le signal est trop court : il faut au moins {minimum_ms:.0f} ms")


def _check_enough_frames_for_deltas(n_frames: int, config: FeatureConfig) -> None:
    """Vérifie qu'il y a au moins delta_width trames, sinon les deltas sont incalculables."""
    if n_frames >= config.delta_width:
        return
    minimum_samples = (config.delta_width - 1) * config.hop_length
    minimum_ms = 1000 * minimum_samples / config.sample_rate
    raise ValueError(
        f"Le signal est trop court pour les deltas : il faut au moins {minimum_ms:.0f} ms"
    )
