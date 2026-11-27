"""Test de fidélité de Grad-CAM par suppression (E7, C14b) : la partie sans torch.

Question : la carte montre-t-elle vraiment ce qui fait décider le réseau ? On cache des cases du
spectrogramme standardisé, de plus en plus nombreuses, et on suit la probabilité de la classe
prédite au départ. Deux ordres de masquage :
- les cases les plus chaudes de la carte d'abord ;
- un ordre tiré au hasard (le témoin).
Si la carte est fidèle, la probabilité chute nettement plus vite avec le premier ordre : l'aire
sous sa courbe est plus petite (Petsiuk et al., « RISE », BMVC 2018, métrique de suppression).

Une case vaut un point de la carte du bloc 4 (16 bandes × 16 trames) ; une case masquée prend la
moyenne du train, 0 après la standardisation R4 (décision C14). Paramètres :
configs/grad_cam_fidelity.yaml. Le calcul avec le réseau est dans grad_cam_fidelity_models.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, Field, field_validator

from echolens.config import CONFIG_DIR, load_yaml
from echolens.core.features import FloatArray
from echolens.training.evaluation import EvaluationConfig, IntArray

FIDELITY_CONFIG_PATH = CONFIG_DIR / "grad_cam_fidelity.yaml"


class FidelityConfig(BaseModel):
    """Contenu de configs/grad_cam_fidelity.yaml."""

    cell_bands: int = Field(gt=0)
    cell_frames: int = Field(gt=0)
    fractions: list[float] = Field(min_length=2)
    fill_value: float
    seed: int

    @field_validator("fractions")
    @classmethod
    def _from_nothing_to_everything(cls, fractions: list[float]) -> list[float]:
        # La courbe part de l'entrée intacte et finit tout masqué, en montant pas à pas.
        if fractions[0] != 0.0 or fractions[-1] != 1.0:
            raise ValueError("Les parts masquées doivent aller de 0 à 1.")
        if sorted(fractions) != fractions:
            raise ValueError("Les parts masquées doivent être croissantes.")
        return fractions


def load_fidelity_config(path: Path = FIDELITY_CONFIG_PATH) -> FidelityConfig:
    """Lit configs/grad_cam_fidelity.yaml."""
    content = load_yaml(path)
    return FidelityConfig(**content)


def cell_scores(grad_map: FloatArray, cell_bands: int, cell_frames: int) -> FloatArray:
    """Chaleur moyenne de chaque case : (groupes de bandes, groupes de trames).

    La dernière colonne peut être incomplète (501 trames = 31 cases de 16 et une de 5).
    """
    band_count, frame_count = grad_map.shape
    row_count = math.ceil(band_count / cell_bands)
    column_count = math.ceil(frame_count / cell_frames)
    scores = np.zeros((row_count, column_count), dtype=np.float64)
    for row in range(row_count):
        for column in range(column_count):
            cell = _cell_view(grad_map, row, column, cell_bands, cell_frames)
            scores[row, column] = cell.mean()
    return scores


def hottest_first_order(scores: FloatArray) -> IntArray:
    """Numéros des cases, de la plus chaude à la plus froide (numéro = ligne × colonnes + colonne).

    Tri stable : à chaleur égale, l'ordre de lecture départage, le même à chaque exécution.
    """
    flat = scores.ravel()
    negated = -flat
    order = np.argsort(negated, kind="stable")
    return np.asarray(order, dtype=np.int_)


def random_order(cell_count: int, generator: np.random.Generator) -> IntArray:
    """Numéros des cases dans un ordre tiré au hasard : le témoin du test."""
    order = generator.permutation(cell_count)
    return np.asarray(order, dtype=np.int_)


def mask_cells(
    standardized: FloatArray, cells: IntArray, column_count: int, config: FidelityConfig
) -> FloatArray:
    """Copie de l'entrée standardisée où les cases demandées valent fill_value."""
    masked = standardized.copy()
    for cell in cells:
        row = int(cell) // column_count
        column = int(cell) % column_count
        view = _cell_view(masked, row, column, config.cell_bands, config.cell_frames)
        view[...] = config.fill_value
    return masked


def deletion_inputs(
    standardized: FloatArray, order: IntArray, column_count: int, config: FidelityConfig
) -> FloatArray:
    """Une entrée par point de la courbe : (parts masquées, bandes, trames).

    Au point de part f, les round(f × nombre de cases) premières cases de l'ordre sont masquées.
    """
    cell_count = len(order)
    inputs = []
    for fraction in config.fractions:
        masked_count = round(fraction * cell_count)
        first_cells = order[:masked_count]
        masked = mask_cells(standardized, first_cells, column_count, config)
        inputs.append(masked)
    stacked = np.stack(inputs)
    return np.asarray(stacked, dtype=np.float32)


def deletion_area(fractions: list[float], probabilities: FloatArray) -> float:
    """Aire sous la courbe de suppression (méthode des trapèzes), entre 0 et 1.

    Plus elle est petite, plus la probabilité est tombée vite quand on a caché les cases.
    """
    area = 0.0
    for point in range(1, len(fractions)):
        width = fractions[point] - fractions[point - 1]
        mean_height = (probabilities[point] + probabilities[point - 1]) / 2.0
        area += width * float(mean_height)
    return area


def summarize_deletion(
    hottest_first: FloatArray,
    random: FloatArray,
    config: FidelityConfig,
    evaluation_config: EvaluationConfig,
) -> dict[str, Any]:
    """Résumé du test sur un jeu d'extraits ; chaque tableau a la forme (extraits, points).

    Écart = aire au hasard − aire des plus chaudes d'abord, extrait par extrait : positif quand
    la carte désigne mieux que le hasard ce qui compte pour le réseau. Son intervalle à 95 %
    vient d'un bootstrap sur les extraits (P8).
    """
    hottest_areas = _areas(hottest_first, config.fractions)
    random_areas = _areas(random, config.fractions)
    differences = random_areas - hottest_areas
    low, high = _bootstrap_mean_interval(differences, evaluation_config)
    hottest_wins = differences > 0.0
    return {
        "clip_count": len(differences),
        "fractions": config.fractions,
        "mean_curve_hottest_first": _mean_curve(hottest_first),
        "mean_curve_random": _mean_curve(random),
        "area_hottest_first": float(hottest_areas.mean()),
        "area_random": float(random_areas.mean()),
        "area_difference": float(differences.mean()),
        "area_difference_ci95": [low, high],
        "share_of_clips_hottest_first_lower": float(hottest_wins.mean()),
    }


def _cell_view(
    values: FloatArray, row: int, column: int, cell_bands: int, cell_frames: int
) -> FloatArray:
    # Vue (pas une copie) sur la case : l'écrire modifie le tableau d'origine.
    first_band = row * cell_bands
    first_frame = column * cell_frames
    bands = slice(first_band, first_band + cell_bands)
    frames = slice(first_frame, first_frame + cell_frames)
    return values[bands, frames]


def _areas(curves: FloatArray, fractions: list[float]) -> FloatArray:
    areas = [deletion_area(fractions, curve) for curve in curves]
    return np.array(areas, dtype=np.float64)


def _mean_curve(curves: FloatArray) -> list[float]:
    mean_per_point = curves.mean(axis=0)
    return [float(value) for value in mean_per_point]


def _bootstrap_mean_interval(
    values: FloatArray, evaluation_config: EvaluationConfig
) -> tuple[float, float]:
    # Bootstrap percentile de la moyenne : mêmes tirages et même niveau que les autres
    # intervalles du projet (configs/evaluation.yaml).
    generator = np.random.default_rng(evaluation_config.seed)
    count = len(values)
    means = np.empty(evaluation_config.n_bootstrap, dtype=np.float64)
    for draw in range(evaluation_config.n_bootstrap):
        picked = generator.integers(0, count, size=count)
        means[draw] = values[picked].mean()
    tail = (1.0 - evaluation_config.confidence) / 2.0
    low, high = np.quantile(means, [tail, 1.0 - tail])
    return float(low), float(high)
