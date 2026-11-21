"""Trames utiles de l'encodeur Whisper et moyennes par couche (C10, Brique 4), sans torch.

Code partagé (R5) : le calcul des représentations de la famille B sur Kaggle et l'application
(prédicteur réel, C13) moyennent les sorties de l'encodeur exactement de la même façon.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float32]


def whisper_useful_frames(sample_count: int, samples_per_frame: int, max_frames: int) -> int:
    """Nombre de trames de sortie de l'encodeur Whisper qui viennent du vrai signal.

    L'encodeur reçoit toujours 30 s : le feature extractor complète l'extrait par du
    silence. Une trame de sortie couvre samples_per_frame échantillons (320, soit 20 ms) :
    on garde ceil(sample_count / samples_per_frame) trames, au moins 1, au plus max_frames.
    Un extrait plus long que 30 s serait coupé par le feature extractor : on le refuse.
    """
    max_samples = samples_per_frame * max_frames
    if sample_count > max_samples:
        raise ValueError(
            f"Extrait trop long pour l'encodeur Whisper : {sample_count} échantillons, "
            f"maximum {max_samples} (30 s à 16 kHz)"
        )
    # Division entière arrondie vers le haut : une trame à moitié remplie compte.
    frame_count = (sample_count + samples_per_frame - 1) // samples_per_frame
    return max(frame_count, 1)


def layer_means(hidden_states: FloatArray, frame_count: int | None = None) -> FloatArray:
    """Moyenne dans le temps de chaque couche : (couches, temps, dimension) → (couches, dimension).

    Avec frame_count, seules les frame_count premières trames comptent (trames utiles de
    Whisper) ; sans, toutes les trames.
    """
    kept = hidden_states
    if frame_count is not None:
        kept = hidden_states[:, :frame_count, :]
    means = kept.mean(axis=1)
    return np.asarray(means, dtype=np.float32)
