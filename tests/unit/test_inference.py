"""Découpage pour l'inférence et résultat global (Brique 6, D5), sans modèle."""

import numpy as np
import pytest

from echolens.core.audio.segment import Segment
from echolens.core.data.class_labels import ClassLabel
from echolens.core.inference import (
    InferenceConfig,
    duration_weighted_mean,
    emotion_windows,
    load_inference_config,
    mean_probabilities,
    ranked_probabilities,
    segment_samples,
    sound_event_windows,
    split_long_segment,
)

SAMPLE_RATE = 16_000


@pytest.fixture
def config() -> InferenceConfig:
    return load_inference_config()


def bounds(segments: list[Segment]) -> list[tuple[float, float]]:
    return [(round(segment.start_s, 6), round(segment.end_s, 6)) for segment in segments]


def test_config_gives_5_s_windows_with_50_percent_overlap(config: InferenceConfig) -> None:
    assert config.sound_event.window_s == 5.0
    assert config.sound_event.hop_s == 2.5
    assert config.emotion.max_window_s == 5.0


def test_short_audio_gives_a_single_window(config: InferenceConfig) -> None:
    # 3 s < 5 s : une seule fenêtre, complétée par du silence au moment de couper le signal.
    assert bounds(sound_event_windows(3.0, config)) == [(0.0, 3.0)]


def test_exactly_5_s_gives_a_single_window(config: InferenceConfig) -> None:
    assert bounds(sound_event_windows(5.0, config)) == [(0.0, 5.0)]


def test_12_s_gives_four_windows_the_last_one_aligned_on_the_end(config: InferenceConfig) -> None:
    # 0-5, 2,5-7,5, 5-10 ; la fenêtre 7,5-12,5 dépasserait : la dernière est calée sur 12 s.
    windows = sound_event_windows(12.0, config)
    assert bounds(windows) == [(0.0, 5.0), (2.5, 7.5), (5.0, 10.0), (7.0, 12.0)]
    for window in windows:
        assert window.duration_s == pytest.approx(5.0)


def test_long_speech_segment_is_cut_in_equal_pieces_of_5_s_at_most() -> None:
    # 12 s → 3 morceaux de 4 s (et non 5, 5 et 2 s).
    pieces = split_long_segment(Segment(start_s=1.0, end_s=13.0), 5.0)
    assert bounds(pieces) == [(1.0, 5.0), (5.0, 9.0), (9.0, 13.0)]


def test_segment_of_5_s_or_less_is_kept_whole() -> None:
    assert bounds(split_long_segment(Segment(start_s=2.0, end_s=7.0), 5.0)) == [(2.0, 7.0)]
    assert bounds(split_long_segment(Segment(start_s=0.0, end_s=0.4), 5.0)) == [(0.0, 0.4)]


def test_10_1_s_gives_three_equal_pieces_without_a_tiny_remainder() -> None:
    # « 5 s, 5 s, puis 0,1 s » laisserait un morceau trop court : on fait 3 morceaux de 3,367 s.
    pieces = split_long_segment(Segment(start_s=0.0, end_s=10.1), 5.0)
    assert len(pieces) == 3
    for piece in pieces:
        assert piece.duration_s == pytest.approx(10.1 / 3)
    assert pieces[-1].end_s == 10.1


def test_emotion_windows_split_each_speech_segment(config: InferenceConfig) -> None:
    speech = [Segment(start_s=0.5, end_s=2.0), Segment(start_s=3.0, end_s=14.0)]
    windows = emotion_windows(speech, config)
    # 1,5 s gardé entier ; 11 s → 3 morceaux de 3,667 s.
    assert len(windows) == 4
    assert bounds(windows)[0] == (0.5, 2.0)
    assert windows[-1].end_s == 14.0
    total = sum(window.duration_s for window in windows)
    assert total == pytest.approx(1.5 + 11.0)


def test_no_speech_gives_no_emotion_window(config: InferenceConfig) -> None:
    assert emotion_windows([], config) == []


def test_segment_samples_takes_the_right_samples() -> None:
    signal = np.arange(3 * SAMPLE_RATE, dtype=np.float32)
    samples = segment_samples(signal, Segment(start_s=1.0, end_s=1.5))
    assert len(samples) == 8_000
    assert samples[0] == 16_000
    assert samples.dtype == np.float32


def test_mean_of_windows_is_computed_by_hand() -> None:
    first = np.array([0.6, 0.4])
    second = np.array([0.2, 0.8])
    np.testing.assert_allclose(mean_probabilities([first, second]), [0.4, 0.6])


def test_duration_weighted_mean_is_computed_by_hand() -> None:
    # Morceau de 4 s : (0,8 ; 0,2) ; morceau de 1 s : (0,0 ; 1,0).
    # Global = (4 × 0,8 + 1 × 0,0) / 5 = 0,64 et (4 × 0,2 + 1 × 1,0) / 5 = 0,36.
    long_piece = np.array([0.8, 0.2])
    short_piece = np.array([0.0, 1.0])
    overall = duration_weighted_mean([long_piece, short_piece], [4.0, 1.0])
    np.testing.assert_allclose(overall, [0.64, 0.36])


def test_global_probabilities_still_sum_to_one() -> None:
    generator = np.random.default_rng(0)
    windows = []
    for _ in range(7):
        scores = generator.random(50)
        windows.append(scores / scores.sum())
    durations = list(generator.uniform(0.2, 5.0, size=7))
    assert mean_probabilities(windows).sum() == pytest.approx(1.0)
    assert duration_weighted_mean(windows, durations).sum() == pytest.approx(1.0)


def test_ranking_goes_from_most_to_least_probable_with_french_labels() -> None:
    classes = [
        ClassLabel(id="neutral", label_fr="Neutre"),
        ClassLabel(id="happy", label_fr="Joie"),
        ClassLabel(id="sad", label_fr="Tristesse"),
    ]
    ranking = ranked_probabilities(np.array([0.2, 0.5, 0.3]), classes)
    assert [entry.label for entry in ranking] == ["happy", "sad", "neutral"]
    assert ranking[0].label_fr == "Joie"
    assert ranking[0].probability == pytest.approx(0.5)


def test_ranking_refuses_a_wrong_number_of_classes() -> None:
    classes = [ClassLabel(id="neutral", label_fr="Neutre")]
    with pytest.raises(ValueError, match="ne concordent pas"):
        ranked_probabilities(np.array([0.5, 0.5]), classes)
