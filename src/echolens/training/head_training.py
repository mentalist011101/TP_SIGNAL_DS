"""Tête de la famille B et sa boucle d'entraînement (C11, Brique 4), sur CPU.

Seul module de C11 qui importe torch (extra [ml], installé d'office sur Kaggle). La
standardisation, la sélection des données et l'assemblage des résultats sont dans
echolens.training.heads, testés en CI sans torch.

Entraînement (Brique 4) : AdamW, schedule cosinus, entropie croisée sans poids de classes,
lots de batch_size, early stopping sur le F1 macro de validation. Les tableaux reçus ici sont
déjà standardisés avec les statistiques du train (R4).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn

from echolens.core.data.splits import esc50_round
from echolens.training.evaluation import IntArray, macro_f1
from echolens.training.heads import (
    FloatArray,
    HeadsConfig,
    HeadSetting,
    LabeledSet,
    SeedPredictions,
    Standardization,
    TuningOutcome,
    best_setting_index,
    grid_settings,
    predicted_classes,
    select_folds,
    standardization_stats,
    standardize_set,
)


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


@dataclass(frozen=True)
class EarlyStoppingResult:
    """Tête remise à sa meilleure époque, cette époque et son F1 macro de validation."""

    model: LayerWeightedHead
    best_epoch: int
    best_f1: float


@dataclass(frozen=True)
class TrainedHead:
    """Une tête finale, ses statistiques de standardisation et ses prédictions."""

    model: LayerWeightedHead
    stats: Standardization
    predictions: SeedPredictions


@dataclass(frozen=True)
class EmotionModelRun:
    """Émotions : réglages essayés, réglage retenu, une tête par graine."""

    outcomes: list[TuningOutcome]
    chosen: TuningOutcome
    heads: list[TrainedHead]
    validation_predictions: list[SeedPredictions]


@dataclass(frozen=True)
class Esc50RoundRun:
    """Un tour d'ESC-50 : réglages essayés, réglage retenu, prédictions de validation du
    réglage (graine tuning_seed), têtes finales sur 4 folds (une par graine)."""

    test_fold: int
    outcomes: list[TuningOutcome]
    chosen: TuningOutcome
    validation: LabeledSet
    validation_predictions: SeedPredictions
    test_targets: IntArray
    heads: list[TrainedHead]


def train_with_early_stopping(
    train: LabeledSet,
    validation: LabeledSet,
    setting: HeadSetting,
    config: HeadsConfig,
    class_count: int,
    seed: int,
) -> EarlyStoppingResult:
    """Entraîne au plus max_epochs époques ; garde l'époque au meilleur F1 macro de validation.

    Arrêt après patience époques sans amélioration stricte du F1 macro de validation.
    """
    model = _new_head(train, setting, config, class_count, seed)
    optimizer, schedule = _optimizer_and_schedule(model, setting, config)
    generator = torch.Generator().manual_seed(seed)
    best_f1 = -1.0
    best_epoch = 0
    best_state = copy.deepcopy(model.state_dict())
    for epoch in range(1, config.max_epochs + 1):
        _train_one_epoch(model, optimizer, train, config.batch_size, generator)
        schedule.step()
        validation_f1 = _macro_f1_of(model, validation)
        if validation_f1 > best_f1:
            best_f1 = validation_f1
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
        elif epoch - best_epoch >= config.patience:
            break
    model.load_state_dict(best_state)
    return EarlyStoppingResult(model=model, best_epoch=best_epoch, best_f1=best_f1)


def train_for_epochs(
    train: LabeledSet,
    setting: HeadSetting,
    config: HeadsConfig,
    class_count: int,
    seed: int,
    epochs: int,
) -> LayerWeightedHead:
    """Entraîne exactement epochs époques, sans validation ni early stopping (P3, final)."""
    model = _new_head(train, setting, config, class_count, seed)
    optimizer, schedule = _optimizer_and_schedule(model, setting, config)
    generator = torch.Generator().manual_seed(seed)
    for _ in range(epochs):
        _train_one_epoch(model, optimizer, train, config.batch_size, generator)
        schedule.step()
    return model


def predict_probabilities(model: LayerWeightedHead, features: FloatArray) -> FloatArray:
    """Probabilités (extraits, classes) : softmax des scores, en mode évaluation (sans dropout)."""
    model.eval()
    inputs = torch.from_numpy(features)
    with torch.no_grad():
        logits = model(inputs)
        probabilities = torch.softmax(logits, dim=1)
    return np.asarray(probabilities.numpy(), dtype=np.float32)


def learned_layer_weights(model: LayerWeightedHead) -> FloatArray:
    """softmax(a) en tableau numpy : un poids par couche, de somme 1 (E7)."""
    with torch.no_grad():
        weights = model.layer_weights()
    return np.asarray(weights.numpy(), dtype=np.float32)


def seed_predictions(model: LayerWeightedHead, features: FloatArray, seed: int) -> SeedPredictions:
    """Probabilités d'une tête et ses poids de couches, rangés avec leur graine."""
    probabilities = predict_probabilities(model, features)
    weights = learned_layer_weights(model)
    return SeedPredictions(seed=seed, probabilities=probabilities, layer_weights=weights)


def tune_head(
    train: LabeledSet, validation: LabeledSet, config: HeadsConfig, class_count: int
) -> tuple[list[TuningOutcome], list[EarlyStoppingResult]]:
    """Essaie chaque réglage de la grille avec la graine tuning_seed, early stopping compris."""
    outcomes: list[TuningOutcome] = []
    results: list[EarlyStoppingResult] = []
    for setting in grid_settings(config):
        result = train_with_early_stopping(
            train, validation, setting, config, class_count, config.tuning_seed
        )
        outcome = TuningOutcome(setting, result.best_epoch, result.best_f1)
        outcomes.append(outcome)
        results.append(result)
    return outcomes, results


def run_emotions(
    train_raw: LabeledSet,
    validation_raw: LabeledSet,
    test_raw: LabeledSet,
    config: HeadsConfig,
    class_count: int,
) -> EmotionModelRun:
    """Émotions (P1, Brique 4) : réglage sur la validation, puis une tête par graine.

    Chaque tête s'entraîne sur le train avec early stopping sur la validation ; le test n'est
    prédit qu'une fois, par la tête remise à sa meilleure époque.
    """
    # Étape 1 : statistiques du train seul, appliquées aux trois parties (R4).
    stats = standardization_stats(train_raw.features)
    train = standardize_set(train_raw, stats)
    validation = standardize_set(validation_raw, stats)
    test = standardize_set(test_raw, stats)
    # Étape 2 : réglage avec la graine tuning_seed.
    outcomes, _ = tune_head(train, validation, config, class_count)
    chosen = outcomes[best_setting_index(outcomes)]
    # Étape 3 : une tête par graine avec le réglage retenu.
    heads: list[TrainedHead] = []
    validation_predictions: list[SeedPredictions] = []
    for seed in config.seeds:
        result = train_with_early_stopping(
            train, validation, chosen.setting, config, class_count, seed
        )
        validation_predictions.append(seed_predictions(result.model, validation.features, seed))
        predictions = seed_predictions(result.model, test.features, seed)
        heads.append(TrainedHead(model=result.model, stats=stats, predictions=predictions))
    return EmotionModelRun(outcomes, chosen, heads, validation_predictions)


def run_esc50_round(
    features: FloatArray, targets: IntArray, folds: IntArray, test_fold: int, config: HeadsConfig
) -> Esc50RoundRun:
    """Un tour d'ESC-50 (P3) : réglage sur 3 folds et le fold k + 1, puis final sur 4 folds.

    L'entraînement final dure le nombre d'époques retenu au réglage, sans early stopping, puis
    on évalue une seule fois sur le fold k.
    """
    fold_count = len(np.unique(folds))
    round_folds = esc50_round(test_fold, fold_count)
    # Étape 1 : réglage sur 3 folds, choix sur le fold k + 1.
    tuning_raw = select_folds(features, targets, folds, round_folds.tuning_train_folds)
    validation_raw = select_folds(features, targets, folds, [round_folds.validation_fold])
    outcomes, chosen, validation, validation_predictions = _tune_esc50_round(
        tuning_raw, validation_raw, config
    )
    # Étape 2 : têtes finales sur les 4 folds hors test, une par graine.
    final_raw = select_folds(features, targets, folds, round_folds.final_train_folds)
    test_raw = select_folds(features, targets, folds, [test_fold])
    heads = _final_esc50_heads(final_raw, test_raw, chosen, config)
    return Esc50RoundRun(
        test_fold, outcomes, chosen, validation, validation_predictions, test_raw.targets, heads
    )


def save_head(path: Path, model: LayerWeightedHead) -> None:
    """Écrit les poids appris de la tête (state_dict de torch)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), path)


def _tune_esc50_round(
    tuning_raw: LabeledSet, validation_raw: LabeledSet, config: HeadsConfig
) -> tuple[list[TuningOutcome], TuningOutcome, LabeledSet, SeedPredictions]:
    # Statistiques des 3 folds d'entraînement du réglage seulement (R4).
    stats = standardization_stats(tuning_raw.features)
    tuning_train = standardize_set(tuning_raw, stats)
    validation = standardize_set(validation_raw, stats)
    outcomes, results = tune_head(tuning_train, validation, config, config.esc50_class_count)
    chosen_index = best_setting_index(outcomes)
    chosen_model = results[chosen_index].model
    # Prédictions de validation du réglage retenu, gardées pour le calibrage (E2, C13).
    validation_predictions = seed_predictions(chosen_model, validation.features, config.tuning_seed)
    return outcomes, outcomes[chosen_index], validation, validation_predictions


def _final_esc50_heads(
    train_raw: LabeledSet, test_raw: LabeledSet, chosen: TuningOutcome, config: HeadsConfig
) -> list[TrainedHead]:
    # Statistiques recalculées sur les 4 folds d'entraînement final (R4).
    stats = standardization_stats(train_raw.features)
    train = standardize_set(train_raw, stats)
    test = standardize_set(test_raw, stats)
    heads: list[TrainedHead] = []
    for seed in config.seeds:
        model = train_for_epochs(
            train, chosen.setting, config, config.esc50_class_count, seed, chosen.best_epoch
        )
        predictions = seed_predictions(model, test.features, seed)
        heads.append(TrainedHead(model=model, stats=stats, predictions=predictions))
    return heads


def _new_head(
    train: LabeledSet, setting: HeadSetting, config: HeadsConfig, class_count: int, seed: int
) -> LayerWeightedHead:
    # La graine fixe l'initialisation des poids : même graine, même tête de départ.
    torch.manual_seed(seed)
    layer_count = train.features.shape[1]
    dimension = train.features.shape[2]
    return LayerWeightedHead(
        layer_count, dimension, config.hidden_size, class_count, setting.dropout
    )


def _optimizer_and_schedule(
    model: LayerWeightedHead, setting: HeadSetting, config: HeadsConfig
) -> tuple[torch.optim.AdamW, torch.optim.lr_scheduler.CosineAnnealingLR]:
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=setting.learning_rate, weight_decay=config.weight_decay
    )
    # Cosinus sur max_epochs : au réglage comme au final, le taux suit la même courbe.
    schedule = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=config.max_epochs, eta_min=0.0
    )
    return optimizer, schedule


def _train_one_epoch(
    model: LayerWeightedHead,
    optimizer: torch.optim.Optimizer,
    train: LabeledSet,
    batch_size: int,
    generator: torch.Generator,
) -> None:
    model.train()
    features = torch.from_numpy(train.features)
    targets = torch.from_numpy(train.targets).long()
    # Nouvel ordre des extraits à chaque époque, tiré avec le générateur de la graine.
    order = torch.randperm(len(targets), generator=generator)
    loss_function = nn.CrossEntropyLoss()
    for start in range(0, len(order), batch_size):
        batch_index = order[start : start + batch_size]
        logits = model(features[batch_index])
        loss = loss_function(logits, targets[batch_index])
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()


def _macro_f1_of(model: LayerWeightedHead, labeled: LabeledSet) -> float:
    probabilities = predict_probabilities(model, labeled.features)
    y_pred = predicted_classes(probabilities)
    return macro_f1(labeled.targets, y_pred)
