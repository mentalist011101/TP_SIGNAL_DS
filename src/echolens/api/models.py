"""Routes des modèles (EF-16) : le catalogue (GET /api/v1/models, lu dans
configs/registry.yaml) et la fiche d'un modèle (GET /api/v1/models/{id}).

Les routes ne font que traduire HTTP ↔ service : la mise en forme vit dans
echolens.services.model_catalog et echolens.services.model_cards. Erreur : 404 si le modèle
n'est pas au registre (« message » en français).
"""

from __future__ import annotations

from typing import Any

from flask import current_app
from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields

# abort de webargs (republié par flask-smorest) : typé NoReturn, ce qui satisfait mypy.
from webargs.flaskparser import abort

from echolens.config import AppSettings
from echolens.core.data.class_labels import load_class_labels
from echolens.core.models.registry import ModelRegistry
from echolens.services.model_cards import load_card_sources, model_card
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


class ConfusionSchema(Schema):
    """Matrice de confusion normalisée : lignes = vraie classe, chaque ligne somme à 1."""

    labels = fields.List(
        fields.String(),
        required=True,
        metadata={"description": "Noms des lignes et des colonnes, dans l'ordre de la matrice."},
    )
    matrix = fields.List(
        fields.List(fields.Float()),
        required=True,
        metadata={"description": "matrix[i][j] : part des extraits de la classe i prédits j."},
    )


class ClassF1Schema(Schema):
    """F1 de test d'une classe."""

    label = fields.String(required=True)
    label_fr = fields.String(required=True)
    f1 = fields.Float(required=True)


class ModelCardSchema(ModelSchema):
    """Fiche d'un modèle (EF-16) : le catalogue, la calibration et, pour la classification, la
    matrice de confusion et le F1 par classe, recopiés des résultats des notebooks."""

    ece_before = fields.Float(
        allow_none=True,
        metadata={"description": "ECE avant la calibration (E2) ; null sans calibration."},
    )
    ece_after = fields.Float(
        allow_none=True,
        metadata={"description": "ECE après la calibration par température (ENF-06)."},
    )
    evaluation = fields.String(
        allow_none=True, metadata={"description": "Sur quoi les chiffres ont été mesurés."}
    )
    results_file = fields.String(
        allow_none=True,
        metadata={"description": "Fichier de résultats du dépôt d'où viennent les chiffres."},
    )
    results_commit = fields.String(
        allow_none=True, metadata={"description": "Commit du code qui a produit ces résultats."}
    )
    confusion = fields.Nested(ConfusionSchema, allow_none=True)
    per_class_f1 = fields.List(
        fields.Nested(ClassF1Schema),
        required=True,
        metadata={
            "description": "F1 de chaque classe, du plus haut au plus bas ; vide hors "
            "classification."
        },
    )


@blp.route("/<model_id>")
class ModelCard(MethodView):
    @blp.response(200, ModelCardSchema)
    @blp.alt_response(404, description="Modèle absent du registre.")
    def get(self, model_id: str) -> dict[str, Any]:
        """Fiche d'un modèle : scores, calibration, matrice de confusion, F1 par classe."""
        settings: AppSettings = current_app.config["ECHOLENS_SETTINGS"]
        registry = ModelRegistry.from_yaml(settings.registry_path)
        try:
            entry = registry.get(model_id)
        except KeyError:
            abort(404, message=f"Aucun modèle « {model_id} » dans le registre.")
        return model_card(entry, load_card_sources(), load_class_labels())
