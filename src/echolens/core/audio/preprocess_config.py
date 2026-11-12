"""Paramètres du débruitage (D4), de la détection de parole (D5) et des fenêtres (D8).

Les valeurs sont dans configs/preprocess.yaml ; ce module ne fait que les lire et vérifier
leurs bornes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from echolens.config import CONFIG_DIR, load_yaml

PREPROCESS_CONFIG_PATH = CONFIG_DIR / "preprocess.yaml"


class DenoiseConfig(BaseModel):
    """Spectral gating de noisereduce (D4)."""

    enabled: bool
    stationary: bool
    # Force : part du bruit retirée (0 = rien, 1 = tout).
    prop_decrease: float = Field(ge=0, le=1)
    # Seuil : nombre d'écarts-types au-dessus de la moyenne du bruit.
    n_std_thresh_stationary: float = Field(gt=0)
    n_fft: int = Field(gt=0)
    freq_mask_smooth_hz: int = Field(gt=0)
    time_mask_smooth_ms: int = Field(gt=0)


class VadConfig(BaseModel):
    """Détection de parole avec webrtcvad et nettoyage des segments (D5)."""

    aggressiveness: int = Field(ge=0, le=3)
    # webrtcvad n'accepte que des trames de 10, 20 ou 30 ms.
    frame_ms: Literal[10, 20, 30]
    merge_gap_ms: int = Field(ge=0)
    min_segment_ms: int = Field(ge=0)
    padding_ms: int = Field(ge=0)


class WindowConfig(BaseModel):
    """Fenêtres glissantes : durée et décalage, en secondes."""

    window_s: float = Field(gt=0)
    hop_s: float = Field(gt=0)


class WindowProfiles(BaseModel):
    """Fenêtres des événements sonores et du flux micro (D5, D8)."""

    events: WindowConfig
    stream: WindowConfig


class PreprocessConfig(BaseModel):
    """Contenu de configs/preprocess.yaml."""

    denoise: DenoiseConfig
    vad: VadConfig
    windows: WindowProfiles


def load_preprocess_config(path: Path = PREPROCESS_CONFIG_PATH) -> PreprocessConfig:
    """Lit configs/preprocess.yaml."""
    content = load_yaml(path)
    return PreprocessConfig(**content)
