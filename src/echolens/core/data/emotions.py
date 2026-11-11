"""Correspondance des étiquettes d'émotion vers les 6 classes communes (P2, règles Ly2).

Chaque jeu a sa propre liste d'émotions : CREMA-D en a 6, RAVDESS 8, CaFE 7. Le manifeste
garde l'étiquette d'origine (P9) ; ce module la traduit en l'une des 6 classes communes
(neutral, happy, sad, angry, fear, disgust), ou l'exclut (calme, surprise). La table de
correspondance est dans configs/labels.yaml, jamais dans le code.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from echolens.config import CONFIG_DIR, load_yaml

LABELS_PATH = CONFIG_DIR / "labels.yaml"


class EmotionLabels(BaseModel):
    """Les 6 classes communes et la table de correspondance de chaque jeu."""

    # Identifiants des classes communes, dans l'ordre de configs/labels.yaml.
    emotions: list[str]
    # Jeu → (étiquette d'origine → classe commune, ou None si l'étiquette est exclue).
    label_mapping: dict[str, dict[str, str | None]]


def load_emotion_labels(path: Path = LABELS_PATH) -> EmotionLabels:
    """Lit configs/labels.yaml et vérifie que chaque correspondance vise une classe commune."""
    content = load_yaml(path)
    # Étape 1 : la liste des identifiants des classes communes.
    emotion_ids: list[str] = []
    for emotion in content["emotions"]:
        emotion_ids.append(emotion["id"])
    # Étape 2 : la table de correspondance, lue telle quelle.
    labels = EmotionLabels(emotions=emotion_ids, label_mapping=content["label_mapping"])
    # Étape 3 : refuser une faute de frappe dans le YAML (ex. « angy » au lieu de « angry »).
    _check_targets_are_common_emotions(labels)
    return labels


def common_emotion(dataset: str, original_label: str, labels: EmotionLabels) -> str | None:
    """Classe commune d'une étiquette d'origine (« ravdess », « 05 » → « angry »).

    Renvoie None si l'étiquette est exclue (calme, surprise). Lève ValueError si le jeu ou
    l'étiquette n'est pas dans la table : on ne devine jamais une correspondance.
    """
    if dataset not in labels.label_mapping:
        raise ValueError(f"Aucune correspondance d'émotions pour le jeu « {dataset} »")
    mapping = labels.label_mapping[dataset]
    if original_label not in mapping:
        raise ValueError(
            f"Étiquette « {original_label} » inconnue pour le jeu « {dataset} » "
            "(à ajouter dans configs/labels.yaml, label_mapping)"
        )
    return mapping[original_label]


def _check_targets_are_common_emotions(labels: EmotionLabels) -> None:
    common = set(labels.emotions)
    for dataset, mapping in labels.label_mapping.items():
        for original_label, target in mapping.items():
            if target is None:
                continue
            if target not in common:
                raise ValueError(
                    f"configs/labels.yaml : « {dataset} » « {original_label} » vise « {target} », "
                    "qui n'est pas une des classes communes"
                )
