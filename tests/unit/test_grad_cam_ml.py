"""Grad-CAM sur de petits CNN et CRNN à poids aléatoires (E7, C14), avec torch (marqueur ml)."""

import numpy as np
import pytest

pytest.importorskip("torch")

import torch

from echolens.core.models.family_a import SpectrogramCnn, SpectrogramCrnn
from echolens.core.models.grad_cam import grad_cam
from echolens.core.models.network_config import NetworkConfig

pytestmark = pytest.mark.ml

BANDS = 64
FRAMES = 101
CLASSES = 6


def small_config() -> NetworkConfig:
    return NetworkConfig(
        channels=[4, 8, 8, 8], kernel_size=3, padding=1, pool_size=2, dropout=0.0, gru_hidden_size=8
    )


def random_input() -> np.ndarray:
    generator = np.random.default_rng(0)
    return generator.standard_normal((BANDS, FRAMES)).astype(np.float32)


@pytest.mark.parametrize("network_class", [SpectrogramCnn, SpectrogramCrnn])
def test_map_has_the_input_size_and_no_negative_value(network_class: type) -> None:
    torch.manual_seed(0)
    network = network_class(CLASSES, small_config()).eval()

    result = grad_cam(network, random_input(), class_index=None)

    assert result.values.shape == (BANDS, FRAMES)
    assert result.values.dtype == np.float32
    # ReLU : la carte ne garde que ce qui soutient la classe.
    assert result.values.min() >= 0.0


def test_default_class_is_the_predicted_one() -> None:
    torch.manual_seed(0)
    network = SpectrogramCrnn(CLASSES, small_config()).eval()
    inputs = random_input()
    with torch.no_grad():
        logits = network(torch.from_numpy(inputs).unsqueeze(0)).logits[0]
    predicted = int(torch.argmax(logits).item())

    result = grad_cam(network, inputs, class_index=None)

    assert result.class_index == predicted


def test_requested_class_is_explained() -> None:
    torch.manual_seed(0)
    network = SpectrogramCrnn(CLASSES, small_config()).eval()

    result = grad_cam(network, random_input(), class_index=3)

    assert result.class_index == 3


def test_explaining_does_not_change_the_weights() -> None:
    torch.manual_seed(0)
    network = SpectrogramCnn(CLASSES, small_config()).eval()
    before = [parameter.detach().clone() for parameter in network.parameters()]

    grad_cam(network, random_input(), class_index=None)

    for old, new in zip(before, network.parameters(), strict=True):
        assert torch.equal(old, new.detach())
