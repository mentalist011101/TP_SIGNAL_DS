"""Famille A (C9) : boucle d'entraînement du CNN et du CRNN sur le log-Mel (Brique 4).

Les réseaux eux-mêmes sont dans echolens.core.models.family_a : l'application les charge avec
le même code (R5). Les calculs sur les tableaux (statistiques par bande, augmentations) sont
dans echolens.training.family_a, testés en CI sans torch.

La boucle ne suppose rien d'ESC-50 : elle reçoit des log-Mel et des étiquettes entières, et
servira telle quelle aux émotions (C12). Calcul en float32, sans précision mixte.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass

import numpy as np
import torch
from torch import nn
from torch.nn import functional

from echolens.core.features import FloatArray
from echolens.core.frame_windows import center_windows, random_windows
from echolens.core.models.family_a import Architecture, build_network
from echolens.training.evaluation import IntArray, macro_f1
from echolens.training.family_a import (
    BandStatistics,
    FamilyAConfig,
    MixedBatch,
    augment_batch,
    band_statistics,
    standardize,
)


@dataclass(frozen=True)
class LabeledSpectrograms:
    """Log-Mel en dB absolus (non standardisés) et classe de chaque extrait.

    Sans lengths, log_mels ont déjà la longueur que voit le réseau (ESC-50, C9). Avec lengths
    (émotions, C12), log_mels sont les extraits entiers, complétés jusqu'au plus long par du
    silence : à l'entraînement, chaque lot prend une fenêtre de window_frames tirée au hasard,
    et les statistiques de standardisation se calculent sur les fenêtres centrales.
    """

    log_mels: FloatArray  # (extraits, bandes, trames)
    labels: IntArray
    lengths: IntArray | None = None  # nombre de vraies trames de chaque extrait
    window_frames: int | None = None  # longueur de la fenêtre vue par le réseau
    silence_db: float | None = None  # valeur du silence ajouté (plancher du log-Mel, R2)


@dataclass(frozen=True)
class TrainedNetwork:
    """Un réseau entraîné et ce qu'il faut pour le réutiliser ou le citer."""

    network: nn.Module
    # Statistiques de SON entraînement : à réappliquer telles quelles en prédiction (R4).
    statistics: BandStatistics
    epochs_run: int


@dataclass(frozen=True)
class ValidatedNetwork:
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


def seed_everything(seed: int) -> None:
    """Fixe la graine de torch (CPU et GPU) et demande des convolutions déterministes (ENF-07)."""
    torch.manual_seed(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def train_with_validation(
    architecture: Architecture,
    train: LabeledSpectrograms,
    validation: LabeledSpectrograms,
    class_count: int,
    learning_rate: float,
    seed: int,
    config: FamilyAConfig,
    device: torch.device,
) -> ValidatedNetwork:
    """Réglage (P3) : entraîne jusqu'à max_epochs époques, garde la meilleure sur la validation.

    Après chaque époque, F1 macro sur la validation. Avec patience à None (configuration
    actuelle), on parcourt la courbe complète ; avec un entier, on s'arrête après `patience`
    époques sans amélioration. Puis on recharge les poids de la meilleure époque.
    """
    state = _start_training(architecture, train, class_count, learning_rate, seed, config, device)
    history: list[float] = []
    best_f1 = -1.0
    best_epoch = 0
    best_weights = copy.deepcopy(state.network.state_dict())
    for epoch in range(1, config.training.max_epochs + 1):
        train_one_epoch(state, train, class_count, config, device)
        # Étape 1 : F1 macro sur la validation, qui choisit la meilleure époque.
        score = validation_macro_f1(state.network, validation, state.statistics, config, device)
        history.append(score)
        # Étape 2 : meilleure époque jusqu'ici → on garde une copie de ses poids.
        if score > best_f1:
            best_f1 = score
            best_epoch = epoch
            best_weights = copy.deepcopy(state.network.state_dict())
        # Étape 3 : arrêt anticipé seulement si une patience est donnée.
        patience = config.training.patience
        if patience is None:
            continue
        if epoch - best_epoch >= patience:
            break
    # On revient aux poids de la meilleure époque.
    state.network.load_state_dict(best_weights)
    trained = TrainedNetwork(state.network, state.statistics, epochs_run=len(history))
    return ValidatedNetwork(
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
        batch_log_mels = _training_windows(train, batch_indices, state.generator)
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
    """F1 macro sur la validation, qui choisit la meilleure époque (Brique 4)."""
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
    # Étape 1 : statistiques de standardisation sur CET entraînement seulement (R4), calculées
    # sur ce que voit le réseau (les fenêtres centrales quand les extraits sont découpés).
    statistics = band_statistics(_statistics_windows(train))
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


def _training_windows(
    train: LabeledSpectrograms, batch_indices: IntArray, generator: np.random.Generator
) -> FloatArray:
    batch_log_mels = train.log_mels[batch_indices]
    if train.lengths is None or train.window_frames is None or train.silence_db is None:
        return batch_log_mels
    # Émotions (C12) : une fenêtre tirée au hasard dans chaque extrait, à chaque lot.
    batch_lengths = train.lengths[batch_indices]
    return random_windows(
        batch_log_mels, batch_lengths, train.window_frames, train.silence_db, generator
    )


def _statistics_windows(train: LabeledSpectrograms) -> FloatArray:
    if train.lengths is None or train.window_frames is None or train.silence_db is None:
        return train.log_mels
    return center_windows(train.log_mels, train.lengths, train.window_frames, train.silence_db)
