import numpy as np
import pytest

from echolens.training.evaluation import (
    accuracy,
    macro_f1,
    mean_and_std,
    normalized_confusion,
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
