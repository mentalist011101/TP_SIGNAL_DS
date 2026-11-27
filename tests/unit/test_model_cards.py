"""Fiches des modèles (EF-16) : lecture des résultats versionnés, sans modèle."""

import json
from pathlib import Path

import numpy as np
import pytest

from echolens.config import CONFIG_DIR, REPO_ROOT
from echolens.core.data.class_labels import load_class_labels
from echolens.core.models.registry import ModelRegistry, Task
from echolens.services.model_cards import CardSource, load_card_sources, model_card, read_path

CLASSIFICATION_TASKS = (Task.EMOTION, Task.SOUND_EVENT)


def registry() -> ModelRegistry:
    return ModelRegistry.from_yaml(CONFIG_DIR / "registry.yaml")


def test_read_path_follows_keys_and_positions() -> None:
    document = {"seeds": [{"test": {"f1": [0.5, 0.7]}}]}

    assert read_path(document, ["seeds", 0, "test", "f1"]) == [0.5, 0.7]


def test_every_classification_model_has_a_card_source() -> None:
    sources = load_card_sources()
    for entry in registry().models:
        if entry.task in CLASSIFICATION_TASKS:
            assert entry.id in sources, entry.id
            assert entry.ece_before is not None and entry.ece_after is not None


@pytest.mark.parametrize("model_id", sorted(load_card_sources()))
def test_card_matrix_rows_sum_to_one_and_every_class_has_an_f1(model_id: str) -> None:
    entry = registry().get(model_id)
    labels = load_class_labels()

    card = model_card(entry, load_card_sources(), labels)

    matrix = card["confusion"]["matrix"]
    assert len(card["confusion"]["labels"]) == len(matrix)
    for row in matrix:
        assert sum(row) == pytest.approx(1.0, abs=1e-6)
    classes = labels.emotions if entry.task == Task.EMOTION else labels.esc50_classes
    assert len(card["per_class_f1"]) == len(classes)
    f1_values = [row["f1"] for row in card["per_class_f1"]]
    assert f1_values == sorted(f1_values, reverse=True)
    assert card["results_commit"]


def test_both_per_class_formats_give_the_same_rows(tmp_path: Path) -> None:
    labels = load_class_labels()
    emotion_ids = [class_label.id for class_label in labels.emotions]
    as_numbers = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    as_objects = [
        {"class": class_id, "f1": value}
        for class_id, value in zip(emotion_ids, as_numbers, strict=True)
    ]
    confusion = np.eye(6).tolist()
    results = {
        "commit": "abc",
        "confusion": confusion,
        "numbers": as_numbers,
        "objects": as_objects,
    }
    (tmp_path / "r.json").write_text(json.dumps(results), encoding="utf-8")
    entry = registry().get("echolens-emotion-crnn")
    cards = []
    for path in (["numbers"], ["objects"]):
        source = CardSource(
            model_id=entry.id,
            results="r.json",
            evaluation="test",
            task_labels="emotions",
            confusion=["confusion"],
            per_class_f1=path,
        )
        cards.append(model_card(entry, {entry.id: source}, labels, repo_root=tmp_path))

    assert cards[0]["per_class_f1"] == cards[1]["per_class_f1"]
    assert cards[0]["per_class_f1"][0]["label"] == "disgust"
    assert cards[0]["confusion"]["labels"][0] == "Neutre"


def test_model_without_card_source_keeps_registry_fields_only() -> None:
    entry = registry().for_task(Task.SPEAKER)[0]

    card = model_card(entry, load_card_sources(), load_class_labels(), repo_root=REPO_ROOT)

    assert card["id"] == entry.id
    assert card["confusion"] is None
    assert card["per_class_f1"] == []
