"""Têtes de classification de la famille B : tout ce qui se calcule sans torch (C11, Brique 4).

La tête lit les moyennes par couche de C10, un tableau (couches, dimension) par extrait, en
trois étapes :
1. standardisation de chaque (couche, dimension) avec la moyenne et l'écart-type du train
   seul (R4) ;
2. somme pondérée des couches, avec des poids w = softmax(a) appris (E7) ;
3. MLP : Linear(dimension, 256), ReLU, Dropout, Linear(256, classes).

Ce module n'importe jamais torch : la CI n'installe pas l'extra [ml]. Il contient la
standardisation, la sélection des données (folds d'ESC-50, parties des émotions), le choix du
réglage et l'assemblage des résultats. La tête et sa boucle d'entraînement sont dans
echolens.training.head_training.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field, model_validator
from sklearn.metrics import f1_score

from echolens.config import CONFIG_DIR, load_yaml
from echolens.core.data.emotions import EmotionLabels, common_emotion
from echolens.core.data.manifest import ManifestRow
from echolens.core.data.splits import SpeakerSplit, Split, SplitConfig, split_of_row
from echolens.training.evaluation import (
    EvaluationConfig,
    IntArray,
    accuracy,
    bootstrap_ci,
    macro_f1,
    mcnemar_test,
    mean_and_std,
    normalized_confusion,
    scores_by_group,
    to_categories,
)

HEADS_CONFIG_PATH = CONFIG_DIR / "heads.yaml"

FloatArray = npt.NDArray[np.float32]
Float64Array = npt.NDArray[np.float64]


class HeadModel(BaseModel):
    """Un modèle comparé : un encodeur de C10, avec ou sans le remplissage de Whisper."""

    id: str
    encoder: str
    padded: bool


class HeadsConfig(BaseModel):
    """Contenu de configs/heads.yaml."""

    hidden_size: int = Field(gt=0)
    batch_size: int = Field(gt=0)
    max_epochs: int = Field(gt=0)
    # None : pas d'arrêt anticipé, le réglage parcourt les max_epochs époques.
    patience: int | None = Field(gt=0)
    weight_decay: float = Field(ge=0)
    learning_rates: list[float] = Field(min_length=1)
    dropouts: list[float] = Field(min_length=1)
    tuning_seed: int
    seeds: list[int] = Field(min_length=1)
    statistics_seed: int
    models: list[HeadModel] = Field(min_length=1)
    mcnemar_pairs: list[tuple[str, str]]
    emotion_datasets: list[str] = Field(min_length=1)
    esc50_class_count: int = Field(gt=1)

    @model_validator(mode="after")
    def check_seeds_and_pairs(self) -> HeadsConfig:
        """La graine des tests statistiques a un résultat ; chaque paire vise un modèle connu."""
        if self.statistics_seed not in self.seeds:
            raise ValueError("statistics_seed doit être l'une des graines de seeds")
        model_ids = [model.id for model in self.models]
        for first, second in self.mcnemar_pairs:
            if first not in model_ids or second not in model_ids:
                raise ValueError(f"Paire de McNemar avec un modèle inconnu : {first} / {second}")
        return self


@dataclass(frozen=True)
class HeadSetting:
    """Un réglage de la grille : taux d'apprentissage et dropout."""

    learning_rate: float
    dropout: float


@dataclass(frozen=True)
class TuningOutcome:
    """Résultat d'un réglage : meilleure époque et F1 macro de validation à cette époque."""

    setting: HeadSetting
    best_epoch: int
    validation_f1: float


@dataclass(frozen=True)
class Standardization:
    """Moyenne et écart-type du train, de forme (couches, dimension) (R4)."""

    mean: Float64Array
    std: Float64Array


@dataclass(frozen=True)
class LabeledSet:
    """Des extraits (extraits, couches, dimension) et leurs classes."""

    features: FloatArray
    targets: IntArray


@dataclass(frozen=True)
class EmotionExample:
    """Un extrait d'émotion gardé : sa ligne dans le manifeste, son acteur, sa partie, sa classe."""

    position: int
    dataset: str
    speaker: str
    gender: str
    split: Split
    target: int


@dataclass(frozen=True)
class EmotionPart:
    """Une partie (train, validation ou test) des émotions, jeux réunis."""

    data: LabeledSet
    datasets: list[str]
    genders: list[str]
    speakers: list[tuple[str, str]]


@dataclass(frozen=True)
class SeedPredictions:
    """Sortie d'une tête entraînée avec une graine : probabilités et poids des couches."""

    seed: int
    probabilities: FloatArray
    layer_weights: FloatArray


@dataclass(frozen=True)
class Esc50FoldPredictions:
    """Un tour d'ESC-50 : réglage retenu, nombre d'époques, et prédictions de chaque graine."""

    test_fold: int
    setting: HeadSetting
    epochs: int
    y_true: IntArray
    runs: list[SeedPredictions]


def load_heads_config(path: Path = HEADS_CONFIG_PATH) -> HeadsConfig:
    """Lit configs/heads.yaml."""
    content = load_yaml(path)
    return HeadsConfig(**content)


def grid_settings(config: HeadsConfig) -> list[HeadSetting]:
    """Tous les réglages de la grille, dans l'ordre du fichier (taux d'apprentissage d'abord)."""
    settings: list[HeadSetting] = []
    for learning_rate in config.learning_rates:
        for dropout in config.dropouts:
            settings.append(HeadSetting(learning_rate=learning_rate, dropout=dropout))
    return settings


def best_setting_index(outcomes: list[TuningOutcome]) -> int:
    """Position du réglage au meilleur F1 macro de validation ; à égalité, le premier."""
    if not outcomes:
        raise ValueError("Aucun réglage à comparer")
    best_index = 0
    for index, outcome in enumerate(outcomes):
        # Inégalité stricte : un réglage plus loin dans la grille doit faire mieux, pas autant.
        if outcome.validation_f1 > outcomes[best_index].validation_f1:
            best_index = index
    return best_index


def standardization_stats(train_features: FloatArray) -> Standardization:
    """Moyenne et écart-type de chaque (couche, dimension), sur le train seul (R4).

    Calcul en float64, pour ne pas perdre de précision sur des milliers d'extraits. Un
    écart-type nul (valeur constante sur tout le train) est remplacé par 1 : la colonne
    standardisée vaut alors 0, la moyenne du train, au lieu d'une division par zéro.
    """
    values = train_features.astype(np.float64)
    mean = values.mean(axis=0)
    std = values.std(axis=0)
    is_constant = std == 0.0
    safe_std = np.where(is_constant, 1.0, std)
    return Standardization(mean=mean, std=safe_std)


def standardize(features: FloatArray, stats: Standardization) -> FloatArray:
    """(x − moyenne du train) / écart-type du train, pour chaque (couche, dimension) (R4)."""
    centered = features.astype(np.float64) - stats.mean
    scaled = centered / stats.std
    return np.asarray(scaled, dtype=np.float32)


def standardize_set(labeled: LabeledSet, stats: Standardization) -> LabeledSet:
    """Le même ensemble, avec ses représentations standardisées par les statistiques données."""
    features = standardize(labeled.features, stats)
    return LabeledSet(features=features, targets=labeled.targets)


def save_standardization(path: Path, stats: Standardization) -> None:
    """Écrit la moyenne et l'écart-type du train dans un fichier .npz."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, mean=stats.mean, std=stats.std)


def esc50_targets_and_folds(rows: list[ManifestRow]) -> tuple[IntArray, IntArray]:
    """Classe (0 à 49, dernier champ du nom de fichier) et fold officiel de chaque extrait."""
    targets: list[int] = []
    folds: list[int] = []
    for row in rows:
        # Nom {fold}-{id}-{take}-{target}.wav : la classe est le dernier champ.
        stem = Path(row.path).stem
        fields = stem.split("-")
        targets.append(int(fields[3]))
        if row.fold is None:
            raise ValueError(f"Fold manquant dans le manifeste pour {row.path}")
        folds.append(row.fold)
    return np.array(targets, dtype=np.int_), np.array(folds, dtype=np.int_)


def select_folds(
    features: FloatArray, targets: IntArray, folds: IntArray, chosen_folds: list[int]
) -> LabeledSet:
    """Les extraits des folds choisis, dans l'ordre du manifeste (P3)."""
    is_chosen = np.isin(folds, chosen_folds)
    return LabeledSet(features=features[is_chosen], targets=targets[is_chosen])


def emotion_examples(
    rows: list[ManifestRow],
    labels: EmotionLabels,
    splits: list[SpeakerSplit],
    split_config: SplitConfig,
) -> list[EmotionExample]:
    """Extraits d'un jeu d'émotions gardés, avec leur partie (P1) et leur classe commune (P2).

    Calme et surprise (classe commune None) sont exclus. position est la ligne du manifeste,
    donc aussi la ligne de embeddings.npy de C10.
    """
    examples: list[EmotionExample] = []
    for position, row in enumerate(rows):
        if row.label is None or row.speaker is None or row.gender is None:
            raise ValueError(f"Étiquette, acteur ou genre manquant pour {row.path}")
        emotion = common_emotion(row.dataset, row.label, labels)
        if emotion is None:
            continue
        split = split_of_row(row, splits, split_config)
        target = labels.emotions.index(emotion)
        example = EmotionExample(position, row.dataset, row.speaker, row.gender, split, target)
        examples.append(example)
    return examples


def emotion_part(
    examples_by_dataset: dict[str, list[EmotionExample]],
    features_by_dataset: dict[str, FloatArray],
    split: Split,
) -> EmotionPart:
    """Réunit une partie (train, validation ou test) de tous les jeux d'émotions, jeu par jeu."""
    blocks: list[FloatArray] = []
    targets: list[int] = []
    datasets: list[str] = []
    genders: list[str] = []
    speakers: list[tuple[str, str]] = []
    for dataset, examples in examples_by_dataset.items():
        chosen = [example for example in examples if example.split == split]
        positions = [example.position for example in chosen]
        dataset_features = features_by_dataset[dataset]
        blocks.append(dataset_features[positions])
        for example in chosen:
            targets.append(example.target)
            datasets.append(example.dataset)
            genders.append(example.gender)
            speakers.append((example.dataset, example.speaker))
    features = np.concatenate(blocks)
    data = LabeledSet(features=features, targets=np.array(targets, dtype=np.int_))
    return EmotionPart(data=data, datasets=datasets, genders=genders, speakers=speakers)


def check_disjoint_speakers(parts: dict[str, EmotionPart]) -> None:
    """Vérifie qu'aucun acteur n'est dans deux parties ; lève ValueError sinon (P1)."""
    part_of_speaker: dict[tuple[str, str], str] = {}
    for name, part in parts.items():
        for speaker in set(part.speakers):
            known_part = part_of_speaker.get(speaker)
            if known_part is not None:
                raise ValueError(f"Fuite : l'acteur {speaker} est en {known_part} et en {name}")
            part_of_speaker[speaker] = name


def check_classes(targets: IntArray, class_count: int) -> None:
    """Vérifie que chaque classe est entre 0 et class_count − 1 ; lève ValueError sinon (P2)."""
    outside = (targets < 0) | (targets >= class_count)
    if np.any(outside):
        unexpected = sorted(set(targets[outside].tolist()))
        raise ValueError(f"Classes hors des {class_count} attendues : {unexpected}")


def predicted_classes(probabilities: FloatArray) -> IntArray:
    """Classe prédite : celle de plus grande probabilité."""
    return np.asarray(probabilities.argmax(axis=1), dtype=np.int_)


def run_of_seed(runs: list[SeedPredictions], seed: int) -> SeedPredictions:
    """Les prédictions d'une graine donnée."""
    for run in runs:
        if run.seed == seed:
            return run
    raise ValueError(f"Aucune prédiction pour la graine {seed}")


def pooled_esc50_predictions(
    folds: list[Esc50FoldPredictions], seed: int
) -> tuple[IntArray, IntArray]:
    """Prédictions de test des 5 tours réunies : chaque extrait d'ESC-50 prédit une fois (P8)."""
    ordered = sorted(folds, key=_test_fold_of)
    y_true_blocks: list[IntArray] = []
    y_pred_blocks: list[IntArray] = []
    for fold in ordered:
        run = run_of_seed(fold.runs, seed)
        y_true_blocks.append(fold.y_true)
        y_pred_blocks.append(predicted_classes(run.probabilities))
    return np.concatenate(y_true_blocks), np.concatenate(y_pred_blocks)


def summary_of(values: list[float]) -> dict[str, Any]:
    """Moyenne, écart-type de population (ddof = 0) et valeurs d'origine."""
    mean, std = mean_and_std(values)
    return {"mean": mean, "std": std, "values": values}


def layer_weights_summary(weights: list[FloatArray]) -> dict[str, Any]:
    """Poids moyens des couches sur plusieurs têtes, et leur écart-type (E7)."""
    stacked = np.stack(weights).astype(np.float64)
    mean = stacked.mean(axis=0)
    std = stacked.std(axis=0)
    return {"mean": mean.tolist(), "std": std.tolist(), "head_count": len(weights)}


def classification_details(y_true: IntArray, y_pred: IntArray, class_count: int) -> dict[str, Any]:
    """F1 par classe et matrice de confusion normalisée par ligne (P4)."""
    all_classes = list(range(class_count))
    per_class = f1_score(y_true, y_pred, labels=all_classes, average=None, zero_division=0.0)
    confusion = normalized_confusion(y_true, y_pred, class_count)
    return {"f1_per_class": per_class.tolist(), "confusion": confusion.tolist()}


def emotion_results(
    test: EmotionPart,
    runs: list[SeedPredictions],
    class_count: int,
    config: HeadsConfig,
    evaluation_config: EvaluationConfig,
) -> dict[str, Any]:
    """Résultats de test d'un modèle sur les émotions : tous jeux, par jeu, par genre (P4, E4).

    Moyenne et écart-type sur les graines ; intervalle à 95 %, F1 par classe et matrice avec
    la graine statistics_seed seulement (décidé à l'avance).
    """
    y_true = test.data.targets
    f1_values: list[float] = []
    accuracy_values: list[float] = []
    by_dataset: dict[str, list[float]] = {}
    by_gender: dict[str, list[float]] = {}
    for run in runs:
        y_pred = predicted_classes(run.probabilities)
        f1_values.append(macro_f1(y_true, y_pred))
        accuracy_values.append(accuracy(y_true, y_pred))
        _append_scores(by_dataset, scores_by_group(y_true, y_pred, test.datasets))
        _append_scores(by_gender, scores_by_group(y_true, y_pred, test.genders))
    statistics_run = run_of_seed(runs, config.statistics_seed)
    statistics_pred = predicted_classes(statistics_run.probabilities)
    low, high = bootstrap_ci(y_true, statistics_pred, evaluation_config)
    results: dict[str, Any] = {
        "macro_f1": summary_of(f1_values),
        "accuracy": summary_of(accuracy_values),
        "macro_f1_ci": [low, high],
        "macro_f1_by_dataset": _summaries(by_dataset),
        "macro_f1_by_gender": _summaries(by_gender),
        "layer_weights": layer_weights_summary([run.layer_weights for run in runs]),
    }
    results.update(classification_details(y_true, statistics_pred, class_count))
    return results


def esc50_results(
    folds: list[Esc50FoldPredictions],
    config: HeadsConfig,
    category_count: int,
    evaluation_config: EvaluationConfig,
) -> dict[str, Any]:
    """Résultats de test d'un modèle sur ESC-50 : 5 tours × graines (P3, P4).

    Écart-type sur les 5 tours (ddof = 0), comme la référence SVM, chaque tour pris en moyenne
    sur les graines ; écart-type sur les graines à part. Intervalle, F1 par classe et matrices :
    prédictions réunies des 5 tours avec la graine statistics_seed.
    """
    fold_f1, fold_accuracy, seed_f1 = _esc50_scores(folds, config.seeds)
    y_true, y_pred = pooled_esc50_predictions(folds, config.statistics_seed)
    low, high = bootstrap_ci(y_true, y_pred, evaluation_config)
    categories_true = to_categories(y_true)
    categories_pred = to_categories(y_pred)
    confusion_categories = normalized_confusion(categories_true, categories_pred, category_count)
    all_weights = _all_layer_weights(folds)
    results: dict[str, Any] = {
        "macro_f1": summary_of(fold_f1),
        "accuracy": summary_of(fold_accuracy),
        "macro_f1_by_seed": summary_of(seed_f1),
        "macro_f1_ci": [low, high],
        "per_fold": _esc50_fold_details(folds),
        "layer_weights": layer_weights_summary(all_weights),
        "confusion_categories": confusion_categories.tolist(),
    }
    results.update(classification_details(y_true, y_pred, config.esc50_class_count))
    return results


def mcnemar_results(
    y_true: IntArray,
    predictions_by_model: dict[str, IntArray],
    pairs: list[tuple[str, str]],
    evaluation_config: EvaluationConfig,
) -> list[dict[str, Any]]:
    """Test de McNemar pour chaque paire de modèles, sur les mêmes extraits de test (P8)."""
    results: list[dict[str, Any]] = []
    for first, second in pairs:
        first_pred = predictions_by_model[first]
        second_pred = predictions_by_model[second]
        test = mcnemar_test(y_true, first_pred, second_pred, evaluation_config)
        entry: dict[str, Any] = {"model_a": first, "model_b": second}
        entry["macro_f1_a"] = macro_f1(y_true, first_pred)
        entry["macro_f1_b"] = macro_f1(y_true, second_pred)
        entry.update(asdict(test))
        results.append(entry)
    return results


def save_probabilities(path: Path, targets: IntArray, probabilities: FloatArray) -> None:
    """Écrit les classes vraies et les probabilités (extraits, classes) dans un .npz (E2, C13)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, targets=targets, probabilities=probabilities)


def write_results(path: Path, content: dict[str, Any]) -> None:
    """Écrit un JSON de résultats lisible (indentation, accents gardés)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(content, ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")


def _append_scores(collected: dict[str, list[float]], scores: dict[str, float]) -> None:
    for name, score in scores.items():
        collected.setdefault(name, []).append(score)


def _summaries(collected: dict[str, list[float]]) -> dict[str, dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for name, values in collected.items():
        summaries[name] = summary_of(values)
    return summaries


def _esc50_scores(
    folds: list[Esc50FoldPredictions], seeds: list[int]
) -> tuple[list[float], list[float], list[float]]:
    # Par tour : F1 et accuracy moyens sur les graines. Par graine : F1 moyen sur les tours.
    fold_f1: list[float] = []
    fold_accuracy: list[float] = []
    f1_by_seed: dict[int, list[float]] = {}
    for fold in sorted(folds, key=_test_fold_of):
        f1_of_seeds: list[float] = []
        accuracy_of_seeds: list[float] = []
        for seed in seeds:
            run = run_of_seed(fold.runs, seed)
            y_pred = predicted_classes(run.probabilities)
            f1 = macro_f1(fold.y_true, y_pred)
            f1_of_seeds.append(f1)
            accuracy_of_seeds.append(accuracy(fold.y_true, y_pred))
            f1_by_seed.setdefault(seed, []).append(f1)
        fold_f1.append(float(np.mean(f1_of_seeds)))
        fold_accuracy.append(float(np.mean(accuracy_of_seeds)))
    seed_f1: list[float] = []
    for seed in seeds:
        seed_f1.append(float(np.mean(f1_by_seed[seed])))
    return fold_f1, fold_accuracy, seed_f1


def _all_layer_weights(folds: list[Esc50FoldPredictions]) -> list[FloatArray]:
    weights: list[FloatArray] = []
    for fold in folds:
        for run in fold.runs:
            weights.append(run.layer_weights)
    return weights


def _esc50_fold_details(folds: list[Esc50FoldPredictions]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for fold in sorted(folds, key=_test_fold_of):
        f1_by_seed: dict[str, float] = {}
        for run in fold.runs:
            y_pred = predicted_classes(run.probabilities)
            f1_by_seed[str(run.seed)] = macro_f1(fold.y_true, y_pred)
        detail: dict[str, Any] = {"test_fold": fold.test_fold, "epochs": fold.epochs}
        detail["learning_rate"] = fold.setting.learning_rate
        detail["dropout"] = fold.setting.dropout
        detail["macro_f1_by_seed"] = f1_by_seed
        details.append(detail)
    return details


def _test_fold_of(fold: Esc50FoldPredictions) -> int:
    return fold.test_fold
