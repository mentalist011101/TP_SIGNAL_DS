"""Libellés des classes prédites : identifiant anglais et libellé français (EF-05, EF-06).

L'ordre des listes de configs/labels.yaml est l'ordre des sorties des modèles : la case i des
probabilités correspond à la classe i de la liste.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from echolens.config import CONFIG_DIR, load_yaml

LABELS_PATH = CONFIG_DIR / "labels.yaml"


class ClassLabel(BaseModel):
    """Une classe : identifiant utilisé par les modèles et l'API, libellé affiché."""

    id: str = Field(min_length=1)
    label_fr: str = Field(min_length=1)


class ClassLabels(BaseModel):
    """Classes des deux tâches de classification, dans l'ordre des sorties des modèles."""

    # Les 6 classes communes d'émotion (P2).
    emotions: list[ClassLabel] = Field(min_length=1)
    # Les 50 classes d'ESC-50, dans l'ordre des cibles 0 à 49.
    esc50_classes: list[ClassLabel] = Field(min_length=1)


def load_class_labels(path: Path = LABELS_PATH) -> ClassLabels:
    """Lit les classes d'émotion et d'ESC-50 dans configs/labels.yaml."""
    content = load_yaml(path)
    return ClassLabels(emotions=content["emotions"], esc50_classes=content["esc50_classes"])
