"""Configuration de l'application : configs/app.yaml, surchargé par l'environnement.

Toute variable d'environnement préfixée par ``ECHOLENS_`` remplace la clé correspondante,
par exemple ``ECHOLENS_MAX_UPLOAD_MB=50``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

# Racine du dépôt : src/echolens/config.py → remonter de trois niveaux.
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"


class AppSettings(BaseModel):
    """Paramètres d'exécution de l'application Flask."""

    max_upload_mb: int = Field(default=100, gt=0)
    max_audio_seconds: float = Field(default=300.0, gt=0)
    data_dir: Path = REPO_ROOT / "var"
    # Racine des jeux de données ; sur Kaggle : ECHOLENS_DATASETS_DIR=/kaggle/input/...
    datasets_dir: Path = REPO_ROOT / "data"
    database_url: str = ""
    web_dist_dir: Path = REPO_ROOT / "web" / "dist"
    registry_path: Path = CONFIG_DIR / "registry.yaml"
    features_path: Path = CONFIG_DIR / "features.yaml"

    def resolved_database_url(self) -> str:
        """Renvoie l'URL SQLAlchemy ; par défaut une base SQLite dans data_dir."""
        return self.database_url or f"sqlite:///{self.data_dir / 'echolens.db'}"


def load_yaml(path: Path) -> dict[str, Any]:
    """Lit un fichier YAML et renvoie un dictionnaire (vide si le fichier est vide)."""
    with path.open(encoding="utf-8") as handle:
        content = yaml.safe_load(handle)
    if content is None:
        return {}
    if not isinstance(content, dict):
        raise ValueError(f"{path} doit contenir un dictionnaire YAML à la racine")
    return content


def load_settings(path: Path | None = None) -> AppSettings:
    """Charge les paramètres : fichier YAML, puis variables d'environnement ECHOLENS_*."""
    values: dict[str, Any] = {}
    config_path = path or CONFIG_DIR / "app.yaml"
    if config_path.exists():
        values.update(load_yaml(config_path))

    for field_name in AppSettings.model_fields:
        env_value = os.environ.get(f"ECHOLENS_{field_name.upper()}")
        if env_value is not None:
            values[field_name] = env_value

    return AppSettings(**values)
