"""Catalogue des modèles pour l'interface (EF-16) : ce que dit configs/registry.yaml (S1).

Le catalogue ne charge aucun modèle : il lit le registre et le met en forme pour la page
Modèles et pour la page Résultat (F1 de test, température, lien vers Hugging Face).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from echolens.core.models.registry import ModelEntry, ModelRegistry

HF_PREFIX = "hf://"
HF_WEBSITE = "https://huggingface.co/"


def huggingface_url(weights: str) -> str | None:
    """Page Hugging Face d'un dépôt « hf://<utilisateur>/<dépôt> » ; None pour un autre dépôt."""
    if not weights.startswith(HF_PREFIX):
        return None
    repository = weights.removeprefix(HF_PREFIX)
    return HF_WEBSITE + repository


def model_summary(entry: ModelEntry) -> dict[str, Any]:
    """Une entrée du registre, telle que l'API la renvoie (schéma ModelSchema)."""
    profiles = [profile.value for profile in entry.profiles]
    return {
        "id": entry.id,
        "task": entry.task.value,
        "family": entry.family.value,
        "profiles": profiles,
        "version": entry.version,
        "f1_macro": entry.metrics.get("f1_macro"),
        "accuracy": entry.metrics.get("accuracy"),
        "temperature": entry.temperature,
        "calibrated": entry.temperature is not None,
        "huggingface_url": huggingface_url(entry.weights),
        "revision": entry.revision or None,
        "description": entry.description,
    }


def list_models(registry_path: Path) -> list[dict[str, Any]]:
    """Tous les modèles du registre, dans l'ordre du fichier."""
    registry = ModelRegistry.from_yaml(registry_path)
    summaries = []
    for entry in registry.models:
        summaries.append(model_summary(entry))
    return summaries
