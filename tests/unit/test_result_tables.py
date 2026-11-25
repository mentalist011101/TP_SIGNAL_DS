"""Tableaux de la page Comparer, construits sur de petits fichiers de résultats fabriqués."""

import json
from pathlib import Path
from typing import Any

import pytest

from echolens.services.result_tables import (
    comparison_tables,
    emotion_rows,
    esc50_rows,
    mcnemar_row,
)

NAMES = {
    "mfcc_svm": {"label": "MFCC + SVM", "family": "baseline"},
    "crnn": {"label": "CRNN", "family": "A"},
    "whisper-base": {"label": "Whisper base", "family": "B"},
}


def write_json(folder: Path, name: str, content: dict[str, Any]) -> None:
    path = folder / name
    path.write_text(json.dumps(content), encoding="utf-8")


def nested(f1: float) -> dict[str, Any]:
    """Bloc de scores au format des fichiers C11 et C12."""
    return {
        "macro_f1": {"mean": f1, "std": 0.01},
        "accuracy": {"mean": f1 + 0.01, "std": 0.02},
        "macro_f1_ci": [f1 - 0.02, f1 + 0.02],
    }


def test_esc50_rows_read_flat_and_nested_files(tmp_path: Path) -> None:
    flat = {"macro_f1_mean": 0.4, "macro_f1_std": 0.04, "accuracy_mean": 0.42, "accuracy_std": 0.03}
    write_json(tmp_path, "esc50_mfcc_svm.json", flat)
    write_json(tmp_path, "c11_family_b_esc50.json", {"models": {"whisper-base": nested(0.83)}})

    rows = esc50_rows(tmp_path, NAMES)

    # Le fichier CNN et le fichier CRNN manquent : leurs lignes disparaissent, sans erreur.
    labels = [row["label"] for row in rows]
    assert labels == ["MFCC + SVM", "Whisper base"]
    assert rows[0]["family"] == "baseline"
    assert rows[0]["f1_macro_ci"] is None
    assert rows[1]["f1_macro_mean"] == 0.83
    assert rows[1]["f1_macro_ci"] == pytest.approx([0.81, 0.85])


def test_emotion_rows_take_family_a_summary_and_its_interval(tmp_path: Path) -> None:
    crnn = {"summary": nested(0.67), "macro_f1_ci": [0.65, 0.70]}
    write_json(tmp_path, "emotions_family_a_crnn.json", crnn)

    rows = emotion_rows(tmp_path, NAMES)

    assert len(rows) == 1
    assert rows[0]["label"] == "CRNN"
    assert rows[0]["f1_macro_ci"] == [0.65, 0.70]


def test_mcnemar_row_prefers_the_holm_corrected_p_value() -> None:
    test = {
        "model_a": "crnn",
        "model_b": "whisper-base",
        "macro_f1_a": 0.68,
        "macro_f1_b": 0.75,
        "only_a_right": 107,
        "only_b_right": 201,
        "p_value": 0.03,
        "p_value_holm": 0.09,
    }

    row = mcnemar_row(test, NAMES, 0.05)

    # p = 0,03 seul serait significatif ; corrigé de Holm (0,09), il ne l'est plus.
    assert row["model_a"] == "CRNN"
    assert row["model_b"] == "Whisper base"
    assert row["significant"] is False


def test_unknown_model_keeps_its_identifier() -> None:
    test = {
        "model_a": "nouveau-modele",
        "model_b": "crnn",
        "macro_f1_a": 0.5,
        "macro_f1_b": 0.6,
        "only_a_right": 1,
        "only_b_right": 9,
        "p_value": 0.01,
    }

    row = mcnemar_row(test, NAMES, 0.05)

    assert row["model_a"] == "nouveau-modele"
    assert row["p_value_holm"] is None
    assert row["significant"] is True


def test_empty_results_folder_gives_empty_tables(tmp_path: Path) -> None:
    tables = comparison_tables(tmp_path)

    assert [table["task"] for table in tables["classification"]] == ["sound_event", "emotion"]
    assert tables["classification"][0]["models"] == []
    assert tables["transcription"] == []
    assert tables["latency"] == []
