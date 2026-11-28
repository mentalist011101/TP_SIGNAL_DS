"""Bip de marquage des voix synthétiques (EF-18, ENF-10, C35), sans torch."""

import numpy as np
import pytest

from echolens.core.inference import load_inference_config
from echolens.core.synthetic_marker import mark_synthetic, marker_tone

SAMPLE_RATE = 24_000


def test_marker_is_a_soft_tone_at_the_configured_frequency() -> None:
    settings = load_inference_config().voice_cloning

    tone = marker_tone(SAMPLE_RATE, settings)

    assert len(tone) == round(settings.marker_duration_s * SAMPLE_RATE)
    # Début et fin à zéro (fenêtre de Hann) : pas de clic.
    assert tone[0] == pytest.approx(0.0, abs=1e-6)
    assert tone[-1] == pytest.approx(0.0, abs=1e-6)
    assert np.abs(tone).max() <= settings.marker_amplitude
    # La fréquence la plus forte du bip est celle de la configuration.
    spectrum = np.abs(np.fft.rfft(tone))
    frequencies = np.fft.rfftfreq(len(tone), d=1 / SAMPLE_RATE)
    peak_hz = frequencies[int(np.argmax(spectrum))]
    assert peak_hz == pytest.approx(settings.marker_frequency_hz, abs=10)


def test_speech_follows_the_marker_and_a_silence() -> None:
    settings = load_inference_config().voice_cloning
    speech = np.full(SAMPLE_RATE, 0.5, dtype=np.float32)

    marked = mark_synthetic(speech, SAMPLE_RATE, settings)

    tone_count = round(settings.marker_duration_s * SAMPLE_RATE)
    gap_count = round(settings.marker_gap_s * SAMPLE_RATE)
    assert len(marked) == tone_count + gap_count + len(speech)
    gap = marked[tone_count : tone_count + gap_count]
    assert np.all(gap == 0.0)
    assert np.all(marked[tone_count + gap_count :] == 0.5)
