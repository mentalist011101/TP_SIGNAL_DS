"""Résultats de la famille A sans torch : choix du réglage, scores, prédictions réunies (P3, P8)."""

import json
from pathlib import Path

import numpy as np
import pytest

from echolens.training.evaluation import ClipPrediction, EvaluationConfig
from echolens.training.family_a import BandStatistics
from echolens.training.family_a_report import (
    RoundIndices,
    RoundResult,
    SeedRun,
    TuningOutcome,
    TuningTrial,
    choose_trial,
    compare_models,
    cross_validation_scores,
    pooled_scores,
    pooled_test_predictions,
    ranked_classes,
    round_details,
    run_for_seed,
    save_round_arrays,
    seed_scores,
)

CLASSES = 3


def trial(learning_rate: float, f1: float, epoch: int = 10) -> TuningTrial:
    return TuningTrial(
        learning_rate=learning_rate,
        best_epoch=epoch,
        best_validation_f1=f1,
        epochs_run=epoch + 15,
        validation_f1_history=[f1],
    )


def statistics() -> BandStatistics:
    return BandStatistics(mean=np.zeros(4, dtype=np.float32), std=np.ones(4, dtype=np.float32))


def seed_run(seed: int, f1: float, predictions: list[int], with_attention: bool) -> SeedRun:
    count = len(predictions)
    attention = None
    if with_attention:
        attention = np.full((count, 5), 0.2, dtype=np.float32)
    return SeedRun(
        seed=seed,
        macro_f1=f1,
        accuracy=f1 + 0.01,
        predictions=np.array(predictions),
        probabilities=np.full((count, CLASSES), 1.0 / CLASSES, dtype=np.float32),
        attention=attention,
    )


def round_result(
    test_fold: int, test_indices: list[int], f1_by_seed: dict[int, float]
) -> RoundResult:
    """Un faux tour : les extraits de test sont prédits correctement (classe = position % 3)."""
    labels = [index % CLASSES for index in test_indices]
    runs = []
    for seed, f1 in f1_by_seed.items():
        runs.append(seed_run(seed, f1, labels, with_attention=True))
    chosen = trial(3e-4, 0.6, epoch=42)
    tuning = TuningOutcome(
        trials=[trial(1e-3, 0.5), chosen],
        chosen=chosen,
        statistics=statistics(),
        validation_probabilities=np.full((2, CLASSES), 1.0 / CLASSES, dtype=np.float32),
        validation_attention=None,
    )
    indices = RoundIndices(
        tuning_train=np.array([100, 101]),
        validation=np.array([200, 201]),
        final_train=np.array([100, 101, 200, 201]),
        test=np.array(test_indices),
    )
    return RoundResult(
        test_fold=test_fold,
        validation_fold=test_fold % 5 + 1,
        indices=indices,
        tuning=tuning,
        validation_labels=np.array([0, 1]),
        test_labels=np.array(labels),
        final_statistics=statistics(),
        runs=runs,
    )


def test_choose_trial_takes_best_validation_f1_and_first_on_tie() -> None:
    assert choose_trial([trial(1e-3, 0.5), trial(3e-4, 0.7)]) == 1
    assert choose_trial([trial(1e-3, 0.7), trial(3e-4, 0.7)]) == 0


def test_cross_validation_scores_average_seeds_then_rounds() -> None:
    rounds = [
        round_result(1, [0, 1, 2], {42: 0.5, 43: 0.7}),
        round_result(2, [3, 4, 5], {42: 0.8, 43: 0.8}),
    ]
    scores = cross_validation_scores(rounds)
    # Tour 1 : (0,5 + 0,7) / 2 = 0,6 ; tour 2 : 0,8 → moyenne 0,7, écart-type (ddof 0) 0,1.
    assert scores["macro_f1_mean"] == pytest.approx(0.7)
    assert scores["macro_f1_std"] == pytest.approx(0.1)
    assert scores["accuracy_mean"] == pytest.approx(0.71)


def test_seed_scores_measure_spread_between_seeds() -> None:
    rounds = [
        round_result(1, [0, 1, 2], {42: 0.5, 43: 0.7}),
        round_result(2, [3, 4, 5], {42: 0.7, 43: 0.9}),
    ]
    scores = seed_scores(rounds, [42, 43])
    per_seed = scores["per_seed"]
    assert per_seed[0]["seed"] == 42
    assert per_seed[0]["macro_f1_mean"] == pytest.approx(0.6)
    assert per_seed[1]["macro_f1_mean"] == pytest.approx(0.8)
    assert scores["macro_f1_std_between_seeds"] == pytest.approx(0.1)


def test_run_for_unknown_seed_is_refused() -> None:
    with pytest.raises(ValueError, match="graine 7"):
        run_for_seed(round_result(1, [0], {42: 0.5}), 7)


def test_round_details_report_chosen_learning_rate_and_epochs() -> None:
    details = round_details(round_result(3, [0, 1], {42: 0.5}))
    assert details["test_fold"] == 3
    assert details["validation_fold"] == 4
    assert details["chosen_learning_rate"] == 3e-4
    assert details["chosen_epochs"] == 42
    assert len(details["tuning"]) == 2
    assert details["final_runs"] == [{"seed": 42, "macro_f1": 0.5, "accuracy": 0.51}]


def test_pooled_predictions_cover_each_test_clip_once_with_its_path() -> None:
    paths = [f"audio/clip{index}.wav" for index in range(6)]
    rounds = [
        round_result(1, [0, 2, 4], {42: 1.0}),
        round_result(2, [1, 3, 5], {42: 1.0}),
    ]
    predictions = pooled_test_predictions(rounds, paths, 42)
    assert sorted(item.path for item in predictions) == sorted(paths)
    first = predictions[0]
    assert first == ClipPrediction(path="audio/clip0.wav", fold=1, target=0, prediction=0)
    assert predictions[3].fold == 2


def test_pooled_scores_of_perfect_predictions() -> None:
    predictions = []
    for index in range(30):
        label = index % 20
        predictions.append(ClipPrediction(f"audio/{index}.wav", 1, label, label))
    class_names = [f"classe{index}" for index in range(20)]
    config = EvaluationConfig(n_bootstrap=50)
    scores = pooled_scores(predictions, class_names, ["a", "b"], config)
    assert scores["clip_count"] == 30
    assert scores["macro_f1_ci"] == [1.0, 1.0]
    assert scores["per_class_f1"][0] == {"class": "classe0", "f1": 1.0}
    np.testing.assert_allclose(scores["confusion_categories"], np.eye(2))
    assert len(scores["confusion_classes"]) == 20


def test_ranked_classes_go_from_best_to_worst() -> None:
    ranking = ranked_classes(np.array([0.2, 0.9, 0.2]), ["chien", "pluie", "chat"])
    names = [entry["class"] for entry in ranking]
    assert names == ["pluie", "chat", "chien"]


def test_round_arrays_are_saved_with_attention(tmp_path: Path) -> None:
    path = save_round_arrays(round_result(2, [0, 1, 2], {42: 1.0, 43: 1.0}), "crnn", tmp_path)
    assert path.name == "crnn_fold2.npz"
    with np.load(path) as content:
        names = set(content.files)
        assert {"test_indices", "validation_probabilities", "final_band_mean"} <= names
        assert {"seed42_predictions", "seed43_probabilities", "seed42_attention"} <= names
        assert "validation_attention" not in names
        np.testing.assert_array_equal(content["test_indices"], [0, 1, 2])
    details = json.loads((tmp_path / "crnn_fold2.json").read_text(encoding="utf-8"))
    assert details["chosen_epochs"] == 42


def test_compare_models_counts_disagreements() -> None:
    first = []
    second = []
    for index in range(40):
        target = index % 4
        # A se trompe sur les 10 premiers extraits, B seulement sur les 2 premiers.
        prediction_a = (target + 1) % 4 if index < 10 else target
        prediction_b = (target + 1) % 4 if index < 2 else target
        first.append(ClipPrediction(f"audio/{index}.wav", 1, target, prediction_a))
        second.append(ClipPrediction(f"audio/{index}.wav", 1, target, prediction_b))
    result = compare_models("cnn", first, "crnn", second, EvaluationConfig(n_bootstrap=50))
    assert result["model_a"] == "cnn"
    assert result["clip_count"] == 40
    assert result["both_wrong"] == 2
    assert result["only_b_right"] == 8
    assert result["only_a_right"] == 0
    assert result["exact"] is True
    assert result["macro_f1_b"] > result["macro_f1_a"]
