"""Modèles de production (C13) : réglage retenu et calibration honnête, sans torch.

Pour ESC-50, le modèle de production est entraîné sur les 5 folds : il n'existe plus de
données jamais vues pour régler T. On réutilise donc les 5 tours de la validation croisée :
au tour k, le modèle n'avait jamais vu le fold k, et T_k se règle sur ses prédictions de ce
fold. La température de production est la moyenne des 5 T_k.

Pour mesurer l'ECE sans tricher, chaque fold k est calibré avec la moyenne des 4 AUTRES
températures : T n'a alors jamais vu les extraits sur lesquels on la juge (ECE « hors fold »).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field

from echolens.config import CONFIG_DIR, load_yaml
from echolens.training.evaluation import (
    EvaluationConfig,
    FloatMatrix,
    IntArray,
    apply_temperature,
    expected_calibration_error,
    fit_temperature,
)

PRODUCTION_CONFIG_PATH = CONFIG_DIR / "production.yaml"


class PlannedModel(BaseModel):
    """Un modèle de production prévu dans configs/production.yaml."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9\-]*$")
    task: str
    architecture: str
    license: str
    data: str


class ProductionPlan(BaseModel):
    """Contenu de configs/production.yaml."""

    seed: int
    models: list[PlannedModel] = Field(min_length=1)

    def model(self, model_id: str) -> PlannedModel:
        """Le modèle prévu sous cet identifiant ; lève KeyError s'il n'existe pas."""
        for planned in self.models:
            if planned.id == model_id:
                return planned
        raise KeyError(f"Modèle de production inconnu : {model_id}")


def load_production_plan(path: Path = PRODUCTION_CONFIG_PATH) -> ProductionPlan:
    """Lit configs/production.yaml."""
    content = load_yaml(path)
    return ProductionPlan(**content)


@dataclass(frozen=True)
class RoundPredictions:
    """Prédictions d'un modèle sur des extraits qu'il n'a jamais vus, et leurs vraies classes."""

    y_true: IntArray
    probabilities: FloatMatrix


@dataclass(frozen=True)
class CalibrationOutcome:
    """Température retenue et ECE avant / après calibration."""

    temperature: float
    ece_before: float
    ece_after: float
    round_temperatures: list[float]


def median_value(values: list[float]) -> float:
    """Médiane des réglages des 5 tours (taux d'apprentissage, dropout ou époques).

    Avec 5 valeurs, la médiane est la 3e après tri : c'est toujours une valeur réellement
    retenue par un tour, jamais un compromis inventé entre deux réglages.
    """
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def out_of_fold_calibration(
    rounds: list[RoundPredictions], config: EvaluationConfig
) -> CalibrationOutcome:
    """T de production = moyenne des T des tours ; ECE hors fold, avant et après (E2)."""
    # Étape 1 : une température par tour, réglée sur le fold de test de ce tour.
    round_temperatures = []
    for round_predictions in rounds:
        temperature = fit_temperature(
            round_predictions.y_true, round_predictions.probabilities, config
        )
        round_temperatures.append(temperature)
    # Étape 2 : chaque fold calibré avec la moyenne des 4 autres températures.
    calibrated = []
    for index, round_predictions in enumerate(rounds):
        others = round_temperatures[:index] + round_temperatures[index + 1 :]
        temperature_without_this_fold = float(np.mean(others))
        probabilities = apply_temperature(
            round_predictions.probabilities, temperature_without_this_fold, config
        )
        calibrated.append(probabilities)
    # Étape 3 : ECE sur toutes les prédictions réunies, avant et après.
    all_y_true = np.concatenate([round_predictions.y_true for round_predictions in rounds])
    raw = np.concatenate([round_predictions.probabilities for round_predictions in rounds])
    ece_before = expected_calibration_error(all_y_true, raw, config).ece
    all_calibrated = np.concatenate(calibrated)
    ece_after = expected_calibration_error(all_y_true, all_calibrated, config).ece
    return CalibrationOutcome(
        temperature=float(np.mean(round_temperatures)),
        ece_before=ece_before,
        ece_after=ece_after,
        round_temperatures=round_temperatures,
    )


def validation_calibration(
    validation: RoundPredictions, test: RoundPredictions, config: EvaluationConfig
) -> CalibrationOutcome:
    """T réglée sur la validation, ECE mesurée sur le test avant et après (E2)."""
    temperature = fit_temperature(validation.y_true, validation.probabilities, config)
    calibrated = apply_temperature(test.probabilities, temperature, config)
    ece_before = expected_calibration_error(test.y_true, test.probabilities, config).ece
    ece_after = expected_calibration_error(test.y_true, calibrated, config).ece
    return CalibrationOutcome(
        temperature=temperature, ece_before=ece_before, ece_after=ece_after, round_temperatures=[]
    )
