import numpy as np
import pytest

from echolens.config import CONFIG_DIR
from echolens.core.features import FeatureConfig, log_mel_spectrogram, mfcc

pytestmark = pytest.mark.ml  # nécessite torch : exclu de la CI


@pytest.fixture
def config() -> FeatureConfig:
    return FeatureConfig.from_yaml(CONFIG_DIR / "features.yaml")


def test_log_mel_shape(sine_wave: np.ndarray, config: FeatureConfig) -> None:
    # 1 s à 16 kHz avec un pas de 160 : T = 1 + 16 000 // 160 = 101 instants.
    result = log_mel_spectrogram(sine_wave, config)
    assert result.shape == (64, 101)
    assert result.dtype == np.float32


def test_log_mel_peak_is_in_low_bands(sine_wave: np.ndarray, config: FeatureConfig) -> None:
    # Une sinusoïde de 440 Hz doit allumer une bande des graves, pas des aigus.
    result = log_mel_spectrogram(sine_wave, config)
    mean_per_band = result.mean(axis=1)
    assert int(mean_per_band.argmax()) < 20
    assert mean_per_band.max() - mean_per_band[-1] > 30  # la dernière bande est bien plus basse


def test_mfcc_shapes(sine_wave: np.ndarray, config: FeatureConfig) -> None:
    assert mfcc(sine_wave, config, with_deltas=False).shape == (40, 101)
    assert mfcc(sine_wave, config, with_deltas=True).shape == (120, 101)
