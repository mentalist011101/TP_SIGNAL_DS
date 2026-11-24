"""Tests du découpage pour l'identification du locuteur (P11, C15)."""

from pathlib import Path

import pytest

from echolens.core.data.manifest import ManifestRow
from echolens.core.data.speaker_enrollment import (
    SpeakerConfig,
    load_speaker_config,
    save_enrollment,
    speaker_key,
    split_enrollment,
)


def make_config() -> SpeakerConfig:
    return SpeakerConfig(
        seed=42,
        enrollment_per_speaker=5,
        min_utterances_per_speaker=10,
        sample_rate=16000,
        max_seconds=20.0,
        encoders=[],
    )


def make_rows(subset: str, speaker: str, count: int) -> list[ManifestRow]:
    """count phrases de synthèse pour un locuteur (aucun vrai fichier n'est lu)."""
    rows = []
    for index in range(count):
        path = f"speech/train/{subset}/{speaker}/{speaker}_{index:03d}.wav"
        row = ManifestRow(
            dataset="openslr57", path=path, speaker=speaker, duration_s=1.0, subset=subset
        )
        rows.append(row)
    return rows


def test_config_file_is_valid() -> None:
    config = load_speaker_config()
    assert config.enrollment_per_speaker == 5
    assert config.min_utterances_per_speaker == 10
    assert config.seed == 42


def test_speaker_key_includes_subset() -> None:
    # Le même dossier « 002 » dans train et devtest de ca16 est la même personne.
    row = make_rows("ca16", "002", 1)[0]
    assert speaker_key(row) == "ca16/002"


def test_phrases_are_split_without_overlap() -> None:
    rows = make_rows("ca16", "002", 12) + make_rows("ca16", "003", 10)

    speakers = split_enrollment(rows, make_config())

    assert len(speakers) == 2
    for speaker in speakers:
        assert len(speaker.enrollment_paths) == 5
        # P11 : aucune phrase à la fois en enregistrement et en test.
        assert set(speaker.enrollment_paths).isdisjoint(speaker.test_paths)
    first = speakers[0]
    assert first.speaker == "ca16/002"
    assert len(first.test_paths) == 7


def test_speakers_with_too_few_phrases_are_dropped() -> None:
    rows = make_rows("ca16", "002", 10) + make_rows("ca16", "003", 9)

    speakers = split_enrollment(rows, make_config())

    assert [speaker.speaker for speaker in speakers] == ["ca16/002"]


def test_four_groups_within_each_subset() -> None:
    rows = []
    for number in range(8):
        rows += make_rows("ca16", f"00{number}", 10)
        rows += make_rows("yaounde", f"ctell1-0{number}", 10)

    speakers = split_enrollment(rows, make_config())

    for subset in ["ca16", "yaounde"]:
        groups = [speaker.group for speaker in speakers if speaker.subset == subset]
        for group in ["calibration", "evaluation", "impostor_calibration", "impostor_evaluation"]:
            assert groups.count(group) == 2


def test_split_is_deterministic() -> None:
    rows = make_rows("ca16", "002", 15) + make_rows("niger", "niger_sys1_1", 15)

    first = split_enrollment(rows, make_config())
    reversed_rows = list(reversed(rows))
    second = split_enrollment(reversed_rows, make_config())

    assert first == second


def test_missing_speaker_raises() -> None:
    row = ManifestRow(dataset="openslr57", path="x.wav", duration_s=1.0, subset="ca16")
    with pytest.raises(ValueError, match="Locuteur manquant"):
        speaker_key(row)


def test_save_enrollment_writes_one_line_per_phrase(tmp_path: Path) -> None:
    rows = make_rows("ca16", "002", 10)
    speakers = split_enrollment(rows, make_config())
    output = tmp_path / "split.csv"

    save_enrollment(speakers, output)

    lines = output.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "speaker,subset,group,role,path"
    assert len(lines) == 11
    enrollment_lines = [line for line in lines if ",enrollment," in line]
    assert len(enrollment_lines) == 5
