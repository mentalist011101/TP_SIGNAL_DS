"""Route du catalogue des modèles (EF-16) : GET /api/v1/models, lu dans configs/registry.yaml.

La route ne fait que traduire HTTP ↔ service : la mise en forme vit dans
echolens.services.model_catalog.
"""

from __future__ import annotations

from typing import Any

from flask import current_app
from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields

from echolens.config import AppSettings
from echolens.services.model_catalog import list_models

blp = Blueprint(
    "models", __name__, url_prefix="/api/v1/models", description="Modèles du registre (S1)"
)


class ModelSchema(Schema):
    """Un modèle du registre, avec ce qu'il faut pour le comparer et le retrouver."""

    id = fields.String(
        required=True, metadata={"description": "Identifiant, aussi nom du dépôt Hugging Face."}
    )
    task = fields.String(
        required=True,
        metadata={"description": "emotion, sound_event, transcription, speaker ou voice_cloning."},
    )
    family = fields.String(
        required=True, metadata={"description": "Famille comparée : baseline, A, B ou pretrained."}
    )
    profiles = fields.List(
        fields.String(),
        required=True,
        metadata={"description": "Profils qui utilisent ce modèle : quality, realtime (EF-07)."},
    )
    version = fields.String(required=True)
    f1_macro = fields.Float(
        allow_none=True,
        metadata={
            "description": "F1 macro de test (ESC-50 : moyenne des 5 tours, P3 ; émotions : "
            "moyenne des 3 graines, P1) ; null si non mesuré."
        },
    )
    accuracy = fields.Float(allow_none=True, metadata={"description": "Accuracy de test."})
    temperature = fields.Float(
        allow_none=True,
        metadata={"description": "Température T de la calibration (ENF-06) ; null sinon."},
    )
    calibrated = fields.Boolean(
        required=True, metadata={"description": "Vrai si les probabilités sont calibrées."}
    )
    huggingface_url = fields.String(
        allow_none=True, metadata={"description": "Page du dépôt des poids sur Hugging Face."}
    )
    revision = fields.String(
        allow_none=True, metadata={"description": "Révision figée des poids (hash de commit)."}
    )
    description = fields.String(required=True)


@blp.route("")
class Models(MethodView):
    @blp.response(200, ModelSchema(many=True))
    def get(self) -> list[dict[str, Any]]:
        """Liste les modèles du registre, dans l'ordre de configs/registry.yaml."""
        settings: AppSettings = current_app.config["ECHOLENS_SETTINGS"]
        return list_models(settings.registry_path)
