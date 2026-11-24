"""Scores de l'identification du locuteur (C15, P11, E1) : calculs purs, sans torch.

Méthode, pour un groupe de locuteurs :

1. Chaque phrase devient un vecteur (ECAPA ou mHuBERT), ramené à une norme 1.
2. La « voix enregistrée » d'un locuteur est la moyenne de ses 5 vecteurs d'enregistrement,
   ramenée à une norme 1 (centroïde).
3. Le score entre une phrase de test et un locuteur est la similarité cosinus : le produit
   scalaire de deux vecteurs de norme 1, entre −1 et 1 (1 = même direction).

On en tire trois mesures (E1) :

- accuracy en ensemble fermé : le locuteur au score le plus haut est-il le bon ?
- EER : on teste chaque paire (phrase, locuteur) en « même personne ou non » ; l'EER est le taux
  d'erreur au seuil où fausses acceptations et faux rejets s'égalent ;
- ensemble ouvert : avec le seuil choisi sur le groupe de calibration, une phrase dont le
  meilleur score reste sous le seuil est déclarée « locuteur inconnu ». On mesure les voix
  connues bien reconnues, et les voix jamais enregistrées bien rejetées.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from echolens.core.data.speaker_enrollment import SpeakerGroup, SpeakerUtterances
from echolens.training.evaluation import equal_error_rate

FloatMatrix = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int_]
# Vecteur d'une phrase, rangé par chemin de fichier (colonne path du manifeste).
EmbeddingsByPath = dict[str, npt.NDArray[np.floating]]


@dataclass(frozen=True)
class GroupScores:
    """Scores des phrases de test d'un groupe contre les voix enregistrées de ce groupe."""

    # (phrases de test, locuteurs) : similarité cosinus.
    scores: FloatMatrix
    # Position du vrai locuteur de chaque phrase de test.
    true_index: IntArray
    # Sous-corpus de chaque phrase de test (pour les scores par sous-corpus).
    subsets: list[str]


@dataclass(frozen=True)
class SpeakerResult:
    """Résultats d'un encodeur sur le groupe d'évaluation."""

    speaker_count: int
    test_utterance_count: int
    closed_set_accuracy: float
    eer: float
    # Seuil « inconnu », choisi à l'EER du groupe de calibration.
    threshold: float
    known_accepted_and_correct: float
    unknown_rejected: float
    accuracy_by_subset: dict[str, float]


def normalize_rows(matrix: FloatMatrix) -> FloatMatrix:
    """Ramène chaque ligne à une norme 1, pour que le produit scalaire soit un cosinus."""
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    if np.any(norms == 0):
        raise ValueError("Un vecteur nul ne peut pas être normalisé")
    normalized: FloatMatrix = matrix / norms
    return normalized


def stack_paths(paths: list[str], embeddings: EmbeddingsByPath) -> FloatMatrix:
    """Empile les vecteurs de plusieurs phrases en une matrice normalisée (phrases, dimension)."""
    vectors = [np.asarray(embeddings[path], dtype=np.float64) for path in paths]
    matrix = np.stack(vectors)
    return normalize_rows(matrix)


def enrolled_voices(speakers: list[SpeakerUtterances], embeddings: EmbeddingsByPath) -> FloatMatrix:
    """Voix enregistrée de chaque locuteur : moyenne de ses phrases d'enregistrement, norme 1."""
    centroids: list[FloatMatrix] = []
    for speaker in speakers:
        enrollment = stack_paths(speaker.enrollment_paths, embeddings)
        centroid = enrollment.mean(axis=0)
        centroids.append(centroid)
    matrix = np.stack(centroids)
    return normalize_rows(matrix)


def group_scores(speakers: list[SpeakerUtterances], embeddings: EmbeddingsByPath) -> GroupScores:
    """Scores de toutes les phrases de test d'un groupe contre toutes les voix de ce groupe."""
    voices = enrolled_voices(speakers, embeddings)
    test_paths: list[str] = []
    true_index: list[int] = []
    subsets: list[str] = []
    for position, speaker in enumerate(speakers):
        for path in speaker.test_paths:
            test_paths.append(path)
            true_index.append(position)
            subsets.append(speaker.subset)
    tests = stack_paths(test_paths, embeddings)
    # Produit de vecteurs de norme 1 : chaque case est une similarité cosinus.
    scores = tests @ voices.T
    return GroupScores(scores=scores, true_index=np.array(true_index), subsets=subsets)


def closed_set_accuracy(group: GroupScores) -> float:
    """Part des phrases de test dont le meilleur score désigne le bon locuteur."""
    predicted = np.argmax(group.scores, axis=1)
    correct = predicted == group.true_index
    return float(correct.mean())


def verification_labels(group: GroupScores) -> IntArray:
    """Pour chaque paire (phrase, locuteur), 1 si c'est la même personne, 0 sinon (aplati)."""
    phrase_count, speaker_count = group.scores.shape
    labels = np.zeros((phrase_count, speaker_count), dtype=np.int_)
    rows = np.arange(phrase_count)
    labels[rows, group.true_index] = 1
    return labels.ravel()


def verification_eer(group: GroupScores) -> tuple[float, float]:
    """EER et seuil correspondant, sur toutes les paires (phrase, locuteur) du groupe."""
    labels = verification_labels(group)
    scores = group.scores.ravel()
    result = equal_error_rate(labels, scores)
    return result.eer, result.threshold


def known_accepted_and_correct(group: GroupScores, threshold: float) -> float:
    """Voix connues : part des phrases attribuées au bon locuteur ET au-dessus du seuil."""
    predicted = np.argmax(group.scores, axis=1)
    best_scores = np.max(group.scores, axis=1)
    correct = predicted == group.true_index
    accepted = best_scores >= threshold
    return float(np.mean(correct & accepted))


def unknown_rejected(unknown_scores: FloatMatrix, threshold: float) -> float:
    """Voix jamais enregistrées : part des phrases dont le meilleur score reste sous le seuil."""
    best_scores = np.max(unknown_scores, axis=1)
    rejected = best_scores < threshold
    return float(rejected.mean())


def accuracy_by_subset(group: GroupScores) -> dict[str, float]:
    """Accuracy en ensemble fermé, séparément pour chaque sous-corpus (ca16, niger, yaounde)."""
    predicted = np.argmax(group.scores, axis=1)
    correct = predicted == group.true_index
    subsets = np.array(group.subsets)
    result: dict[str, float] = {}
    for subset in sorted(set(group.subsets)):
        in_subset = subsets == subset
        result[subset] = float(correct[in_subset].mean())
    return result


def speakers_of_group(
    speakers: list[SpeakerUtterances], group: SpeakerGroup
) -> list[SpeakerUtterances]:
    """Locuteurs d'un seul groupe, dans l'ordre d'origine."""
    return [speaker for speaker in speakers if speaker.group == group]


def evaluate_speakers(
    speakers: list[SpeakerUtterances], embeddings: EmbeddingsByPath
) -> SpeakerResult:
    """Évaluation complète d'un encodeur : seuil sur la calibration, scores sur l'évaluation."""
    calibration = speakers_of_group(speakers, "calibration")
    evaluation = speakers_of_group(speakers, "evaluation")
    # Étape 1 : le seuil « inconnu » est choisi sur des voix que l'évaluation ne contient pas.
    calibration_scores = group_scores(calibration, embeddings)
    _, threshold = verification_eer(calibration_scores)
    # Étape 2 : scores du groupe d'évaluation, avec ce seuil gardé tel quel.
    evaluation_scores = group_scores(evaluation, embeddings)
    eer, _ = verification_eer(evaluation_scores)
    # Étape 3 : voix inconnues = phrases de test des locuteurs de calibration, comparées aux
    # voix enregistrées du groupe d'évaluation (elles n'y figurent pas).
    unknown_paths = _test_paths(calibration)
    unknown_tests = stack_paths(unknown_paths, embeddings)
    evaluation_voices = enrolled_voices(evaluation, embeddings)
    unknown_scores = unknown_tests @ evaluation_voices.T
    return SpeakerResult(
        speaker_count=len(evaluation),
        test_utterance_count=len(evaluation_scores.true_index),
        closed_set_accuracy=closed_set_accuracy(evaluation_scores),
        eer=eer,
        threshold=threshold,
        known_accepted_and_correct=known_accepted_and_correct(evaluation_scores, threshold),
        unknown_rejected=unknown_rejected(unknown_scores, threshold),
        accuracy_by_subset=accuracy_by_subset(evaluation_scores),
    )


def best_layer(
    speakers: list[SpeakerUtterances], layered: dict[str, npt.NDArray[np.floating]]
) -> int:
    """Couche de mHuBERT à garder : la plus faible EER sur le groupe de calibration seul.

    layered range, par chemin, un tableau (couches, dimension). Le groupe d'évaluation n'est
    jamais regardé : le choix de la couche ne peut donc pas gonfler son score.
    """
    calibration = speakers_of_group(speakers, "calibration")
    first_vector = next(iter(layered.values()))
    layer_count = first_vector.shape[0]
    best_index = 0
    best_eer = float("inf")
    for layer in range(layer_count):
        one_layer = select_layer(layered, layer)
        scores = group_scores(calibration, one_layer)
        eer, _ = verification_eer(scores)
        if eer < best_eer:
            best_eer = eer
            best_index = layer
    return best_index


def select_layer(layered: dict[str, npt.NDArray[np.floating]], layer: int) -> EmbeddingsByPath:
    """Garde une seule couche pour chaque phrase : (couches, dimension) → (dimension,)."""
    result: EmbeddingsByPath = {}
    for path, layers in layered.items():
        result[path] = layers[layer]
    return result


def _test_paths(speakers: list[SpeakerUtterances]) -> list[str]:
    paths: list[str] = []
    for speaker in speakers:
        paths.extend(speaker.test_paths)
    return paths
