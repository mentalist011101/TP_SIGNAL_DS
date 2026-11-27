"""Carte d'explicabilité d'un audio entier, à partir des cartes de ses fenêtres (E7, EF-13)."""

import numpy as np
import pytest

from echolens.core.explain import MapPiece, combine_window_maps

BANDS = 4


def constant_map(value: float, frames: int) -> np.ndarray:
    return np.full((BANDS, frames), value, dtype=np.float32)


def test_each_window_is_scaled_between_zero_and_one() -> None:
    piece = MapPiece(first_frame=2, values=constant_map(7.0, 3))

    combined = combine_window_maps(BANDS, 10, [piece])

    assert combined.shape == (BANDS, 10)
    assert combined[:, 2:5].tolist() == np.ones((BANDS, 3)).tolist()
    # Les trames couvertes par aucune fenêtre restent à 0.
    assert combined[:, :2].max() == 0.0
    assert combined[:, 5:].max() == 0.0


def test_overlapping_windows_are_averaged() -> None:
    strong = np.zeros((BANDS, 4), dtype=np.float32)
    strong[0, :] = 2.0
    weak = np.zeros((BANDS, 4), dtype=np.float32)
    weak[0, :] = 1.0
    weak[1, :] = 1.0

    combined = combine_window_maps(BANDS, 6, [MapPiece(0, strong), MapPiece(2, weak)])

    # Trames 2 et 3 : couvertes par les deux fenêtres, chacune ramenée entre 0 et 1.
    assert combined[0, 2] == pytest.approx(1.0)
    assert combined[1, 2] == pytest.approx(0.5)
    # Trames 4 et 5 : seulement la seconde fenêtre.
    assert combined[1, 4] == pytest.approx(1.0)


def test_window_past_the_end_is_cut() -> None:
    piece = MapPiece(first_frame=8, values=constant_map(1.0, 5))

    combined = combine_window_maps(BANDS, 10, [piece])

    assert combined.shape == (BANDS, 10)
    assert combined[:, 8:].min() == pytest.approx(1.0)


def test_window_before_the_start_is_cut() -> None:
    values = np.arange(BANDS * 4, dtype=np.float32).reshape(BANDS, 4)

    combined = combine_window_maps(BANDS, 6, [MapPiece(first_frame=-2, values=values)])

    # Seules les colonnes 2 et 3 de la fenêtre tombent dans l'audio, en trames 0 et 1.
    expected = values[:, 2:4] / values.max()
    assert combined[:, :2] == pytest.approx(expected)


def test_a_zero_map_stays_zero() -> None:
    combined = combine_window_maps(BANDS, 5, [MapPiece(0, constant_map(0.0, 5))])

    assert combined.max() == 0.0
