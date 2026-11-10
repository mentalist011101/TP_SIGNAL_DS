"""Référence classique sur ESC-50 : résumé MFCC de chaque extrait, puis SVM (P3, P4, P5).

Protocole (P3) : validation croisée sur les 5 folds officiels. Pour chaque fold de test k,
C est choisi sur le fold k + 1 (1 après 5) en entraînant sur les 3 autres, puis le modèle
est réentraîné sur les 4 folds hors test et évalué une seule fois sur le fold k.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from echolens.config import load_yaml
from echolens.core.audio import load_audio
from echolens.core.data.manifest import ManifestRow, audio_path
from echolens.core.features import FeatureConfig, FloatArray, mfcc
from echolens.training.evaluation import (
    FloatMatrix,
    IntArray,
    accuracy,
    macro_f1,
    mean_and_std,
    normalized_confusion,
    to_categories,
)

FeatureMatrix = npt.NDArray[np.float64]


class SvmConfig(BaseModel):
    """Paramètres de la référence MFCC + SVM (configs/baseline_svm.yaml)."""

    kernel: Literal["rbf", "linear", "poly", "sigmoid"] = "rbf"
    gamma: Literal["scale", "auto"] | float = "scale"
    c_grid: list[float] = Field(min_length=1)
    category_names: list[str] = Field(min_length=1)

    @classmethod
    def from_yaml(cls, path: Path) -> SvmConfig:
        """Charge la configuration depuis un fichier YAML."""
        return cls(**load_yaml(path))


@dataclass(frozen=True)
class FoldResult:
    """Résultat d'un tour de validation croisée : un fold de test."""

    test_fold: int
    chosen_c: float
    macro_f1: float
    accuracy: float
    y_true: IntArray
    y_pred: IntArray
    model: Pipeline


@dataclass(frozen=True)
class CrossValidationResult:
    """Résultats des 5 tours, avec moyennes et matrices cumulées sur les folds de test."""

    folds: list[FoldResult]
    macro_f1_mean: float
    macro_f1_std: float
    accuracy_mean: float
    accuracy_std: float
    confusion_classes: FloatMatrix
    confusion_categories: FloatMatrix


def summarize_mfcc(signal: FloatArray, config: FeatureConfig) -> FeatureMatrix:
    """Résume un extrait en 240 nombres : moyenne et écart-type dans le temps (R3, P5).

    mfcc renvoie 120 lignes (40 MFCC, 40 Δ, 40 ΔΔ) et une colonne par trame de 10 ms.
    Un SVM attend un vecteur de taille fixe : on garde, pour chaque ligne, sa moyenne (le
    timbre moyen) et son écart-type (sa variabilité), soit 2 × 120 = 240 valeurs.
    """
    coefficients = mfcc(signal, config, with_deltas=True)
    mean_per_coefficient = coefficients.mean(axis=1)
    std_per_coefficient = coefficients.std(axis=1)
    summary = np.concatenate([mean_per_coefficient, std_per_coefficient])
    return np.asarray(summary, dtype=np.float64)


def extract_features(
    rows: list[ManifestRow], datasets_dir: Path, config: FeatureConfig, cache_path: Path
) -> tuple[FeatureMatrix, IntArray, IntArray]:
    """Features (n, 240), classes (target d'ESC-50, 0 à 49) et folds de chaque extrait.

    Le résultat est enregistré dans cache_path (.npz) ; si ce fichier existe, il est relu
    au lieu de tout recalculer. Supprimer le cache après un changement de features.yaml.
    """
    if cache_path.exists():
        cached = np.load(cache_path)
        return cached["features"], cached["targets"], cached["folds"]

    summaries = []
    target_list = []
    fold_list = []
    for row in rows:
        # Chemin donné par le manifeste et datasets_dir, jamais construit à la main.
        path = audio_path(row, datasets_dir)
        # Mono 16 kHz float32 (D1, D2), comme dans l'application.
        signal = load_audio(path)
        summary = summarize_mfcc(signal, config)
        target = esc50_target(row.path)
        fold = _fold_of(row)
        summaries.append(summary)
        target_list.append(target)
        fold_list.append(fold)

    features = np.stack(summaries)
    targets = np.array(target_list, dtype=np.int_)
    folds = np.array(fold_list, dtype=np.int_)
    np.savez(cache_path, features=features, targets=targets, folds=folds)
    return features, targets, folds


def esc50_target(path: str) -> int:
    """Classe d'ESC-50 (0 à 49), dernier champ du nom {fold}-{id}-{take}-{target}.wav."""
    stem = Path(path).stem
    fields = stem.split("-")
    return int(fields[3])


def make_svm(c_value: float, svm_config: SvmConfig) -> Pipeline:
    """Pipeline StandardScaler puis SVC (P5).

    Le scaler fait partie du pipeline : fit() apprend sa moyenne et son écart-type sur les
    seules données d'entraînement passées à fit(), puis predict() les réutilise tels quels
    sur la validation ou le test. Aucune statistique ne vient donc du fold évalué (R4).
    """
    scaler = StandardScaler(with_mean=True, with_std=True)
    classifier = SVC(C=c_value, kernel=svm_config.kernel, gamma=svm_config.gamma)
    return Pipeline([("scaler", scaler), ("svm", classifier)])


def validation_fold(test_fold: int, n_folds: int = 5) -> int:
    """Fold de validation associé à un fold de test : le suivant, 1 après le dernier (P3)."""
    return test_fold % n_folds + 1


def choose_c(
    features: FeatureMatrix,
    targets: IntArray,
    folds: IntArray,
    test_fold: int,
    svm_config: SvmConfig,
) -> float:
    """Choisit C au meilleur F1 macro sur le fold de validation, sans voir le fold de test (P3).

    Entraînement sur les 3 folds qui ne sont ni le test ni la validation. En cas d'égalité,
    le premier C de la grille (le plus simple) est gardé.
    """
    n_folds = len(np.unique(folds))
    validation = validation_fold(test_fold, n_folds)
    is_validation = folds == validation
    is_not_test = folds != test_fold
    is_not_validation = folds != validation
    is_train = is_not_test & is_not_validation

    best_c = svm_config.c_grid[0]
    best_score = -1.0
    for c_value in svm_config.c_grid:
        model = make_svm(c_value, svm_config)
        model.fit(features[is_train], targets[is_train])
        predictions = model.predict(features[is_validation])
        score = macro_f1(targets[is_validation], predictions)
        if score > best_score:
            best_score = score
            best_c = c_value
    return best_c


def run_fold(
    features: FeatureMatrix,
    targets: IntArray,
    folds: IntArray,
    test_fold: int,
    svm_config: SvmConfig,
) -> FoldResult:
    """Un tour : choix de C, réentraînement sur les 4 folds hors test, évaluation sur le test."""
    # Étape 1 : C choisi sans le fold de test.
    chosen_c = choose_c(features, targets, folds, test_fold, svm_config)
    # Étape 2 : réentraînement avec ce C sur tout ce qui n'est pas le test (validation incluse).
    is_test = folds == test_fold
    is_train = ~is_test
    model = make_svm(chosen_c, svm_config)
    model.fit(features[is_train], targets[is_train])
    # Étape 3 : une seule évaluation sur le fold de test.
    y_true = targets[is_test]
    predictions = model.predict(features[is_test])
    y_pred = np.asarray(predictions, dtype=np.int_)
    fold_f1 = macro_f1(y_true, y_pred)
    fold_accuracy = accuracy(y_true, y_pred)
    return FoldResult(
        test_fold=test_fold,
        chosen_c=chosen_c,
        macro_f1=fold_f1,
        accuracy=fold_accuracy,
        y_true=y_true,
        y_pred=y_pred,
        model=model,
    )


def cross_validate(
    features: FeatureMatrix, targets: IntArray, folds: IntArray, svm_config: SvmConfig
) -> CrossValidationResult:
    """Validation croisée sur les folds officiels, chaque fold servant une fois de test (P3, P4)."""
    results = []
    for test_fold in np.unique(folds):
        result = run_fold(features, targets, folds, int(test_fold), svm_config)
        results.append(result)

    f1_scores = [result.macro_f1 for result in results]
    accuracies = [result.accuracy for result in results]
    f1_mean, f1_std = mean_and_std(f1_scores)
    accuracy_mean, accuracy_std = mean_and_std(accuracies)

    n_classes = int(targets.max()) + 1
    n_categories = len(svm_config.category_names)
    confusion_classes, confusion_categories = _cumulated_confusions(
        results, n_classes, n_categories
    )
    return CrossValidationResult(
        folds=results,
        macro_f1_mean=f1_mean,
        macro_f1_std=f1_std,
        accuracy_mean=accuracy_mean,
        accuracy_std=accuracy_std,
        confusion_classes=confusion_classes,
        confusion_categories=confusion_categories,
    )


def _cumulated_confusions(
    results: list[FoldResult], n_classes: int, n_categories: int
) -> tuple[FloatMatrix, FloatMatrix]:
    # Toutes les prédictions de test réunies : chaque extrait compte une fois, dans son fold.
    all_true = np.concatenate([result.y_true for result in results])
    all_pred = np.concatenate([result.y_pred for result in results])
    confusion_classes = normalized_confusion(all_true, all_pred, n_classes)
    # Même matrice en 5 catégories : chaque classe remplacée par target // 10.
    categories_true = to_categories(all_true)
    categories_pred = to_categories(all_pred)
    confusion_categories = normalized_confusion(categories_true, categories_pred, n_categories)
    return confusion_classes, confusion_categories


def _fold_of(row: ManifestRow) -> int:
    if row.fold is None:
        raise ValueError(f"Fold manquant dans le manifeste pour {row.path}")
    return row.fold
