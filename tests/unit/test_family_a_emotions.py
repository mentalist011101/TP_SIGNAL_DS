"""Famille A sur les émotions (C12) sans torch : log-Mel, parties, silence ajouté, scores."""

from pathlib import Path

import numpy as np
import pytest

from echolens.config import CONFIG_DIR
from echolens.core.data.emotions import load_emotion_labels
from echolens.core.data.manifest import ManifestRow
from echolens.core.data.splits import SpeakerSplit, load_split_config
from echolens.core.features import FeatureConfig
from echolens.training import family_a_emotions
from echolens.training.family_a import load_family_a_config
from echolens.training.family_a_emotions import (
    actor_spread,
    clip_predictions,
    compute_emotion_log_mels,
    load_emotion_log_mels,
    save_emotion_log_mels,
    seed_summary,
    seed_test_scores,
    silence_shares,
    split_indices,
)

SAMPLE_RATE = 16_000


def cremad_row(actor: str, emotion: str, gender: str, seconds: float) -> ManifestRow:
    return ManifestRow(
        dataset="cremad",
        path=f"AudioWAV/{actor}_IEO_{emotion}_HI.wav",
        label=emotion,
        speaker=actor,
        gender=gender,
        duration_s=seconds,
    )


@pytest.fixture
def emotion_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> family_a_emotions.EmotionLogMelSet:
    """4 extraits de CREMA-D : 2 acteurs en train, 1 en test, de 2 s et 4 s."""
    rows = [
        cremad_row("1001", "ANG", "M", 2.0),
        cremad_row("1001", "SAD", "M", 4.0),
        cremad_row("1002", "HAP", "F", 4.0),
        cremad_row("1003", "NEU", "F", 2.0),
    ]
    splits = [
        SpeakerSplit(dataset="cremad", speaker="1001", gender="M", split="train"),
        SpeakerSplit(dataset="cremad", speaker="1002", gender="F", split="train"),
        SpeakerSplit(dataset="cremad", speaker="1003", gender="F", split="test"),
    ]
    durations = {row.path: row.duration_s for row in rows}

    def fake_load_audio(path: Path) -> np.ndarray:
        seconds = durations[f"AudioWAV/{Path(path).name}"]
        times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
        return (0.3 * np.sin(2 * np.pi * 220 * times)).astype(np.float32)

    monkeypatch.setattr(family_a_emotions, "load_audio", fake_load_audio)
    feature_config = FeatureConfig.from_yaml(CONFIG_DIR / "features.yaml")
    return compute_emotion_log_mels(
        {"cremad": rows},
        tmp_path,
        load_emotion_labels(),
        splits,
        load_split_config(),
        feature_config,
    )


def test_config_has_the_3_s_window_and_100_epochs() -> None:
    emotions = load_family_a_config().emotions
    assert emotions is not None
    assert emotions.window_s == 3.0
    assert emotions.max_epochs == 100
    assert emotions.seeds == [42, 43, 44]


def test_log_mels_keep_true_lengths_and_pad_with_silence(
    emotion_set: family_a_emotions.EmotionLogMelSet,
) -> None:
    # 2 s → 201 trames, 4 s → 401 trames ; le tableau est à la longueur du plus long.
    np.testing.assert_array_equal(emotion_set.lengths, [201, 401, 401, 201])
    assert emotion_set.log_mels.shape == (4, 64, 401)
    assert np.all(emotion_set.log_mels[0, :, 201:] == -100.0)
    # Classes communes (P2) dans l'ordre de labels.yaml : angry = 3, sad = 2, happy = 1.
    np.testing.assert_array_equal(emotion_set.targets, [3, 2, 1, 0])
    np.testing.assert_array_equal(split_indices(emotion_set, "train"), [0, 1, 2])
    np.testing.assert_array_equal(split_indices(emotion_set, "test"), [3])


def test_silence_share_is_measured_per_dataset(
    emotion_set: family_a_emotions.EmotionLogMelSet,
) -> None:
    # Fenêtre de 301 trames : les extraits de 201 trames ont 100 / 301 de silence ajouté.
    shares = silence_shares(emotion_set, 301)
    assert shares["cremad"] == pytest.approx((100 / 301 + 0 + 0 + 100 / 301) / 4)


def test_log_mels_are_saved_and_reloaded(
    emotion_set: family_a_emotions.EmotionLogMelSet, tmp_path: Path
) -> None:
    path = tmp_path / "emotions.npz"
    save_emotion_log_mels(emotion_set, path)
    reloaded = load_emotion_log_mels(path)
    assert reloaded.speakers == emotion_set.speakers
    assert reloaded.splits == emotion_set.splits
    np.testing.assert_array_equal(reloaded.log_mels, emotion_set.log_mels)


def test_scores_by_dataset_gender_and_actor_then_over_seeds(
    emotion_set: family_a_emotions.EmotionLogMelSet,
) -> None:
    indices = np.array([0, 1, 2, 3])
    perfect = seed_test_scores(emotion_set, indices, emotion_set.targets, 6)
    wrong_on_one = seed_test_scores(emotion_set, indices, np.array([3, 2, 1, 1]), 6)
    assert perfect["macro_f1"] == pytest.approx(1.0)
    assert set(perfect["macro_f1_by_gender"]) == {"F", "M"}
    assert set(perfect["macro_f1_by_actor"]) == {"cremad:1001", "cremad:1002", "cremad:1003"}
    assert wrong_on_one["macro_f1_by_actor"]["cremad:1003"] == 0.0
    summary = seed_summary([perfect, wrong_on_one])
    assert summary["accuracy"]["mean"] == pytest.approx((1.0 + 0.75) / 2)
    assert summary["macro_f1_by_actor"]["cremad:1001"]["mean"] == pytest.approx(1.0)
    spread = actor_spread(emotion_set, indices, summary["macro_f1_by_actor"])
    assert spread["M"]["actors"] == 1
    assert spread["F"]["actors"] == 2
    assert spread["F"]["min"] == pytest.approx(0.5)


def test_clip_predictions_use_dataset_and_path(
    emotion_set: family_a_emotions.EmotionLogMelSet,
) -> None:
    predictions = clip_predictions(emotion_set, np.array([3]), np.array([4]))
    assert predictions[0].path == "cremad/AudioWAV/1003_IEO_NEU_HI.wav"
    assert predictions[0].target == 0
    assert predictions[0].prediction == 4
