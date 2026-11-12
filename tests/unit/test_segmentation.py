import numpy as np
import pytest

from echolens.core.audio.preprocess import denoise, detect_speech, sliding_windows


def test_sliding_windows_stream_profile() -> None:
    # Profil flux (D8) : fenêtre de 2 s, décalage de 0,5 s, sur 3 s d'audio.
    windows = sliding_windows(3.0, window_s=2.0, hop_s=0.5)
    assert windows == [(0.0, 2.0), (0.5, 2.5), (1.0, 3.0)]


def test_sliding_windows_event_profile() -> None:
    # Événements : fenêtres de 5 s avec 50 % de recouvrement.
    windows = sliding_windows(10.0, window_s=5.0, hop_s=2.5)
    assert windows == [(0.0, 5.0), (2.5, 7.5), (5.0, 10.0)]


def test_sliding_windows_last_window_reaches_the_end() -> None:
    windows = sliding_windows(3.2, window_s=2.0, hop_s=0.5)
    assert windows[0][0] == 0.0
    assert windows[-1][0] == pytest.approx(1.2)
    assert windows[-1][1] == pytest.approx(3.2)


def test_sliding_windows_short_audio_gives_one_window() -> None:
    assert sliding_windows(1.0, window_s=2.0, hop_s=0.5) == [(0.0, 1.0)]


@pytest.mark.ml
def test_denoise_reduces_noise_and_keeps_tone() -> None:
    # 3 s de bruit avec une courte note de 0,3 s : le bruit de fond est stable, la note est
    # un événement bref, comme la parole. Une sinusoïde continue serait prise pour du bruit.
    sample_rate = 16_000
    rng = np.random.default_rng(0)
    clean = np.zeros(3 * sample_rate, dtype=np.float32)
    t = np.arange(int(0.3 * sample_rate)) / sample_rate
    start = sample_rate  # la note commence à 1 s
    clean[start : start + t.size] = 0.5 * np.sin(2 * np.pi * 440 * t)
    noisy = (clean + rng.normal(0.0, 0.05, clean.size)).astype(np.float32)

    cleaned = denoise(noisy)

    def rms(signal: np.ndarray) -> float:
        return float(np.sqrt(np.mean(np.square(signal))))

    noise_zone = slice(0, sample_rate)
    tone_zone = slice(start, start + t.size)
    assert cleaned.dtype == np.float32
    assert cleaned.shape == noisy.shape
    assert rms(cleaned[noise_zone]) < 0.7 * rms(noisy[noise_zone])  # le bruit est atténué
    # La porte spectrale atténue aussi un peu la note : on vérifie qu'elle n'est pas effacée.
    assert rms(cleaned[tone_zone]) > 0.25 * rms(clean[tone_zone])


@pytest.mark.ml
def test_detect_speech_finds_nothing_in_silence() -> None:
    assert detect_speech(np.zeros(16_000, dtype=np.float32)) == []
