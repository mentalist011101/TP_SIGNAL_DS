"""Brique 2 : représentations temps-fréquence (STFT, log-Mel, MFCC).

Module unique (décision R5) : le même code calcule les features à l'entraînement sur Kaggle
et à l'inférence dans Flask. Les paramètres viennent de configs/features.yaml.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from echolens.config import load_yaml


class FeatureConfig(BaseModel):
    """Paramètres des représentations (décisions R1 à R3)."""

    sample_rate: int = Field(default=16_000, gt=0)
    n_fft: int = Field(default=400, gt=0)
    hop_length: int = Field(default=160, gt=0)
    window: str = "hann"
    n_mels: int = Field(default=64, gt=0)
    f_min: float = Field(default=0.0, ge=0)
    f_max: float = Field(default=8_000.0, gt=0)
    n_mfcc: int = Field(default=40, gt=0)
    top_db: float = Field(default=80.0, gt=0)

    @property
    def frequency_resolution_hz(self) -> float:
        """Résolution fréquentielle Δf = fs / n_fft (40 Hz avec les valeurs par défaut)."""
        return self.sample_rate / self.n_fft

    @classmethod
    def from_yaml(cls, path: Path) -> FeatureConfig:
        """Charge la configuration depuis un fichier YAML."""
        return cls(**load_yaml(path))


def log_mel_spectrogram() -> None:
    """Spectrogramme log-Mel (R1, R2). À implémenter en S1 avec torchaudio."""
    raise NotImplementedError("Brique 2 — log-Mel à implémenter (sprint S1)")


def mfcc() -> None:
    """MFCC avec deltas (R3). À implémenter en S1 avec torchaudio."""
    raise NotImplementedError("Brique 2 — MFCC à implémenter (sprint S1)")
