"""Test de fidélité de Grad-CAM (E7, C14b) : la partie sans torch, sur des tableaux de synthèse."""

import numpy as np
import pytest
from pydantic import ValidationError

from echolens.config import CONFIG_DIR
from echolens.training.evaluation import EvaluationConfig
from echolens.training.grad_cam_fidelity import (
    FidelityConfig,
    cell_scores,
    deletion_area,
    deletion_inputs,
    hottest_first_order,
    load_fidelity_config,
    mask_cells,
    random_order,
    summarize_deletion,
)

BANDS = 64
FRAMES = 501


def small_config(fractions: list[float] | None = None) -> FidelityConfig:
    if fractions is None:
        fractions = [0.0, 0.5, 1.0]
    return FidelityConfig(
        cell_bands=16, cell_frames=16, fractions=fractions, fill_value=0.0, seed=0
    )


def evaluation_config() -> EvaluationConfig:
    return EvaluationConfig.from_yaml(CONFIG_DIR / "evaluation.yaml")


def test_repository_config_is_valid() -> None:
    config = load_fidelity_config()

    assert config.fractions[0] == 0.0
    assert config.fractions[-1] == 1.0
    assert config.fill_value == 0.0


@pytest.mark.parametrize("fractions", [[0.1, 1.0], [0.0, 0.5], [0.0, 0.6, 0.4, 1.0]])
def test_fractions_must_go_up_from_nothing_to_everything(fractions: list[float]) -> None:
    with pytest.raises(ValidationError):
        small_config(fractions)


def test_cells_follow_the_block_4_grid() -> None:
    grad_map = np.zeros((BANDS, FRAMES), dtype=np.float32)
    # Une zone chaude : bandes 16 à 31, trames 32 à 47, soit la case (ligne 1, colonne 2).
    grad_map[16:32, 32:48] = 1.0

    scores = cell_scores(grad_map, 16, 16)

    # 64 / 16 = 4 lignes ; 501 trames = 31 cases pleines et une de 5 trames.
    assert scores.shape == (4, 32)
    assert scores[1, 2] == 1.0
    assert scores.sum() == 1.0


def test_last_incomplete_column_is_averaged_on_its_real_frames() -> None:
    grad_map = np.zeros((BANDS, FRAMES), dtype=np.float32)
    grad_map[:, 496:] = 1.0

    scores = cell_scores(grad_map, 16, 16)

    assert scores[0, 31] == 1.0


def test_hottest_cells_come_first_and_ties_keep_reading_order() -> None:
    scores = np.array([[0.1, 0.9], [0.5, 0.5]])

    order = hottest_first_order(scores)

    assert order.tolist() == [1, 2, 3, 0]


def test_random_order_visits_every_cell_once() -> None:
    generator = np.random.default_rng(0)

    order = random_order(128, generator)

    assert sorted(order.tolist()) == list(range(128))


def test_masking_fills_only_the_chosen_cells() -> None:
    standardized = np.ones((BANDS, FRAMES), dtype=np.float32)
    column_count = 32
    # Case 33 = ligne 1, colonne 1 : bandes 16 à 31, trames 16 à 31.
    cells = np.array([33])

    masked = mask_cells(standardized, cells, column_count, small_config())

    assert masked[16:32, 16:32].max() == 0.0
    assert masked.sum() == BANDS * FRAMES - 16 * 16
    # L'entrée d'origine n'est pas touchée.
    assert standardized.min() == 1.0


def test_deletion_inputs_go_from_intact_to_fully_masked() -> None:
    standardized = np.ones((BANDS, FRAMES), dtype=np.float32)
    order = np.arange(4 * 32)

    inputs = deletion_inputs(standardized, order, 32, small_config())

    assert inputs.shape == (3, BANDS, FRAMES)
    assert inputs[0].min() == 1.0
    assert inputs[2].max() == 0.0
    # À mi-parcours, les 64 premières cases (les deux premières lignes) sont masquées.
    assert inputs[1][:32].max() == 0.0
    assert inputs[1][32:].min() == 1.0


def test_area_of_a_flat_curve_is_its_height() -> None:
    area = deletion_area([0.0, 0.5, 1.0], np.array([0.8, 0.8, 0.8]))

    assert area == pytest.approx(0.8)


def test_area_of_a_straight_drop_is_half() -> None:
    area = deletion_area([0.0, 0.25, 1.0], np.array([1.0, 0.75, 0.0]))

    assert area == pytest.approx(0.5)


def test_summary_rewards_a_map_that_beats_chance() -> None:
    # La probabilité tombe tout de suite avec la carte, lentement au hasard.
    hottest_first = np.array([[0.9, 0.1, 0.0], [0.8, 0.2, 0.0]])
    random = np.array([[0.9, 0.6, 0.0], [0.8, 0.5, 0.0]])

    summary = summarize_deletion(hottest_first, random, small_config(), evaluation_config())

    assert summary["clip_count"] == 2
    assert summary["share_of_clips_hottest_first_lower"] == 1.0
    assert summary["area_difference"] > 0.0
    low, high = summary["area_difference_ci95"]
    assert low <= summary["area_difference"] <= high
    assert summary["mean_curve_hottest_first"] == pytest.approx([0.85, 0.15, 0.0])
