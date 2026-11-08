"""Brique 2 : représentations temps-fréquence (STFT, log-Mel, MFCC).

Module unique (décision R5) : le même code calcule les features à l'entraînement sur Kaggle
et à l'inférence dans Flask. Les paramètres viennent de configs/features.yaml.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field

from echolens.config import load_yaml

FloatArray = npt.NDArray[np.float32]


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


def log_mel_spectrogram(signal: FloatArray, config: FeatureConfig) -> FloatArray:
    """Calcule le spectrogramme log-Mel en décibels (décisions R1 et R2).

    Étapes : STFT avec fenêtre de Hann, puissance |X|², banc de filtres Mel, puis
    conversion en décibels avec un plancher dynamique de ``top_db``.
    Entrée : signal mono float32 à ``sample_rate``. Sortie : tableau (n_mels, T).
    """
    # torch est importé ici (et non en haut du fichier) pour que la CI, qui n'installe pas
    # les dépendances [ml], puisse quand même importer FeatureConfig.
    import torch
    import torchaudio

    mel_transform = torchaudio.transforms.MelSpectrogram(
        sample_rate=config.sample_rate,
        n_fft=config.n_fft,
        win_length=config.n_fft,
        hop_length=config.hop_length,
        f_min=config.f_min,
        f_max=config.f_max,
        n_mels=config.n_mels,
        window_fn=torch.hann_window,
        power=2.0,  # puissance |X|², pas amplitude
    )
    to_db = torchaudio.transforms.AmplitudeToDB(stype="power", top_db=config.top_db)

    with torch.no_grad():
        waveform = torch.from_numpy(signal).unsqueeze(0)  # (1, N) : un canal
        log_mel = to_db(mel_transform(waveform))  # (1, n_mels, T)

    result: FloatArray = log_mel.squeeze(0).numpy().astype(np.float32)
    return result


def mfcc(signal: FloatArray, config: FeatureConfig, with_deltas: bool = True) -> FloatArray:
    """Calcule les MFCC par DCT du log-Mel (décision R3), avec deltas si demandé.

    Sortie : (n_mfcc, T) sans deltas, ou (3 * n_mfcc, T) avec Δ et ΔΔ empilés.
    """
    import torch
    import torchaudio

    log_mel = torch.from_numpy(log_mel_spectrogram(signal, config))  # (n_mels, T)

    # Matrice de la DCT de forme (n_mels, n_mfcc) : on garde les n_mfcc premiers coefficients.
    dct_matrix = torchaudio.functional.create_dct(config.n_mfcc, config.n_mels, norm="ortho")
    coefficients = (log_mel.T @ dct_matrix).T  # (n_mfcc, T)

    if with_deltas:
        delta = torchaudio.functional.compute_deltas(coefficients)
        delta2 = torchaudio.functional.compute_deltas(delta)
        coefficients = torch.cat([coefficients, delta, delta2], dim=0)

    result: FloatArray = coefficients.numpy().astype(np.float32)
    return result
