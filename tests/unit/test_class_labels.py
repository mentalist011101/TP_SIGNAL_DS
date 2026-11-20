"""Libellés des classes : 6 émotions et 50 classes d'ESC-50 dans l'ordre des cibles."""

from echolens.config import REPO_ROOT
from echolens.core.data.class_labels import load_class_labels
from echolens.core.data.emotions import load_emotion_labels
from echolens.core.data.manifest import load_manifest
from echolens.training.esc50_svm import esc50_target

ESC50_MANIFEST = REPO_ROOT / "data" / "manifests" / "esc50.csv"


def test_esc50_has_50_unique_ids_in_the_order_of_the_targets() -> None:
    labels = load_class_labels()
    ids = [class_label.id for class_label in labels.esc50_classes]
    assert len(ids) == 50
    assert len(set(ids)) == 50
    # La classe i de labels.yaml est la classe de cible i dans le manifeste d'ESC-50.
    label_of_target: dict[int, str] = {}
    for row in load_manifest(ESC50_MANIFEST):
        target = esc50_target(row.path)
        assert row.label is not None
        label_of_target[target] = row.label
    expected = [label_of_target[target] for target in range(50)]
    assert ids == expected


def test_every_esc50_class_has_a_french_label() -> None:
    labels = load_class_labels()
    french = [class_label.label_fr for class_label in labels.esc50_classes]
    assert len(set(french)) == 50
    assert french[0] == "Chien"
    assert french[10] == "Pluie"


def test_emotions_are_the_6_common_classes_in_the_same_order() -> None:
    labels = load_class_labels()
    ids = [class_label.id for class_label in labels.emotions]
    assert ids == load_emotion_labels().emotions
    assert labels.emotions[3].label_fr == "Colère"
