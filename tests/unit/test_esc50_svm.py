from pathlib import Path

import numpy as np
import pytest

from echolens.config import CONFIG_DIR
from echolens.core.data.manifest import ManifestRow
from echolens.core.features import FeatureConfig
from echolens.training import esc50_svm
from echolens.training.esc50_svm import (
    SvmConfig,
    choose_c,
    cross_validate,
    esc50_target,
    extract_features,
    run_fold,
    summarize_mfcc,
    validation_fold,
)

N_FOLDS = 5
N_CLASSES = 5
POINTS_PER_CLASS_AND_FOLD = 8
N_DIMENSIONS = 6


@pytest.fixture
def svm_config() -> SvmConfig:
    return SvmConfig.from_yaml(CONFIG_DIR / "baseline_svm.yaml")


@pytest.fixture
def feature_config() -> FeatureConfig:
    return FeatureConfig.from_yaml(CONFIG_DIR / "features.yaml")


def separated_clouds() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """5 nuages de points bien séparés (un par classe), répartis sur 5 folds."""
    generator = np.random.default_rng(0)
    features = []
    targets = []
    folds = []
    for fold in range(1, N_FOLDS + 1):
        for target in range(N_CLASSES):
            center = np.zeros(N_DIMENSIONS)
            center[target] = 10.0
            noise = generator.normal(0.0, 1.0, size=(POINTS_PER_CLASS_AND_FOLD, N_DIMENSIONS))
            features.append(center + noise)
            targets.extend([target] * POINTS_PER_CLASS_AND_FOLD)
            folds.extend([fold] * POINTS_PER_CLASS_AND_FOLD)
    return np.concatenate(features), np.array(targets), np.array(folds)


def test_yaml_config_is_valid(svm_config: SvmConfig) -> None:
    assert svm_config.kernel == "rbf"
    assert svm_config.gamma == "scale"
    assert svm_config.c_grid == [1.0, 10.0, 100.0]
    assert svm_config.category_names[0] == "animaux"
    assert len(svm_config.category_names) == 5


def test_summarize_mfcc_gives_240_finite_values(feature_config: FeatureConfig) -> None:
    t = np.arange(5 * 16_000) / 16_000
    sine = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    summary = summarize_mfcc(sine, feature_config)
    assert summary.shape == (240,)
    assert np.all(np.isfinite(summary))


def test_target_is_read_from_filename() -> None:
    assert esc50_target("audio/1-100032-A-0.wav") == 0
    assert esc50_target("audio/5-9032-A-49.wav") == 49


def test_validation_fold_is_the_next_one() -> None:
    assert validation_fold(1) == 2
    assert validation_fold(4) == 5
    assert validation_fold(5) == 1


def test_choose_c_never_uses_the_test_fold(svm_config: SvmConfig) -> None:
    features, targets, folds = separated_clouds()
    # Des NaN dans le fold de test : le SVM lèverait une erreur s'il y touchait.
    features[folds == 5] = np.nan
    chosen_c = choose_c(features, targets, folds, test_fold=5, svm_config=svm_config)
    assert chosen_c in svm_config.c_grid


def test_choose_c_validates_on_fold_1_when_testing_fold_5(svm_config: SvmConfig) -> None:
    features, targets, folds = separated_clouds()
    # Des NaN dans le fold 1 : il doit être utilisé (validation de 5), donc l'erreur apparaît.
    features[folds == 1] = np.nan
    with pytest.raises(ValueError):
        choose_c(features, targets, folds, test_fold=5, svm_config=svm_config)


def test_scaler_learns_mean_of_training_folds_only(svm_config: SvmConfig) -> None:
    features, targets, folds = separated_clouds()
    # Fold de test très décalé : s'il entrait dans la moyenne, elle bougerait nettement.
    features[folds == 3] += 1000.0
    result = run_fold(features, targets, folds, test_fold=3, svm_config=svm_config)
    scaler = result.model.named_steps["scaler"]
    train_mean = features[folds != 3].mean(axis=0)
    np.testing.assert_allclose(scaler.mean_, train_mean)


def test_cross_validate_separates_clean_clouds(svm_config: SvmConfig) -> None:
    features, targets, folds = separated_clouds()
    result = cross_validate(features, targets, folds, svm_config)
    assert len(result.folds) == N_FOLDS
    assert result.macro_f1_mean > 0.9
    assert result.confusion_classes.shape == (N_CLASSES, N_CLASSES)
    np.testing.assert_allclose(result.confusion_classes.sum(axis=1), np.ones(N_CLASSES))
    # Les classes 0 à 4 sont toutes dans la catégorie 0 : sa ligne somme à 1.
    assert result.confusion_categories.shape == (5, 5)
    assert result.confusion_categories[0].sum() == pytest.approx(1.0)


def test_extract_features_writes_then_reads_cache(
    tmp_path: Path, feature_config: FeatureConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        ManifestRow(dataset="esc50", path="audio/1-100032-A-0.wav", duration_s=1.0, fold=1),
        ManifestRow(dataset="esc50", path="audio/2-100038-A-14.wav", duration_s=1.0, fold=2),
    ]
    loaded_paths = []

    def fake_load_audio(path: Path) -> np.ndarray:
        loaded_paths.append(path)
        t = np.arange(16_000) / 16_000
        return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    monkeypatch.setattr(esc50_svm, "load_audio", fake_load_audio)
    cache_path = tmp_path / "features.npz"

    features, targets, folds = extract_features(rows, tmp_path, feature_config, cache_path)
    assert features.shape == (2, 240)
    assert list(targets) == [0, 14]
    assert list(folds) == [1, 2]
    assert loaded_paths[0] == tmp_path / "esc50" / "audio" / "1-100032-A-0.wav"
    assert cache_path.exists()

    # Deuxième appel : relu depuis le cache, aucun audio rechargé.
    cached_features, _, _ = extract_features(rows, tmp_path, feature_config, cache_path)
    assert len(loaded_paths) == 2
    np.testing.assert_allclose(cached_features, features)
