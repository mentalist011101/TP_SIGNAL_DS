"""Fiche d'un modèle (EF-16) : ses scores, sa calibration, sa matrice de confusion et son F1 par
classe, lus dans le registre et dans les résultats versionnés des notebooks (training/results/).

Rien n'est recalculé : la fiche recopie ce que les notebooks ont mesuré, et dit d'où vient
chaque chiffre (fichier, commit). configs/model_cards.yaml indique, pour chaque modèle de
classification, où trouver la matrice et le F1 par classe dans son fichier de résultats. Les
modèles de transcription, de locuteur et de clonage n'ont pas de matrice : leur fiche se limite
au registre.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from echolens.config import CONFIG_DIR, REPO_ROOT, load_yaml
from echolens.core.data.class_labels import ClassLabel, ClassLabels
from echolens.core.models.registry import ModelEntry
from echolens.services.model_catalog import model_summary

MODEL_CARDS_PATH = CONFIG_DIR / "model_cards.yaml"
JsonPath = list[str | int]


class CardSource(BaseModel):
    """Où trouver les chiffres d'un modèle dans son fichier de résultats."""

    model_id: str
    results: str
    evaluation: str
    task_labels: Literal["emotions", "esc50"]
    confusion: JsonPath = Field(min_length=1)
    confusion_labels: JsonPath | None = None
    per_class_f1: JsonPath = Field(min_length=1)


class CardSources(BaseModel):
    """Contenu de configs/model_cards.yaml."""

    cards: list[CardSource]


def load_card_sources(path: Path = MODEL_CARDS_PATH) -> dict[str, CardSource]:
    """Sources des fiches, rangées par identifiant de modèle."""
    sources = CardSources(**load_yaml(path))
    by_model: dict[str, CardSource] = {}
    for source in sources.cards:
        by_model[source.model_id] = source
    return by_model


def model_card(
    entry: ModelEntry,
    sources: dict[str, CardSource],
    labels: ClassLabels,
    repo_root: Path = REPO_ROOT,
) -> dict[str, Any]:
    """Fiche d'un modèle : le résumé du catalogue, l'ECE, puis la matrice et le F1 par classe
    s'il s'agit d'un modèle de classification (schéma ModelCardSchema)."""
    card = model_summary(entry)
    card["ece_before"] = entry.ece_before
    card["ece_after"] = entry.ece_after
    card["evaluation"] = None
    card["results_file"] = None
    card["results_commit"] = None
    card["confusion"] = None
    card["per_class_f1"] = []
    source = sources.get(entry.id)
    if source is None:
        return card
    # Étape 1 : le fichier de résultats, tel que le notebook l'a écrit.
    results_path = repo_root / source.results
    results = json.loads(results_path.read_text(encoding="utf-8"))
    classes = _task_classes(labels, source.task_labels)
    # Étape 2 : la matrice et le F1 par classe, aux endroits indiqués par la configuration.
    card["evaluation"] = source.evaluation
    card["results_file"] = source.results
    card["results_commit"] = results.get("commit")
    card["confusion"] = _confusion(results, source, classes)
    card["per_class_f1"] = _per_class_f1(results, source, classes)
    return card


def read_path(document: Any, path: JsonPath) -> Any:
    """Valeur au bout d'un chemin de clés (dictionnaires) et de positions (listes)."""
    value = document
    for step in path:
        value = value[step]
    return value


def _task_classes(labels: ClassLabels, task_labels: str) -> list[ClassLabel]:
    if task_labels == "emotions":
        return labels.emotions
    return labels.esc50_classes


def _confusion(results: Any, source: CardSource, classes: list[ClassLabel]) -> dict[str, Any]:
    # Lignes = vraie classe ; noms des catégories ESC-50, ou libellés français des classes.
    matrix = read_path(results, source.confusion)
    names = [class_label.label_fr for class_label in classes]
    if source.confusion_labels is not None:
        names = read_path(results, source.confusion_labels)
    if len(names) != len(matrix):
        raise ValueError(f"{source.model_id} : {len(names)} noms pour {len(matrix)} lignes.")
    return {"labels": names, "matrix": matrix}


def _per_class_f1(
    results: Any, source: CardSource, classes: list[ClassLabel]
) -> list[dict[str, Any]]:
    # Deux formats selon le notebook : nombres dans l'ordre des classes, ou {class, f1}.
    raw = read_path(results, source.per_class_f1)
    f1_by_class: dict[str, float] = {}
    for position, item in enumerate(raw):
        if isinstance(item, dict):
            f1_by_class[item["class"]] = float(item["f1"])
        else:
            f1_by_class[classes[position].id] = float(item)
    rows = []
    for class_label in classes:
        f1 = f1_by_class[class_label.id]
        rows.append({"label": class_label.id, "label_fr": class_label.label_fr, "f1": f1})
    # Du mieux reconnu au moins bien reconnu.
    rows.sort(key=_f1_of, reverse=True)
    return rows


def _f1_of(row: dict[str, Any]) -> float:
    f1: float = row["f1"]
    return f1
