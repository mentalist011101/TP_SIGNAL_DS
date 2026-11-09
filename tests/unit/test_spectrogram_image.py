from pathlib import Path

import matplotlib
import matplotlib.image
import numpy as np
import pytest

from echolens.config import CONFIG_DIR
from echolens.core.features import FeatureConfig
from echolens.services.spectrogram_image import save_spectrogram_png

N_FRAMES = 50
SILENCE_DB = -100.0


@pytest.fixture
def config() -> FeatureConfig:
    return FeatureConfig.from_yaml(CONFIG_DIR / "features.yaml")


def silent_log_mel(config: FeatureConfig) -> np.ndarray:
    """Log-Mel de synthèse : toutes les bandes au plancher de −100 dB."""
    return np.full((config.n_mels, N_FRAMES), SILENCE_DB, dtype=np.float32)


def save_and_read(log_mel: np.ndarray, tmp_path: Path, config: FeatureConfig) -> np.ndarray:
    """Écrit le PNG puis le relit : tableau (hauteur, largeur, 4) de couleurs RGBA entre 0 et 1."""
    path = tmp_path / "spectrogram.png"
    save_spectrogram_png(log_mel, path, config)
    return matplotlib.image.imread(path)


def colormap_end(config: FeatureConfig, position: float) -> np.ndarray:
    """Couleur RGBA de la palette à une position entre 0 (plus sombre) et 1 (plus claire)."""
    colormap = matplotlib.colormaps[config.display_colormap]
    return np.array(colormap(position))


def test_image_has_one_pixel_per_frame_and_per_mel_band(
    tmp_path: Path, config: FeatureConfig
) -> None:
    image = save_and_read(silent_log_mel(config), tmp_path, config)
    height = image.shape[0]
    width = image.shape[1]
    assert height == config.n_mels
    assert width == N_FRAMES


def test_display_max_is_brightest_and_silence_is_darkest(
    tmp_path: Path, config: FeatureConfig
) -> None:
    log_mel = silent_log_mel(config)
    log_mel[:, 0] = config.display_db_max

    image = save_and_read(log_mel, tmp_path, config)
    loud_pixel = image[0, 0]
    silent_pixel = image[0, 1]
    # Tolérance d'un niveau sur 255 : le PNG stocke chaque couleur sur 8 bits.
    tolerance = 1 / 255
    np.testing.assert_allclose(loud_pixel, colormap_end(config, 1.0), atol=tolerance)
    np.testing.assert_allclose(silent_pixel, colormap_end(config, 0.0), atol=tolerance)


def test_low_frequencies_are_at_the_bottom(tmp_path: Path, config: FeatureConfig) -> None:
    # Seule la bande Mel 0 (la plus grave) est forte.
    log_mel = silent_log_mel(config)
    log_mel[0, :] = config.display_db_max

    image = save_and_read(log_mel, tmp_path, config)
    bottom_row = image[-1]
    top_row = image[0]
    brightest = colormap_end(config, 1.0)
    darkest = colormap_end(config, 0.0)
    tolerance = 1 / 255
    np.testing.assert_allclose(bottom_row[0], brightest, atol=tolerance)
    np.testing.assert_allclose(top_row[0], darkest, atol=tolerance)
