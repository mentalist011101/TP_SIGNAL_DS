"""Famille A sur les émotions (C12) : log-Mel des extraits, parties et scores, sans torch.

Les extraits gardés sont ceux de C11 (echolens.training.heads.emotion_examples) : découpage
par acteur de C4 (P1), étiquettes ramenées aux 6 classes communes (P2), calme et surprise
exclus. Le log-Mel de chaque extrait entier est calculé une seule fois (R5, R6), puis complété
par du silence jusqu'au plus long extrait, avec sa vraie longueur à côté : la fenêtre de 3 s
est découpée au moment de l'entraînement ou de la prédiction (echolens.core.frame_windows).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from echolens.core.audio import load_audio
from echolens.core.data.emotions import EmotionLabels
from echolens.core.data.manifest import ManifestRow, audio_path
from echolens.core.data.splits import SpeakerSplit, SplitConfig
from echolens.core.features import FeatureConfig, FloatArray, log_mel_spectrogram
from echolens.core.frame_windows import silence_share
from echolens.training.evaluation import (
    ClipPrediction,
    IntArray,
    accuracy,
    macro_f1,
    mean_and_std,
    per_class_f1,
    scores_by_group,
)
from echolens.training.heads import emotion_examples


@dataclass(frozen=True)
class EmotionLogMelSet:
    """Log-Mel de tous les extraits d'émotion gardés, avec leurs métadonnées (P1, P2)."""

    datasets: list[str]
    paths: list[str]
    speakers: list[str]
    genders: list[str]
    splits: list[str]
    targets: IntArray
    lengths: IntArray  # nombre de vraies trames de chaque extrait
    log_mels: FloatArray  # (extraits, bandes, trames du plus long), silence après la fin


def compute_emotion_log_mels(
    rows_by_dataset: dict[str, list[ManifestRow]],
    datasets_dir: Path,
    labels: EmotionLabels,
    speaker_splits: list[SpeakerSplit],
    split_config: SplitConfig,
    feature_config: FeatureConfig,
) -> EmotionLogMelSet:
    """Log-Mel (R2) de chaque extrait gardé, jeu par jeu, dans l'ordre du manifeste (R5, R6)."""
    columns: dict[str, list[Any]] = {
        name: [] for name in ["datasets", "paths", "speakers", "genders", "splits", "targets"]
    }
    spectrograms: list[FloatArray] = []
    for dataset, rows in rows_by_dataset.items():
        examples = emotion_examples(rows, labels, speaker_splits, split_config)
        for example in examples:
            row = rows[example.position]
            # Mono 16 kHz (D1, D2), puis le module unique de features (R5).
            path = audio_path(row, datasets_dir)
            signal = load_audio(path)
            spectrogram = log_mel_spectrogram(signal, feature_config)
            spectrograms.append(spectrogram)
            columns["datasets"].append(dataset)
            columns["paths"].append(row.path)
            columns["speakers"].append(example.speaker)
            columns["genders"].append(example.gender)
            columns["splits"].append(example.split)
            columns["targets"].append(example.target)
    lengths, padded = _pad_to_longest(spectrograms, feature_config.db_floor)
    return EmotionLogMelSet(
        datasets=columns["datasets"],
        paths=columns["paths"],
        speakers=columns["speakers"],
        genders=columns["genders"],
        splits=columns["splits"],
        targets=np.array(columns["targets"], dtype=np.int_),
        lengths=lengths,
        log_mels=padded,
    )


def save_emotion_log_mels(log_mel_set: EmotionLogMelSet, path: Path) -> None:
    """Écrit le jeu de log-Mel dans un .npz (sortie Kaggle, jamais sur GitHub)."""
    np.savez(
        path,
        datasets=np.array(log_mel_set.datasets, dtype=np.str_),
        paths=np.array(log_mel_set.paths, dtype=np.str_),
        speakers=np.array(log_mel_set.speakers, dtype=np.str_),
        genders=np.array(log_mel_set.genders, dtype=np.str_),
        splits=np.array(log_mel_set.splits, dtype=np.str_),
        targets=log_mel_set.targets,
        lengths=log_mel_set.lengths,
        log_mels=log_mel_set.log_mels,
    )


def load_emotion_log_mels(path: Path) -> EmotionLogMelSet:
    """Relit un fichier écrit par save_emotion_log_mels, entièrement en mémoire."""
    with np.load(path) as content:
        return EmotionLogMelSet(
            datasets=[str(item) for item in content["datasets"]],
            paths=[str(item) for item in content["paths"]],
            speakers=[str(item) for item in content["speakers"]],
            genders=[str(item) for item in content["genders"]],
            splits=[str(item) for item in content["splits"]],
            targets=content["targets"],
            lengths=content["lengths"],
            log_mels=content["log_mels"],
        )


def split_indices(log_mel_set: EmotionLogMelSet, split: str) -> IntArray:
    """Positions des extraits d'une partie (train, validation ou test), dans l'ordre du jeu."""
    positions = [index for index, name in enumerate(log_mel_set.splits) if name == split]
    return np.array(positions, dtype=np.int_)


def silence_shares(log_mel_set: EmotionLogMelSet, window_frames: int) -> dict[str, float]:
    """Part moyenne de la fenêtre remplie de silence ajouté, par jeu (extraits trop courts)."""
    shares: dict[str, list[float]] = {}
    for index, dataset in enumerate(log_mel_set.datasets):
        share = silence_share(int(log_mel_set.lengths[index]), window_frames)
        shares.setdefault(dataset, []).append(share)
    return {dataset: float(np.mean(values)) for dataset, values in shares.items()}


def seed_test_scores(
    log_mel_set: EmotionLogMelSet, indices: IntArray, y_pred: IntArray, class_count: int
) -> dict[str, Any]:
    """Scores d'une graine sur le test : global, par classe, par jeu, par genre, par acteur (E4)."""
    y_true = log_mel_set.targets[indices]
    datasets = [log_mel_set.datasets[index] for index in indices]
    genders = [log_mel_set.genders[index] for index in indices]
    # Un acteur est identifié par son jeu et son numéro : « 1001 » n'existe que dans CREMA-D.
    actors = [actor_key(log_mel_set, index) for index in indices]
    return {
        "macro_f1": macro_f1(y_true, y_pred),
        "accuracy": accuracy(y_true, y_pred),
        "f1_per_class": per_class_f1(y_true, y_pred, class_count).tolist(),
        "macro_f1_by_dataset": scores_by_group(y_true, y_pred, datasets),
        "macro_f1_by_gender": scores_by_group(y_true, y_pred, genders),
        "macro_f1_by_actor": scores_by_group(y_true, y_pred, actors),
    }


def seed_summary(per_seed: list[dict[str, Any]]) -> dict[str, Any]:
    """Moyenne et écart-type (ddof = 0) sur les graines, pour chaque score et chaque groupe."""
    summary: dict[str, Any] = {}
    for name in ["macro_f1", "accuracy"]:
        mean, std = mean_and_std([scores[name] for scores in per_seed])
        summary[name] = {"mean": mean, "std": std}
    for name in ["macro_f1_by_dataset", "macro_f1_by_gender", "macro_f1_by_actor"]:
        groups = sorted(per_seed[0][name])
        summary[name] = {}
        for group in groups:
            mean, std = mean_and_std([scores[name][group] for scores in per_seed])
            summary[name][group] = {"mean": mean, "std": std}
    return summary


def actor_spread(
    log_mel_set: EmotionLogMelSet, indices: IntArray, by_actor: dict[str, Any]
) -> dict[str, Any]:
    """Écart de genre comparé à la variabilité entre acteurs d'un même genre (E4).

    by_actor est le résumé sur les graines (moyenne par acteur). Si l'écart entre les genres
    est du même ordre que l'écart-type entre acteurs d'un même genre, on ne peut pas l'imputer
    au genre avec si peu d'acteurs.
    """
    gender_of_actor: dict[str, str] = {}
    for index in indices:
        gender_of_actor[actor_key(log_mel_set, index)] = log_mel_set.genders[index]
    spread: dict[str, Any] = {}
    for gender in sorted(set(gender_of_actor.values())):
        values = []
        for actor, actor_gender in gender_of_actor.items():
            if actor_gender == gender:
                values.append(by_actor[actor]["mean"])
        mean, std = mean_and_std(values)
        spread[gender] = {
            "actors": len(values),
            "mean": mean,
            "std": std,
            "min": min(values),
            "max": max(values),
        }
    return spread


def clip_predictions(
    log_mel_set: EmotionLogMelSet, indices: IntArray, y_pred: IntArray
) -> list[ClipPrediction]:
    """Prédictions de test au format commun (path = « jeu/chemin »), pour McNemar (P8)."""
    predictions: list[ClipPrediction] = []
    for position, index in enumerate(indices):
        path = f"{log_mel_set.datasets[index]}/{log_mel_set.paths[index]}"
        target = int(log_mel_set.targets[index])
        item = ClipPrediction(path=path, fold=0, target=target, prediction=int(y_pred[position]))
        predictions.append(item)
    return predictions


def actor_key(log_mel_set: EmotionLogMelSet, index: int) -> str:
    """Identifiant d'acteur unique entre les jeux : « cremad:1001 », « ravdess:Actor_03 »."""
    return f"{log_mel_set.datasets[index]}:{log_mel_set.speakers[index]}"


def _pad_to_longest(
    spectrograms: list[FloatArray], silence_db: float
) -> tuple[IntArray, FloatArray]:
    # Chaque log-Mel est recopié dans un tableau à la longueur du plus long, rempli de silence.
    lengths = np.array([spectrogram.shape[1] for spectrogram in spectrograms], dtype=np.int_)
    band_count = spectrograms[0].shape[0]
    shape = (len(spectrograms), band_count, int(lengths.max()))
    padded = np.full(shape, silence_db, dtype=np.float32)
    for index, spectrogram in enumerate(spectrograms):
        padded[index, :, : spectrogram.shape[1]] = spectrogram
    return lengths, padded
