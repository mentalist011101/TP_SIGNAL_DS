"""Test de fidélité de Grad-CAM (E7, C14b) : la partie torch, sur un petit CRNN (marqueur ml)."""

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("torch")

import torch

from echolens.core.models.family_a import SpectrogramCrnn
from echolens.core.models.network_config import NetworkConfig
from echolens.training.family_a import BandStatistics
from echolens.training.family_a_esc50 import save_weights
from echolens.training.family_a_models import TrainedNetwork
from echolens.training.grad_cam_fidelity import FidelityConfig
from echolens.training.grad_cam_fidelity_models import deletion_curves, load_c9_network

pytestmark = pytest.mark.ml

BANDS = 64
FRAMES = 101
CLASSES = 5


def small_network_config() -> NetworkConfig:
    return NetworkConfig(
        channels=[4, 8, 8, 8], kernel_size=3, padding=1, pool_size=2, dropout=0.0, gru_hidden_size=8
    )


def fidelity_config() -> FidelityConfig:
    return FidelityConfig(
        cell_bands=16, cell_frames=16, fractions=[0.0, 0.5, 1.0], fill_value=0.0, seed=0
    )


def random_clips(count: int) -> np.ndarray:
    generator = np.random.default_rng(0)
    return generator.standard_normal((count, BANDS, FRAMES)).astype(np.float32)


def test_curves_start_from_the_predicted_class_probability() -> None:
    torch.manual_seed(0)
    network = SpectrogramCrnn(CLASSES, small_network_config()).eval()
    clips = random_clips(2)
    with torch.no_grad():
        logits = network(torch.from_numpy(clips)).logits
    probabilities = torch.softmax(logits, dim=1)
    predicted = torch.argmax(logits, dim=1)

    curves = deletion_curves(network, clips, fidelity_config())

    assert curves.class_indices.tolist() == predicted.tolist()
    assert curves.hottest_first.shape == (2, 3)
    # Rien n'est masqué au premier point, tout est masqué au dernier : les deux ordres
    # donnent alors la même entrée, donc la même probabilité.
    for clip in range(2):
        expected = float(probabilities[clip, predicted[clip]])
        assert curves.hottest_first[clip, 0] == pytest.approx(expected, abs=1e-5)
        assert curves.random[clip, 0] == pytest.approx(curves.hottest_first[clip, 0], abs=1e-6)
        assert curves.random[clip, 2] == pytest.approx(curves.hottest_first[clip, 2], abs=1e-6)


def test_c9_checkpoint_is_reloaded_with_its_statistics(tmp_path: Path) -> None:
    torch.manual_seed(0)
    network = SpectrogramCrnn(CLASSES, small_network_config()).eval()
    statistics = BandStatistics(
        mean=np.full(BANDS, -40.0, dtype=np.float32), std=np.full(BANDS, 12.0, dtype=np.float32)
    )
    trained = TrainedNetwork(network=network, statistics=statistics, epochs_run=3)
    path = tmp_path / "crnn_fold1_seed42.pt"
    save_weights(trained, "crnn", CLASSES, 1e-3, path)

    reloaded, reloaded_statistics = load_c9_network(path, small_network_config())

    inputs = torch.from_numpy(random_clips(1))
    with torch.no_grad():
        torch.testing.assert_close(reloaded(inputs).logits, network(inputs).logits)
    assert reloaded_statistics.mean.tolist() == statistics.mean.tolist()
    assert reloaded_statistics.std.tolist() == statistics.std.tolist()
