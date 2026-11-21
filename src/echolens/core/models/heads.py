"""Tête de la famille B : somme pondérée des couches d'un encodeur gelé, puis MLP (C11).

Code partagé (R5) : l'entraînement (echolens.training.head_training) et l'application
(prédicteur réel, C13) utilisent cette même classe. Elle reçoit les moyennes par couche déjà
standardisées avec les statistiques du train (R4).
"""

from __future__ import annotations

import torch
from torch import nn


class LayerWeightedHead(nn.Module):
    """Somme pondérée des couches (w = softmax(a)), puis MLP à une couche cachée."""

    def __init__(
        self, layer_count: int, dimension: int, hidden_size: int, class_count: int, dropout: float
    ) -> None:
        super().__init__()
        # a vaut 0 au départ : softmax(0, …, 0) donne à chaque couche le poids 1 / couches.
        self.layer_logits = nn.Parameter(torch.zeros(layer_count))
        self.hidden = nn.Linear(dimension, hidden_size)
        self.activation = nn.ReLU()
        self.dropout = nn.Dropout(p=dropout)
        self.output = nn.Linear(hidden_size, class_count)

    def layer_weights(self) -> torch.Tensor:
        """Poids des couches : positifs et de somme 1 grâce au softmax (E7)."""
        return torch.softmax(self.layer_logits, dim=0)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        """(lot, couches, dimension) → scores bruts (lot, classes), avant softmax."""
        # Étape 1 : un poids par couche, mis en forme (1, couches, 1) pour multiplier le lot.
        weights = self.layer_weights()
        weights_per_layer = weights.view(1, -1, 1)
        # Étape 2 : somme pondérée des couches → (lot, dimension).
        weighted = features * weights_per_layer
        combined = weighted.sum(dim=1)
        # Étape 3 : MLP.
        hidden = self.hidden(combined)
        hidden = self.activation(hidden)
        hidden = self.dropout(hidden)
        scores: torch.Tensor = self.output(hidden)
        return scores
