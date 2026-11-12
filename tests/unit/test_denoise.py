import numpy as np

from echolens.core.audio.denoise import denoise
from echolens.core.audio.preprocess_config import DenoiseConfig, load_preprocess_config

SAMPLE_RATE = 16_000
NOTE_START = SAMPLE_RATE  # la note commence à 1 s
NOTE_LENGTH = int(0.3 * SAMPLE_RATE)
NOISE_ZONE = slice(0, SAMPLE_RATE)
NOTE_ZONE = slice(NOTE_START, NOTE_START + NOTE_LENGTH)


def enabled_config(prop_decrease: float) -> DenoiseConfig:
    config = load_preprocess_config().denoise
    return config.model_copy(update={"enabled": True, "prop_decrease": prop_decrease})


def note_in_noise() -> tuple[np.ndarray, np.ndarray]:
    # 3 s de bruit avec une courte note de 0,3 s : le bruit de fond est stable, la note est
    # un événement bref, comme la parole. Une sinusoïde continue serait prise pour du bruit.
    rng = np.random.default_rng(0)
    clean = np.zeros(3 * SAMPLE_RATE, dtype=np.float32)
    t = np.arange(NOTE_LENGTH) / SAMPLE_RATE
    clean[NOTE_ZONE] = 0.5 * np.sin(2 * np.pi * 440 * t)
    noisy = (clean + rng.normal(0.0, 0.05, clean.size)).astype(np.float32)
    return clean, noisy


def rms(signal: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(signal))))


def test_denoise_reduces_noise_and_keeps_tone() -> None:
    clean, noisy = note_in_noise()
    cleaned = denoise(noisy, enabled_config(0.8))
    assert cleaned.dtype == np.float32
    assert cleaned.shape == noisy.shape
    assert rms(cleaned[NOISE_ZONE]) < 0.7 * rms(noisy[NOISE_ZONE])  # le bruit est atténué
    # La porte spectrale atténue aussi un peu la note : on vérifie qu'elle n'est pas effacée.
    assert rms(cleaned[NOTE_ZONE]) > 0.25 * rms(clean[NOTE_ZONE])


def test_force_08_keeps_more_of_the_note_than_force_10() -> None:
    _, noisy = note_in_noise()
    note_at_08 = denoise(noisy, enabled_config(0.8))[NOTE_ZONE]
    note_at_10 = denoise(noisy, enabled_config(1.0))[NOTE_ZONE]
    assert rms(note_at_08) > rms(note_at_10)


def test_disabled_denoise_returns_identical_signal() -> None:
    _, noisy = note_in_noise()
    config = load_preprocess_config().denoise
    assert config.enabled is False
    result = denoise(noisy, config)
    np.testing.assert_array_equal(result, noisy)
    assert result is not noisy
