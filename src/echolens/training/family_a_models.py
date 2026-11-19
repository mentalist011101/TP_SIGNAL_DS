"""Famille A (C9) : réseaux CNN et CRNN sur le log-Mel, et boucle d'entraînement (Brique 4).

Seul module de la famille A qui importe torch (extra [ml], installé d'office sur Kaggle). Les
calculs sur les tableaux (statistiques par bande, augmentations) sont dans
echolens.training.family_a, testés en CI sans torch.

La boucle ne suppose rien d'ESC-50 : elle reçoit des log-Mel et des étiquettes entières, et
servira telle quelle aux émotions (C12). Calcul en float32, sans précision mixte.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Literal, NamedTuple

import numpy as np
import torch
from torch import nn
from torch.nn import functional

from echolens.core.features import FloatArray
from echolens.training.evaluation import IntArray, macro_f1
from echolens.training.family_a import (
    BandStatistics,
    FamilyAConfig,
    MixedBatch,
    NetworkConfig,
    augment_batch,
    band_statistics,
    standardize,
)

Architecture = Literal["cnn", "crnn"]
# Une seule « couleur » à l'entrée du premier bloc : l'énergie en dB de chaque case.
INPUT_CHANNELS = 1


class NetworkOutput(NamedTuple):
    """Sortie d'un réseau : scores bruts par classe, et poids d'attention pour le CRNN."""

    logits: torch.Tensor  # (lot, classes)
    attention: torch.Tensor | None  # (lot, pas de temps), None pour le CNN


@dataclass(frozen=True)
class LabeledSpectrograms:
    """Log-Mel en dB absolus (non standardisés) et classe de chaque extrait."""

    log_mels: FloatArray  # (extraits, bandes, trames)
    labels: IntArray


@dataclass(frozen=True)
class TrainedNetwork:
    """Un réseau entraîné et ce qu'il faut pour le réutiliser ou le citer."""

    network: nn.Module
    # Statistiques de SON entraînement : à réappliquer telles quelles en prédiction (R4).
    statistics: BandStatistics
    epochs_run: int


@dataclass(frozen=True)
class EarlyStoppedNetwork:
    """Résultat du réglage : le réseau de la meilleure époque et la courbe de validation."""

    trained: TrainedNetwork
    best_epoch: int
    best_validation_f1: float
    validation_f1_history: list[float]


@dataclass(frozen=True)
class Predictions:
    """Probabilités par classe, et poids d'attention pour le CRNN."""

    probabilities: FloatArray  # (extraits, classes)
    attention: FloatArray | None  # (extraits, pas de temps)


@dataclass
class _TrainingState:
    network: nn.Module
    optimizer: torch.optim.Optimizer
    scheduler: torch.optim.lr_scheduler.LRScheduler
    statistics: BandStatistics
    generator: np.random.Generator


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


def seed_everything(seed: int) -> None:
    """Fixe la graine de torch (CPU et GPU) et demande des convolutions déterministes (ENF-07)."""
    torch.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def train_with_early_stopping(
    architecture: Architecture,
    train: LabeledSpectrograms,
    validation: LabeledSpectrograms,
    class_count: int,
    learning_rate: float,
    seed: int,
    config: FamilyAConfig,
    device: torch.device,
) -> EarlyStoppedNetwork:
    """Réglage (P3) : entraîne au plus max_epochs époques, garde la meilleure sur la validation.

    Après chaque époque, F1 macro sur la validation ; on s'arrête après `patience` époques
    sans amélioration (jamais si patience vaut None) et on recharge les poids de la meilleure
    époque.
    """
    state = _start_training(architecture, train, class_count, learning_rate, seed, config, device)
    history: list[float] = []
    best_f1 = -1.0
    best_epoch = 0
    best_weights = copy.deepcopy(state.network.state_dict())
    for epoch in range(1, config.training.max_epochs + 1):
        train_one_epoch(state, train, class_count, config, device)
        # Étape 1 : F1 macro sur la validation, critère de l'early stopping.
        score = validation_macro_f1(state.network, validation, state.statistics, config, device)
        history.append(score)
        # Étape 2 : meilleure époque jusqu'ici → on garde une copie de ses poids.
        if score > best_f1:
            best_f1 = score
            best_epoch = epoch
            best_weights = copy.deepcopy(state.network.state_dict())
        # Étape 3 : `patience` époques de suite sans faire mieux → on arrête.
        patience = config.training.patience
        if patience is None:
            continue
        if epoch - best_epoch >= patience:
            break
    # On revient aux poids de la meilleure époque.
    state.network.load_state_dict(best_weights)
    trained = TrainedNetwork(state.network, state.statistics, epochs_run=len(history))
    return EarlyStoppedNetwork(
        trained=trained,
        best_epoch=best_epoch,
        best_validation_f1=best_f1,
        validation_f1_history=history,
    )


def train_fixed_epochs(
    architecture: Architecture,
    train: LabeledSpectrograms,
    class_count: int,
    learning_rate: float,
    epoch_count: int,
    seed: int,
    config: FamilyAConfig,
    device: torch.device,
) -> TrainedNetwork:
    """Entraînement final (P3) : exactement epoch_count époques, sans validation ni arrêt."""
    state = _start_training(architecture, train, class_count, learning_rate, seed, config, device)
    for _ in range(epoch_count):
        train_one_epoch(state, train, class_count, config, device)
    return TrainedNetwork(state.network, state.statistics, epochs_run=epoch_count)


def train_one_epoch(
    state: _TrainingState,
    train: LabeledSpectrograms,
    class_count: int,
    config: FamilyAConfig,
    device: torch.device,
) -> float:
    """Une époque : chaque extrait passe une fois, dans un ordre tiré au hasard ; perte moyenne."""
    state.network.train()
    batch_size = config.training.batch_size
    order = state.generator.permutation(len(train.labels))
    losses = []
    for start in range(0, len(order), batch_size):
        batch_indices = order[start : start + batch_size]
        batch_log_mels = train.log_mels[batch_indices]
        batch_labels = train.labels[batch_indices]
        # Augmentations recalculées à chaque époque, sur le train seulement (P6).
        batch = augment_batch(
            batch_log_mels,
            batch_labels,
            state.statistics,
            class_count,
            config.augmentation,
            state.generator,
        )
        loss = _training_step(state, batch, device)
        losses.append(loss)
    # Le cosinus avance d'un cran par époque.
    state.scheduler.step()
    return float(np.mean(losses))


def predict(
    network: nn.Module,
    log_mels: FloatArray,
    statistics: BandStatistics,
    config: FamilyAConfig,
    device: torch.device,
) -> Predictions:
    """Probabilités (softmax) de chaque extrait, sans augmentation ni dropout.

    Les log-Mel sont standardisés avec les statistiques de l'ENTRAÎNEMENT du réseau (R4).
    """
    network.eval()
    standardized = standardize(log_mels, statistics)
    batch_size = config.training.prediction_batch_size
    probability_batches = []
    attention_batches = []
    with torch.no_grad():
        for start in range(0, len(standardized), batch_size):
            batch = standardized[start : start + batch_size]
            inputs = torch.from_numpy(batch).to(device)
            output = network(inputs)
            probabilities = torch.softmax(output.logits, dim=1)
            probability_batches.append(probabilities.cpu().numpy())
            if output.attention is not None:
                attention_batches.append(output.attention.cpu().numpy())
    probabilities_of_all = np.concatenate(probability_batches)
    attention = None
    if attention_batches:
        attention = np.concatenate(attention_batches)
    return Predictions(probabilities=probabilities_of_all, attention=attention)


def predicted_classes(predictions: Predictions) -> IntArray:
    """Classe prédite de chaque extrait : celle de plus grande probabilité."""
    best = predictions.probabilities.argmax(axis=1)
    return np.asarray(best, dtype=np.int_)


def validation_macro_f1(
    network: nn.Module,
    validation: LabeledSpectrograms,
    statistics: BandStatistics,
    config: FamilyAConfig,
    device: torch.device,
) -> float:
    """F1 macro sur la validation, critère de l'early stopping (Brique 4)."""
    predictions = predict(network, validation.log_mels, statistics, config, device)
    y_pred = predicted_classes(predictions)
    return macro_f1(validation.labels, y_pred)


def _start_training(
    architecture: Architecture,
    train: LabeledSpectrograms,
    class_count: int,
    learning_rate: float,
    seed: int,
    config: FamilyAConfig,
    device: torch.device,
) -> _TrainingState:
    # Étape 1 : statistiques de standardisation sur CET entraînement seulement (R4).
    statistics = band_statistics(train.log_mels)
    # Étape 2 : même graine → mêmes poids de départ, même ordre des lots, mêmes augmentations.
    seed_everything(seed)
    generator = np.random.default_rng(seed)
    network = build_network(architecture, class_count, config.network)
    network = network.to(device=device, dtype=torch.float32)
    # Étape 3 : AdamW et cosinus sur max_epochs, au réglage comme à l'entraînement final.
    optimizer = torch.optim.AdamW(
        network.parameters(),
        lr=learning_rate,
        weight_decay=config.training.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=config.training.max_epochs
    )
    return _TrainingState(network, optimizer, scheduler, statistics, generator)


def _training_step(state: _TrainingState, batch: MixedBatch, device: torch.device) -> float:
    inputs = torch.from_numpy(batch.inputs).to(device)
    targets = torch.from_numpy(batch.targets).to(device)
    state.optimizer.zero_grad()
    output = state.network(inputs)
    # Entropie croisée avec des cibles « douces » : celles du mixup, λ et 1 − λ.
    loss = functional.cross_entropy(output.logits, targets)
    torch.autograd.backward(loss)
    state.optimizer.step()
    return float(loss.item())
