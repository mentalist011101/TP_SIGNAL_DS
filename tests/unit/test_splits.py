"""Tests des découpages sans fuite (C4 : P1, P2, P3, P7, règles Ly2).

Les premiers tests utilisent de petits manifestes de synthèse. Les derniers vérifient les vrais
manifestes et le vrai découpage versionnés dans data/ (des CSV, sans aucun audio).
"""

from collections import Counter
from pathlib import Path

import pytest

from echolens.config import REPO_ROOT
from echolens.core.data.emotions import common_emotion, load_emotion_labels
from echolens.core.data.manifest import ManifestRow, load_manifest
from echolens.core.data.splits import (
    Gender,
    SpeakerSplit,
    check_no_speaker_leak,
    esc50_round,
    load_speaker_splits,
    load_split_config,
    save_speaker_splits,
    split_emotion_speakers,
    split_of_row,
)

MANIFESTS_DIR = REPO_ROOT / "data" / "manifests"
EMOTION_SPLIT_PATH = REPO_ROOT / "data" / "splits" / "emotion_split.csv"
# Les manifestes de CREMA-D et de RAVDESS viennent de C3 (Luciano). S'ils manquent (copie
# partielle du dépôt), les tests sur les vraies données sont sautés, pas échoués.
CREMAD_PATH = MANIFESTS_DIR / "cremad.csv"
RAVDESS_PATH = MANIFESTS_DIR / "ravdess.csv"
REAL_MANIFESTS_PRESENT = CREMAD_PATH.exists() and RAVDESS_PATH.exists()
needs_real_manifests = pytest.mark.skipif(
    not REAL_MANIFESTS_PRESENT,
    reason="manifestes de CREMA-D et de RAVDESS absents de data/manifests/",
)


def make_rows(
    dataset: str, speakers: dict[str, Gender], files_per_speaker: int
) -> list[ManifestRow]:
    """Manifeste de synthèse : quelques fichiers par acteur, jamais de vrai fichier."""
    rows: list[ManifestRow] = []
    for speaker, gender in speakers.items():
        for number in range(files_per_speaker):
            row = ManifestRow(
                dataset=dataset,
                path=f"{speaker}/{number}.wav",
                label="ANG",
                speaker=speaker,
                gender=gender,
                duration_s=1.0,
            )
            rows.append(row)
    return rows


def twenty_speakers() -> dict[str, Gender]:
    """10 femmes et 10 hommes, identifiants 01 à 20."""
    speakers: dict[str, Gender] = {}
    for number in range(1, 21):
        speaker = f"{number:02d}"
        if number % 2 == 0:
            speakers[speaker] = "F"
        else:
            speakers[speaker] = "M"
    return speakers


# --- Correspondance des émotions (P2) ---


def test_mapping_targets_only_the_six_common_emotions() -> None:
    labels = load_emotion_labels()
    assert labels.emotions == ["neutral", "happy", "sad", "angry", "fear", "disgust"]
    for mapping in labels.label_mapping.values():
        for target in mapping.values():
            assert target is None or target in labels.emotions


def test_calm_and_surprise_are_excluded() -> None:
    labels = load_emotion_labels()
    assert common_emotion("ravdess", "02", labels) is None
    assert common_emotion("ravdess", "08", labels) is None
    assert common_emotion("cafe", "S", labels) is None
    assert common_emotion("ravdess", "05", labels) == "angry"
    assert common_emotion("cremad", "FEA", labels) == "fear"


def test_unknown_label_is_refused() -> None:
    labels = load_emotion_labels()
    with pytest.raises(ValueError, match="inconnue"):
        common_emotion("cremad", "SUR", labels)


# --- Découpage des acteurs (P1) ---


def test_no_speaker_in_two_splits_and_every_speaker_has_one() -> None:
    config = load_split_config()
    rows = make_rows("cremad", twenty_speakers(), files_per_speaker=3)
    splits = split_emotion_speakers(rows, config)
    check_no_speaker_leak(splits)
    assert len(splits) == 20
    # Chaque fichier reçoit la partie de son acteur : aucun fichier sans partie.
    for row in rows:
        split_of_row(row, splits, config)


def test_validation_and_test_are_gender_balanced() -> None:
    config = load_split_config()
    rows = make_rows("cremad", twenty_speakers(), files_per_speaker=1)
    splits = split_emotion_speakers(rows, config)
    counts: Counter[tuple[str, str]] = Counter()
    for speaker_split in splits:
        counts[(speaker_split.split, speaker_split.gender)] += 1
    # 20 acteurs × 0,15 / 2 = 1,5 → 2 par genre en validation, et 2 en test.
    assert counts[("validation", "F")] == counts[("validation", "M")] == 2
    assert counts[("test", "F")] == counts[("test", "M")] == 2


def test_split_is_deterministic_whatever_the_row_order() -> None:
    config = load_split_config()
    rows = make_rows("cremad", twenty_speakers(), files_per_speaker=2)
    reversed_rows = list(reversed(rows))
    first = split_emotion_speakers(rows, config)
    second = split_emotion_speakers(reversed_rows, config)
    assert first == second


def test_leak_is_detected() -> None:
    leaking = [
        SpeakerSplit(dataset="cremad", speaker="1001", gender="M", split="train"),
        SpeakerSplit(dataset="cremad", speaker="1001", gender="M", split="test"),
    ]
    with pytest.raises(ValueError, match="Fuite"):
        check_no_speaker_leak(leaking)


def test_speaker_without_split_is_refused() -> None:
    config = load_split_config()
    row = make_rows("cremad", {"9999": "F"}, files_per_speaker=1)[0]
    with pytest.raises(ValueError, match="Aucune partie"):
        split_of_row(row, [], config)


def test_split_file_round_trip(tmp_path: Path) -> None:
    config = load_split_config()
    rows = make_rows("ravdess", twenty_speakers(), files_per_speaker=1)
    splits = split_emotion_speakers(rows, config)
    path = tmp_path / "split.csv"
    save_speaker_splits(splits, path)
    assert load_speaker_splits(path) == splits


# --- Jeux réservés au test (P7) ---


def test_out_of_domain_datasets_are_always_in_test() -> None:
    config = load_split_config()
    for dataset in ["cafe", "ace", "openslr57", "team"]:
        row = make_rows(dataset, {"01": "F"}, files_per_speaker=1)[0]
        assert split_of_row(row, [], config) == "test"


# --- ESC-50 (P3) ---


def test_esc50_rounds_test_each_fold_once_and_train_finally_on_four() -> None:
    config = load_split_config()
    test_folds: list[int] = []
    for test_fold in range(1, config.esc50_fold_count + 1):
        esc_round = esc50_round(test_fold, config.esc50_fold_count)
        # Réglage : 3 folds d'entraînement, distincts de la validation et du test.
        assert len(esc_round.tuning_train_folds) == 3
        assert esc_round.validation_fold not in esc_round.tuning_train_folds
        assert esc_round.test_fold not in esc_round.tuning_train_folds
        # Entraînement final : les 4 folds hors test, comme dans les articles.
        assert len(esc_round.final_train_folds) == 4
        assert esc_round.test_fold not in esc_round.final_train_folds
        assert esc_round.validation_fold in esc_round.final_train_folds
        test_folds.append(esc_round.test_fold)
    assert test_folds == [1, 2, 3, 4, 5]
    # Le fold suivant sert de validation, et 1 après 5.
    assert esc50_round(5, 5).validation_fold == 1


# --- Vrais manifestes et vrai découpage versionnés ---


@needs_real_manifests
def test_real_mapping_counts_match_ly2() -> None:
    labels = load_emotion_labels()
    # Effectifs attendus de Ly2 : gardés, exclus, neutres, et chacune des 5 autres classes.
    expected = {
        "cremad": (7442, 0, 1087, 1271),
        "ravdess": (1056, 384, 96, 192),
    }
    for dataset, (kept, excluded, neutral, other) in expected.items():
        rows = load_manifest(MANIFESTS_DIR / f"{dataset}.csv")
        counts: Counter[str | None] = Counter()
        for row in rows:
            assert row.label is not None
            counts[common_emotion(dataset, row.label, labels)] += 1
        assert counts[None] == excluded
        assert sum(counts.values()) - excluded == kept
        assert counts["neutral"] == neutral
        for emotion in ["happy", "sad", "angry", "fear", "disgust"]:
            assert counts[emotion] == other


@needs_real_manifests
def test_real_split_matches_ly2_and_has_no_leak() -> None:
    config = load_split_config()
    splits = load_speaker_splits(EMOTION_SPLIT_PATH)
    check_no_speaker_leak(splits)
    counts: Counter[tuple[str, str, str]] = Counter()
    for speaker_split in splits:
        counts[(speaker_split.dataset, speaker_split.split, speaker_split.gender)] += 1
    # Tableau P1 de Ly2.
    assert counts[("cremad", "train", "M")] == 34
    assert counts[("cremad", "train", "F")] == 29
    assert counts[("cremad", "validation", "M")] == counts[("cremad", "validation", "F")] == 7
    assert counts[("cremad", "test", "M")] == counts[("cremad", "test", "F")] == 7
    assert counts[("ravdess", "train", "M")] == counts[("ravdess", "train", "F")] == 8
    assert counts[("ravdess", "validation", "M")] == counts[("ravdess", "validation", "F")] == 2
    assert counts[("ravdess", "test", "M")] == counts[("ravdess", "test", "F")] == 2
    # Le fichier versionné est bien celui que le script produit aujourd'hui (tirage unique).
    for dataset in config.training_emotion_datasets:
        rows = load_manifest(MANIFESTS_DIR / f"{dataset}.csv")
        regenerated = split_emotion_speakers(rows, config)
        versioned = [s for s in splits if s.dataset == dataset]
        assert regenerated == versioned
