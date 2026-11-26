from pathlib import Path

import numpy as np
import pytest

from echolens.core.audio.preprocess_config import VadConfig, load_preprocess_config
from echolens.core.data.manifest import ManifestRow
from echolens.training.vad_benchmark import (
    ClipDecisions,
    OptionScore,
    VadBenchmarkConfig,
    VadOption,
    benchmark_options,
    clip_decisions,
    false_positive_rate,
    load_clip_decisions,
    load_vad_benchmark_config,
    non_vocal_esc50_rows,
    option_flags,
    sample_rows,
    save_clip_decisions,
    select_option,
    silero_end_threshold,
    speech_recall,
    speech_seconds,
)

SAMPLE_RATE = 16_000
WEBRTC_OPTION = VadOption("webrtcvad 2", "webrtcvad", aggressiveness=2)
BAND_OPTION = VadOption(
    "webrtcvad 2 + bande ≥ 0.60", "webrtcvad_band", aggressiveness=2, band_threshold=0.6
)
SILERO_OPTION = VadOption("Silero ≥ 0.50", "silero", silero_threshold=0.5)
HYSTERESIS_OPTION = VadOption(
    "Silero ≥ 0.40, fin < 0.25", "silero", silero_threshold=0.4, silero_end_threshold=0.25
)
LOW_THRESHOLD_OPTION = VadOption("Silero ≥ 0.20", "silero", silero_threshold=0.2)


def config() -> VadBenchmarkConfig:
    return load_vad_benchmark_config()


def vad_config() -> VadConfig:
    return load_preprocess_config().vad


def make_clip(label: str, speech_frames: int, band_share: float) -> ClipDecisions:
    # 2,01 s en trames de 30 ms (67 trames) : les speech_frames premières sont « parole »
    # pour webrtcvad à tous les niveaux et pour Silero (tranches de 30 ms ici, pour simplifier).
    frame_count = 67
    flags = [index < speech_frames for index in range(frame_count)]
    probabilities = [0.9 if flag else 0.1 for flag in flags]
    return ClipDecisions(
        label=label,
        duration_s=frame_count * 0.03,
        webrtcvad_flags=[flags, flags, flags, flags],
        webrtcvad_frame_s=0.03,
        band_shares=[band_share] * frame_count,
        silero_probabilities=probabilities,
        silero_frame_s=0.03,
    )


def make_row(label: str, index: int) -> ManifestRow:
    return ManifestRow(dataset="esc50", path=f"audio/{index}.wav", label=label, duration_s=5.0)


def test_vocal_esc50_classes_are_removed() -> None:
    rows = [make_row("rain", 0), make_row("coughing", 1), make_row("dog", 2)]
    kept = non_vocal_esc50_rows(rows, config().excluded_esc50_classes)
    assert [row.label for row in kept] == ["rain", "dog"]


def test_sample_is_reproducible_and_without_duplicates() -> None:
    rows = [make_row("dog", index) for index in range(50)]
    first = sample_rows(rows, size=10, seed=42)
    second = sample_rows(rows, size=10, seed=42)
    paths = [row.path for row in first]
    assert paths == [row.path for row in second]
    assert len(set(paths)) == 10


def test_options_are_listed_from_simplest_to_heaviest() -> None:
    options = benchmark_options(config())
    thresholds = len(config().band_share_thresholds)
    silero_count = 2 * len(config().silero_thresholds)
    assert len(options) == 4 + 4 * thresholds + silero_count
    assert options[0].method == "webrtcvad"
    assert options[-1].method == "silero"


def test_band_check_removes_frames_with_too_little_band_energy() -> None:
    clip = make_clip("rain", speech_frames=67, band_share=0.4)
    webrtc_flags, _ = option_flags(clip, WEBRTC_OPTION, config())
    band_flags, _ = option_flags(clip, BAND_OPTION, config())
    assert all(webrtc_flags)
    assert not any(band_flags)


def test_speech_seconds_uses_the_d5_segment_cleaning() -> None:
    # 10 trames de parole (0,30 s) en début d'audio : marge de 100 ms ajoutée à la fin seulement.
    clip = make_clip("speech", speech_frames=10, band_share=0.9)
    seconds = speech_seconds(clip, WEBRTC_OPTION, vad_config(), config())
    assert seconds == pytest.approx(0.4)


def test_false_positive_rate_counts_clips_with_half_a_second_of_speech() -> None:
    clips = [
        make_clip("rain", speech_frames=67, band_share=0.4),
        make_clip("dog", speech_frames=0, band_share=0.4),
    ]
    assert false_positive_rate(clips, WEBRTC_OPTION, vad_config(), config()) == 0.5
    assert false_positive_rate(clips, BAND_OPTION, vad_config(), config()) == 0.0


def test_speech_recall_needs_half_the_duration() -> None:
    clips = [
        make_clip("speech", speech_frames=60, band_share=0.9),
        make_clip("speech", speech_frames=10, band_share=0.9),
    ]
    assert speech_recall(clips, SILERO_OPTION, vad_config(), config()) == 0.5


def test_best_recall_under_the_false_positive_limit_wins() -> None:
    # Chiffres de C24 : aucune option ne tient les deux critères (passes=False partout).
    scores = [
        OptionScore(WEBRTC_OPTION, 0.976, 0.905, passes=False),
        OptionScore(SILERO_OPTION, 0.034, 0.850, passes=False),
        OptionScore(HYSTERESIS_OPTION, 0.072, 0.910, passes=False),
        OptionScore(LOW_THRESHOLD_OPTION, 0.135, 0.935, passes=False),
    ]
    selected = select_option(scores, max_false_positive_rate=0.10)
    assert selected is not None
    assert selected.option == HYSTERESIS_OPTION


def test_equal_recall_prefers_fewer_false_positives() -> None:
    scores = [
        OptionScore(HYSTERESIS_OPTION, 0.08, 0.90, passes=False),
        OptionScore(SILERO_OPTION, 0.03, 0.90, passes=False),
    ]
    selected = select_option(scores, max_false_positive_rate=0.10)
    assert selected is not None
    assert selected.option == SILERO_OPTION


def test_no_option_selected_when_all_exceed_the_false_positive_limit() -> None:
    scores = [OptionScore(WEBRTC_OPTION, 0.4, 0.99, passes=False)]
    assert select_option(scores, max_false_positive_rate=0.10) is None


def test_clip_decisions_align_webrtcvad_and_band_frames() -> None:
    signal = np.zeros(SAMPLE_RATE, dtype=np.float32)
    decisions = clip_decisions(signal, "silence", vad_config(), config(), [0.0], 0.032)
    assert len(decisions.webrtcvad_flags) == 4
    assert len(decisions.webrtcvad_flags[2]) == len(decisions.band_shares) == 33


def test_decisions_survive_a_json_round_trip(tmp_path: Path) -> None:
    clips = [make_clip("rain", speech_frames=5, band_share=0.4)]
    path = tmp_path / "decisions.json"
    save_clip_decisions(clips, path)
    assert load_clip_decisions(path) == clips


def test_silero_end_threshold_never_goes_below_the_floor() -> None:
    assert silero_end_threshold(0.5, config()) == pytest.approx(0.35)
    assert silero_end_threshold(0.1, config()) == pytest.approx(0.01)
