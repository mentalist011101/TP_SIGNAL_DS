"""Famille A (C9) : résultats des 5 tours d'ESC-50, résumés et fichiers, sans torch (P3, P4, P8).

Règles de calcul :
- F1 macro et accuracy d'un tour = moyenne des 3 graines sur le fold de test ; on rapporte
  ensuite la moyenne et l'écart-type (ddof = 0) de ces 5 valeurs, comme la référence SVM ;
- l'écart-type entre graines (moyenne de chaque graine sur les 5 tours) mesure à part l'effet
  de l'initialisation ;
- les analyses sur les 2 000 prédictions réunies des 5 folds de test (intervalle bootstrap,
  F1 par classe, matrices, McNemar) utilisent la graine de référence, 42 (P8).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from echolens.core.features import FloatArray
from echolens.training.evaluation import (
    ClipPrediction,
    EvaluationConfig,
    IntArray,
    align_predictions,
    bootstrap_ci,
    macro_f1,
    mcnemar_test,
    mean_and_std,
    normalized_confusion,
    per_class_f1,
    to_categories,
)
from echolens.training.family_a import BandStatistics


@dataclass(frozen=True)
class TuningTrial:
    """Un taux d'apprentissage essayé au réglage, sur le fold k + 1 (P3)."""

    learning_rate: float
    best_epoch: int
    best_validation_f1: float
    epochs_run: int
    validation_f1_history: list[float]


@dataclass(frozen=True)
class SeedRun:
    """Un entraînement final (4 folds, une graine) évalué une seule fois sur le fold de test."""

    seed: int
    macro_f1: float
    accuracy: float
    predictions: IntArray
    probabilities: FloatArray  # (extraits de test, classes)
    attention: FloatArray | None  # CRNN seulement : (extraits de test, pas de temps)


@dataclass(frozen=True)
class RoundIndices:
    """Positions des extraits de chaque partie d'un tour, dans le jeu de log-Mel (P3)."""

    tuning_train: IntArray  # 3 folds
    validation: IntArray  # fold k + 1
    final_train: IntArray  # 4 folds hors test
    test: IntArray  # fold k


@dataclass(frozen=True)
class TuningOutcome:
    """Réglage d'un tour : essais, essai retenu, et modèle réglé appliqué au fold k + 1."""

    trials: list[TuningTrial]
    chosen: TuningTrial
    # Statistiques de standardisation des 3 folds du réglage (R4).
    statistics: BandStatistics
    # Probabilités du modèle réglé sur le fold k + 1 : serviront à la calibration (E2).
    validation_probabilities: FloatArray
    validation_attention: FloatArray | None


@dataclass(frozen=True)
class RoundResult:
    """Tout ce que produit un tour k : réglage, entraînements finaux, positions des extraits."""

    test_fold: int
    validation_fold: int
    indices: RoundIndices
    tuning: TuningOutcome
    validation_labels: IntArray
    test_labels: IntArray
    # Statistiques de standardisation des 4 folds de l'entraînement final (R4).
    final_statistics: BandStatistics
    runs: list[SeedRun]


def choose_trial(trials: list[TuningTrial]) -> int:
    """Position du meilleur essai au F1 macro de validation ; le premier en cas d'égalité (P3)."""
    best_position = 0
    for position, trial in enumerate(trials):
        if trial.best_validation_f1 > trials[best_position].best_validation_f1:
            best_position = position
    return best_position


def run_for_seed(round_result: RoundResult, seed: int) -> SeedRun:
    """Entraînement final d'une graine donnée dans un tour."""
    for run in round_result.runs:
        if run.seed == seed:
            return run
    raise ValueError(f"Aucun entraînement avec la graine {seed} au tour {round_result.test_fold}")


def cross_validation_scores(rounds: list[RoundResult]) -> dict[str, float]:
    """Moyenne et écart-type (ddof = 0) sur les 5 tours des scores moyennés sur les graines (P3)."""
    round_f1: list[float] = []
    round_accuracy: list[float] = []
    for round_result in rounds:
        f1_of_seeds = [run.macro_f1 for run in round_result.runs]
        accuracy_of_seeds = [run.accuracy for run in round_result.runs]
        round_f1.append(float(np.mean(f1_of_seeds)))
        round_accuracy.append(float(np.mean(accuracy_of_seeds)))
    f1_mean, f1_std = mean_and_std(round_f1)
    accuracy_mean, accuracy_std = mean_and_std(round_accuracy)
    return {
        "macro_f1_mean": f1_mean,
        "macro_f1_std": f1_std,
        "accuracy_mean": accuracy_mean,
        "accuracy_std": accuracy_std,
    }


def seed_scores(rounds: list[RoundResult], seeds: list[int]) -> dict[str, Any]:
    """Moyenne et écart-type de chaque graine sur les 5 tours, puis écart-type entre graines."""
    per_seed = []
    seed_means = []
    for seed in seeds:
        runs = [run_for_seed(round_result, seed) for round_result in rounds]
        f1_of_rounds = [run.macro_f1 for run in runs]
        accuracy_of_rounds = [run.accuracy for run in runs]
        f1_mean, f1_std = mean_and_std(f1_of_rounds)
        accuracy_mean, accuracy_std = mean_and_std(accuracy_of_rounds)
        seed_means.append(f1_mean)
        per_seed.append(
            {
                "seed": seed,
                "macro_f1_mean": f1_mean,
                "macro_f1_std": f1_std,
                "accuracy_mean": accuracy_mean,
                "accuracy_std": accuracy_std,
            }
        )
    _, between_seeds_std = mean_and_std(seed_means)
    return {"per_seed": per_seed, "macro_f1_std_between_seeds": between_seeds_std}


def round_details(round_result: RoundResult) -> dict[str, Any]:
    """Réglage et scores d'un tour : taux et nombre d'époques retenus, scores par graine."""
    trials = []
    for trial in round_result.tuning.trials:
        trials.append(
            {
                "learning_rate": trial.learning_rate,
                "best_epoch": trial.best_epoch,
                "best_validation_macro_f1": trial.best_validation_f1,
                "epochs_run": trial.epochs_run,
                "validation_macro_f1_per_epoch": trial.validation_f1_history,
            }
        )
    runs = []
    for run in round_result.runs:
        runs.append({"seed": run.seed, "macro_f1": run.macro_f1, "accuracy": run.accuracy})
    return {
        "test_fold": round_result.test_fold,
        "validation_fold": round_result.validation_fold,
        "chosen_learning_rate": round_result.tuning.chosen.learning_rate,
        "chosen_epochs": round_result.tuning.chosen.best_epoch,
        "tuning": trials,
        "final_runs": runs,
    }


def pooled_test_predictions(
    rounds: list[RoundResult], paths: list[str], seed: int
) -> list[ClipPrediction]:
    """Prédictions d'une graine sur les 5 folds de test réunis : chaque extrait une fois (P8)."""
    predictions: list[ClipPrediction] = []
    for round_result in rounds:
        run = run_for_seed(round_result, seed)
        for position, index in enumerate(round_result.indices.test):
            item = ClipPrediction(
                path=paths[index],
                fold=round_result.test_fold,
                target=int(round_result.test_labels[position]),
                prediction=int(run.predictions[position]),
            )
            predictions.append(item)
    return predictions


def pooled_scores(
    predictions: list[ClipPrediction],
    class_names: list[str],
    category_names: list[str],
    config: EvaluationConfig,
) -> dict[str, Any]:
    """Intervalle bootstrap, F1 par classe et matrices (50 classes, 5 catégories) (P4, P8)."""
    y_true = np.array([item.target for item in predictions], dtype=np.int_)
    y_pred = np.array([item.prediction for item in predictions], dtype=np.int_)
    low, high = bootstrap_ci(y_true, y_pred, config)
    class_scores = per_class_f1(y_true, y_pred, len(class_names))
    confusion_classes = normalized_confusion(y_true, y_pred, len(class_names))
    categories_true = to_categories(y_true)
    categories_pred = to_categories(y_pred)
    confusion_categories = normalized_confusion(
        categories_true, categories_pred, len(category_names)
    )
    return {
        "clip_count": len(predictions),
        "macro_f1_ci": [low, high],
        "per_class_f1": ranked_classes(class_scores, class_names),
        "confusion_classes": confusion_classes.tolist(),
        "category_names": category_names,
        "confusion_categories": confusion_categories.tolist(),
    }


def ranked_classes(
    class_scores: npt.NDArray[np.float64], class_names: list[str]
) -> list[dict[str, Any]]:
    """Classes de la mieux à la moins bien reconnue (F1 décroissant, puis nom)."""
    ranking = []
    for index, name in enumerate(class_names):
        ranking.append({"class": name, "f1": float(class_scores[index])})
    ranking.sort(key=_ranking_key)
    return ranking


def save_round_arrays(round_result: RoundResult, architecture: str, directory: Path) -> Path:
    """Écrit les prédictions, probabilités et poids d'attention d'un tour (.npz, sortie Kaggle)."""
    tuning = round_result.tuning
    arrays: dict[str, np.ndarray] = {
        "test_indices": round_result.indices.test,
        "test_labels": round_result.test_labels,
        "validation_indices": round_result.indices.validation,
        "validation_labels": round_result.validation_labels,
        "validation_probabilities": tuning.validation_probabilities,
        "tuning_band_mean": tuning.statistics.mean,
        "tuning_band_std": tuning.statistics.std,
        "final_band_mean": round_result.final_statistics.mean,
        "final_band_std": round_result.final_statistics.std,
    }
    if tuning.validation_attention is not None:
        arrays["validation_attention"] = tuning.validation_attention
    for run in round_result.runs:
        arrays[f"seed{run.seed}_predictions"] = run.predictions
        arrays[f"seed{run.seed}_probabilities"] = run.probabilities
        if run.attention is not None:
            arrays[f"seed{run.seed}_attention"] = run.attention
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{architecture}_fold{round_result.test_fold}.npz"
    # Les annotations de numpy confondent **arrays avec l'option allow_pickle : on les ignore.
    np.savez(path, **arrays)  # type: ignore[arg-type]
    return path


def compare_models(
    name_a: str,
    first: list[ClipPrediction],
    name_b: str,
    second: list[ClipPrediction],
    config: EvaluationConfig,
) -> dict[str, Any]:
    """McNemar et F1 macro (intervalle bootstrap) de deux modèles sur les mêmes extraits (P8)."""
    aligned = align_predictions(first, second)
    y_true = aligned.y_true
    test = mcnemar_test(y_true, aligned.pred_a, aligned.pred_b, config)
    low_a, high_a = bootstrap_ci(y_true, aligned.pred_a, config)
    low_b, high_b = bootstrap_ci(y_true, aligned.pred_b, config)
    return {
        "model_a": name_a,
        "model_b": name_b,
        "clip_count": len(aligned.paths),
        "macro_f1_a": macro_f1(y_true, aligned.pred_a),
        "macro_f1_a_ci": [low_a, high_a],
        "macro_f1_b": macro_f1(y_true, aligned.pred_b),
        "macro_f1_b_ci": [low_b, high_b],
        "both_right": test.both_right,
        "only_a_right": test.only_a_right,
        "only_b_right": test.only_b_right,
        "both_wrong": test.both_wrong,
        "statistic": test.statistic,
        "p_value": test.p_value,
        "exact": test.exact,
    }


def _ranking_key(entry: dict[str, Any]) -> tuple[float, str]:
    # F1 décroissant (d'où le signe moins), puis ordre alphabétique en cas d'égalité.
    return (-entry["f1"], entry["class"])
