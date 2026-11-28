"""Scores de l'identification du locuteur (C15, P8, P11, E1) : calculs purs, sans torch.

Méthode, pour un groupe de locuteurs :

1. Chaque phrase devient un vecteur (ECAPA ou mHuBERT), ramené à une norme 1.
2. La « voix enregistrée » d'un locuteur est la moyenne de ses 5 vecteurs d'enregistrement,
   ramenée à une norme 1 (centroïde).
3. Le score entre une phrase et un locuteur est la similarité cosinus : le produit scalaire de
   deux vecteurs de norme 1, entre −1 et 1 (1 = même direction).

Mesures sur le groupe d'évaluation :

- accuracy en ensemble fermé : le locuteur au meilleur score est-il le bon ?
- EER de vérification : chaque paire (phrase, locuteur) est jugée « même personne ou non » ;
  l'EER est le taux d'erreur au seuil où fausses acceptations et faux rejets s'égalent ;
- ensemble ouvert, comme dans l'application : on compare le MEILLEUR score d'une phrase au
  seuil « inconnu ». Le seuil est choisi sur le groupe de calibration et ses propres
  imposteurs ; il est mesuré sur le groupe d'évaluation et d'autres imposteurs ;
- intervalles de confiance à 95 % par bootstrap sur les locuteurs (P8).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from echolens.core.data.speaker_enrollment import SpeakerGroup, SpeakerUtterances
from echolens.training.evaluation import EvaluationConfig, equal_error_rate

FloatMatrix = npt.NDArray[np.float64]
FloatArray = npt.NDArray[np.float64]
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
    impostor_speaker_count: int
    impostor_utterance_count: int
    closed_set_accuracy: float
    closed_set_accuracy_ci: tuple[float, float]
    eer: float
    eer_ci: tuple[float, float]
    # Seuil « inconnu », choisi sur la calibration et ses imposteurs.
    threshold: float
    known_accepted_and_correct: float
    unknown_rejected: float
    # EER de la décision en ensemble ouvert sur l'évaluation (avec son propre seuil).
    open_set_eer: float
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


def impostor_scores(
    impostors: list[SpeakerUtterances],
    enrolled: list[SpeakerUtterances],
    embeddings: EmbeddingsByPath,
) -> FloatMatrix:
    """Scores des phrases de test d'imposteurs contre les voix enregistrées d'un autre groupe."""
    voices = enrolled_voices(enrolled, embeddings)
    impostor_paths = test_paths_of(impostors)
    tests = stack_paths(impostor_paths, embeddings)
    scores: FloatMatrix = tests @ voices.T
    return scores


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


def open_set_eer(group: GroupScores, unknown: FloatMatrix) -> tuple[float, float]:
    """EER et seuil de la décision « connu ou inconnu » sur le MEILLEUR score de chaque phrase.

    C'est la décision de l'application : une phrase est déclarée « inconnue » si son meilleur
    score parmi toutes les voix enregistrées reste sous le seuil. Au seuil rendu, la part des
    voix connues rejetées égale la part des voix inconnues acceptées.
    """
    known_best = np.max(group.scores, axis=1)
    unknown_best = np.max(unknown, axis=1)
    known_labels = np.ones(len(known_best), dtype=np.int_)
    unknown_labels = np.zeros(len(unknown_best), dtype=np.int_)
    labels = np.concatenate([known_labels, unknown_labels])
    scores = np.concatenate([known_best, unknown_best])
    result = equal_error_rate(labels, scores)
    return result.eer, result.threshold


def known_accepted_and_correct(group: GroupScores, threshold: float) -> float:
    """Voix connues : part des phrases attribuées au bon locuteur ET au-dessus du seuil."""
    predicted = np.argmax(group.scores, axis=1)
    best_scores = np.max(group.scores, axis=1)
    correct = predicted == group.true_index
    accepted = best_scores >= threshold
    return float(np.mean(correct & accepted))


def unknown_rejected(unknown: FloatMatrix, threshold: float) -> float:
    """Voix jamais enregistrées : part des phrases dont le meilleur score reste sous le seuil."""
    best_scores = np.max(unknown, axis=1)
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


def bootstrap_speaker_ci(
    group: GroupScores, config: EvaluationConfig
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Intervalles de l'accuracy et de l'EER, par bootstrap sur les LOCUTEURS (P8).

    Les phrases d'une même personne se ressemblent : tirer des phrases au hasard ferait croire
    à plus d'information qu'il n'y en a, et l'intervalle serait trop étroit. On tire donc des
    locuteurs avec remise, et on garde toutes leurs phrases de test. Les voix enregistrées
    (colonnes) ne changent pas.
    """
    speaker_count = group.scores.shape[1]
    rows_of_speaker = _rows_of_each_speaker(group, speaker_count)
    generator = np.random.default_rng(config.seed)
    accuracies = np.empty(config.n_bootstrap, dtype=np.float64)
    eers = np.empty(config.n_bootstrap, dtype=np.float64)
    for draw in range(config.n_bootstrap):
        drawn = generator.integers(0, speaker_count, size=speaker_count)
        picked_speakers = np.asarray(drawn, dtype=np.int_)
        picked_rows = _rows_of_picked_speakers(rows_of_speaker, picked_speakers)
        resampled = _select_rows(group, picked_rows)
        accuracies[draw] = closed_set_accuracy(resampled)
        resampled_eer, _ = verification_eer(resampled)
        eers[draw] = resampled_eer
    accuracy_ci = _percentile_interval(accuracies, config.confidence)
    eer_ci = _percentile_interval(eers, config.confidence)
    return accuracy_ci, eer_ci


def speakers_of_group(
    speakers: list[SpeakerUtterances], group: SpeakerGroup
) -> list[SpeakerUtterances]:
    """Locuteurs d'un seul groupe, dans l'ordre d'origine."""
    return [speaker for speaker in speakers if speaker.group == group]


def choose_threshold(speakers: list[SpeakerUtterances], embeddings: EmbeddingsByPath) -> float:
    """Seuil « inconnu » : EER de la décision en ensemble ouvert, sur la calibration seule."""
    calibration = speakers_of_group(speakers, "calibration")
    impostors = speakers_of_group(speakers, "impostor_calibration")
    known = group_scores(calibration, embeddings)
    unknown = impostor_scores(impostors, calibration, embeddings)
    _, threshold = open_set_eer(known, unknown)
    return threshold


def evaluate_speakers(
    speakers: list[SpeakerUtterances],
    embeddings: EmbeddingsByPath,
    config: EvaluationConfig,
) -> SpeakerResult:
    """Évaluation complète d'un encodeur : seuil sur la calibration, scores sur l'évaluation."""
    # Étape 1 : le seuil est choisi sans jamais regarder l'évaluation ni ses imposteurs.
    threshold = choose_threshold(speakers, embeddings)
    # Étape 2 : voix connues et imposteurs propres au groupe d'évaluation.
    evaluation = speakers_of_group(speakers, "evaluation")
    impostors = speakers_of_group(speakers, "impostor_evaluation")
    known = group_scores(evaluation, embeddings)
    unknown = impostor_scores(impostors, evaluation, embeddings)
    # Étape 3 : mesures et intervalles de confiance.
    eer, _ = verification_eer(known)
    evaluation_open_set_eer, _ = open_set_eer(known, unknown)
    accuracy_ci, eer_ci = bootstrap_speaker_ci(known, config)
    return SpeakerResult(
        speaker_count=len(evaluation),
        test_utterance_count=len(known.true_index),
        impostor_speaker_count=len(impostors),
        impostor_utterance_count=unknown.shape[0],
        closed_set_accuracy=closed_set_accuracy(known),
        closed_set_accuracy_ci=accuracy_ci,
        eer=eer,
        eer_ci=eer_ci,
        threshold=threshold,
        known_accepted_and_correct=known_accepted_and_correct(known, threshold),
        unknown_rejected=unknown_rejected(unknown, threshold),
        open_set_eer=evaluation_open_set_eer,
        accuracy_by_subset=accuracy_by_subset(known),
    )


def best_layer(
    speakers: list[SpeakerUtterances], layered: dict[str, npt.NDArray[np.floating]]
) -> int:
    """Couche de mHuBERT à garder : la plus faible EER de vérification sur la calibration seule.

    layered range, par chemin, un tableau (couches, dimension). Ni l'évaluation ni ses
    imposteurs ne sont regardés : le choix de la couche ne peut donc pas gonfler leur score.
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


def test_paths_of(speakers: list[SpeakerUtterances]) -> list[str]:
    """Toutes les phrases de test de plusieurs locuteurs, dans l'ordre."""
    paths: list[str] = []
    for speaker in speakers:
        paths.extend(speaker.test_paths)
    return paths


def _rows_of_each_speaker(group: GroupScores, speaker_count: int) -> list[IntArray]:
    rows: list[IntArray] = []
    for speaker_index in range(speaker_count):
        speaker_rows = np.flatnonzero(group.true_index == speaker_index)
        rows.append(speaker_rows)
    return rows


def _rows_of_picked_speakers(rows_of_speaker: list[IntArray], picked: IntArray) -> IntArray:
    # Un locuteur tiré deux fois apporte deux fois ses phrases (tirage avec remise).
    pieces: list[IntArray] = []
    for position in range(len(picked)):
        speaker_index = int(picked[position])
        pieces.append(rows_of_speaker[speaker_index])
    return np.concatenate(pieces)


def _select_rows(group: GroupScores, rows: IntArray) -> GroupScores:
    subsets = [group.subsets[row] for row in rows]
    scores = group.scores[rows]
    true_index = group.true_index[rows]
    return GroupScores(scores=scores, true_index=true_index, subsets=subsets)


def _percentile_interval(values: FloatArray, confidence: float) -> tuple[float, float]:
    # Pour 95 % : on garde le centre, en coupant 2,5 % de chaque côté.
    tail = (1.0 - confidence) / 2.0
    low, high = np.quantile(values, [tail, 1.0 - tail])
    return float(low), float(high)
