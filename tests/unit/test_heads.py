"""Calculs sans torch des têtes de la famille B (C11) : standardisation, réglage, agrégation."""

import numpy as np
import pytest
from pydantic import ValidationError

from echolens.core.data.emotions import load_emotion_labels
from echolens.core.data.manifest import ManifestRow
from echolens.core.data.splits import SpeakerSplit, load_split_config
from echolens.training.evaluation import EvaluationConfig
from echolens.training.heads import (
    EmotionPart,
    Esc50FoldPredictions,
    HeadsConfig,
    HeadSetting,
    LabeledSet,
    SeedPredictions,
    TuningOutcome,
    best_setting_index,
    check_classes,
    check_disjoint_speakers,
    emotion_examples,
    emotion_results,
    esc50_results,
    esc50_targets_and_folds,
    grid_settings,
    layer_weights_summary,
    load_heads_config,
    mcnemar_results,
    pooled_esc50_predictions,
    select_folds,
    standardization_stats,
    standardize,
    summary_of,
)

# Peu de tirages : on vérifie la forme de l'intervalle, pas sa précision.
FAST_EVALUATION = EvaluationConfig(n_bootstrap=20)
LAYER_WEIGHTS = np.array([0.5, 0.5], dtype=np.float32)


def test_standardization_matches_hand_computation() -> None:
    # 2 extraits, 1 couche, 2 dimensions : colonne 1 = (1, 3), colonne 2 = (10, 30).
    train = np.array([[[1.0, 10.0]], [[3.0, 30.0]]], dtype=np.float32)
    stats = standardization_stats(train)
    # Moyennes 2 et 20 ; écarts-types de population |3 − 2| = 1 et |30 − 20| = 10.
    np.testing.assert_allclose(stats.mean, [[2.0, 20.0]])
    np.testing.assert_allclose(stats.std, [[1.0, 10.0]])
    standardized = standardize(train, stats)
    np.testing.assert_allclose(standardized, [[[-1.0, -1.0]], [[1.0, 1.0]]])


def test_zero_std_is_replaced_by_one() -> None:
    # Colonne 2 constante (5) : écart-type nul → 1, et la colonne standardisée vaut 0.
    train = np.array([[[1.0, 5.0]], [[3.0, 5.0]]], dtype=np.float32)
    stats = standardization_stats(train)
    np.testing.assert_allclose(stats.std, [[1.0, 1.0]])
    standardized = standardize(train, stats)
    np.testing.assert_allclose(standardized[:, 0, 1], [0.0, 0.0])
    assert np.all(np.isfinite(standardized))


def test_other_data_uses_train_statistics() -> None:
    train = np.array([[[1.0]], [[3.0]]], dtype=np.float32)
    stats = standardization_stats(train)
    # Une validation à 5 est à 3 écarts-types de la moyenne du train, pas à 0 (R4).
    validation = np.array([[[5.0]]], dtype=np.float32)
    np.testing.assert_allclose(standardize(validation, stats), [[[3.0]]])


def test_best_setting_has_highest_validation_f1() -> None:
    outcomes = [
        TuningOutcome(HeadSetting(1e-3, 0.1), best_epoch=5, validation_f1=0.4),
        TuningOutcome(HeadSetting(1e-3, 0.3), best_epoch=8, validation_f1=0.6),
        TuningOutcome(HeadSetting(3e-4, 0.1), best_epoch=9, validation_f1=0.5),
    ]
    assert best_setting_index(outcomes) == 1


def test_tie_keeps_first_setting_of_grid() -> None:
    outcomes = [
        TuningOutcome(HeadSetting(1e-3, 0.1), best_epoch=5, validation_f1=0.6),
        TuningOutcome(HeadSetting(3e-4, 0.3), best_epoch=8, validation_f1=0.6),
    ]
    assert best_setting_index(outcomes) == 0


def test_real_config_gives_four_settings() -> None:
    config = load_heads_config()
    settings = grid_settings(config)
    assert len(settings) == 4
    assert settings[0] == HeadSetting(learning_rate=1e-3, dropout=0.1)
    assert config.statistics_seed in config.seeds


def test_config_refuses_statistics_seed_outside_seeds() -> None:
    content = load_heads_config().model_dump()
    content["statistics_seed"] = 7
    with pytest.raises(ValidationError, match="statistics_seed"):
        HeadsConfig.model_validate(content)


def test_config_refuses_unknown_mcnemar_model() -> None:
    content = load_heads_config().model_dump()
    content["mcnemar_pairs"] = [["wav2vec2-base", "inconnu"]]
    with pytest.raises(ValidationError, match="McNemar"):
        HeadsConfig.model_validate(content)


def test_esc50_targets_and_folds_come_from_manifest() -> None:
    rows = [_esc50_row("audio/1-100032-A-0.wav", 1), _esc50_row("audio/3-1234-B-49.wav", 3)]
    targets, folds = esc50_targets_and_folds(rows)
    assert targets.tolist() == [0, 49]
    assert folds.tolist() == [1, 3]


def test_select_folds_keeps_manifest_order() -> None:
    features = np.arange(4, dtype=np.float32).reshape(4, 1, 1)
    targets = np.array([0, 1, 2, 3])
    folds = np.array([1, 2, 1, 3])
    selected = select_folds(features, targets, folds, [1, 3])
    assert selected.targets.tolist() == [0, 2, 3]
    assert selected.features[:, 0, 0].tolist() == [0.0, 2.0, 3.0]


def test_emotion_examples_exclude_calm_and_follow_speaker_split() -> None:
    labels = load_emotion_labels()
    split_config = load_split_config()
    splits = [SpeakerSplit(dataset="ravdess", speaker="01", gender="M", split="test")]
    rows = [_ravdess_row("05"), _ravdess_row("02"), _ravdess_row("01")]
    examples = emotion_examples(rows, labels, splits, split_config)
    # Le calme (02) est exclu ; la colère (05) et le neutre (01) gardent leur ligne d'origine.
    assert [example.position for example in examples] == [0, 2]
    assert [example.target for example in examples] == [3, 0]
    assert {example.split for example in examples} == {"test"}


def test_shared_speaker_between_parts_is_refused() -> None:
    train = _emotion_part([0], ["cremad"], ["F"], [("cremad", "1001")])
    test = _emotion_part([0], ["cremad"], ["F"], [("cremad", "1001")])
    with pytest.raises(ValueError, match="Fuite"):
        check_disjoint_speakers({"train": train, "test": test})


def test_class_outside_six_emotions_is_refused() -> None:
    check_classes(np.array([0, 5]), class_count=6)
    with pytest.raises(ValueError, match="6"):
        check_classes(np.array([0, 6]), class_count=6)


def test_summary_uses_population_std() -> None:
    summary = summary_of([0.5, 0.7])
    assert summary["mean"] == pytest.approx(0.6)
    assert summary["std"] == pytest.approx(0.1)


def test_layer_weights_summary_averages_heads() -> None:
    first = np.array([0.2, 0.8], dtype=np.float32)
    second = np.array([0.4, 0.6], dtype=np.float32)
    summary = layer_weights_summary([first, second])
    assert summary["mean"] == pytest.approx([0.3, 0.7])
    assert summary["head_count"] == 2


def test_esc50_results_average_seeds_then_folds() -> None:
    config = load_heads_config()
    # Tour 1 : juste pour les 3 graines. Tour 2 : seule la graine 43 a juste.
    fold_one = _fold(1, [0, 1], {42: [0, 1], 43: [0, 1], 44: [0, 1]})
    fold_two = _fold(2, [2, 3], {42: [3, 2], 43: [2, 3], 44: [3, 2]})
    results = esc50_results([fold_two, fold_one], config, 5, FAST_EVALUATION)
    # Par tour, moyenne des graines : 1 puis 1/3. Écart-type sur les tours, ddof = 0.
    assert results["macro_f1"]["values"] == pytest.approx([1.0, 1 / 3])
    assert results["macro_f1"]["std"] == pytest.approx(1 / 3)
    # Par graine, moyenne des tours : 0,5 ; 1 ; 0,5.
    assert results["macro_f1_by_seed"]["values"] == pytest.approx([0.5, 1.0, 0.5])
    assert results["per_fold"][0]["test_fold"] == 1
    assert len(results["f1_per_class"]) == config.esc50_class_count


def test_pooled_predictions_follow_fold_order() -> None:
    fold_one = _fold(1, [0, 1], {42: [0, 1], 43: [0, 1], 44: [0, 1]})
    fold_two = _fold(2, [2, 3], {42: [3, 2], 43: [2, 3], 44: [3, 2]})
    y_true, y_pred = pooled_esc50_predictions([fold_two, fold_one], seed=42)
    assert y_true.tolist() == [0, 1, 2, 3]
    assert y_pred.tolist() == [0, 1, 3, 2]


def test_emotion_results_by_dataset_and_gender() -> None:
    config = load_heads_config()
    test = _emotion_part(
        [0, 1, 0, 1],
        ["cremad", "cremad", "ravdess", "ravdess"],
        ["F", "M", "F", "M"],
        [("cremad", "1"), ("cremad", "2"), ("ravdess", "01"), ("ravdess", "02")],
    )
    # Juste sur CREMA-D, faux sur RAVDESS, pour les 3 graines.
    runs = [_seed_run(seed, [0, 1, 1, 0], class_count=2) for seed in config.seeds]
    results = emotion_results(test, runs, 2, config, FAST_EVALUATION)
    assert results["macro_f1_by_dataset"]["cremad"]["mean"] == pytest.approx(1.0)
    assert results["macro_f1_by_dataset"]["ravdess"]["mean"] == pytest.approx(0.0)
    assert set(results["macro_f1_by_gender"]) == {"F", "M"}
    assert results["accuracy"]["mean"] == pytest.approx(0.5)


def test_mcnemar_results_name_each_pair() -> None:
    y_true = np.array([0, 1, 0, 1])
    predictions = {"a": np.array([0, 1, 0, 1]), "b": np.array([1, 1, 0, 1])}
    results = mcnemar_results(y_true, predictions, [("a", "b")], FAST_EVALUATION)
    assert results[0]["model_a"] == "a"
    assert results[0]["only_a_right"] == 1
    assert results[0]["only_b_right"] == 0


def _esc50_row(path: str, fold: int) -> ManifestRow:
    return ManifestRow(dataset="esc50", path=path, label="x", duration_s=5.0, fold=fold)


def _ravdess_row(label: str) -> ManifestRow:
    path = f"Actor_01/03-01-{label}-01-01-01-01.wav"
    return ManifestRow(
        dataset="ravdess", path=path, label=label, speaker="01", gender="M", duration_s=3.0
    )


def _emotion_part(
    targets: list[int], datasets: list[str], genders: list[str], speakers: list[tuple[str, str]]
) -> EmotionPart:
    features = np.zeros((len(targets), 1, 1), dtype=np.float32)
    data = LabeledSet(features=features, targets=np.array(targets))
    return EmotionPart(data=data, datasets=datasets, genders=genders, speakers=speakers)


def _seed_run(seed: int, predicted: list[int], class_count: int) -> SeedPredictions:
    # Probabilité 1 sur la classe prédite : argmax redonne exactement predicted.
    probabilities = np.eye(class_count, dtype=np.float32)[predicted]
    return SeedPredictions(seed=seed, probabilities=probabilities, layer_weights=LAYER_WEIGHTS)


def _fold(
    test_fold: int, y_true: list[int], predicted: dict[int, list[int]]
) -> Esc50FoldPredictions:
    runs = [_seed_run(seed, labels, class_count=50) for seed, labels in predicted.items()]
    return Esc50FoldPredictions(
        test_fold=test_fold,
        setting=HeadSetting(1e-3, 0.1),
        epochs=10,
        y_true=np.array(y_true),
        runs=runs,
    )
