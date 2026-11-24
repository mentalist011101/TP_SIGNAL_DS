"""Fenêtres de longueur fixe dans un log-Mel (C12) : découpe et complément par du silence."""

import numpy as np
import pytest

from echolens.config import CONFIG_DIR
from echolens.core.features import FeatureConfig
from echolens.core.frame_windows import (
    center_windows,
    centered_start,
    frame_window,
    random_start,
    random_windows,
    silence_share,
    window_frame_count,
)

BANDS = 4
WINDOW = 301
SILENCE = -100.0


@pytest.fixture
def feature_config() -> FeatureConfig:
    return FeatureConfig.from_yaml(CONFIG_DIR / "features.yaml")


def ramp(frames: int) -> np.ndarray:
    """Log-Mel de synthèse : la trame t vaut t, sur toutes les bandes (facile à vérifier)."""
    values = np.tile(np.arange(frames, dtype=np.float32), (BANDS, 1))
    return values


def test_3_s_give_301_frames_and_5_s_give_501(feature_config: FeatureConfig) -> None:
    assert window_frame_count(3.0, feature_config) == 301
    assert window_frame_count(5.0, feature_config) == 501


def test_center_window_of_a_longer_clip(feature_config: FeatureConfig) -> None:
    # 401 trames, fenêtre de 301 : 100 trames en trop, 50 de chaque côté.
    log_mel = ramp(401)
    start = centered_start(401, WINDOW)
    assert start == 50
    window = frame_window(log_mel, 401, start, WINDOW, SILENCE)
    assert window.shape == (BANDS, WINDOW)
    assert window[0, 0] == 50
    assert window[0, -1] == 350


def test_short_clip_is_completed_with_silence_at_the_end() -> None:
    # 200 vraies trames, stockées dans un tableau plus long déjà rempli de silence.
    stored = np.full((BANDS, 500), SILENCE, dtype=np.float32)
    stored[:, :200] = ramp(200)
    window = frame_window(stored, 200, centered_start(200, WINDOW), WINDOW, SILENCE)
    assert window.shape == (BANDS, WINDOW)
    np.testing.assert_array_equal(window[:, :200], ramp(200))
    assert np.all(window[:, 200:] == SILENCE)
    assert silence_share(200, WINDOW) == pytest.approx(101 / 301)
    assert silence_share(450, WINDOW) == 0.0


def test_random_start_stays_inside_the_clip_and_covers_every_position() -> None:
    generator = np.random.default_rng(0)
    starts = {random_start(310, WINDOW, generator) for _ in range(2000)}
    assert starts == set(range(10))
    assert random_start(250, WINDOW, generator) == 0


def test_random_windows_are_reproducible_with_the_seed() -> None:
    lengths = np.array([350, 290, 500, 301])
    log_mels = np.full((4, BANDS, 500), SILENCE, dtype=np.float32)
    for index, length in enumerate(lengths):
        log_mels[index, :, :length] = ramp(int(length))
    first = random_windows(log_mels, lengths, WINDOW, SILENCE, np.random.default_rng(7))
    second = random_windows(log_mels, lengths, WINDOW, SILENCE, np.random.default_rng(7))
    other = random_windows(log_mels, lengths, WINDOW, SILENCE, np.random.default_rng(8))
    np.testing.assert_array_equal(first, second)
    assert not np.array_equal(first, other)
    assert first.shape == (4, BANDS, WINDOW)


def test_windows_always_have_301_frames() -> None:
    generator = np.random.default_rng(1)
    for length in [1, 150, 300, 301, 302, 480]:
        log_mels = np.full((1, BANDS, 480), SILENCE, dtype=np.float32)
        log_mels[0, :, :length] = ramp(length)
        lengths = np.array([length])
        assert random_windows(log_mels, lengths, WINDOW, SILENCE, generator).shape[2] == WINDOW
        assert center_windows(log_mels, lengths, WINDOW, SILENCE).shape[2] == WINDOW
