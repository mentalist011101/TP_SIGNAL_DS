"""Métriques communes à tous les modèles (P4) : F1 macro, accuracy, matrices normalisées.

Les étiquettes sont des entiers de 0 à n_classes − 1.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

IntArray = npt.NDArray[np.int_]
FloatMatrix = npt.NDArray[np.float64]


def macro_f1(y_true: IntArray, y_pred: IntArray) -> float:
    """F1 macro : moyenne simple des F1 par classe, chaque classe compte autant (P4)."""
    score = f1_score(y_true, y_pred, average="macro", zero_division=0.0)
    return float(score)


def accuracy(y_true: IntArray, y_pred: IntArray) -> float:
    """Part des prédictions correctes."""
    score = accuracy_score(y_true, y_pred)
    return float(score)


def normalized_confusion(y_true: IntArray, y_pred: IntArray, n_classes: int) -> FloatMatrix:
    """Matrice de confusion normalisée par ligne : case (i, j) = part de la classe i prédite j.

    Chaque ligne d'une classe présente somme à 1. Une classe absente de y_true donne une
    ligne de zéros (aucune division par zéro).
    """
    # Étape 1 : comptes bruts, avec toutes les classes même si l'une n'apparaît pas.
    all_classes = np.arange(n_classes)
    counts = confusion_matrix(y_true, y_pred, labels=all_classes)
    # Étape 2 : division de chaque ligne par son total (nombre d'exemples de la classe).
    row_totals = counts.sum(axis=1, keepdims=True)
    safe_totals = np.maximum(row_totals, 1)
    normalized = counts / safe_totals
    return np.asarray(normalized, dtype=np.float64)


def to_categories(labels: IntArray, group_size: int = 10) -> IntArray:
    """Passe des 50 classes d'ESC-50 aux 5 catégories : target // 10 (0-9 → 0, 10-19 → 1…)."""
    categories = labels // group_size
    return np.asarray(categories, dtype=np.int_)


def mean_and_std(values: Sequence[float]) -> tuple[float, float]:
    """Moyenne et écart-type (de population, ddof=0) d'une liste de scores, par exemple par fold."""
    array = np.asarray(values, dtype=np.float64)
    mean = float(array.mean())
    std = float(array.std())
    return mean, std
