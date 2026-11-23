"""Poids des modèles de production en safetensors, jamais en pickle (C13, I7), avec torch.

torch.save et torch.load passent par pickle : relire un fichier pickle peut exécuter du code
caché dedans. Un fichier safetensors ne contient que des tableaux de nombres et leurs noms :
le relire ne peut rien exécuter. Les poids publiés sur Hugging Face sont donc en safetensors.
"""

from __future__ import annotations

from pathlib import Path

import torch
from safetensors.torch import load_file, save_file

from echolens.core.models.production_config import (
    WEIGHTS_FILE,
    ProductionModelConfig,
    save_production_config,
)


def save_production_model(
    network: torch.nn.Module, config: ProductionModelConfig, directory: Path
) -> Path:
    """Écrit model.safetensors (poids) et config.json (description) dans le dossier."""
    directory.mkdir(parents=True, exist_ok=True)
    # Copie sur CPU et en mémoire contiguë : c'est ce qu'exige safetensors.
    weights: dict[str, torch.Tensor] = {}
    for name, tensor in network.state_dict().items():
        on_cpu = tensor.detach().cpu()
        weights[name] = on_cpu.contiguous()
    weights_path = directory / WEIGHTS_FILE
    save_file(weights, str(weights_path))
    save_production_config(config, directory)
    return weights_path


def load_weights(network: torch.nn.Module, weights_path: Path) -> torch.nn.Module:
    """Charge des poids safetensors dans un réseau déjà construit, puis le met en mode eval.

    strict=True : un nom de poids absent ou en trop fait échouer le chargement, au lieu de
    laisser une couche à ses valeurs aléatoires sans prévenir.
    """
    weights = load_file(str(weights_path), device="cpu")
    network.load_state_dict(weights, strict=True)
    network.eval()
    return network
