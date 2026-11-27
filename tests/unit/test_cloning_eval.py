"""Évaluation du clonage (EF-18, C35b) : la partie sans modèle."""

from pathlib import Path

import numpy as np
import pytest

from echolens.core.speaker_id import unit_vector
from echolens.training.cloning_eval import (
    MissingConsentError,
    cosine_scores,
    find_team_voices,
    load_cloning_eval_config,
    similarity_summary,
    voice_report,
)
from echolens.training.transcription_eval import score_sentence


def make_voice(root: Path, name: str, consent: bool = True) -> None:
    folder = root / name
    (folder / "reference").mkdir(parents=True)
    (folder / "test").mkdir()
    (folder / "reference" / "r1.wav").write_bytes(b"")
    (folder / "test" / "t1.wav").write_bytes(b"")
    if consent:
        (folder / "consentement.txt").write_text("clonage-v1", encoding="utf-8")


def test_repository_config_is_valid() -> None:
    config = load_cloning_eval_config()

    assert config.consent_file == "consentement.txt"
    assert len(config.sentences) >= 5


def test_team_voices_are_found_in_alphabetical_order(tmp_path: Path) -> None:
    make_voice(tmp_path, "steve")
    make_voice(tmp_path, "luciano")

    voices = find_team_voices(tmp_path, load_cloning_eval_config())

    assert [voice.name for voice in voices] == ["luciano", "steve"]
    assert voices[0].reference_paths[0].name == "r1.wav"


def test_a_voice_without_written_consent_stops_everything(tmp_path: Path) -> None:
    make_voice(tmp_path, "luciano")
    make_voice(tmp_path, "inconnu", consent=False)

    with pytest.raises(MissingConsentError, match="inconnu"):
        find_team_voices(tmp_path, load_cloning_eval_config())


def test_cosine_scores_use_unit_vectors() -> None:
    voice = unit_vector(np.array([1.0, 0.0]))

    scores = cosine_scores([np.array([3.0, 0.0]), np.array([0.0, 2.0])], voice)

    assert scores == pytest.approx([1.0, 0.0])


def test_similarity_summary_counts_scores_above_threshold() -> None:
    summary = similarity_summary([0.9, 0.6, 0.3, 0.5], threshold=0.5485)

    assert summary["count"] == 4
    assert summary["mean"] == pytest.approx(0.575)
    assert summary["share_above_threshold"] == pytest.approx(0.5)


def test_voice_report_has_both_witnesses_and_the_wer() -> None:
    transcriptions = [score_sentence("1", "luciano", "Bonjour à tous", "bonjour à tous")]

    report = voice_report([0.8, 0.7], [0.9], [0.2], transcriptions, threshold=0.5485)

    assert report["clones"]["share_above_threshold"] == 1.0
    assert report["real_sentences"]["mean"] == pytest.approx(0.9)
    assert report["other_voices_clones"]["share_above_threshold"] == 0.0
    assert report["transcription"]["wer"] == 0.0


def test_single_voice_has_no_other_voice_witness() -> None:
    transcriptions = [score_sentence("1", "luciano", "un deux", "un trois")]

    report = voice_report([0.8], [0.9], [], transcriptions, threshold=0.5485)

    assert "other_voices_clones" not in report
    assert report["transcription"]["wer"] == pytest.approx(0.5)
