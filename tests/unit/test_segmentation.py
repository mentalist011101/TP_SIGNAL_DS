import numpy as np
import pytest
from pydantic import ValidationError

from echolens.core.audio.preprocess_config import VadConfig, load_preprocess_config
from echolens.core.audio.segment import (
    Segment,
    cut_window,
    detect_speech,
    flags_to_segments,
    sliding_windows,
    speech_flags,
)

SAMPLE_RATE = 16_000
# Trames de 10 ms dans les tests de flags_to_segments : 1 trame = 0,01 s.
FRAME_S = 0.01
# Retard toléré de webrtcvad en fin de voix (80 ms mesurés, voir le test de la voix).
WEBRTCVAD_END_DELAY_S = 0.1


def vad_config() -> VadConfig:
    return load_preprocess_config().vad


def vad_config_without_padding() -> VadConfig:
    return vad_config().model_copy(update={"padding_ms": 0})


def make_flags(*runs: tuple[bool, int]) -> list[bool]:
    # (True, 50) = 50 trames de parole, (False, 20) = 20 trames de silence.
    flags: list[bool] = []
    for is_speech, frame_count in runs:
        flags.extend([is_speech] * frame_count)
    return flags


def voice_like(duration_s: float) -> np.ndarray:
    # Voix de synthèse : fondamentale de 150 Hz et ses harmoniques (amplitude 1/k),
    # modulée en amplitude à 4 Hz, le rythme des syllabes.
    t = np.arange(int(duration_s * SAMPLE_RATE)) / SAMPLE_RATE
    tone = np.zeros_like(t)
    for harmonic in range(1, 11):
        tone += np.sin(2 * np.pi * 150 * harmonic * t) / harmonic
    envelope = 0.5 * (1 - np.cos(2 * np.pi * 4 * t))
    voice = tone * envelope
    return (0.3 * voice / np.max(np.abs(voice))).astype(np.float32)


def test_gap_of_200_ms_is_merged() -> None:
    flags = make_flags((False, 100), (True, 50), (False, 20), (True, 50), (False, 100))
    segments = flags_to_segments(flags, FRAME_S, vad_config_without_padding(), 3.2)
    assert len(segments) == 1
    assert segments[0].start_s == pytest.approx(1.0)
    assert segments[0].end_s == pytest.approx(2.2)


def test_gap_of_400_ms_is_not_merged() -> None:
    flags = make_flags((False, 100), (True, 50), (False, 40), (True, 50), (False, 100))
    segments = flags_to_segments(flags, FRAME_S, vad_config_without_padding(), 3.4)
    assert len(segments) == 2
    assert segments[0].end_s == pytest.approx(1.5)
    assert segments[1].start_s == pytest.approx(1.9)


def test_segment_of_60_ms_is_dropped() -> None:
    flags = make_flags((False, 100), (True, 6), (False, 100))
    assert flags_to_segments(flags, FRAME_S, vad_config_without_padding(), 2.06) == []


def test_padding_is_clipped_at_start_and_end_of_audio() -> None:
    # Parole dès la première trame et jusqu'à la dernière : la marge de 100 ms ne doit
    # sortir de l'audio ni avant 0 ni après 2 s.
    flags = make_flags((True, 50), (False, 100), (True, 50))
    segments = flags_to_segments(flags, FRAME_S, vad_config(), 2.0)
    assert len(segments) == 2
    assert segments[0].start_s == 0.0
    assert segments[0].end_s == pytest.approx(0.6)
    assert segments[1].start_s == pytest.approx(1.4)
    assert segments[1].end_s == 2.0


def test_padding_wider_than_half_the_merge_gap_is_refused() -> None:
    # 2 × 200 ms > 300 ms : les marges de deux segments voisins se chevaucheraient.
    with pytest.raises(ValidationError, match="chevaucheraient"):
        VadConfig(
            aggressiveness=2, frame_ms=30, merge_gap_ms=300, min_segment_ms=100, padding_ms=200
        )


def test_last_incomplete_frame_is_ignored() -> None:
    # 1 s + 10 ms d'audio en trames de 30 ms : 33 trames entières, le reste est ignoré.
    signal = np.zeros(SAMPLE_RATE + 160, dtype=np.float32)
    assert len(speech_flags(signal, vad_config())) == 33


def test_detect_speech_finds_nothing_in_silence() -> None:
    assert detect_speech(np.zeros(3 * SAMPLE_RATE, dtype=np.float32), vad_config()) == []


def test_detect_speech_finds_voice_like_signal_between_silences() -> None:
    # 1 s de silence, 1,5 s de voix de synthèse (de 1,0 à 2,5 s), 1 s de silence.
    silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
    signal = np.concatenate([silence, voice_like(1.5), silence])
    config = vad_config()
    segments = detect_speech(signal, config)
    # Tolérance tirée de la configuration : la marge ajoutée de chaque côté, plus une trame
    # (la décision de webrtcvad tombe sur une grille de frame_ms).
    tolerance_s = (config.padding_ms + config.frame_ms) / 1000
    assert len(segments) >= 1
    assert segments[0].start_s == pytest.approx(1.0, abs=tolerance_s)
    # En fin de voix, webrtcvad continue de répondre « parole » quelques trames après la fin.
    # Mesure observée : dernière trame de parole à 2,58 s pour une voix qui finit à 2,5 s,
    # soit 80 ms de retard, et fin détectée à 2,68 s une fois la marge de 100 ms ajoutée.
    # On tolère 100 ms de retard.
    end_tolerance_s = tolerance_s + WEBRTCVAD_END_DELAY_S
    assert segments[-1].end_s == pytest.approx(2.5, abs=end_tolerance_s)


def test_sliding_windows_stream_profile() -> None:
    # Profil flux (D8) : fenêtre de 2 s, décalage de 0,5 s, sur 3 s d'audio.
    windows = sliding_windows(3.0, window_s=2.0, hop_s=0.5)
    assert windows == [
        Segment(start_s=0.0, end_s=2.0),
        Segment(start_s=0.5, end_s=2.5),
        Segment(start_s=1.0, end_s=3.0),
    ]


def test_sliding_windows_event_profile() -> None:
    # Événements : fenêtres de 5 s avec 50 % de recouvrement.
    windows = sliding_windows(10.0, window_s=5.0, hop_s=2.5)
    assert windows == [
        Segment(start_s=0.0, end_s=5.0),
        Segment(start_s=2.5, end_s=7.5),
        Segment(start_s=5.0, end_s=10.0),
    ]


def test_sliding_windows_last_window_reaches_the_end() -> None:
    windows = sliding_windows(3.2, window_s=2.0, hop_s=0.5)
    assert windows[0].start_s == 0.0
    assert windows[-1].start_s == pytest.approx(1.2)
    assert windows[-1].end_s == pytest.approx(3.2)


def test_sliding_windows_short_audio_gives_one_window() -> None:
    assert sliding_windows(1.0, window_s=2.0, hop_s=0.5) == [Segment(start_s=0.0, end_s=1.0)]


def test_short_audio_is_padded_with_zeros_to_the_window() -> None:
    # 3 s d'audio coupé en fenêtres de 5 s : une fenêtre, complétée par 2 s de zéros.
    signal = np.ones(3 * SAMPLE_RATE, dtype=np.float32)
    windows = sliding_windows(3.0, window_s=5.0, hop_s=2.5)
    window = cut_window(signal, windows[0], window_s=5.0)
    assert window.shape == (5 * SAMPLE_RATE,)
    assert np.all(window[: 3 * SAMPLE_RATE] == 1.0)
    assert np.all(window[3 * SAMPLE_RATE :] == 0.0)


def test_last_window_is_taken_from_the_audio_not_padded() -> None:
    signal = np.arange(int(3.2 * SAMPLE_RATE)).astype(np.float32)
    windows = sliding_windows(3.2, window_s=2.0, hop_s=0.5)
    window = cut_window(signal, windows[-1], window_s=2.0)
    np.testing.assert_array_equal(window, signal[-2 * SAMPLE_RATE :])
