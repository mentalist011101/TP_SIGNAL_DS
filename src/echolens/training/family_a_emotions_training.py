"""Famille A sur les émotions (C12) : réglage et graines avec torch, sans réentraînement.

Un seul découpage par acteur (P1) : train, validation, test. Le taux d'apprentissage est
choisi sur la validation avec la graine de réglage ; puis, pour chaque graine, le réseau suit
la courbe complète (100 époques, sans arrêt anticipé) et garde sa meilleure époque de
validation. Contrairement à ESC-50, il n'y a pas de folds à réunir : on ne réentraîne pas.

La boucle est celle de C9 (echolens.training.family_a_models.train_with_validation) : seuls
changent les 6 sorties et la fenêtre de 3 s tirée au hasard dans chaque extrait du train.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch

from echolens.core.frame_windows import center_windows
from echolens.core.models.family_a import Architecture
from echolens.training.evaluation import IntArray
from echolens.training.family_a import EmotionTrainingConfig, FamilyAConfig
from echolens.training.family_a_emotions import EmotionLogMelSet, split_indices
from echolens.training.family_a_models import (
    LabeledSpectrograms,
    Predictions,
    TrainedNetwork,
    ValidatedNetwork,
    predict,
    train_with_validation,
)
from echolens.training.family_a_report import TuningTrial, choose_trial


@dataclass(frozen=True)
class EmotionParts:
    """Les trois parties du découpage par acteur (P1), prêtes pour le réseau."""

    train: LabeledSpectrograms  # extraits entiers : fenêtre tirée au hasard à chaque lot
    validation: LabeledSpectrograms  # fenêtres centrales de 3 s
    test: LabeledSpectrograms  # fenêtres centrales de 3 s
    validation_indices: IntArray
    test_indices: IntArray


@dataclass(frozen=True)
class EmotionSeedRun:
    """Une graine : meilleure époque de validation, et prédictions de validation et de test."""

    seed: int
    best_epoch: int
    best_validation_f1: float
    validation_f1_history: list[float]
    trained: TrainedNetwork
    validation: Predictions
    test: Predictions


@dataclass(frozen=True)
class EmotionArchitectureRun:
    """Un réseau (CNN ou CRNN) : taux essayés, taux retenu, une exécution par graine."""

    architecture: Architecture
    trials: list[TuningTrial]
    chosen_learning_rate: float
    runs: list[EmotionSeedRun]


def emotion_training_config(config: FamilyAConfig) -> FamilyAConfig:
    """Configuration de la boucle pour les émotions : 100 époques, cosinus sur 100, sans arrêt."""
    emotions = require_emotions(config)
    update = {"max_epochs": emotions.max_epochs, "patience": None}
    training = config.training.model_copy(update=update)
    return config.model_copy(update={"training": training})


def require_emotions(config: FamilyAConfig) -> EmotionTrainingConfig:
    """La section emotions de configs/family_a.yaml ; ValueError si elle manque."""
    if config.emotions is None:
        raise ValueError("Section emotions absente de configs/family_a.yaml")
    return config.emotions


def emotion_parts(
    log_mel_set: EmotionLogMelSet, window_frames: int, silence_db: float
) -> EmotionParts:
    """Train (extraits entiers, découpe au hasard), validation et test (fenêtres centrales)."""
    train_indices = split_indices(log_mel_set, "train")
    train = LabeledSpectrograms(
        log_mels=log_mel_set.log_mels[train_indices],
        labels=log_mel_set.targets[train_indices],
        lengths=log_mel_set.lengths[train_indices],
        window_frames=window_frames,
        silence_db=silence_db,
    )
    validation_indices = split_indices(log_mel_set, "validation")
    test_indices = split_indices(log_mel_set, "test")
    return EmotionParts(
        train=train,
        validation=_centered_part(log_mel_set, validation_indices, window_frames, silence_db),
        test=_centered_part(log_mel_set, test_indices, window_frames, silence_db),
        validation_indices=validation_indices,
        test_indices=test_indices,
    )


def run_emotion_architecture(
    architecture: Architecture,
    parts: EmotionParts,
    class_count: int,
    config: FamilyAConfig,
    device: torch.device,
) -> EmotionArchitectureRun:
    """Réglage du taux (graine de réglage), puis une exécution par graine (Brique 4)."""
    emotions = require_emotions(config)
    loop_config = emotion_training_config(config)
    # Étape 1 : un entraînement par taux d'apprentissage, avec la graine de réglage.
    trials: list[TuningTrial] = []
    tuned: list[ValidatedNetwork] = []
    for learning_rate in emotions.learning_rates:
        validated = train_with_validation(
            architecture,
            parts.train,
            parts.validation,
            class_count,
            learning_rate,
            emotions.tuning_seed,
            loop_config,
            device,
        )
        trials.append(_trial(learning_rate, validated))
        tuned.append(validated)
    chosen_position = choose_trial(trials)
    chosen_learning_rate = trials[chosen_position].learning_rate
    # Étape 2 : une exécution par graine. La graine de réglage avec le taux retenu est
    # exactement l'entraînement déjà fait (même graine, même taux, mêmes données) : réutilisé.
    runs = []
    for seed in emotions.seeds:
        validated = tuned[chosen_position]
        if seed != emotions.tuning_seed:
            validated = train_with_validation(
                architecture,
                parts.train,
                parts.validation,
                class_count,
                chosen_learning_rate,
                seed,
                loop_config,
                device,
            )
        runs.append(_seed_run(seed, validated, parts, loop_config, device))
    return EmotionArchitectureRun(architecture, trials, chosen_learning_rate, runs)


def _seed_run(
    seed: int,
    validated: ValidatedNetwork,
    parts: EmotionParts,
    config: FamilyAConfig,
    device: torch.device,
) -> EmotionSeedRun:
    # Le test n'est prédit qu'une fois par graine, avec la meilleure époque de validation.
    trained = validated.trained
    validation = predict(
        trained.network, parts.validation.log_mels, trained.statistics, config, device
    )
    test = predict(trained.network, parts.test.log_mels, trained.statistics, config, device)
    return EmotionSeedRun(
        seed=seed,
        best_epoch=validated.best_epoch,
        best_validation_f1=validated.best_validation_f1,
        validation_f1_history=validated.validation_f1_history,
        trained=trained,
        validation=validation,
        test=test,
    )


def _trial(learning_rate: float, validated: ValidatedNetwork) -> TuningTrial:
    return TuningTrial(
        learning_rate=learning_rate,
        best_epoch=validated.best_epoch,
        best_validation_f1=validated.best_validation_f1,
        epochs_run=validated.trained.epochs_run,
        validation_f1_history=validated.validation_f1_history,
    )


def _centered_part(
    log_mel_set: EmotionLogMelSet, indices: IntArray, window_frames: int, silence_db: float
) -> LabeledSpectrograms:
    windows = center_windows(
        log_mel_set.log_mels[indices], log_mel_set.lengths[indices], window_frames, silence_db
    )
    return LabeledSpectrograms(log_mels=windows, labels=log_mel_set.targets[indices])
