"""Forme des réseaux de la famille A (Brique 4), sans torch : lue dans configs/family_a.yaml.

Séparée des réseaux pour que la configuration se lise et se teste sans torch (CI).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class NetworkConfig(BaseModel):
    """Forme des réseaux CNN et CRNN (Brique 4)."""

    channels: list[int] = Field(min_length=1)
    kernel_size: int = Field(gt=0)
    padding: int = Field(ge=0)
    pool_size: int = Field(gt=0)
    dropout: float = Field(ge=0, lt=1)
    gru_hidden_size: int = Field(gt=0)
