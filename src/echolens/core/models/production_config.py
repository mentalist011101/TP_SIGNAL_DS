"""Description d'un modèle de production : le config.json publié avec ses poids (C13, I7, S1).

Sans torch : l'application lit ce fichier avant de charger les poids (safetensors). Tout ce
qu'il faut pour refaire exactement la chaîne d'entraînement y est écrit : classes dans l'ordre
des sorties, statistiques de standardisation (R4), température (E2), encodeur et sa révision
figée pour la famille B, empreinte de configs/features.yaml pour le CRNN (R5).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from echolens.core.models.network_config import NetworkConfig

CONFIG_FILE = "config.json"
WEIGHTS_FILE = "model.safetensors"


class EncoderReference(BaseModel):
    """Encodeur gelé de la famille B : dépôt Hugging Face, révision figée, trames utiles."""

    checkpoint: str
    revision: str = Field(min_length=40, max_length=40)
    sample_rate: int = Field(gt=0)
    samples_per_output_frame: int = Field(gt=0)
    max_output_frames: int = Field(gt=0)


class HeadShape(BaseModel):
    """Forme de la tête de la famille B (somme pondérée des couches, puis MLP)."""

    layer_count: int = Field(gt=0)
    dimension: int = Field(gt=0)
    hidden_size: int = Field(gt=0)
    dropout: float = Field(ge=0, lt=1)


class TrainingRecord(BaseModel):
    """Comment le modèle a été entraîné : réglage, graine, données, code."""

    learning_rate: float
    dropout: float
    epochs: int
    seed: int
    data: str
    commit: str


class Calibration(BaseModel):
    """Température et ECE avant / après, avec la façon dont elle a été mesurée (E2)."""

    temperature: float = Field(gt=0)
    method: str
    ece_before: float
    ece_after: float
    round_temperatures: list[float] = Field(default_factory=list)


class ProductionModelConfig(BaseModel):
    """Contenu de config.json, publié à côté de model.safetensors."""

    model_id: str
    task: Literal["emotion", "sound_event"]
    architecture: Literal["layer_weighted_head", "crnn"]
    # Identifiants des classes, dans l'ordre des sorties du modèle.
    labels: list[str] = Field(min_length=2)
    # Statistiques de l'entraînement, à réappliquer telles quelles (R4) : (couches, dimension)
    # pour la tête, une valeur par bande Mel pour le CRNN.
    standardization_mean: list[list[float]] | list[float]
    standardization_std: list[list[float]] | list[float]
    calibration: Calibration
    training: TrainingRecord
    # Fenêtres envoyées au modèle par l'application (D5), en secondes.
    window_s: float = Field(gt=0)
    head: HeadShape | None = None
    encoder: EncoderReference | None = None
    network: NetworkConfig | None = None
    # Empreinte SHA-256 de configs/features.yaml à l'entraînement (CRNN) : le log-Mel de
    # l'application doit être calculé avec exactement les mêmes paramètres (R5).
    features_sha256: str | None = None
    license: str


def save_production_config(config: ProductionModelConfig, directory: Path) -> Path:
    """Écrit config.json dans le dossier du modèle."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / CONFIG_FILE
    text = config.model_dump_json(indent=2)
    path.write_text(text + "\n", encoding="utf-8")
    return path


def load_production_config(path: Path) -> ProductionModelConfig:
    """Relit et valide un config.json."""
    text = path.read_text(encoding="utf-8")
    return ProductionModelConfig.model_validate_json(text)
