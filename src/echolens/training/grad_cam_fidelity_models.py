"""Test de fidélité de Grad-CAM (E7, C14b) : la partie avec torch, pour le notebook Kaggle.

Pour chaque extrait : carte Grad-CAM de la classe prédite (echolens.core.models.grad_cam, le
même code que l'application), puis probabilité de cette classe quand on masque les cases dans
l'ordre de la carte ou au hasard (echolens.training.grad_cam_fidelity).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from echolens.core.features import FloatArray
from echolens.core.models.family_a import SpectrogramCrnn
from echolens.core.models.grad_cam import grad_cam
from echolens.core.models.network_config import NetworkConfig
from echolens.core.models.production_config import load_production_config
from echolens.core.models.storage import load_weights
from echolens.training.evaluation import IntArray
from echolens.training.family_a import BandStatistics
from echolens.training.grad_cam_fidelity import (
    FidelityConfig,
    cell_scores,
    deletion_inputs,
    hottest_first_order,
    random_order,
)


@dataclass(frozen=True)
class ClipCurves:
    """Courbes de suppression d'un extrait : une probabilité par part masquée."""

    class_index: int
    hottest_first: FloatArray
    random: FloatArray


@dataclass(frozen=True)
class DeletionCurves:
    """Courbes de tous les extraits : (extraits, points), et la classe expliquée de chacun."""

    class_indices: IntArray
    hottest_first: FloatArray
    random: FloatArray


def load_c9_network(
    checkpoint_path: Path, network_config: NetworkConfig
) -> tuple[SpectrogramCrnn, BandStatistics]:
    """CRNN d'un tour de C9 (fichier torch de notre notebook) et SES statistiques (R4)."""
    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if checkpoint["architecture"] != "crnn":
        raise ValueError(f"{checkpoint_path.name} : un CRNN est attendu.")
    network = SpectrogramCrnn(int(checkpoint["class_count"]), network_config)
    network.load_state_dict(checkpoint["state_dict"], strict=True)
    network.eval()
    mean = checkpoint["band_mean"].numpy().astype(np.float32)
    std = checkpoint["band_std"].numpy().astype(np.float32)
    return network, BandStatistics(mean=mean, std=std)


def load_production_crnn(
    config_path: Path, weights_path: Path
) -> tuple[SpectrogramCrnn, BandStatistics]:
    """CRNN de production (config.json et model.safetensors, C13) et ses statistiques (R4)."""
    config = load_production_config(config_path)
    if config.architecture != "crnn" or config.network is None:
        raise ValueError(f"{config.model_id} : un CRNN est attendu.")
    network = SpectrogramCrnn(len(config.labels), config.network)
    load_weights(network, weights_path)
    mean = np.array(config.standardization_mean, dtype=np.float32)
    std = np.array(config.standardization_std, dtype=np.float32)
    return network, BandStatistics(mean=mean, std=std)


def class_probabilities(
    network: SpectrogramCrnn, inputs: FloatArray, class_index: int
) -> FloatArray:
    """Probabilité (softmax, sans température) d'une classe pour chaque entrée du lot."""
    device = next(network.parameters()).device
    batch = torch.from_numpy(inputs).to(device)
    with torch.no_grad():
        output = network(batch)
    probabilities = torch.softmax(output.logits, dim=1)
    chosen = probabilities[:, class_index]
    return np.asarray(chosen.cpu().numpy(), dtype=np.float64)


def clip_curves(
    network: SpectrogramCrnn,
    standardized: FloatArray,
    config: FidelityConfig,
    generator: np.random.Generator,
) -> ClipCurves:
    """Les deux courbes de suppression d'un extrait standardisé (bandes, trames)."""
    # Étape 1 : carte de la classe prédite, ramenée à une chaleur par case.
    explained = grad_cam(network, standardized, class_index=None)
    scores = cell_scores(explained.values, config.cell_bands, config.cell_frames)
    column_count = scores.shape[1]
    # Étape 2 : les deux ordres de masquage, la carte et le hasard.
    hottest = hottest_first_order(scores)
    shuffled = random_order(scores.size, generator)
    # Étape 3 : probabilité de la même classe à chaque part masquée.
    hottest_inputs = deletion_inputs(standardized, hottest, column_count, config)
    random_inputs = deletion_inputs(standardized, shuffled, column_count, config)
    hottest_curve = class_probabilities(network, hottest_inputs, explained.class_index)
    random_curve = class_probabilities(network, random_inputs, explained.class_index)
    return ClipCurves(
        class_index=explained.class_index, hottest_first=hottest_curve, random=random_curve
    )


def deletion_curves(
    network: SpectrogramCrnn, standardized_clips: FloatArray, config: FidelityConfig
) -> DeletionCurves:
    """Courbes de chaque extrait de (extraits, bandes, trames), entrées déjà standardisées."""
    # Mode eval : ni dropout ni mise à jour de la BatchNorm, comme dans l'application.
    network.eval()
    generator = np.random.default_rng(config.seed)
    class_indices = []
    hottest_curves = []
    random_curves = []
    for standardized in standardized_clips:
        curves = clip_curves(network, standardized, config, generator)
        class_indices.append(curves.class_index)
        hottest_curves.append(curves.hottest_first)
        random_curves.append(curves.random)
    return DeletionCurves(
        class_indices=np.array(class_indices, dtype=np.int_),
        hottest_first=np.stack(hottest_curves),
        random=np.stack(random_curves),
    )
