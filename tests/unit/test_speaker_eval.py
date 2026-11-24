"""Tests des scores du locuteur (C15) sur des vecteurs de synthèse, sans modèle."""

import numpy as np
import pytest

from echolens.core.data.speaker_enrollment import SpeakerUtterances
from echolens.training.speaker_eval import (
    GroupScores,
    best_layer,
    closed_set_accuracy,
    evaluate_speakers,
    group_scores,
    known_accepted_and_correct,
    normalize_rows,
    unknown_rejected,
    verification_labels,
)

DIMENSION = 16


def make_speakers(group: str, names: list[str], test_count: int) -> list[SpeakerUtterances]:
    speakers = []
    for name in names:
        enrollment = [f"{name}/enrol_{index}.wav" for index in range(5)]
        test = [f"{name}/test_{index}.wav" for index in range(test_count)]
        speaker = SpeakerUtterances(
            speaker=f"ca16/{name}",
            subset="ca16",
            group=group,
            enrollment_paths=enrollment,
            test_paths=test,
        )
        speakers.append(speaker)
    return speakers


def make_embeddings(speakers: list[SpeakerUtterances], noise: float) -> dict[str, np.ndarray]:
    """Chaque locuteur a une direction propre ; ses phrases en sont des versions bruitées."""
    generator = np.random.default_rng(0)
    embeddings = {}
    for speaker in speakers:
        direction = generator.normal(size=DIMENSION)
        for path in speaker.enrollment_paths + speaker.test_paths:
            embeddings[path] = direction + noise * generator.normal(size=DIMENSION)
    return embeddings


def test_normalize_rows_gives_unit_norm() -> None:
    matrix = np.array([[3.0, 4.0], [0.0, 2.0]])
    normalized = normalize_rows(matrix)
    assert np.linalg.norm(normalized, axis=1) == pytest.approx([1.0, 1.0])


def test_normalize_rows_refuses_zero_vector() -> None:
    with pytest.raises(ValueError, match="nul"):
        normalize_rows(np.zeros((1, 3)))


def test_clean_voices_are_all_recognized() -> None:
    speakers = make_speakers("evaluation", ["a", "b", "c"], test_count=4)
    embeddings = make_embeddings(speakers, noise=0.01)

    group = group_scores(speakers, embeddings)

    assert group.scores.shape == (12, 3)
    assert closed_set_accuracy(group) == 1.0


def test_verification_labels_mark_the_true_speaker() -> None:
    group = GroupScores(
        scores=np.zeros((2, 3)), true_index=np.array([0, 2]), subsets=["ca16", "ca16"]
    )
    labels = verification_labels(group)
    assert labels.tolist() == [1, 0, 0, 0, 0, 1]


def test_threshold_decisions() -> None:
    group = GroupScores(
        scores=np.array([[0.9, 0.1], [0.2, 0.4], [0.3, 0.8]]),
        true_index=np.array([0, 1, 0]),
        subsets=["ca16", "ca16", "ca16"],
    )
    # Phrase 1 : bonne et au-dessus du seuil ; phrase 2 : bonne mais sous le seuil ;
    # phrase 3 : au-dessus du seuil mais mauvaise.
    assert known_accepted_and_correct(group, threshold=0.5) == pytest.approx(1 / 3)
    unknown_scores = np.array([[0.1, 0.2], [0.7, 0.1]])
    assert unknown_rejected(unknown_scores, threshold=0.5) == pytest.approx(0.5)


def test_evaluate_speakers_on_separable_voices() -> None:
    calibration = make_speakers("calibration", ["a", "b", "c"], test_count=5)
    evaluation = make_speakers("evaluation", ["d", "e", "f"], test_count=5)
    speakers = calibration + evaluation
    embeddings = make_embeddings(speakers, noise=0.05)

    result = evaluate_speakers(speakers, embeddings)

    assert result.speaker_count == 3
    assert result.test_utterance_count == 15
    assert result.closed_set_accuracy == 1.0
    assert result.eer == pytest.approx(0.0)
    assert result.accuracy_by_subset == {"ca16": 1.0}


def test_best_layer_picks_the_informative_layer() -> None:
    calibration = make_speakers("calibration", ["a", "b", "c"], test_count=5)
    clean = make_embeddings(calibration, noise=0.01)
    generator = np.random.default_rng(1)
    layered = {}
    for path, vector in clean.items():
        # Couche 0 : bruit pur ; couche 1 : la voix.
        noise_layer = generator.normal(size=DIMENSION)
        layered[path] = np.stack([noise_layer, vector])

    assert best_layer(calibration, layered) == 1
