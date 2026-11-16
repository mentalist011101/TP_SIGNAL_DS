import numpy as np
import pytest

from echolens.training.evaluation import (
    EvaluationConfig,
    accuracy,
    bootstrap_ci,
    macro_f1,
    mean_and_std,
    normalized_confusion,
    scores_by_group,
    to_categories,
)


def test_perfect_predictions_give_f1_and_accuracy_of_one() -> None:
    labels = np.array([0, 1, 2, 2])
    assert macro_f1(labels, labels) == pytest.approx(1.0)
    assert accuracy(labels, labels) == pytest.approx(1.0)


def test_macro_f1_gives_each_class_the_same_weight() -> None:
    # Classe 0 : 3 exemples tous justes (F1 = 1). Classe 1 : 1 exemple, manqué (F1 = 0).
    y_true = np.array([0, 0, 0, 1])
    y_pred = np.array([0, 0, 0, 0])
    assert accuracy(y_true, y_pred) == pytest.approx(0.75)
    # F1 de la classe 0 : précision 3/4, rappel 1, soit 6/7 ; moyenne avec 0.
    assert macro_f1(y_true, y_pred) == pytest.approx((6 / 7) / 2)


def test_normalized_confusion_rows_sum_to_one() -> None:
    y_true = np.array([0, 0, 1, 1, 1, 2])
    y_pred = np.array([0, 1, 1, 1, 2, 0])
    matrix = normalized_confusion(y_true, y_pred, n_classes=3)
    np.testing.assert_allclose(matrix.sum(axis=1), [1.0, 1.0, 1.0])
    assert matrix[1, 2] == pytest.approx(1 / 3)


def test_absent_class_gives_a_row_of_zeros() -> None:
    y_true = np.array([0, 1])
    y_pred = np.array([0, 1])
    matrix = normalized_confusion(y_true, y_pred, n_classes=3)
    np.testing.assert_allclose(matrix[2], [0.0, 0.0, 0.0])


def test_to_categories_groups_classes_by_ten() -> None:
    categories = to_categories(np.array([0, 9, 10, 49]))
    assert list(categories) == [0, 0, 1, 4]


def test_mean_and_std() -> None:
    mean, std = mean_and_std([0.4, 0.6])
    assert mean == pytest.approx(0.5)
    assert std == pytest.approx(0.1)


def test_scores_by_group_matches_hand_computation() -> None:
    y_true = np.array([0, 0, 1, 1, 0, 1])
    y_pred = np.array([0, 1, 1, 1, 0, 1])
    groups = ["F", "F", "F", "F", "H", "H"]

    scores = scores_by_group(y_true, y_pred, groups)

    # Groupe F : classe 0 → P=1, R=1/2, F1=2/3 ; classe 1 → P=2/3, R=1, F1=4/5.
    # Macro = (2/3 + 4/5) / 2 = 11/15.
    assert scores["F"] == pytest.approx(11 / 15)
    # Groupe H : tout est correct.
    assert scores["H"] == pytest.approx(1.0)


def test_scores_by_group_accepts_other_metric() -> None:
    y_true = np.array([0, 0, 1, 1, 0, 1])
    y_pred = np.array([0, 1, 1, 1, 0, 1])
    groups = ["F", "F", "F", "F", "H", "H"]
    scores = scores_by_group(y_true, y_pred, groups, metric=accuracy)
    assert scores == {"F": pytest.approx(0.75), "H": pytest.approx(1.0)}


def test_scores_by_group_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError):
        scores_by_group(np.array([0, 1]), np.array([0, 1]), ["F"])


def test_bootstrap_ci_of_perfect_predictions_is_degenerate() -> None:
    # Tout est juste : chaque faux échantillon donne 1, donc l'intervalle vaut [1, 1].
    labels = np.array([0, 1, 0, 1, 0, 1])
    low, high = bootstrap_ci(labels, labels, EvaluationConfig(n_bootstrap=200))
    assert (low, high) == (pytest.approx(1.0), pytest.approx(1.0))


def test_bootstrap_ci_contains_the_point_estimate() -> None:
    # 100 extraits, 70 justes : l'accuracy vaut 0,70 et doit tomber dans l'intervalle.
    y_true = np.zeros(100, dtype=np.int_)
    y_pred = np.concatenate([np.zeros(70, dtype=np.int_), np.ones(30, dtype=np.int_)])
    low, high = bootstrap_ci(y_true, y_pred, EvaluationConfig(n_bootstrap=500), metric=accuracy)
    assert low < 0.70 < high
    # Écart-type théorique ≈ sqrt(0,7 × 0,3 / 100) ≈ 0,046 : l'intervalle fait ≈ ±0,09.
    assert 0.12 < high - low < 0.25


def test_bootstrap_ci_is_reproducible_with_the_same_seed() -> None:
    y_true = np.array([0, 1, 0, 1, 1, 0, 1, 0])
    y_pred = np.array([0, 1, 1, 1, 0, 0, 1, 0])
    config = EvaluationConfig(n_bootstrap=100, seed=7)
    assert bootstrap_ci(y_true, y_pred, config) == bootstrap_ci(y_true, y_pred, config)


def test_bootstrap_ci_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError):
        bootstrap_ci(np.array([0, 1]), np.array([0]), EvaluationConfig())
