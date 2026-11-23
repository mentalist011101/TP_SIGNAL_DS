"""Tête de la famille B sur des données de synthèse (extra [ml], C11)."""

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from echolens.training import head_training  # noqa: E402
from echolens.training.evaluation import macro_f1  # noqa: E402
from echolens.training.head_training import (  # noqa: E402
    learned_layer_weights,
    predict_probabilities,
    run_esc50_round,
    train_for_epochs,
    train_with_validation,
)
from echolens.training.heads import (  # noqa: E402
    HeadsConfig,
    HeadSetting,
    LabeledSet,
    load_heads_config,
    predicted_classes,
)

pytestmark = pytest.mark.ml

LAYER_COUNT = 3
DIMENSION = 8
CLASS_COUNT = 3
SETTING = HeadSetting(learning_rate=1e-3, dropout=0.1)


def test_head_learns_separable_classes() -> None:
    config = _small_config()
    train = _separable_set(90, seed=0)
    validation = _separable_set(30, seed=1)
    result = train_with_validation(train, validation, SETTING, config, CLASS_COUNT, seed=42)
    probabilities = predict_probabilities(result.model, validation.features)
    assert result.best_f1 == pytest.approx(1.0)
    assert macro_f1(validation.targets, predicted_classes(probabilities)) == pytest.approx(1.0)
    assert 1 <= result.best_epoch <= config.max_epochs


@pytest.mark.parametrize(("patience", "expected_epochs"), [(None, 12), (3, 4)])
def test_patience_none_runs_the_whole_curve(
    patience: int | None, expected_epochs: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    # F1 de validation qui baisse à chaque époque : la meilleure époque est toujours la 1re.
    scores = iter([1.0 - 0.01 * epoch for epoch in range(100)])
    calls = []

    def fake_macro_f1(model: object, validation: LabeledSet) -> float:
        calls.append(1)
        return next(scores)

    monkeypatch.setattr(head_training, "_macro_f1_of", fake_macro_f1)
    config = _small_config().model_copy(update={"max_epochs": 12, "patience": patience})
    train = _separable_set(30, seed=0)
    result = train_with_validation(train, train, SETTING, config, CLASS_COUNT, seed=42)
    # Sans patience : les 12 époques ; avec 3 : arrêt à l'époque 1 + 3 = 4.
    assert len(calls) == expected_epochs
    assert result.best_epoch == 1


def test_layer_weights_sum_to_one() -> None:
    config = _small_config()
    model = train_for_epochs(_separable_set(60, seed=0), SETTING, config, CLASS_COUNT, 42, 5)
    weights = learned_layer_weights(model)
    assert weights.shape == (LAYER_COUNT,)
    assert float(weights.sum()) == pytest.approx(1.0, abs=1e-6)
    assert np.all(weights > 0)


def test_same_seed_gives_same_predictions() -> None:
    config = _small_config()
    train = _separable_set(60, seed=0)
    test = _separable_set(20, seed=1)
    first = train_for_epochs(train, SETTING, config, CLASS_COUNT, 42, 5)
    second = train_for_epochs(train, SETTING, config, CLASS_COUNT, 42, 5)
    first_probabilities = predict_probabilities(first, test.features)
    second_probabilities = predict_probabilities(second, test.features)
    np.testing.assert_array_equal(first_probabilities, second_probabilities)


def test_esc50_round_tunes_then_retrains_on_four_folds() -> None:
    config = _small_config().model_copy(update={"esc50_class_count": CLASS_COUNT})
    data = _separable_set(150, seed=0)
    folds = np.repeat(np.arange(1, 6), 30)
    run = run_esc50_round(data.features, data.targets, folds, test_fold=2, config=config)
    assert run.test_fold == 2
    assert len(run.outcomes) == 4
    # Validation du réglage = fold 3 ; une tête finale par graine, évaluée sur le fold 2.
    assert len(run.validation.targets) == 30
    assert len(run.heads) == len(config.seeds)
    assert run.heads[0].predictions.probabilities.shape == (30, CLASS_COUNT)
    np.testing.assert_array_equal(run.test_targets, data.targets[folds == 2])


def _small_config() -> HeadsConfig:
    return load_heads_config().model_copy(update={"batch_size": 16})


def _separable_set(count: int, seed: int) -> LabeledSet:
    # Chaque classe a un centre bien distinct dans la couche du milieu ; les autres couches
    # ne sont que du bruit. Les classes se séparent donc sans erreur.
    generator = np.random.default_rng(seed)
    targets = np.arange(count) % CLASS_COUNT
    features = generator.normal(0.0, 1.0, size=(count, LAYER_COUNT, DIMENSION))
    for index, target in enumerate(targets):
        features[index, 1, target] += 10.0
    return LabeledSet(features=features.astype(np.float32), targets=targets)
