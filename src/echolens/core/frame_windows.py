"""Fenêtres de longueur fixe dans un log-Mel (C12) : découpe et complément par du silence.

Les réseaux de la famille A attendent une image de taille fixe (64 bandes × 301 trames pour
3 s). Un extrait plus long est découpé : au hasard à l'entraînement (une augmentation de plus,
à chaque lot), au centre en validation, en test et dans l'application. Un extrait plus court
est complété à la fin par du silence : le plancher du log-Mel en dB absolus (−100 dB, R2),
c'est-à-dire ce que donnerait un signal nul.

Fonctions pures, sans torch, testées en CI.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from echolens.core.features import FeatureConfig, FloatArray

IntArray = npt.NDArray[np.int_]


def window_frame_count(window_s: float, config: FeatureConfig) -> int:
    """Nombre de trames du log-Mel d'une fenêtre de window_s (R1) : 301 pour 3 s, 501 pour 5 s.

    Trames centrées (center=True) : 1 + nombre d'échantillons / pas, soit 1 + 48 000 / 160.
    """
    sample_count = round(window_s * config.sample_rate)
    return 1 + sample_count // config.hop_length


def centered_start(length: int, window_frames: int) -> int:
    """Première trame de la fenêtre centrale ; 0 si l'extrait est plus court que la fenêtre."""
    extra = length - window_frames
    if extra <= 0:
        return 0
    return extra // 2


def random_start(length: int, window_frames: int, generator: np.random.Generator) -> int:
    """Première trame d'une fenêtre tirée au hasard, entièrement dans l'extrait."""
    extra = length - window_frames
    if extra <= 0:
        return 0
    return int(generator.integers(low=0, high=extra + 1))


def frame_window(
    log_mel: FloatArray, length: int, start: int, window_frames: int, silence_db: float
) -> FloatArray:
    """Fenêtre (bandes, window_frames) à partir de la trame start, complétée par du silence.

    length est le nombre de vraies trames : log_mel peut être plus long (stocké avec d'autres
    extraits plus longs, le reste est déjà du silence).
    """
    real_frames = log_mel[:, :length]
    piece = real_frames[:, start : start + window_frames]
    missing = window_frames - piece.shape[1]
    if missing <= 0:
        return np.asarray(piece, dtype=np.float32)
    band_count = log_mel.shape[0]
    silence = np.full((band_count, missing), silence_db, dtype=np.float32)
    completed = np.concatenate([piece, silence], axis=1)
    return np.asarray(completed, dtype=np.float32)


def center_windows(
    log_mels: FloatArray, lengths: IntArray, window_frames: int, silence_db: float
) -> FloatArray:
    """Fenêtre centrale de chaque extrait : (extraits, bandes, window_frames)."""
    windows = []
    for index in range(len(log_mels)):
        length = int(lengths[index])
        start = centered_start(length, window_frames)
        window = frame_window(log_mels[index], length, start, window_frames, silence_db)
        windows.append(window)
    return np.stack(windows)


def random_windows(
    log_mels: FloatArray,
    lengths: IntArray,
    window_frames: int,
    silence_db: float,
    generator: np.random.Generator,
) -> FloatArray:
    """Une fenêtre tirée au hasard dans chaque extrait (augmentation du train)."""
    windows = []
    for index in range(len(log_mels)):
        length = int(lengths[index])
        start = random_start(length, window_frames, generator)
        window = frame_window(log_mels[index], length, start, window_frames, silence_db)
        windows.append(window)
    return np.stack(windows)


def silence_share(length: int, window_frames: int) -> float:
    """Part de la fenêtre remplie de silence ajouté : 0 si l'extrait est assez long."""
    missing = max(window_frames - length, 0)
    return missing / window_frames
