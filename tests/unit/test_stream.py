"""Flux micro en direct (EF-14, D8) : PCM reçu, tampon et fenêtres, sans modèle."""

import numpy as np
import pytest

from echolens.core.inference import load_inference_config
from echolens.core.stream import StreamBuffer, level_dbfs, pcm16_to_float32
from echolens.services.stream_service import StreamError, parse_start

SAMPLE_RATE = 16_000
WINDOW_S = 2.0
HOP_S = 0.5


def seconds_of_signal(seconds: float, value: float = 0.1) -> np.ndarray:
    return np.full(int(seconds * SAMPLE_RATE), value, dtype=np.float32)


def feed(buffer: StreamBuffer, seconds: float, chunk_s: float = 0.1) -> list[float]:
    """Envoie `seconds` de son par morceaux de chunk_s ; renvoie la fin de chaque fenêtre rendue."""
    ends = []
    chunk_count = round(seconds / chunk_s)
    for _ in range(chunk_count):
        buffer.append(seconds_of_signal(chunk_s))
        window = buffer.next_window()
        if window is not None:
            ends.append(window.end_s)
    return ends


def test_pcm16_is_scaled_to_minus_one_one() -> None:
    samples = np.array([0, 16_384, -32_768, 32_767], dtype="<i2")

    signal = pcm16_to_float32(samples.tobytes())

    assert signal.dtype == np.float32
    assert signal.tolist() == pytest.approx([0.0, 0.5, -1.0, 32_767 / 32_768])


def test_odd_number_of_bytes_is_refused() -> None:
    with pytest.raises(ValueError, match="pair"):
        pcm16_to_float32(b"\x00\x01\x02")


def test_no_window_before_two_seconds() -> None:
    buffer = StreamBuffer(WINDOW_S, HOP_S, SAMPLE_RATE)

    ends = feed(buffer, 1.9)

    assert ends == []


def test_one_window_every_half_second_after_the_first() -> None:
    buffer = StreamBuffer(WINDOW_S, HOP_S, SAMPLE_RATE)

    ends = feed(buffer, 4.0)

    # Première fenêtre à 2 s, puis toutes les 0,5 s : 2 ; 2,5 ; 3 ; 3,5 ; 4.
    assert ends == pytest.approx([2.0, 2.5, 3.0, 3.5, 4.0])


def test_window_is_the_last_two_seconds() -> None:
    buffer = StreamBuffer(WINDOW_S, HOP_S, SAMPLE_RATE)
    buffer.append(seconds_of_signal(1.5, value=0.1))
    buffer.append(seconds_of_signal(1.0, value=0.9))

    window = buffer.next_window()

    assert window is not None
    assert len(window.signal) == 2 * SAMPLE_RATE
    # Les 0,5 premières secondes reçues sont sorties du tampon.
    assert window.signal[0] == pytest.approx(0.1)
    assert window.signal[-1] == pytest.approx(0.9)
    assert window.end_s == pytest.approx(2.5)


def test_late_windows_are_skipped_and_counted() -> None:
    buffer = StreamBuffer(WINDOW_S, HOP_S, SAMPLE_RATE)
    feed(buffer, 2.0)
    # Le serveur a pris du retard : 1,5 s arrive d'un coup, soit 3 décalages de 0,5 s.
    buffer.append(seconds_of_signal(1.5))

    window = buffer.next_window()

    assert window is not None
    assert window.skipped == 2
    assert window.end_s == pytest.approx(3.5)
    # Rien de plus à analyser tant que 0,5 s de son n'est pas arrivée.
    assert buffer.next_window() is None


def test_start_without_recording() -> None:
    settings = load_inference_config().stream

    options = parse_start({"type": "start", "record": False}, settings)

    assert options.record is False
    assert options.consent_version is None


def test_recording_with_accepted_consent() -> None:
    settings = load_inference_config().stream
    consent = {"accepted": True, "version": settings.consent_version}

    options = parse_start({"type": "start", "record": True, "consent": consent}, settings)

    assert options.record is True
    assert options.consent_version == settings.consent_version


@pytest.mark.parametrize(
    "consent",
    [None, {"accepted": False, "version": "direct-v1"}, {"version": "direct-v1"}],
)
def test_recording_without_consent_is_refused(consent: object) -> None:
    settings = load_inference_config().stream
    message = {"type": "start", "record": True, "consent": consent}

    with pytest.raises(StreamError, match="cochez la case"):
        parse_start(message, settings)


def test_recording_with_unknown_consent_text_is_refused() -> None:
    settings = load_inference_config().stream
    message = {"type": "start", "record": True, "consent": {"accepted": True, "version": "v0"}}

    with pytest.raises(StreamError, match="rechargez la page"):
        parse_start(message, settings)


def test_level_of_zeros_is_the_floor() -> None:
    assert level_dbfs(np.zeros(16_000, dtype=np.float32)) == pytest.approx(-200.0)


def test_level_of_a_full_scale_sine_is_minus_3_dbfs() -> None:
    times = np.arange(16_000) / SAMPLE_RATE
    sine = np.sin(2 * np.pi * 440 * times).astype(np.float32)

    # RMS d'une sinusoïde = amplitude / racine de 2, soit -3,01 dBFS à pleine échelle.
    assert level_dbfs(sine) == pytest.approx(-3.01, abs=0.01)
