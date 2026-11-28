import numpy as np
import pytest

from echolens.training.evaluation import EvaluationConfig, macro_f1
from echolens.training.ood_eval import (
    actor_bootstrap_ci,
    actor_positions,
    check_in_domain,
    draw_actor_samples,
    f1_drop,
    h2_verdict,
    intensity_scores,
    load_ood_config,
    paired_difference,
)

CONFIG = EvaluationConfig(n_bootstrap=200, confidence=0.95, seed=42)
ACTORS = ["a", "a", "b", "b", "c", "c", "d", "d"]


def test_actor_positions_groups_clips_by_actor():
    positions = actor_positions(ACTORS)
    assert list(positions) == ["a", "b", "c", "d"]
    assert positions["c"].tolist() == [4, 5]


def test_samples_take_whole_actors_and_are_reproducible():
    first = draw_actor_samples(ACTORS, CONFIG)
    second = draw_actor_samples(ACTORS, CONFIG)
    assert len(first) == 200
    for sample_a, sample_b in zip(first, second, strict=True):
        assert sample_a.tolist() == sample_b.tolist()
        # 4 acteurs tirés, 2 extraits chacun : 8 positions. Un acteur est pris en entier :
        # les positions 0 et 1 (acteur « a ») sont tirées le même nombre de fois, etc.
        assert len(sample_a) == 8
        counts = np.bincount(sample_a, minlength=8)
        assert counts[0::2].tolist() == counts[1::2].tolist()


def test_perfect_model_has_degenerate_interval_at_one():
    y_true = np.array([0, 1, 0, 1, 0, 1, 0, 1])
    samples = draw_actor_samples(ACTORS, CONFIG)
    low, high = actor_bootstrap_ci(y_true, y_true.copy(), samples, CONFIG)
    assert (low, high) == (1.0, 1.0)


def test_paired_difference_of_identical_models_is_zero():
    y_true = np.array([0, 1, 0, 1, 0, 1, 0, 1])
    y_pred = np.array([0, 1, 1, 1, 0, 0, 0, 1])
    samples = draw_actor_samples(ACTORS, CONFIG)
    observed, low, high = paired_difference(y_true, y_pred, y_pred, samples, CONFIG)
    assert (observed, low, high) == (0.0, 0.0, 0.0)


def test_paired_difference_positive_when_first_is_better():
    y_true = np.array([0, 1] * 4)
    good = y_true.copy()
    bad = 1 - y_true
    samples = draw_actor_samples(ACTORS, CONFIG)
    observed, low, high = paired_difference(y_true, good, bad, samples, CONFIG)
    assert observed == pytest.approx(macro_f1(y_true, good) - macro_f1(y_true, bad))
    assert low > 0.0 and high > 0.0


def test_h2_verdict_rule():
    assert h2_verdict(0.01, 0.05) == "confirmée"
    assert h2_verdict(-0.05, -0.01) == "infirmée"
    assert h2_verdict(-0.02, 0.03) == "non tranchée"
    assert h2_verdict(0.0, 0.03) == "non tranchée"


def test_intensity_scores_leave_neutral_out():
    # Classe 0 = neutre (seulement en « faible »), classes 1 et 2 jouées aux deux intensités.
    y_true = np.array([0, 0, 1, 2, 1, 2])
    y_pred = np.array([1, 2, 1, 2, 0, 0])
    intensities = ["faible", "faible", "faible", "faible", "forte", "forte"]
    scores = intensity_scores(y_true, y_pred, intensities, neutral_target=0)
    # Les neutres mal classés ne pèsent pas sur « faible » : ses 2 extraits émotionnels sont justes.
    assert scores["faible"] == 1.0
    # En « forte », les deux extraits sont prédits neutres : erreurs, sans classe neutre en plus.
    assert scores["forte"] == 0.0
    assert list(scores) == ["faible", "forte"]


def test_drop_and_in_domain_check():
    assert f1_drop(0.75, 0.40) == pytest.approx(0.35)
    assert check_in_domain(0.7602, 0.7535, 0.01)
    assert not check_in_domain(0.7400, 0.7535, 0.01)


def test_ood_config_matches_task():
    config = load_ood_config()
    assert [model.id for model in config.models] == [
        "cnn",
        "crnn",
        "wav2vec2-base",
        "mhubert-147",
        "whisper-base",
    ]
    assert config.h2.first == "mhubert-147"
    assert config.cafe_expected_clips == 792
    assert config.neutral_class == "neutral"
