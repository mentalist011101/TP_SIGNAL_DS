"""Métriques communes à tous les modèles (P4) : F1 macro, accuracy, matrices normalisées.

Les étiquettes sont des entiers de 0 à n_classes − 1.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field
from scipy.stats import binomtest, chi2
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from echolens.config import load_yaml

IntArray = npt.NDArray[np.int_]
FloatMatrix = npt.NDArray[np.float64]


class EvaluationConfig(BaseModel):
    """Paramètres de l'évaluation comparée, lus dans configs/evaluation.yaml."""

    n_bootstrap: int = Field(default=1000, gt=0)
    confidence: float = Field(default=0.95, gt=0, lt=1)
    ece_bins: int = Field(default=10, gt=0)
    seed: int = 42
    mcnemar_exact_below: int = Field(default=25, gt=0)

    @classmethod
    def from_yaml(cls, path: Path) -> EvaluationConfig:
        """Charge la configuration depuis un fichier YAML."""
        return cls(**load_yaml(path))


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


def scores_by_group(
    y_true: IntArray,
    y_pred: IntArray,
    groups: Sequence[str],
    metric: Callable[[IntArray, IntArray], float] = macro_f1,
) -> dict[str, float]:
    """Calcule une métrique séparément pour chaque groupe (genre, locuteur) (E4).

    ``groups[i]`` est le groupe de l'extrait i. Renvoie {nom du groupe: score}, trié par nom.
    """
    group_array = np.asarray(groups)
    if not (len(y_true) == len(y_pred) == len(group_array)):
        raise ValueError("y_true, y_pred et groups doivent avoir la même longueur")

    scores: dict[str, float] = {}
    for name in sorted(set(group_array.tolist())):
        # Masque booléen : True pour les extraits de ce groupe seulement.
        mask = group_array == name
        scores[name] = metric(y_true[mask], y_pred[mask])
    return scores


def bootstrap_ci(
    y_true: IntArray,
    y_pred: IntArray,
    config: EvaluationConfig,
    metric: Callable[[IntArray, IntArray], float] = macro_f1,
) -> tuple[float, float]:
    """Intervalle de confiance par bootstrap percentile d'une métrique (P8).

    On rééchantillonne les extraits avec remise ``n_bootstrap`` fois, on recalcule la métrique
    à chaque tirage, puis on prend les percentiles qui encadrent ``confidence`` des scores.
    """
    if len(y_true) != len(y_pred):
        raise ValueError("y_true et y_pred doivent avoir la même longueur")

    rng = np.random.default_rng(config.seed)
    n = len(y_true)
    scores = np.empty(config.n_bootstrap, dtype=np.float64)
    for i in range(config.n_bootstrap):
        # Les indices tirés avec remise donnent un faux jeu de test de même taille.
        picked = rng.integers(0, n, size=n)
        scores[i] = metric(y_true[picked], y_pred[picked])

    # Pour 95 % : on garde le centre, en coupant 2,5 % de chaque côté.
    tail = (1.0 - config.confidence) / 2.0
    low, high = np.quantile(scores, [tail, 1.0 - tail])
    return float(low), float(high)


@dataclass(frozen=True)
class McNemarResult:
    """Résultat du test de McNemar entre deux modèles sur les mêmes extraits."""

    both_right: int
    only_a_right: int
    only_b_right: int
    both_wrong: int
    statistic: float | None  # None pour le test exact : il n'a pas de statistique χ²
    p_value: float
    exact: bool


def mcnemar_test(
    y_true: IntArray,
    pred_a: IntArray,
    pred_b: IntArray,
    config: EvaluationConfig,
) -> McNemarResult:
    """Test de McNemar : les modèles A et B ont-ils la même erreur sur les mêmes extraits ? (P8)

    Seuls les désaccords comptent. Sous H0 (aucun modèle meilleur), chaque désaccord est un
    pile ou face : exact (binomial) si peu de désaccords, sinon χ² avec correction de continuité.
    """
    if not (len(y_true) == len(pred_a) == len(pred_b)):
        raise ValueError("y_true, pred_a et pred_b doivent avoir la même longueur")

    a_right = pred_a == y_true
    b_right = pred_b == y_true
    both_right = int(np.sum(a_right & b_right))
    only_a = int(np.sum(a_right & ~b_right))
    only_b = int(np.sum(~a_right & b_right))
    both_wrong = int(np.sum(~a_right & ~b_right))

    disagreements = only_a + only_b
    if disagreements == 0:
        # Les deux modèles se trompent exactement aux mêmes endroits : rien à départager.
        return McNemarResult(both_right, only_a, only_b, both_wrong, 0.0, 1.0, exact=False)

    if disagreements < config.mcnemar_exact_below:
        # Test exact : on regarde le plus petit des deux comptes dans une binomiale (n, 0,5).
        p_value = float(binomtest(min(only_a, only_b), disagreements, 0.5).pvalue)
        return McNemarResult(both_right, only_a, only_b, both_wrong, None, p_value, exact=True)

    # Le « − 1 » est la correction de continuité (une loi discrète approchée par une continue).
    statistic = (abs(only_a - only_b) - 1) ** 2 / disagreements
    p_value = float(chi2.sf(statistic, df=1))
    return McNemarResult(both_right, only_a, only_b, both_wrong, statistic, p_value, exact=False)
