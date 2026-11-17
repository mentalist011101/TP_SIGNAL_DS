import numpy as np
import pytest

from echolens.training.evaluation import (
    EvaluationConfig,
    accuracy,
    bootstrap_ci,
    expected_calibration_error,
    macro_f1,
    mcnemar_test,
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


def test_mcnemar_exact_matches_hand_computation() -> None:
    # 10 extraits : 4 où les deux ont raison, 1 où A seul a raison, 5 où B seul a raison.
    y_true = np.zeros(10, dtype=np.int_)
    pred_a = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    pred_b = np.array([0, 0, 0, 0, 1, 0, 0, 0, 0, 0])
    result = mcnemar_test(y_true, pred_a, pred_b, EvaluationConfig())

    assert (result.both_right, result.only_a_right, result.only_b_right) == (4, 1, 5)
    assert result.exact
    # 6 désaccords, P(X ≤ 1) = (1 + 6) / 64 = 7/64 ; bilatéral : 2 × 7/64 = 14/64.
    assert result.p_value == pytest.approx(14 / 64)


def test_mcnemar_chi2_matches_hand_computation() -> None:
    # 40 désaccords : A seul juste 30 fois, B seul juste 10 fois.
    y_true = np.zeros(40, dtype=np.int_)
    pred_a = np.array([0] * 30 + [1] * 10)
    pred_b = np.array([1] * 30 + [0] * 10)
    result = mcnemar_test(y_true, pred_a, pred_b, EvaluationConfig())

    assert not result.exact
    # (|30 − 10| − 1)² / 40 = 361 / 40 = 9,025 ; p = P(χ²₁ > 9,025) ≈ 0,0027.
    assert result.statistic == pytest.approx(9.025)
    assert result.p_value == pytest.approx(0.00266, abs=2e-4)


def test_mcnemar_is_symmetric_in_the_two_models() -> None:
    y_true = np.zeros(10, dtype=np.int_)
    pred_a = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1])
    pred_b = np.array([0, 0, 0, 0, 1, 0, 0, 0, 0, 0])
    config = EvaluationConfig()
    forward = mcnemar_test(y_true, pred_a, pred_b, config)
    backward = mcnemar_test(y_true, pred_b, pred_a, config)
    assert forward.p_value == pytest.approx(backward.p_value)


def test_mcnemar_identical_models_give_p_value_one() -> None:
    y_true = np.array([0, 1, 0, 1])
    pred = np.array([0, 1, 1, 1])
    result = mcnemar_test(y_true, pred, pred, EvaluationConfig())
    assert result.p_value == pytest.approx(1.0)


def test_mcnemar_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError):
        mcnemar_test(np.array([0, 1]), np.array([0, 1]), np.array([0]), EvaluationConfig())


def test_ece_matches_hand_computation() -> None:
    # 4 extraits, 3 classes, 2 intervalles : ]0 ; 0,5] et ]0,5 ; 1].
    probabilities = np.array(
        [
            [0.90, 0.05, 0.05],  # confiance 0,9, prédit 0, vrai 0 → juste
            [0.80, 0.10, 0.10],  # confiance 0,8, prédit 0, vrai 1 → faux
            [0.40, 0.35, 0.25],  # confiance 0,4, prédit 0, vrai 0 → juste
            [0.40, 0.30, 0.30],  # confiance 0,4, prédit 0, vrai 2 → faux
        ]
    )
    y_true = np.array([0, 1, 0, 2])
    result = expected_calibration_error(y_true, probabilities, EvaluationConfig(ece_bins=2))

    assert list(result.bin_counts) == [2, 2]
    # Intervalle bas : confiance 0,4, exactitude 0,5 → écart 0,1.
    # Intervalle haut : confiance 0,85, exactitude 0,5 → écart 0,35.
    np.testing.assert_allclose(result.bin_confidence, [0.40, 0.85])
    np.testing.assert_allclose(result.bin_accuracy, [0.5, 0.5])
    # ECE = 2/4 × 0,1 + 2/4 × 0,35 = 0,225.
    assert result.ece == pytest.approx(0.225)


def test_ece_of_confident_and_correct_model_is_zero() -> None:
    probabilities = np.eye(3)
    y_true = np.array([0, 1, 2])
    result = expected_calibration_error(y_true, probabilities, EvaluationConfig())
    assert result.ece == pytest.approx(0.0)


def test_ece_detects_overconfidence() -> None:
    # Le modèle affirme 99 % mais se trompe une fois sur deux : ECE proche de 0,49.
    probabilities = np.array([[0.99, 0.01]] * 4)
    y_true = np.array([0, 0, 1, 1])
    result = expected_calibration_error(y_true, probabilities, EvaluationConfig())
    assert result.ece == pytest.approx(0.49)


def test_ece_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError):
        expected_calibration_error(np.array([0, 1]), np.eye(3), EvaluationConfig())
