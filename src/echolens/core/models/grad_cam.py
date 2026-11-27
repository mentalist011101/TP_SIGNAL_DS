"""Grad-CAM sur les réseaux de la famille A, CNN et CRNN (E7, EF-13, C14).

Code ml : importé seulement par le prédicteur réel (services.model_predictor) et par
l'évaluation de fidélité, jamais par le reste de core, pour que l'application tourne sans torch.

Article : R. R. Selvaraju et al., « Grad-CAM », ICCV 2017. Notations de la fiche
docs/fiches/grad-cam.md :
- A^k : cartes d'activation de la sortie du bloc 4 (dernière convolution), (K, h, w) ;
- y^c : score de la classe c AVANT le softmax (logit) ;
- alpha_k = moyenne sur la grille de dy^c / dA^k : importance du filtre k ;
- carte = ReLU(somme sur k de alpha_k × A^k), agrandie à la taille de l'entrée.

Pour le CRNN, le gradient remonte à travers l'attention et le BiGRU jusqu'au bloc 4. La carte
du bloc 4 est grossière : 4 bandes en fréquence et une colonne toutes les 160 ms (4 MaxPool
2 × 2) ; l'agrandissement la lisse sans ajouter d'information.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
import torch
from torch.nn import functional

from echolens.core.models.family_a import SpectrogramCnn, SpectrogramCrnn

FloatArray = npt.NDArray[np.float32]


@dataclass(frozen=True)
class GradCamResult:
    """Carte (bandes, trames) de la taille de l'entrée, et la classe expliquée."""

    values: FloatArray
    class_index: int


def grad_cam(
    network: SpectrogramCnn | SpectrogramCrnn, standardized: FloatArray, class_index: int | None
) -> GradCamResult:
    """Carte Grad-CAM d'une entrée log-Mel standardisée (bandes, trames).

    class_index : la classe à expliquer ; None pour la classe prédite (décision C14). Le réseau
    doit être en mode eval et garder la sortie de son bloc 4 (last_block_output).
    """
    # Étape 1 : passage avant AVEC gradients ; le réseau garde la sortie du bloc 4.
    inputs = torch.from_numpy(standardized).unsqueeze(0)
    with torch.enable_grad():
        output = network(inputs)
        activations = network.last_block_output
        if activations is None:
            raise ValueError("Le réseau n'a pas gardé la sortie de son bloc 4.")
        activations.retain_grad()
        logits = output.logits[0]
        chosen = class_index
        if chosen is None:
            chosen = int(torch.argmax(logits).item())
        # Étape 2 : rétropropagation du logit de la classe jusqu'aux cartes A^k.
        network.zero_grad()
        logits[chosen].backward()
    if activations.grad is None:
        raise ValueError("Aucun gradient n'est arrivé jusqu'au bloc 4.")
    gradients = activations.grad[0]
    maps = activations.detach()[0]
    # Étape 3 : alpha_k = moyenne des gradients sur la grille, un poids par filtre.
    weights = gradients.mean(dim=(1, 2))
    # Étape 4 : somme pondérée des cartes, puis ReLU (seulement ce qui soutient la classe).
    weighted = (weights[:, None, None] * maps).sum(dim=0)
    cam = torch.relu(weighted)
    # Étape 5 : agrandissement bilinéaire à la taille de l'entrée (bandes, trames).
    resized = functional.interpolate(
        cam[None, None], size=standardized.shape, mode="bilinear", align_corners=False
    )
    values = resized[0, 0].numpy().astype(np.float32)
    return GradCamResult(values=values, class_index=chosen)
