"""Réseaux de la famille A : CNN et CRNN sur le log-Mel (Brique 4, C9), avec torch.

Code partagé (R5) : l'entraînement (echolens.training.family_a_models) et l'application
(prédicteur réel, C13) construisent les réseaux avec ces mêmes classes, donc les poids
sauvegardés à l'entraînement se rechargent tels quels. torch n'est importé que dans les
modules de core/models qui en ont besoin (extra [ml]) : le reste de core et la CI s'en passent.
"""

from __future__ import annotations

from typing import Literal, NamedTuple

import torch
from torch import nn

from echolens.core.models.network_config import NetworkConfig

Architecture = Literal["cnn", "crnn"]
# Une seule « couleur » à l'entrée du premier bloc : l'énergie en dB de chaque case.
INPUT_CHANNELS = 1


class NetworkOutput(NamedTuple):
    """Sortie d'un réseau : scores bruts par classe, et poids d'attention pour le CRNN."""

    logits: torch.Tensor  # (lot, classes)
    attention: torch.Tensor | None  # (lot, pas de temps), None pour le CNN


def conv_block(in_channels: int, out_channels: int, config: NetworkConfig) -> nn.Sequential:
    """Un bloc : Conv2d 3×3 → BatchNorm → ReLU → MaxPool 2×2 (Brique 4).

    La convolution fait glisser out_channels petits filtres 3×3 (3 bandes × 3 trames) sur
    l'image ; BatchNorm recentre chaque filtre sur le lot ; ReLU garde les valeurs positives ;
    MaxPool garde le maximum de chaque carré 2×2 et divise la taille de l'image par 2.
    """
    convolution = nn.Conv2d(
        in_channels,
        out_channels,
        kernel_size=config.kernel_size,
        padding=config.padding,
    )
    normalization = nn.BatchNorm2d(out_channels)
    activation = nn.ReLU()
    pooling = nn.MaxPool2d(kernel_size=config.pool_size)
    return nn.Sequential(convolution, normalization, activation, pooling)


def conv_blocks(config: NetworkConfig) -> nn.Sequential:
    """Les 4 blocs à la suite : 1 → 32 → 64 → 128 → 256 canaux ; 64 × 501 devient 4 × 31."""
    blocks = []
    in_channels = INPUT_CHANNELS
    for out_channels in config.channels:
        block = conv_block(in_channels, out_channels, config)
        blocks.append(block)
        in_channels = out_channels
    return nn.Sequential(*blocks)


class SpectrogramCnn(nn.Module):
    """CNN : 4 blocs, moyenne sur le temps et la fréquence, Dropout, couche linéaire."""

    def __init__(self, class_count: int, config: NetworkConfig) -> None:
        super().__init__()
        self.blocks = conv_blocks(config)
        self.dropout = nn.Dropout(p=config.dropout)
        self.classifier = nn.Linear(config.channels[-1], class_count)
        # Sortie du bloc 4 au dernier passage, (lot, 256, 4, 31) : base de Grad-CAM (C14).
        self.last_block_output: torch.Tensor | None = None

    def forward(self, log_mels: torch.Tensor) -> NetworkOutput:
        """log_mels standardisés (lot, bandes, trames) → scores (lot, classes)."""
        # Étape 1 : une image à un canal par extrait, (lot, 1, bandes, trames).
        images = log_mels.unsqueeze(1)
        feature_maps = self.blocks(images)
        self.last_block_output = feature_maps
        # Étape 2 : moyenne globale sur la fréquence (axe 2) et le temps (axe 3).
        pooled = feature_maps.mean(dim=(2, 3))
        dropped = self.dropout(pooled)
        logits = self.classifier(dropped)
        return NetworkOutput(logits=logits, attention=None)


class AttentionPooling(nn.Module):
    """Pooling par attention : un score par pas de temps, softmax, somme pondérée."""

    def __init__(self, feature_size: int) -> None:
        super().__init__()
        self.scorer = nn.Linear(feature_size, 1)

    def forward(self, sequence: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """(lot, pas, 256) → résumé (lot, 256) et poids (lot, pas) qui somment à 1."""
        scores = self.scorer(sequence)
        scores = scores.squeeze(2)
        # Le softmax transforme les scores en poids positifs de somme 1 sur les pas de temps.
        weights = torch.softmax(scores, dim=1)
        weighted = sequence * weights.unsqueeze(2)
        pooled = weighted.sum(dim=1)
        return pooled, weights


class SpectrogramCrnn(nn.Module):
    """CRNN : 4 blocs, moyenne sur la fréquence, BiGRU, attention, Dropout, couche linéaire."""

    def __init__(self, class_count: int, config: NetworkConfig) -> None:
        super().__init__()
        self.blocks = conv_blocks(config)
        self.gru = nn.GRU(
            input_size=config.channels[-1],
            hidden_size=config.gru_hidden_size,
            num_layers=1,
            batch_first=True,
            bidirectional=True,
        )
        # Bidirectionnel : les deux sens sont mis bout à bout, 2 × 128 = 256 valeurs par pas.
        sequence_size = 2 * config.gru_hidden_size
        self.attention = AttentionPooling(sequence_size)
        self.dropout = nn.Dropout(p=config.dropout)
        self.classifier = nn.Linear(sequence_size, class_count)
        self.last_block_output: torch.Tensor | None = None

    def forward(self, log_mels: torch.Tensor) -> NetworkOutput:
        """log_mels standardisés (lot, bandes, trames) → scores et poids d'attention."""
        images = log_mels.unsqueeze(1)
        feature_maps = self.blocks(images)
        self.last_block_output = feature_maps
        # Étape 1 : moyenne sur la fréquence → une suite de pas de temps, (lot, pas, 256).
        per_step = feature_maps.mean(dim=2)
        sequence = per_step.transpose(1, 2)
        # Étape 2 : le BiGRU lit la suite dans les deux sens (contexte avant et après).
        recurrent, _ = self.gru(sequence)
        # Étape 3 : l'attention choisit les pas de temps qui comptent pour la décision.
        pooled, weights = self.attention(recurrent)
        dropped = self.dropout(pooled)
        logits = self.classifier(dropped)
        return NetworkOutput(logits=logits, attention=weights)


def build_network(architecture: Architecture, class_count: int, config: NetworkConfig) -> nn.Module:
    """Crée un CNN ou un CRNN à poids aléatoires (graine fixée par l'appelant)."""
    if architecture == "cnn":
        return SpectrogramCnn(class_count, config)
    if architecture == "crnn":
        return SpectrogramCrnn(class_count, config)
    raise ValueError(f"Architecture inconnue : {architecture}")
