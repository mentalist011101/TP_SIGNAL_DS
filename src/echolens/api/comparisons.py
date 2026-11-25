"""Route de la page Comparer : GET /api/v1/comparisons, lue dans training/results/.

La route ne fait que traduire HTTP ↔ service : la lecture et la mise en forme des fichiers de
résultats vivent dans echolens.services.result_tables.
"""

from __future__ import annotations

from typing import Any

from flask import current_app
from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields

from echolens.config import AppSettings
from echolens.services.result_tables import comparison_tables

blp = Blueprint(
    "comparisons",
    __name__,
    url_prefix="/api/v1/comparisons",
    description="Résultats des expériences, pour comparer les modèles (E1, E5, E6)",
)


class ModelScoreSchema(Schema):
    """Scores de test d'un modèle sur une tâche."""

    model = fields.String(
        required=True, metadata={"description": "Identifiant dans les résultats."}
    )
    label = fields.String(required=True, metadata={"description": "Nom affiché."})
    family = fields.String(required=True, metadata={"description": "baseline, A ou B."})
    f1_macro_mean = fields.Float(required=True, metadata={"description": "F1 macro moyen."})
    f1_macro_std = fields.Float(required=True, metadata={"description": "Écart-type du F1 macro."})
    accuracy_mean = fields.Float(required=True)
    accuracy_std = fields.Float(required=True)
    f1_macro_ci = fields.List(
        fields.Float(),
        allow_none=True,
        metadata={"description": "Intervalle de confiance à 95 % (bootstrap) ; null s'il manque."},
    )


class McNemarSchema(Schema):
    """Test de McNemar entre deux modèles, sur les mêmes extraits de test (P8)."""

    model_a = fields.String(required=True)
    model_b = fields.String(required=True)
    f1_macro_a = fields.Float(required=True)
    f1_macro_b = fields.Float(required=True)
    only_a_right = fields.Integer(
        required=True, metadata={"description": "Extraits que seul le modèle A classe bien."}
    )
    only_b_right = fields.Integer(
        required=True, metadata={"description": "Extraits que seul le modèle B classe bien."}
    )
    p_value = fields.Float(required=True)
    p_value_holm = fields.Float(
        allow_none=True, metadata={"description": "p-valeur corrigée de Holm ; null sinon."}
    )
    significant = fields.Boolean(
        required=True, metadata={"description": "Vrai si p < 0,05 (Holm quand elle existe)."}
    )


class TaskTableSchema(Schema):
    """Tableau d'une tâche de classification : ses modèles et ses tests."""

    task = fields.String(required=True, metadata={"description": "sound_event ou emotion."})
    protocol = fields.String(required=True, metadata={"description": "Données et protocole."})
    models = fields.List(fields.Nested(ModelScoreSchema), required=True)
    tests = fields.List(fields.Nested(McNemarSchema), required=True)


class TranscriptionScoreSchema(Schema):
    """WER et CER d'un modèle Whisper sur un corpus (C17)."""

    model = fields.String(required=True)
    corpus = fields.String(required=True)
    wer = fields.Float(required=True)
    wer_ci = fields.List(fields.Float(), required=True)
    cer = fields.Float(required=True)
    rtf_cpu = fields.Float(
        required=True, metadata={"description": "Temps de calcul ÷ durée de l'audio, sur CPU."}
    )


class LatencySchema(Schema):
    """Taille et vitesse d'un modèle de production sur CPU (E6)."""

    model = fields.String(required=True)
    task = fields.String(required=True)
    f1_macro = fields.Float(required=True)
    parameters = fields.Integer(required=True, metadata={"description": "Paramètres au total."})
    p95_2s = fields.Float(required=True, metadata={"description": "Latence p95, fenêtre de 2 s."})
    rtf_p95_2s = fields.Float(required=True)
    p95_5s = fields.Float(required=True, metadata={"description": "Latence p95, fenêtre de 5 s."})
    realtime = fields.Boolean(
        required=True, metadata={"description": "Vrai si choisi pour le profil temps réel."}
    )


class ComparisonsSchema(Schema):
    """Tous les tableaux de la page Comparer."""

    classification = fields.List(fields.Nested(TaskTableSchema), required=True)
    transcription = fields.List(fields.Nested(TranscriptionScoreSchema), required=True)
    latency = fields.List(fields.Nested(LatencySchema), required=True)


@blp.route("")
class Comparisons(MethodView):
    @blp.response(200, ComparisonsSchema)
    def get(self) -> dict[str, Any]:
        """Résultats de test de chaque modèle, tests de McNemar, transcription et latence."""
        settings: AppSettings = current_app.config["ECHOLENS_SETTINGS"]
        return comparison_tables(settings.results_dir)
