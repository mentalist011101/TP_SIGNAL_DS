import librosa
import numpy as np
import pytest

from echolens.config import CONFIG_DIR
from echolens.core.features import FeatureConfig, log_mel_spectrogram, mfcc

# 1 s à 16 kHz, pas de 160, center=True : 1 + 16000 // 160 = 101 trames.
EXPECTED_FRAMES = 101


@pytest.fixture
def config() -> FeatureConfig:
    return FeatureConfig.from_yaml(CONFIG_DIR / "features.yaml")


def test_yaml_config_gives_40_hz_bins_and_10_ms_frames(config: FeatureConfig) -> None:
    assert config.frequency_resolution_hz == pytest.approx(40.0)
    assert config.hop_length / config.sample_rate == pytest.approx(0.010)
    assert config.n_fft / config.sample_rate == pytest.approx(0.025)


def test_log_mel_shape_and_dtype(sine_wave: np.ndarray, config: FeatureConfig) -> None:
    out = log_mel_spectrogram(sine_wave, config)
    assert out.shape == (config.n_mels, EXPECTED_FRAMES)
    assert out.dtype == np.float32


def test_mfcc_shapes_and_dtype(sine_wave: np.ndarray, config: FeatureConfig) -> None:
    with_deltas = mfcc(sine_wave, config)
    without_deltas = mfcc(sine_wave, config, with_deltas=False)
    assert with_deltas.shape == (3 * config.n_mfcc, EXPECTED_FRAMES)
    assert without_deltas.shape == (config.n_mfcc, EXPECTED_FRAMES)
    assert with_deltas.dtype == np.float32
    assert without_deltas.dtype == np.float32
    np.testing.assert_array_equal(with_deltas[: config.n_mfcc], without_deltas)


def test_440_hz_peaks_in_nearest_mel_band(sine_wave: np.ndarray, config: FeatureConfig) -> None:
    # Les n_mels centres sont les points intérieurs de n_mels + 2 fréquences équiréparties en Mel.
    centers = librosa.mel_frequencies(
        n_mels=config.n_mels + 2, fmin=config.f_min, fmax=config.f_max, htk=True
    )[1:-1]
    expected_band = int(np.argmin(np.abs(centers - 440.0)))
    energy_per_band = log_mel_spectrogram(sine_wave, config).mean(axis=1)
    assert int(np.argmax(energy_per_band)) == expected_band


def test_features_are_deterministic(sine_wave: np.ndarray, config: FeatureConfig) -> None:
    np.testing.assert_array_equal(
        log_mel_spectrogram(sine_wave, config), log_mel_spectrogram(sine_wave, config)
    )
    np.testing.assert_array_equal(mfcc(sine_wave, config), mfcc(sine_wave, config))


def test_log_mel_of_silence_is_finite(config: FeatureConfig) -> None:
    out = log_mel_spectrogram(np.zeros(16_000, dtype=np.float32), config)
    assert np.all(np.isfinite(out))


def test_deltas_of_stationary_sine_vanish(sine_wave: np.ndarray, config: FeatureConfig) -> None:
    features = mfcc(sine_wave, config)
    # Bords exclus : le rembourrage par réflexion et la demi-fenêtre des deltas les perturbent.
    margin = config.n_fft // config.hop_length + config.delta_width
    deltas = features[config.n_mfcc :, margin:-margin]
    coefficients = features[: config.n_mfcc, margin:-margin]
    assert np.abs(deltas).max() < 0.01 * np.abs(coefficients).max()


@pytest.mark.parametrize(
    "signal",
    [np.zeros((2, 16_000), dtype=np.float32), np.zeros(0, dtype=np.float32)],
    ids=["stereo", "empty"],
)
def test_invalid_signal_raises(signal: np.ndarray, config: FeatureConfig) -> None:
    with pytest.raises(ValueError):
        log_mel_spectrogram(signal, config)
    with pytest.raises(ValueError):
        mfcc(signal, config)
