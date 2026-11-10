import csv
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from echolens.core.data.esc50 import build_esc50_manifest

ESC50_COLUMNS = ["filename", "fold", "target", "category", "esc10", "src_file", "take"]
SAMPLE_RATE = 44_100


def write_mini_esc50(root: Path, records: list[dict[str, str]]) -> None:
    """Mini ESC-50 de synthèse : un WAV de 0,5 s par ligne, plus meta/esc50.csv."""
    (root / "audio").mkdir(parents=True)
    (root / "meta").mkdir()
    silence = np.zeros(SAMPLE_RATE // 2, dtype=np.float32)
    for record in records:
        sf.write(root / "audio" / record["filename"], silence, SAMPLE_RATE)
    with (root / "meta" / "esc50.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ESC50_COLUMNS)
        writer.writeheader()
        writer.writerows(records)


def record(filename: str, fold: str, target: str, category: str, src_file: str) -> dict[str, str]:
    return {
        "filename": filename,
        "fold": fold,
        "target": target,
        "category": category,
        "esc10": "False",
        "src_file": src_file,
        "take": "A",
    }


def test_manifest_fields_come_from_metadata(tmp_path: Path) -> None:
    records = [
        record("1-100032-A-0.wav", "1", "0", "dog", "100032"),
        record("2-100038-A-14.wav", "2", "14", "chirping_birds", "100038"),
        record("2-100038-B-14.wav", "2", "14", "chirping_birds", "100038"),
    ]
    write_mini_esc50(tmp_path, records)

    rows = build_esc50_manifest(tmp_path)

    assert len(rows) == 3
    first = rows[0]
    assert first.dataset == "esc50"
    assert first.path == "audio/1-100032-A-0.wav"
    assert first.label == "dog"
    assert first.fold == 1
    assert first.source == "100032"
    assert first.duration_s == pytest.approx(0.5)
    assert rows[2].fold == 2


def test_known_official_exception_is_accepted(tmp_path: Path) -> None:
    # Cas réel d'ESC-50 : la source 134049 sert à hen (fold 2) et à rooster (fold 3).
    records = [
        record("2-134049-A-6.wav", "2", "6", "hen", "134049"),
        record("3-134049-A-1.wav", "3", "1", "rooster", "134049"),
    ]
    write_mini_esc50(tmp_path, records)

    rows = build_esc50_manifest(tmp_path)

    assert [row.fold for row in rows] == [2, 3]


def test_same_source_in_two_folds_is_rejected(tmp_path: Path) -> None:
    records = [
        record("1-100032-A-0.wav", "1", "0", "dog", "100032"),
        record("3-100032-B-0.wav", "3", "0", "dog", "100032"),
        record("2-100038-A-14.wav", "2", "14", "chirping_birds", "100038"),
    ]
    write_mini_esc50(tmp_path, records)

    with pytest.raises(ValueError, match="100032"):
        build_esc50_manifest(tmp_path)
