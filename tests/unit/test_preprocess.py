import numpy as np
import pytest

from echolens.core.audio.preprocess import (
    is_silent,
    peak_limit,
    preprocess,
    rms_dbfs,
    rms_normalize,
)


def test_rms_dbfs_of_full_scale_sine_is_about_minus_3(sine_wave: np.ndarray) -> None:
    # Une sinusoïde d'amplitude A a un RMS de A/√2 ; pour A = 1 : 20·log10(1/√2) ≈ -3,01 dB.
    assert rms_dbfs(sine_wave * 2) == pytest.approx(-3.01, abs=0.05)


def test_rms_normalize_reaches_target(sine_wave: np.ndarray) -> None:
    normalized = rms_normalize(sine_wave, target_dbfs=-20.0)
    assert rms_dbfs(normalized) == pytest.approx(-20.0, abs=0.01)
    assert normalized.dtype == np.float32


def test_rms_normalize_leaves_zero_signal_untouched() -> None:
    silence = np.zeros(1000, dtype=np.float32)
    assert np.array_equal(rms_normalize(silence), silence)


def test_peak_limit_clips_to_ceiling() -> None:
    loud = np.array([-2.0, -0.5, 0.0, 0.5, 2.0], dtype=np.float32)
    limited = peak_limit(loud, ceiling=0.99)
    assert limited.max() == pytest.approx(0.99)
    assert limited.min() == pytest.approx(-0.99)


def test_is_silent_detects_silence(sine_wave: np.ndarray) -> None:
    assert is_silent(np.zeros(16_000, dtype=np.float32))
    assert not is_silent(sine_wave)


def test_preprocess_never_exceeds_ceiling(sine_wave: np.ndarray) -> None:
    out = preprocess(sine_wave, target_dbfs=0.0)
    assert np.abs(out).max() <= 0.99 + 1e-6
