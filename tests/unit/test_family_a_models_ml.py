"""Réseaux et boucle de la famille A (extra [ml]) : formes, attention, petit entraînement."""

from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from echolens.core.models.family_a import (  # noqa: E402
    AttentionPooling,
    SpectrogramCnn,
    SpectrogramCrnn,
)
from echolens.training.evaluation import macro_f1  # noqa: E402
from echolens.training.family_a import (  # noqa: E402
    FamilyAConfig,
    LogMelSet,
    load_family_a_config,
)
from echolens.training.family_a_esc50 import run_esc50_round  # noqa: E402
from echolens.training.family_a_models import (  # noqa: E402
    LabeledSpectrograms,
    predict,
    predicted_classes,
    train_fixed_epochs,
    train_with_validation,
)

pytestmark = pytest.mark.ml

CPU = torch.device("cpu")
ESC50_CLASSES = 50
# Données de synthèse : 32 bandes × 64 trames, chaque classe forte dans sa propre zone de bandes.
SMALL_BANDS = 32
SMALL_FRAMES = 64
SMALL_CLASSES = 3
BANDS_PER_CLASS = 8


def tiny_config(max_epochs: int = 60, patience: int | None = 15) -> FamilyAConfig:
    """La configuration du dépôt, avec de tout petits réseaux pour aller vite sur CPU."""
    base = load_family_a_config()
    network = base.network.model_copy(update={"channels": [4, 8, 8, 16], "gru_hidden_size": 8})
    augmentation = base.augmentation.model_copy(
        update={"frequency_mask_max_bands": 4, "time_mask_max_frames": 8}
    )
    training = base.training.model_copy(
        update={
            "batch_size": 8,
            "max_epochs": max_epochs,
            "patience": patience,
            "learning_rates": [1e-2],
            "final_seeds": [42, 43],
            "prediction_batch_size": 16,
        }
    )
    return FamilyAConfig(network=network, augmentation=augmentation, training=training)


def separable_spectrograms(clips_per_class: int, seed: int) -> LabeledSpectrograms:
    """Bruit autour de −60 dB ; la classe c a ses bandes 8c à 8c + 7 à −20 dB."""
    generator = np.random.default_rng(seed)
    log_mels = []
    labels = []
    for label in range(SMALL_CLASSES):
        for _ in range(clips_per_class):
            clip = generator.normal(-60.0, 3.0, size=(SMALL_BANDS, SMALL_FRAMES))
            first_band = label * BANDS_PER_CLASS
            clip[first_band : first_band + BANDS_PER_CLASS, :] += 40.0
            log_mels.append(clip)
            labels.append(label)
    return LabeledSpectrograms(
        log_mels=np.array(log_mels, dtype=np.float32), labels=np.array(labels, dtype=np.int_)
    )


def test_cnn_output_shapes_and_block_4_output() -> None:
    config = load_family_a_config()
    network = SpectrogramCnn(ESC50_CLASSES, config.network)
    network.eval()
    output = network(torch.zeros(2, 64, 501))
    assert output.logits.shape == (2, ESC50_CLASSES)
    assert output.attention is None
    # 64 × 501 divisé 4 fois par 2 (arrondi en dessous) : 4 × 31, avec 256 canaux.
    assert network.last_block_output.shape == (2, 256, 4, 31)


def test_crnn_output_shapes_and_attention_weights_sum_to_one() -> None:
    config = load_family_a_config()
    network = SpectrogramCrnn(ESC50_CLASSES, config.network)
    network.eval()
    generator = torch.Generator().manual_seed(0)
    output = network(torch.randn(3, 64, 501, generator=generator))
    assert output.logits.shape == (3, ESC50_CLASSES)
    assert output.attention.shape == (3, 31)
    assert torch.all(output.attention >= 0)
    torch.testing.assert_close(output.attention.sum(dim=1), torch.ones(3))
    assert network.last_block_output.shape == (3, 256, 4, 31)


def test_attention_pooling_is_the_weighted_sum_of_steps() -> None:
    pooling = AttentionPooling(feature_size=4)
    generator = torch.Generator().manual_seed(1)
    sequence = torch.randn(2, 5, 4, generator=generator)
    pooled, weights = pooling(sequence)
    expected = torch.einsum("bt,btf->bf", weights, sequence)
    torch.testing.assert_close(pooled, expected)
    torch.testing.assert_close(weights.sum(dim=1), torch.ones(2))


@pytest.mark.parametrize("architecture", ["cnn", "crnn"])
def test_small_training_on_separable_data_reaches_f1_of_one(architecture: str) -> None:
    config = tiny_config()
    train = separable_spectrograms(clips_per_class=12, seed=0)
    validation = separable_spectrograms(clips_per_class=4, seed=1)
    stopped = train_with_validation(
        architecture, train, validation, SMALL_CLASSES, 1e-2, 42, config, CPU
    )
    assert stopped.best_validation_f1 == pytest.approx(1.0)
    assert len(stopped.validation_f1_history) == stopped.trained.epochs_run
    assert stopped.trained.epochs_run <= config.training.max_epochs
    trained = stopped.trained
    # Les poids rechargés sont ceux de la meilleure époque : F1 = 1 sur la validation.
    predictions = predict(trained.network, validation.log_mels, trained.statistics, config, CPU)
    y_pred = predicted_classes(predictions)
    assert macro_f1(validation.labels, y_pred) == pytest.approx(1.0)


def test_without_patience_tuning_runs_every_epoch_and_keeps_the_best() -> None:
    # Données faciles : F1 = 1 très tôt, une patience de 2 arrêterait bien avant 12 époques.
    config = tiny_config(max_epochs=12, patience=None)
    train = separable_spectrograms(clips_per_class=12, seed=0)
    validation = separable_spectrograms(clips_per_class=4, seed=1)
    stopped = train_with_validation("cnn", train, validation, SMALL_CLASSES, 1e-2, 42, config, CPU)
    assert stopped.trained.epochs_run == 12
    assert len(stopped.validation_f1_history) == 12
    assert stopped.best_validation_f1 == max(stopped.validation_f1_history)
    best_position = stopped.validation_f1_history.index(stopped.best_validation_f1)
    assert stopped.best_epoch == best_position + 1


def test_same_seed_gives_same_trained_network() -> None:
    config = tiny_config()
    train = separable_spectrograms(clips_per_class=4, seed=0)
    first = train_fixed_epochs("crnn", train, SMALL_CLASSES, 1e-2, 2, 7, config, CPU)
    second = train_fixed_epochs("crnn", train, SMALL_CLASSES, 1e-2, 2, 7, config, CPU)
    first_output = predict(first.network, train.log_mels, first.statistics, config, CPU)
    second_output = predict(second.network, train.log_mels, second.statistics, config, CPU)
    np.testing.assert_array_equal(first_output.probabilities, second_output.probabilities)
    np.testing.assert_array_equal(first_output.attention, second_output.attention)


def test_esc50_round_never_trains_on_the_test_fold(tmp_path: Path) -> None:
    config = tiny_config(max_epochs=3, patience=2)
    log_mels = []
    labels = []
    folds = []
    for fold in range(1, 6):
        clips = separable_spectrograms(clips_per_class=2, seed=fold)
        log_mels.append(clips.log_mels)
        labels.append(clips.labels)
        folds.append(np.full(len(clips.labels), fold))
    all_folds = np.concatenate(folds)
    log_mel_set = LogMelSet(
        paths=[f"audio/{index}.wav" for index in range(len(all_folds))],
        log_mels=np.concatenate(log_mels),
        labels=np.concatenate(labels),
        folds=all_folds,
    )
    result = run_esc50_round("crnn", log_mel_set, 5, 5, SMALL_CLASSES, config, CPU, tmp_path)
    assert result.validation_fold == 1
    assert set(all_folds[result.indices.test]) == {5}
    assert set(all_folds[result.indices.final_train]) == {1, 2, 3, 4}
    assert set(all_folds[result.indices.tuning_train]) == {2, 3, 4}
    assert [run.seed for run in result.runs] == [42, 43]
    assert result.runs[0].attention.shape == (6, 4)
    # Statistiques recalculées : 3 folds au réglage, 4 folds à l'entraînement final (R4).
    assert not np.allclose(result.tuning.statistics.mean, result.final_statistics.mean)
    checkpoint = torch.load(tmp_path / "crnn_fold5_seed43.pt", weights_only=True)
    assert checkpoint["epochs"] == result.tuning.chosen.best_epoch
    np.testing.assert_allclose(checkpoint["band_mean"].numpy(), result.final_statistics.mean)
