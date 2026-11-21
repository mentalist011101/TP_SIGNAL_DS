"""Modèles de production (C13) : réglage médian, calibration hors fold, config.json."""

from pathlib import Path

import numpy as np
import pytest

from echolens.config import CONFIG_DIR
from echolens.core.models.network_config import NetworkConfig
from echolens.core.models.production_config import (
    Calibration,
    ProductionModelConfig,
    TrainingRecord,
    config_fingerprint,
    load_production_config,
    save_production_config,
)
from echolens.training.evaluation import EvaluationConfig
from echolens.training.production import (
    RoundPredictions,
    huggingface_readme,
    load_production_plan,
    median_value,
    out_of_fold_calibration,
    validation_calibration,
)

CLASS_COUNT = 8


@pytest.fixture
def config() -> EvaluationConfig:
    return EvaluationConfig.from_yaml(CONFIG_DIR / "evaluation.yaml")


def overconfident_round(true_temperature: float, seed: int, count: int = 4_000) -> RoundPredictions:
    """Prédictions d'un modèle trop sûr de lui : logits = T × vrais logits."""
    generator = np.random.default_rng(seed)
    true_logits = generator.normal(0.0, 2.0, size=(count, CLASS_COUNT))
    true_probabilities = np.exp(true_logits) / np.exp(true_logits).sum(axis=1, keepdims=True)
    labels = np.array([generator.choice(CLASS_COUNT, p=row) for row in true_probabilities])
    model_logits = true_logits * true_temperature
    probabilities = np.exp(model_logits) / np.exp(model_logits).sum(axis=1, keepdims=True)
    return RoundPredictions(y_true=labels, probabilities=probabilities)


def test_median_of_five_settings_is_a_real_setting() -> None:
    assert median_value([1e-3, 3e-4, 1e-3, 1e-3, 1e-3]) == 1e-3
    assert median_value([85, 75, 69, 75, 52]) == 75
    assert median_value([0.3, 0.3, 0.1, 0.3, 0.3]) == 0.3
    assert median_value([1.0, 3.0]) == 2.0


def test_out_of_fold_calibration_averages_round_temperatures(config: EvaluationConfig) -> None:
    rounds = [overconfident_round(2.0, seed) for seed in range(5)]
    outcome = out_of_fold_calibration(rounds, config)
    assert len(outcome.round_temperatures) == 5
    assert outcome.temperature == pytest.approx(np.mean(outcome.round_temperatures))
    assert outcome.temperature == pytest.approx(2.0, rel=0.05)
    assert outcome.ece_after < outcome.ece_before / 2


def test_validation_calibration_measures_ece_on_the_test(config: EvaluationConfig) -> None:
    validation = overconfident_round(1.5, seed=10)
    test = overconfident_round(1.5, seed=11)
    outcome = validation_calibration(validation, test, config)
    assert outcome.temperature == pytest.approx(1.5, rel=0.05)
    assert outcome.ece_after < outcome.ece_before
    assert outcome.round_temperatures == []


def test_features_fingerprint_ignores_comments_and_line_endings(tmp_path: Path) -> None:
    path = tmp_path / "features.yaml"
    path.write_bytes(b"n_mels: 64\nhop_length: 160\n")
    fingerprint = config_fingerprint(path)
    assert len(fingerprint) == 64
    # Fins de ligne Windows, commentaire et ordre différent : mêmes valeurs, même empreinte.
    path.write_bytes(b"# commentaire\r\nhop_length: 160\r\nn_mels: 64\r\n")
    assert config_fingerprint(path) == fingerprint
    # Un paramètre change : l'empreinte change.
    path.write_bytes(b"n_mels: 128\nhop_length: 160\n")
    assert config_fingerprint(path) != fingerprint


def test_production_config_is_saved_and_reloaded(tmp_path: Path) -> None:
    production = ProductionModelConfig(
        model_id="echolens-sound-event-crnn",
        task="sound_event",
        architecture="crnn",
        labels=["dog", "rooster"],
        standardization_mean=[-40.0, -41.0],
        standardization_std=[10.0, 11.0],
        calibration=Calibration(
            temperature=1.3, method="hors fold", ece_before=0.08, ece_after=0.03
        ),
        training=TrainingRecord(
            learning_rate=1e-3, dropout=0.3, epochs=129, seed=42, data="ESC-50", commit="abc"
        ),
        window_s=5.0,
        network=NetworkConfig(
            channels=[32, 64],
            kernel_size=3,
            padding=1,
            pool_size=2,
            dropout=0.3,
            gru_hidden_size=128,
        ),
        features_sha256="0" * 64,
        license="cc-by-nc-4.0",
    )
    path = save_production_config(production, tmp_path)
    assert path.name == "config.json"
    assert load_production_config(path) == production


def test_production_plan_lists_the_three_models() -> None:
    plan = load_production_plan()
    assert plan.seed == 42
    ids = [planned.id for planned in plan.models]
    assert ids == [
        "echolens-emotion-whisper-base",
        "echolens-sound-event-whisper-base",
        "echolens-sound-event-crnn",
    ]
    assert plan.model("echolens-sound-event-crnn").license == "cc-by-nc-3.0"
    with pytest.raises(KeyError):
        plan.model("inconnu")


def test_huggingface_readme_has_license_header_then_the_card() -> None:
    card = "# Fiche\n\nTexte.\n"
    readme = huggingface_readme(card, "cc-by-nc-3.0", "openai/whisper-base")
    lines = readme.splitlines()
    assert lines[0] == "---"
    assert "license: cc-by-nc-3.0" in lines
    assert "base_model: openai/whisper-base" in lines
    assert readme.endswith(card)
    crnn_readme = huggingface_readme("# Fiche\n", "cc-by-nc-3.0", None)
    assert "base_model" not in crnn_readme
