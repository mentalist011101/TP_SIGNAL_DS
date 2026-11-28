"""Carte d'explicabilité d'un audio entier, à partir des cartes de ses fenêtres (E7, EF-13).

Calcul pur, sans torch : les cartes Grad-CAM de chaque fenêtre sont calculées par
echolens.core.models.grad_cam. Ici, on les place sur l'axe du temps du spectrogramme de tout
l'audio, pour que la carte se superpose exactement à l'image affichée (même nombre de bandes,
une colonne par trame de 10 ms).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float32]


@dataclass(frozen=True)
class MapPiece:
    """Carte d'une fenêtre, (bandes, trames), qui commence à la trame first_frame de l'audio."""

    first_frame: int
    values: FloatArray


def combine_window_maps(band_count: int, total_frames: int, pieces: list[MapPiece]) -> FloatArray:
    """Carte (bandes, trames) de tout l'audio, entre 0 et 1.

    Chaque carte de fenêtre est d'abord ramenée entre 0 et 1 (divisée par son maximum) : les
    fenêtres ont toutes le même poids. Là où des fenêtres se recouvrent, on fait la moyenne.
    Une trame couverte par aucune fenêtre vaut 0 (rien n'y est expliqué).
    """
    totals = np.zeros((band_count, total_frames), dtype=np.float64)
    counts = np.zeros(total_frames, dtype=np.float64)
    for piece in pieces:
        # Étape 1 : la carte de la fenêtre, entre 0 et 1.
        normalized = _normalized(piece.values)
        # Étape 2 : sa place sur l'axe du temps, coupée au bout de l'audio.
        first = max(piece.first_frame, 0)
        last = min(piece.first_frame + normalized.shape[1], total_frames)
        if last <= first:
            continue
        skipped = first - piece.first_frame
        visible = normalized[:, skipped : skipped + (last - first)]
        totals[:, first:last] += visible
        counts[first:last] += 1
    # Étape 3 : moyenne là où des fenêtres se recouvrent.
    covered = counts > 0
    combined = np.zeros((band_count, total_frames), dtype=np.float32)
    combined[:, covered] = totals[:, covered] / counts[covered]
    return combined


def _normalized(values: FloatArray) -> FloatArray:
    # Une carte nulle (aucune zone ne soutient la classe) reste nulle.
    peak = float(values.max())
    if peak <= 0.0:
        return np.zeros_like(values, dtype=np.float32)
    scaled: FloatArray = (values / peak).astype(np.float32)
    return scaled
