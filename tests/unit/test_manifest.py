from pathlib import Path

import pytest
from pydantic import ValidationError

from echolens.config import CONFIG_DIR, load_settings, load_yaml
from echolens.core.data.manifest import (
    ManifestRow,
    check_manifest,
    load_manifest,
    save_manifest,
)
from echolens.core.models.registry import Task


def make_row(
    path: str, dataset: str = "esc50", fold: int = 1, source: str = "100032"
) -> ManifestRow:
    return ManifestRow(
        dataset=dataset, path=path, label="dog", duration_s=5.0, fold=fold, source=source
    )


def test_save_then_load_gives_identical_rows(tmp_path: Path) -> None:
    rows = [
        make_row("audio/1-100032-A-0.wav"),
        ManifestRow(
            dataset="cremad",
            path="AudioWAV/1001_DFA_ANG_XX.wav",
            label="ANG",
            speaker="1001",
            gender="M",
            duration_s=2.275,
            intensity="XX",
            transcript='Don\'t forget a jacket, "please"',
        ),
        ManifestRow(dataset="openslr57", path="wav/é 1.wav", duration_s=0.1),
    ]
    manifest_path = tmp_path / "manifest.csv"

    save_manifest(rows, manifest_path)
    loaded = load_manifest(manifest_path)

    assert loaded == rows


def test_saved_columns_follow_fixed_order(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.csv"
    save_manifest([make_row("a.wav")], manifest_path)
    header = manifest_path.read_text(encoding="utf-8").splitlines()[0]
    assert header == "dataset,path,label,speaker,gender,duration_s,fold,intensity,source,transcript"


def test_zero_duration_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ManifestRow(dataset="esc50", path="a.wav", duration_s=0.0)


def test_duplicate_path_is_rejected() -> None:
    rows = [make_row("a.wav"), make_row("a.wav")]
    with pytest.raises(ValueError, match="double"):
        check_manifest(rows)


def test_mixed_datasets_are_rejected() -> None:
    rows = [make_row("a.wav", dataset="esc50"), make_row("b.wav", dataset="cremad")]
    with pytest.raises(ValueError, match="plusieurs jeux"):
        check_manifest(rows)


def test_source_split_across_folds_is_rejected() -> None:
    rows = [make_row("a.wav", fold=1), make_row("b.wav", fold=2)]
    with pytest.raises(ValueError, match="folds"):
        check_manifest(rows)


def test_valid_manifest_passes() -> None:
    rows = [make_row("a.wav", fold=1), make_row("b.wav", fold=1, source="200000")]
    check_manifest(rows)


def test_datasets_config_is_valid() -> None:
    datasets = load_yaml(CONFIG_DIR / "datasets.yaml")["datasets"]
    ids = [entry["id"] for entry in datasets]
    assert ids == ["esc50", "cremad", "ravdess", "cafe", "openslr57"]
    allowed_tasks = {Task.EMOTION, Task.SOUND_EVENT, Task.TRANSCRIPTION, Task.SPEAKER}
    for entry in datasets:
        assert entry["task"] in allowed_tasks
        assert entry["name"]
        assert entry["url"].startswith("https://")
        assert entry["license"]
        assert entry["role"]


def test_labels_config_has_the_six_p2_emotions() -> None:
    emotions = load_yaml(CONFIG_DIR / "labels.yaml")["emotions"]
    ids = [emotion["id"] for emotion in emotions]
    assert ids == ["neutral", "happy", "sad", "angry", "fear", "disgust"]
    for emotion in emotions:
        assert emotion["label_fr"]


def test_datasets_dir_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ECHOLENS_DATASETS_DIR", "/kaggle/input/esc50")
    assert load_settings().datasets_dir == Path("/kaggle/input/esc50")
