"""Famille A (C9) : log-Mel, standardisation par bande et augmentations, sans torch.

Ce module n'importe jamais torch : la CI n'installe pas l'extra [ml], et ses fonctions sont
testées sans lui. Les réseaux et la boucle d'entraînement sont dans
echolens.training.family_a_models.

Ordre des opérations sur un lot d'entraînement (P6, R4) :
1. gain, en dB absolus, AVANT la standardisation : multiplier le volume par g revient à
   ajouter 20·log10(g) dB à toutes les cases du log-Mel ;
2. standardisation par bande, avec la moyenne et l'écart-type de l'entraînement seul (R4) ;
3. rotation circulaire des trames ;
4. SpecAugment, APRÈS la standardisation : un masque à 0 vaut alors la moyenne du train
   (P6). Avant, 0 dB serait un son fort, puisque le plancher est à −100 dB (R2) ;
5. mixup : mélange de deux extraits et de leurs cibles.
La validation et le test ne passent que par l'étape 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field

from echolens.config import CONFIG_DIR, load_yaml
from echolens.core.audio import load_audio
from echolens.core.data.manifest import ManifestRow, audio_path
from echolens.core.features import FeatureConfig, FloatArray, log_mel_spectrogram
from echolens.training.esc50_svm import esc50_target
from echolens.training.evaluation import IntArray

FAMILY_A_CONFIG_PATH = CONFIG_DIR / "family_a.yaml"
# P6 : valeur des masques de SpecAugment, appliqués après la standardisation. 0 est alors la
# moyenne de l'entraînement : le masque retire de l'information sans ajouter d'énergie.
MASK_VALUE = 0.0


class NetworkConfig(BaseModel):
    """Forme des réseaux CNN et CRNN (Brique 4)."""

    channels: list[int] = Field(min_length=1)
    kernel_size: int = Field(gt=0)
    padding: int = Field(ge=0)
    pool_size: int = Field(gt=0)
    dropout: float = Field(ge=0, lt=1)
    gru_hidden_size: int = Field(gt=0)


class AugmentationConfig(BaseModel):
    """Augmentations de l'entraînement (P6)."""

    gain_db: float = Field(ge=0)
    frequency_mask_count: int = Field(ge=0)
    frequency_mask_max_bands: int = Field(ge=0)
    time_mask_count: int = Field(ge=0)
    time_mask_max_frames: int = Field(ge=0)
    mixup_alpha: float = Field(gt=0)


class TrainingConfig(BaseModel):
    """Optimisation, réglage et graines (P3, Brique 4)."""

    batch_size: int = Field(gt=0)
    weight_decay: float = Field(ge=0)
    max_epochs: int = Field(gt=0)
    patience: int = Field(gt=0)
    learning_rates: list[float] = Field(min_length=1)
    tuning_seed: int
    final_seeds: list[int] = Field(min_length=1)
    prediction_batch_size: int = Field(gt=0)


class FamilyAConfig(BaseModel):
    """Contenu de configs/family_a.yaml."""

    network: NetworkConfig
    augmentation: AugmentationConfig
    training: TrainingConfig


@dataclass(frozen=True)
class BandStatistics:
    """Moyenne et écart-type de chaque bande Mel, calculés sur un ensemble d'entraînement (R4)."""

    mean: FloatArray
    std: FloatArray


@dataclass(frozen=True)
class MixedBatch:
    """Lot prêt pour le réseau : entrées et cibles après mixup."""

    inputs: FloatArray  # (extraits, bandes, trames)
    targets: FloatArray  # (extraits, classes), chaque ligne somme à 1
    mix_weight: float  # λ : part de l'extrait d'origine dans le mélange
    partner_indices: IntArray  # extrait mélangé avec chaque extrait du lot


@dataclass(frozen=True)
class LogMelSet:
    """Log-Mel de tous les extraits d'un jeu, dans l'ordre du manifeste (R6)."""

    paths: list[str]
    log_mels: FloatArray  # (extraits, bandes, trames), en dB absolus (R2)
    labels: IntArray
    folds: IntArray


def load_family_a_config(path: Path = FAMILY_A_CONFIG_PATH) -> FamilyAConfig:
    """Lit configs/family_a.yaml."""
    content = load_yaml(path)
    return FamilyAConfig(**content)


def band_statistics(log_mels: FloatArray) -> BandStatistics:
    """Moyenne et écart-type de chaque bande sur tous les extraits et toutes les trames (R4).

    log_mels a la forme (extraits, bandes, trames) et ne doit contenir QUE l'entraînement du
    tour en cours : ces statistiques servent ensuite telles quelles pour la validation et le
    test, qui ne doivent rien apprendre au modèle.
    """
    # Étape 1 : on réunit les axes 0 (extraits) et 2 (trames) ; il reste une valeur par bande.
    # Le calcul se fait en float64 : une somme de millions de float32 perdrait des décimales.
    mean = log_mels.mean(axis=(0, 2), dtype=np.float64)
    std = log_mels.std(axis=(0, 2), dtype=np.float64)
    # Étape 2 : une bande constante ne peut pas être standardisée (division par zéro).
    if np.any(std == 0.0):
        raise ValueError("Une bande Mel est constante sur tout l'entraînement : écart-type nul")
    return BandStatistics(mean=mean.astype(np.float32), std=std.astype(np.float32))


def standardize(log_mels: FloatArray, statistics: BandStatistics) -> FloatArray:
    """Centre et réduit chaque bande avec les statistiques de l'entraînement (R4).

    Après cette étape, chaque bande de l'entraînement a une moyenne 0 et un écart-type 1.
    """
    band_count = len(statistics.mean)
    # Forme (1, bandes, 1) : la même valeur pour tous les extraits et toutes les trames.
    mean_per_band = statistics.mean.reshape(1, band_count, 1)
    std_per_band = statistics.std.reshape(1, band_count, 1)
    centered = log_mels - mean_per_band
    standardized = centered / std_per_band
    return standardized.astype(np.float32)


def random_gain(
    log_mels: FloatArray, max_gain_db: float, generator: np.random.Generator
) -> FloatArray:
    """Ajoute à chaque extrait une constante tirée au hasard dans [−max_gain_db ; +max_gain_db] dB.

    Augmentation de gain (P6), tirage uniforme, une valeur par extrait.

    En dB absolus, jouer un son g fois plus fort ajoute 20·log10(g) dB partout : le gain est
    donc une simple addition, à faire AVANT la standardisation.
    """
    clip_count = log_mels.shape[0]
    # Forme (extraits, 1, 1) : une constante par extrait, la même sur toutes ses bandes et trames.
    gain_shape = (clip_count, 1, 1)
    gains_db = generator.uniform(low=-max_gain_db, high=max_gain_db, size=gain_shape)
    gained = log_mels + gains_db
    return np.asarray(gained, dtype=np.float32)


def circular_time_shift(log_mels: FloatArray, generator: np.random.Generator) -> FloatArray:
    """Fait tourner les trames de chaque extrait d'un nombre tiré entre 0 et trames − 1 (P6).

    Les trames qui sortent à droite reviennent à gauche : aucune valeur n'est perdue ni créée.
    Le modèle apprend ainsi qu'un aboiement reste un aboiement à n'importe quel instant.
    """
    frame_count = log_mels.shape[2]
    shifted = np.empty_like(log_mels)
    for index in range(len(log_mels)):
        shift = int(generator.integers(low=0, high=frame_count))
        shifted[index] = np.roll(log_mels[index], shift, axis=1)
    return shifted


def random_mask_range(size: int, max_width: int, generator: np.random.Generator) -> tuple[int, int]:
    """Début et fin (exclue) d'un masque de largeur tirée entre 0 et max_width (SpecAugment)."""
    largest_width = min(max_width, size)
    width = int(generator.integers(low=0, high=largest_width + 1))
    start = int(generator.integers(low=0, high=size - width + 1))
    stop = start + width
    return start, stop


def spec_augment(
    standardized: FloatArray, config: AugmentationConfig, generator: np.random.Generator
) -> FloatArray:
    """Masques de fréquence puis de temps à 0, sur un log-Mel DÉJÀ standardisé (P6).

    Chaque extrait reçoit ses propres masques. Le masque oblige le modèle à reconnaître la
    classe même quand une bande de fréquences ou un moment du son manque.
    """
    masked = standardized.copy()
    band_count = masked.shape[1]
    frame_count = masked.shape[2]
    for clip in masked:
        # Étape 1 : masques de fréquence, des bandes Mel entières mises à la moyenne du train.
        for _ in range(config.frequency_mask_count):
            start, stop = random_mask_range(band_count, config.frequency_mask_max_bands, generator)
            clip[start:stop, :] = MASK_VALUE
        # Étape 2 : masques de temps, des trames entières mises à la moyenne du train.
        for _ in range(config.time_mask_count):
            start, stop = random_mask_range(frame_count, config.time_mask_max_frames, generator)
            clip[:, start:stop] = MASK_VALUE
    return masked


def one_hot(labels: IntArray, class_count: int) -> FloatArray:
    """Cibles « une case à 1 » : la ligne i vaut 1 dans la colonne de la classe de l'extrait i."""
    targets = np.zeros((len(labels), class_count), dtype=np.float32)
    for row, label in enumerate(labels):
        targets[row, label] = 1.0
    return targets


def mixup(
    inputs: FloatArray, targets: FloatArray, alpha: float, generator: np.random.Generator
) -> MixedBatch:
    """Mélange chaque extrait avec un autre du lot, entrées ET cibles avec le même λ (P6).

    x = λ·x_i + (1 − λ)·x_j et y = λ·y_i + (1 − λ)·y_j, avec λ ~ Beta(α, α). Avec α = 0,2,
    λ est le plus souvent proche de 0 ou de 1 : un son domine, l'autre est en fond.
    """
    mix_weight = float(generator.beta(alpha, alpha))
    partner_indices = generator.permutation(len(inputs))
    partner_inputs = inputs[partner_indices]
    partner_targets = targets[partner_indices]
    mixed_inputs = mix_weight * inputs + (1.0 - mix_weight) * partner_inputs
    mixed_targets = mix_weight * targets + (1.0 - mix_weight) * partner_targets
    return MixedBatch(
        inputs=mixed_inputs.astype(np.float32),
        targets=mixed_targets.astype(np.float32),
        mix_weight=mix_weight,
        partner_indices=partner_indices.astype(np.int_),
    )


def augment_batch(
    log_mels: FloatArray,
    labels: IntArray,
    statistics: BandStatistics,
    class_count: int,
    config: AugmentationConfig,
    generator: np.random.Generator,
) -> MixedBatch:
    """Prépare un lot d'ENTRAÎNEMENT : gain, standardisation, rotation, masques, mixup (P6, R4)."""
    # Étape 1 : gain en dB absolus, avant la standardisation.
    gained = random_gain(log_mels, config.gain_db, generator)
    # Étape 2 : standardisation avec les statistiques du train de ce tour (R4).
    standardized = standardize(gained, statistics)
    # Étape 3 : rotation circulaire des trames.
    shifted = circular_time_shift(standardized, generator)
    # Étape 4 : SpecAugment, après la standardisation, masques à 0 (P6).
    masked = spec_augment(shifted, config, generator)
    # Étape 5 : mixup des entrées et des cibles.
    targets = one_hot(labels, class_count)
    return mixup(masked, targets, config.mixup_alpha, generator)


def fold_indices(folds: IntArray, kept_folds: list[int]) -> IntArray:
    """Positions (ordre du manifeste) des extraits dont le fold est dans kept_folds (P3)."""
    is_kept = np.isin(folds, kept_folds)
    indices = np.flatnonzero(is_kept)
    return indices.astype(np.int_)


def compute_esc50_log_mels(
    rows: list[ManifestRow], datasets_dir: Path, config: FeatureConfig
) -> LogMelSet:
    """Log-Mel (R2) de chaque extrait d'ESC-50, calculé une seule fois (R5, R6).

    Chaque audio entre en mono 16 kHz par load_audio (D1, D2), puis passe par le module unique
    de features avec configs/features.yaml. 5 s donnent 64 bandes × 501 trames.
    """
    spectrograms = []
    labels = []
    folds = []
    for row in rows:
        if row.fold is None:
            raise ValueError(f"Fold manquant dans le manifeste pour {row.path}")
        path = audio_path(row, datasets_dir)
        signal = load_audio(path)
        spectrogram = log_mel_spectrogram(signal, config)
        spectrograms.append(spectrogram)
        labels.append(esc50_target(row.path))
        folds.append(row.fold)
    return LogMelSet(
        paths=[row.path for row in rows],
        log_mels=np.stack(spectrograms),
        labels=np.array(labels, dtype=np.int_),
        folds=np.array(folds, dtype=np.int_),
    )


def save_log_mels(log_mel_set: LogMelSet, path: Path) -> None:
    """Écrit le jeu de log-Mel dans un .npz (sortie Kaggle, jamais sur GitHub)."""
    paths = np.array(log_mel_set.paths, dtype=np.str_)
    np.savez(
        path,
        paths=paths,
        log_mels=log_mel_set.log_mels,
        labels=log_mel_set.labels,
        folds=log_mel_set.folds,
    )


def load_log_mels(path: Path) -> LogMelSet:
    """Relit un fichier écrit par save_log_mels, entièrement en mémoire."""
    with np.load(path) as content:
        paths = [str(item) for item in content["paths"]]
        return LogMelSet(
            paths=paths,
            log_mels=content["log_mels"],
            labels=content["labels"],
            folds=content["folds"],
        )
