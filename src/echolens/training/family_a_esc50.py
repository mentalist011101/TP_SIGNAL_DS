"""Famille A (C9) : un tour de validation croisée sur ESC-50 (P3), avec torch.

Au tour k : réglage du taux d'apprentissage et du nombre d'époques en entraînant sur 3 folds,
en suivant le F1 du fold k + 1 sur la courbe complète des 150 époques ; puis, réglages fixés,
entraînement final sur les 4 folds hors test, une fois par graine, et une seule évaluation sur
le fold k. La boucle elle-même
(echolens.training.family_a_models) ne sait rien d'ESC-50.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from echolens.core.data.splits import Esc50Round, esc50_round
from echolens.core.models.family_a import Architecture
from echolens.training.evaluation import accuracy, macro_f1
from echolens.training.family_a import FamilyAConfig, LogMelSet, band_statistics, fold_indices
from echolens.training.family_a_models import (
    LabeledSpectrograms,
    TrainedNetwork,
    predict,
    predicted_classes,
    train_fixed_epochs,
    train_with_validation,
)
from echolens.training.family_a_report import (
    RoundIndices,
    RoundResult,
    SeedRun,
    TuningOutcome,
    TuningTrial,
    choose_trial,
)


def run_esc50_round(
    architecture: Architecture,
    log_mel_set: LogMelSet,
    test_fold: int,
    fold_count: int,
    class_count: int,
    config: FamilyAConfig,
    device: torch.device,
    weights_dir: Path,
) -> RoundResult:
    """Un tour k complet (P3) : réglage sur le fold k + 1, puis 3 entraînements finaux."""
    # Étape 1 : rôle des folds de ce tour, puis positions des extraits de chaque partie.
    roles = esc50_round(test_fold, fold_count)
    indices = round_indices(log_mel_set, roles)
    # Étape 2 : réglage sur 3 folds, meilleure époque choisie sur le fold k + 1, sans le test.
    tuning_train = _subset(log_mel_set, indices.tuning_train)
    validation = _subset(log_mel_set, indices.validation)
    tuning = tune(architecture, tuning_train, validation, class_count, config, device)
    # Étape 3 : réglages fixés, entraînements finaux sur les 4 folds hors test.
    final_train = _subset(log_mel_set, indices.final_train)
    test = _subset(log_mel_set, indices.test)
    runs = _final_runs(architecture, final_train, test, tuning.chosen, class_count, config, device)
    _save_all_weights(runs, architecture, test_fold, tuning.chosen, class_count, weights_dir)
    final_statistics = band_statistics(final_train.log_mels)
    seed_runs = [seed_run for seed_run, _ in runs]
    return RoundResult(
        test_fold=test_fold,
        validation_fold=roles.validation_fold,
        indices=indices,
        tuning=tuning,
        validation_labels=validation.labels,
        test_labels=test.labels,
        final_statistics=final_statistics,
        runs=seed_runs,
    )


def round_indices(log_mel_set: LogMelSet, roles: Esc50Round) -> RoundIndices:
    """Positions des extraits de chaque partie d'un tour ; refuse tout chevauchement (P3)."""
    folds = log_mel_set.folds
    indices = RoundIndices(
        tuning_train=fold_indices(folds, roles.tuning_train_folds),
        validation=fold_indices(folds, [roles.validation_fold]),
        final_train=fold_indices(folds, roles.final_train_folds),
        test=fold_indices(folds, [roles.test_fold]),
    )
    _check_disjoint(indices.test, indices.final_train)
    _check_disjoint(indices.validation, indices.tuning_train)
    return indices


def tune(
    architecture: Architecture,
    tuning_train: LabeledSpectrograms,
    validation: LabeledSpectrograms,
    class_count: int,
    config: FamilyAConfig,
    device: torch.device,
) -> TuningOutcome:
    """Réglage (P3) : un essai par taux d'apprentissage, le meilleur F1 de validation gagne."""
    trials, networks = _tuning_trials(
        architecture, tuning_train, validation, class_count, config, device
    )
    chosen_position = choose_trial(trials)
    chosen_network = networks[chosen_position]
    # Le modèle réglé prédit le fold k + 1 : ces probabilités serviront à la calibration (E2).
    validation_predictions = predict(
        chosen_network.network, validation.log_mels, chosen_network.statistics, config, device
    )
    return TuningOutcome(
        trials=trials,
        chosen=trials[chosen_position],
        statistics=chosen_network.statistics,
        validation_probabilities=validation_predictions.probabilities,
        validation_attention=validation_predictions.attention,
    )


def save_weights(
    trained: TrainedNetwork,
    architecture: Architecture,
    class_count: int,
    learning_rate: float,
    path: Path,
) -> None:
    """Écrit les poids d'un réseau avec SES statistiques de standardisation (sortie Kaggle).

    L'application devra standardiser avec exactement ces moyennes et écarts-types (R4).
    """
    # Poids copiés sur le CPU : le fichier se relit sur une machine sans GPU (application).
    weights = trained.network.state_dict()
    cpu_weights = {}
    for name, tensor in weights.items():
        cpu_weights[name] = tensor.cpu()
    checkpoint = {
        "architecture": architecture,
        "class_count": class_count,
        "learning_rate": learning_rate,
        "epochs": trained.epochs_run,
        "state_dict": cpu_weights,
        "band_mean": torch.from_numpy(trained.statistics.mean),
        "band_std": torch.from_numpy(trained.statistics.std),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, path)


def _tuning_trials(
    architecture: Architecture,
    tuning_train: LabeledSpectrograms,
    validation: LabeledSpectrograms,
    class_count: int,
    config: FamilyAConfig,
    device: torch.device,
) -> tuple[list[TuningTrial], list[TrainedNetwork]]:
    # Un entraînement par taux d'apprentissage, même graine pour tous ; la validation suit.
    trials = []
    networks = []
    for learning_rate in config.training.learning_rates:
        stopped = train_with_validation(
            architecture,
            tuning_train,
            validation,
            class_count,
            learning_rate,
            config.training.tuning_seed,
            config,
            device,
        )
        trial = TuningTrial(
            learning_rate=learning_rate,
            best_epoch=stopped.best_epoch,
            best_validation_f1=stopped.best_validation_f1,
            epochs_run=stopped.trained.epochs_run,
            validation_f1_history=stopped.validation_f1_history,
        )
        trials.append(trial)
        networks.append(stopped.trained)
    return trials, networks


def _final_runs(
    architecture: Architecture,
    final_train: LabeledSpectrograms,
    test: LabeledSpectrograms,
    chosen: TuningTrial,
    class_count: int,
    config: FamilyAConfig,
    device: torch.device,
) -> list[tuple[SeedRun, TrainedNetwork]]:
    runs = []
    for seed in config.training.final_seeds:
        trained = train_fixed_epochs(
            architecture,
            final_train,
            class_count,
            chosen.learning_rate,
            chosen.best_epoch,
            seed,
            config,
            device,
        )
        # Évaluation unique sur le fold de test, avec les statistiques du train final (R4).
        predictions = predict(trained.network, test.log_mels, trained.statistics, config, device)
        y_pred = predicted_classes(predictions)
        seed_run = SeedRun(
            seed=seed,
            macro_f1=macro_f1(test.labels, y_pred),
            accuracy=accuracy(test.labels, y_pred),
            predictions=y_pred,
            probabilities=predictions.probabilities,
            attention=predictions.attention,
        )
        runs.append((seed_run, trained))
    return runs


def _save_all_weights(
    runs: list[tuple[SeedRun, TrainedNetwork]],
    architecture: Architecture,
    test_fold: int,
    chosen: TuningTrial,
    class_count: int,
    weights_dir: Path,
) -> None:
    for seed_run, trained in runs:
        path = weights_dir / f"{architecture}_fold{test_fold}_seed{seed_run.seed}.pt"
        save_weights(trained, architecture, class_count, chosen.learning_rate, path)


def _subset(log_mel_set: LogMelSet, indices: np.ndarray) -> LabeledSpectrograms:
    # Copie des seuls extraits demandés : le reste du jeu n'entre pas dans l'entraînement.
    log_mels = log_mel_set.log_mels[indices]
    labels = log_mel_set.labels[indices]
    return LabeledSpectrograms(log_mels=log_mels, labels=labels)


def _check_disjoint(first: np.ndarray, second: np.ndarray) -> None:
    # Garde-fou de P3 : un extrait ne peut pas être à la fois évalué et appris.
    shared = np.intersect1d(first, second)
    if len(shared) > 0:
        raise ValueError(f"Fuite : {len(shared)} extraits à la fois en évaluation et en train")
