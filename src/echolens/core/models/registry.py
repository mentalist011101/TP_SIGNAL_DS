"""Registre des modèles (décision S1) : décrit chaque modèle disponible sans toucher au code."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from echolens.config import load_yaml


class Task(StrEnum):
    """Tâches couvertes par EchoLens."""

    EMOTION = "emotion"
    SOUND_EVENT = "sound_event"
    TRANSCRIPTION = "transcription"
    SPEAKER = "speaker"
    VOICE_CLONING = "voice_cloning"


class Profile(StrEnum):
    """Profil d'analyse (EF-07) : il choisit les modèles, pas la source du son.

    quality : modèles les plus précis ; realtime : modèles légers, utilisés aussi pour le micro
    en direct.
    """

    QUALITY = "quality"
    REALTIME = "realtime"


class Family(StrEnum):
    """Famille de modèle comparée dans le protocole."""

    BASELINE = "baseline"
    A = "A"
    B = "B"
    PRETRAINED = "pretrained"


class ModelEntry(BaseModel):
    """Description d'un modèle : identité, tâche, emplacement des poids, labels, métriques."""

    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_\-]*$")
    task: Task
    family: Family
    profiles: list[Profile] = Field(min_length=1)
    version: str = "0.1.0"
    weights: str = ""
    labels: list[str] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    description: str = ""


class ModelRegistry(BaseModel):
    """Ensemble des modèles déclarés dans configs/registry.yaml."""

    models: list[ModelEntry] = Field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> ModelRegistry:
        """Charge le registre ; refuse les identifiants en double."""
        registry = cls(**load_yaml(path))
        ids = [entry.id for entry in registry.models]
        duplicates = sorted({model_id for model_id in ids if ids.count(model_id) > 1})
        if duplicates:
            raise ValueError(f"Identifiants de modèles en double : {', '.join(duplicates)}")
        return registry

    def get(self, model_id: str) -> ModelEntry:
        """Renvoie un modèle par son identifiant, ou lève KeyError."""
        for entry in self.models:
            if entry.id == model_id:
                return entry
        raise KeyError(f"Modèle inconnu : {model_id}")

    def for_task(self, task: Task, profile: Profile | None = None) -> list[ModelEntry]:
        """Liste les modèles d'une tâche, éventuellement filtrés par profil."""
        return [
            entry
            for entry in self.models
            if entry.task == task and (profile is None or profile in entry.profiles)
        ]
