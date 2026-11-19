"""Famille A sans torch : statistiques par bande, augmentations et log-Mel (R4, R6, P6)."""

from pathlib import Path

import numpy as np
import pytest

from echolens.config import CONFIG_DIR
from echolens.core.data.manifest import ManifestRow
from echolens.core.features import FeatureConfig
from echolens.training import family_a
from echolens.training.family_a import (
    MASK_VALUE,
    AugmentationConfig,
    BandStatistics,
    LogMelSet,
    augment_batch,
    band_statistics,
    circular_time_shift,
    compute_esc50_log_mels,
    fold_indices,
    load_family_a_config,
    load_log_mels,
    mixup,
    one_hot,
    random_gain,
    random_mask_range,
    save_log_mels,
    spec_augment,
    standardize,
)

BANDS = 16
FRAMES = 60
CLASSES = 4


def random_log_mels(clip_count: int, seed: int = 0) -> np.ndarray:
    """Faux log-Mel en dB absolus, autour de −40 dB."""
    generator = np.random.default_rng(seed)
    values = generator.normal(-40.0, 10.0, size=(clip_count, BANDS, FRAMES))
    return values.astype(np.float32)


def augmentation_config(mask_count: int = 2) -> AugmentationConfig:
    return AugmentationConfig(
        gain_db=6.0,
        frequency_mask_count=mask_count,
        frequency_mask_max_bands=4,
        time_mask_count=mask_count,
        time_mask_max_frames=10,
        mixup_alpha=0.2,
    )


def test_yaml_config_is_valid() -> None:
    config = load_family_a_config()
    assert config.network.channels == [32, 64, 128, 256]
    assert config.network.gru_hidden_size == 128
    assert config.augmentation.gain_db == 6.0
    assert config.augmentation.frequency_mask_max_bands == 8
    assert config.augmentation.time_mask_max_frames == 40
    assert config.training.learning_rates == [1e-3, 3e-4]
    assert config.training.final_seeds == [42, 43, 44]
    assert config.training.patience == 15
    assert config.training.max_epochs == 150


def test_band_statistics_match_hand_computation() -> None:
    # 2 extraits, 2 bandes, 3 trames.
    # Bande 0 : 1, 2, 3, 5, 6, 7 → moyenne 4, variance (9+4+1+1+4+9)/6 = 28/6.
    # Bande 1 : 10, 10, 10, 20, 20, 20 → moyenne 15, écart-type 5.
    log_mels = np.array(
        [
            [[1.0, 2.0, 3.0], [10.0, 10.0, 10.0]],
            [[5.0, 6.0, 7.0], [20.0, 20.0, 20.0]],
        ],
        dtype=np.float32,
    )
    statistics = band_statistics(log_mels)
    np.testing.assert_allclose(statistics.mean, [4.0, 15.0], rtol=1e-6)
    np.testing.assert_allclose(statistics.std, [np.sqrt(28.0 / 6.0), 5.0], rtol=1e-6)


def test_constant_band_is_refused() -> None:
    log_mels = random_log_mels(3)
    log_mels[:, 5, :] = -100.0
    with pytest.raises(ValueError, match="constante"):
        band_statistics(log_mels)


def test_standardized_train_has_zero_mean_and_unit_std_per_band() -> None:
    train = random_log_mels(20)
    statistics = band_statistics(train)
    standardized = standardize(train, statistics)
    np.testing.assert_allclose(standardized.mean(axis=(0, 2)), 0.0, atol=1e-4)
    np.testing.assert_allclose(standardized.std(axis=(0, 2)), 1.0, atol=1e-4)


def test_test_set_is_standardized_with_train_statistics_only() -> None:
    train = random_log_mels(10, seed=1)
    # Un « test » plus fort de 20 dB : avec les statistiques du train, sa moyenne reste haute.
    test = random_log_mels(10, seed=2) + 20.0
    statistics = band_statistics(train)
    standardized_test = standardize(test, statistics)
    assert standardized_test.mean() > 1.0
    expected_first_value = (test[0, 3, 7] - statistics.mean[3]) / statistics.std[3]
    assert standardized_test[0, 3, 7] == pytest.approx(expected_first_value, rel=1e-5)


def test_gain_adds_one_constant_per_clip_within_range() -> None:
    log_mels = random_log_mels(50)
    gained = random_gain(log_mels, 6.0, np.random.default_rng(0))
    added = gained - log_mels
    for clip in added:
        # Même constante sur toutes les bandes et toutes les trames de l'extrait.
        np.testing.assert_allclose(clip, clip[0, 0], atol=1e-4)
        assert -6.0 <= clip[0, 0] <= 6.0
    per_clip_gain = added[:, 0, 0]
    assert per_clip_gain.std() > 1.0


def test_rotation_keeps_every_value_of_each_clip() -> None:
    log_mels = random_log_mels(8)
    shifted = circular_time_shift(log_mels, np.random.default_rng(3))
    for original, rotated in zip(log_mels, shifted, strict=True):
        matching_shifts = []
        for shift in range(FRAMES):
            if np.array_equal(np.roll(original, shift, axis=1), rotated):
                matching_shifts.append(shift)
        assert len(matching_shifts) == 1


def test_mask_ranges_respect_maximum_width_and_bounds() -> None:
    generator = np.random.default_rng(0)
    widths = set()
    for _ in range(2000):
        start, stop = random_mask_range(64, 8, generator)
        assert 0 <= start <= stop <= 64
        widths.add(stop - start)
    assert widths == set(range(9))


def test_spec_augment_masks_are_zero_and_respect_widths() -> None:
    standardized = np.ones((200, BANDS, FRAMES), dtype=np.float32)
    config = augmentation_config(mask_count=1)
    masked = spec_augment(standardized, config, np.random.default_rng(0))
    # Toute case modifiée vaut 0 (moyenne du train, P6) ; les autres restent intactes.
    changed = masked != standardized
    assert np.all(masked[changed] == MASK_VALUE)
    for clip in masked:
        masked_bands = np.all(clip == 0.0, axis=1)
        masked_frames = np.all(clip == 0.0, axis=0)
        assert masked_bands.sum() <= config.frequency_mask_max_bands
        assert masked_frames.sum() <= config.time_mask_max_frames
    # L'entrée n'est pas modifiée.
    assert np.all(standardized == 1.0)


def test_spec_augment_masks_after_standardization_hit_the_train_mean() -> None:
    train = random_log_mels(30)
    statistics = band_statistics(train)
    standardized = standardize(train, statistics)
    masked = spec_augment(standardized, augmentation_config(), np.random.default_rng(1))
    # Une case masquée vaut 0 en échelle standardisée, soit la moyenne du train en dB.
    restored = masked * statistics.std.reshape(1, BANDS, 1) + statistics.mean.reshape(1, BANDS, 1)
    is_masked = masked == 0.0
    band_means = np.broadcast_to(statistics.mean.reshape(1, BANDS, 1), masked.shape)
    np.testing.assert_allclose(restored[is_masked], band_means[is_masked], rtol=1e-5)
    assert is_masked.sum() > 0


def test_one_hot_puts_a_single_one_per_row() -> None:
    targets = one_hot(np.array([2, 0, 3]), CLASSES)
    expected = np.array([[0, 0, 1, 0], [1, 0, 0, 0], [0, 0, 0, 1]], dtype=np.float32)
    np.testing.assert_array_equal(targets, expected)


def test_mixup_is_a_convex_combination_of_inputs_and_targets() -> None:
    inputs = random_log_mels(16)
    targets = one_hot(np.arange(16) % CLASSES, CLASSES)
    batch = mixup(inputs, targets, 0.2, np.random.default_rng(5))
    weight = batch.mix_weight
    partners = batch.partner_indices
    assert 0.0 <= weight <= 1.0
    assert sorted(partners.tolist()) == list(range(16))
    expected_inputs = weight * inputs + (1.0 - weight) * inputs[partners]
    expected_targets = weight * targets + (1.0 - weight) * targets[partners]
    np.testing.assert_allclose(batch.inputs, expected_inputs, rtol=1e-5)
    np.testing.assert_allclose(batch.targets, expected_targets, rtol=1e-6)
    np.testing.assert_allclose(batch.targets.sum(axis=1), 1.0, rtol=1e-6)


def test_same_seed_gives_same_augmentation() -> None:
    log_mels = random_log_mels(12)
    labels = np.arange(12) % CLASSES
    statistics = band_statistics(log_mels)
    config = augmentation_config()
    first = augment_batch(log_mels, labels, statistics, CLASSES, config, np.random.default_rng(7))
    second = augment_batch(log_mels, labels, statistics, CLASSES, config, np.random.default_rng(7))
    other = augment_batch(log_mels, labels, statistics, CLASSES, config, np.random.default_rng(8))
    np.testing.assert_array_equal(first.inputs, second.inputs)
    np.testing.assert_array_equal(first.targets, second.targets)
    assert not np.array_equal(first.inputs, other.inputs)


def test_augmented_batch_keeps_shapes_and_float32() -> None:
    log_mels = random_log_mels(5)
    labels = np.array([0, 1, 2, 3, 0])
    statistics = BandStatistics(
        mean=np.full(BANDS, -40.0, dtype=np.float32), std=np.full(BANDS, 10.0, dtype=np.float32)
    )
    config = augmentation_config()
    batch = augment_batch(log_mels, labels, statistics, CLASSES, config, np.random.default_rng(0))
    assert batch.inputs.shape == (5, BANDS, FRAMES)
    assert batch.inputs.dtype == np.float32
    assert batch.targets.shape == (5, CLASSES)
    assert batch.targets.dtype == np.float32


def test_fold_indices_keep_manifest_order() -> None:
    folds = np.array([1, 2, 3, 1, 5, 2])
    np.testing.assert_array_equal(fold_indices(folds, [2]), [1, 5])
    np.testing.assert_array_equal(fold_indices(folds, [1, 5]), [0, 3, 4])


def test_log_mels_are_saved_and_reloaded(tmp_path: Path) -> None:
    log_mel_set = LogMelSet(
        paths=["audio/1-1-A-0.wav", "audio/2-2-A-7.wav"],
        log_mels=random_log_mels(2),
        labels=np.array([0, 7]),
        folds=np.array([1, 2]),
    )
    path = tmp_path / "log_mels.npz"
    save_log_mels(log_mel_set, path)
    reloaded = load_log_mels(path)
    assert reloaded.paths == log_mel_set.paths
    np.testing.assert_array_equal(reloaded.log_mels, log_mel_set.log_mels)
    np.testing.assert_array_equal(reloaded.labels, [0, 7])
    np.testing.assert_array_equal(reloaded.folds, [1, 2])


def test_esc50_log_mels_have_64_bands_and_501_frames_for_5_seconds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded_paths = []

    def fake_load_audio(path: Path) -> np.ndarray:
        loaded_paths.append(path)
        times = np.arange(5 * 16_000) / 16_000
        return (0.3 * np.sin(2 * np.pi * 440 * times)).astype(np.float32)

    monkeypatch.setattr(family_a, "load_audio", fake_load_audio)
    rows = [
        ManifestRow(dataset="esc50", path="audio/1-100-A-3.wav", duration_s=5.0, fold=1),
        ManifestRow(dataset="esc50", path="audio/4-200-B-41.wav", duration_s=5.0, fold=4),
    ]
    config = FeatureConfig.from_yaml(CONFIG_DIR / "features.yaml")
    log_mel_set = compute_esc50_log_mels(rows, tmp_path, config)
    assert log_mel_set.log_mels.shape == (2, 64, 501)
    assert log_mel_set.log_mels.dtype == np.float32
    np.testing.assert_array_equal(log_mel_set.labels, [3, 41])
    np.testing.assert_array_equal(log_mel_set.folds, [1, 4])
    assert log_mel_set.paths == ["audio/1-100-A-3.wav", "audio/4-200-B-41.wav"]
    assert loaded_paths[0] == tmp_path / "esc50" / "audio" / "1-100-A-3.wav"


def test_missing_fold_is_refused(tmp_path: Path) -> None:
    rows = [ManifestRow(dataset="esc50", path="audio/1-100-A-3.wav", duration_s=5.0)]
    config = FeatureConfig.from_yaml(CONFIG_DIR / "features.yaml")
    with pytest.raises(ValueError, match="Fold manquant"):
        compute_esc50_log_mels(rows, tmp_path, config)
