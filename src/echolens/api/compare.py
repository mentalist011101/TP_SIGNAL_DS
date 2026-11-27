"""Routes de la comparaison de modèles (EF-15) : un même fichier dans chaque modèle du registre.

Les routes ne font que traduire HTTP ↔ service : toute la logique vit dans ComparisonService.
Erreurs au format commun (echolens.api.errors), « message » en français :
- 400 : fichier refusé (format, décodage, durée, silence) ou paramètre invalide ;
- 404 : comparaison inconnue, ou audio pas encore converti ;
- 413 : fichier plus gros que max_upload_mb.
"""

from __future__ import annotations

from typing import Any

from flask import Response, current_app, send_file, url_for
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_smorest.fields import Upload
from marshmallow import Schema, fields, validate

# abort de webargs (republié par flask-smorest) : typé NoReturn, ce qui satisfait mypy.
from webargs.flaskparser import abort

from echolens.api.result_schemas import TaskResultSchema
from echolens.services.analysis_service import AnalysisRejectedError
from echolens.services.comparison_service import (
    COMPARED_TASKS,
    ComparisonNotFoundError,
    ComparisonService,
)
from echolens.services.storage import AnalysisStatus, ComparisonRecord

blp = Blueprint(
    "compare",
    __name__,
    url_prefix="/api/v1/compare",
    description="Comparaison des modèles sur un même fichier (EF-15)",
)

STATUSES = [status.value for status in AnalysisStatus]
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
# Les erreurs de validation des paramètres renvoient 400, comme les contrôles du fichier.
VALIDATION_ERROR_STATUS = 400


class ModelRunSchema(Schema):
    """Passage d'un modèle sur le fichier : qui, dans quels profils, en combien de temps."""

    model_id = fields.String(required=True, metadata={"description": "Identifiant au registre."})
    model_version = fields.String(required=True)
    profiles = fields.List(
        fields.String(),
        required=True,
        metadata={"description": "Profils qui utilisent ce modèle : quality, realtime."},
    )
    compute_s = fields.Float(
        required=True,
        metadata={
            "description": "Temps de calcul du modèle sur tout le fichier, en secondes (CPU du "
            "serveur), détection de parole exclue : elle tourne une fois pour tous."
        },
    )
    result = fields.Nested(
        TaskResultSchema,
        required=True,
        metadata={"description": "Résultat au format d'une analyse (global et segments)."},
    )


class ComparisonSummarySchema(Schema):
    """Comparaison telle que la liste l'affiche, sans les résultats."""

    id = fields.String(required=True)
    created_at = fields.DateTime(required=True)
    original_filename = fields.String(required=True)
    status = fields.String(required=True, validate=validate.OneOf(STATUSES))
    error_message = fields.String(allow_none=True)
    duration_s = fields.Float(allow_none=True)
    tasks = fields.List(fields.String(), required=True)


class ComparisonSchema(ComparisonSummarySchema):
    """Comparaison complète : pour chaque tâche, un passage par modèle."""

    results = fields.Dict(
        keys=fields.String(),
        values=fields.List(fields.Nested(ModelRunSchema)),
        allow_none=True,
        metadata={
            "description": "Pour chaque tâche demandée, les modèles du registre dans l'ordre "
            "des profils (quality puis realtime) ; null tant que le calcul n'est pas fini."
        },
    )
    audio_url = fields.Method("get_audio_url", allow_none=True)

    def get_audio_url(self, record: ComparisonRecord) -> str | None:
        if record.status != AnalysisStatus.DONE:
            return None
        return url_for("compare.ComparisonAudio", comparison_id=record.id)


class ComparisonFormSchema(Schema):
    """Champs texte du formulaire de comparaison."""

    tasks = fields.List(
        fields.String(
            validate=validate.OneOf(
                COMPARED_TASKS,
                error="Tâche non comparable : « {input} ». Tâches possibles : {choices}.",
            )
        ),
        required=True,
        validate=validate.Length(min=1, error="Choisissez au moins une tâche."),
        error_messages={"required": "Choisissez au moins une tâche (champ tasks)."},
        metadata={
            "description": "Tâches à comparer ; répéter le champ pour en demander plusieurs."
        },
    )


class ComparisonFileSchema(Schema):
    """Fichier audio du formulaire de comparaison."""

    file = Upload(
        required=True,
        error_messages={"required": "Aucun fichier reçu (champ file)."},
        metadata={
            "description": "Fichier audio : wav, mp3, flac, ogg, webm ou m4a, 5 min maximum."
        },
    )


class ComparisonListQuerySchema(Schema):
    """Pagination de la liste des comparaisons."""

    limit = fields.Integer(
        load_default=DEFAULT_PAGE_SIZE,
        validate=validate.Range(
            min=1, max=MAX_PAGE_SIZE, error="limit doit être compris entre {min} et {max}."
        ),
        error_messages={"invalid": "limit doit être un nombre entier."},
    )
    offset = fields.Integer(
        load_default=0,
        validate=validate.Range(min=0, error="offset doit être positif ou nul."),
        error_messages={"invalid": "offset doit être un nombre entier."},
    )


@blp.route("")
class Comparisons(MethodView):
    @blp.arguments(
        ComparisonListQuerySchema, location="query", error_status_code=VALIDATION_ERROR_STATUS
    )
    @blp.response(200, ComparisonSummarySchema(many=True))
    def get(self, query: dict[str, int]) -> list[ComparisonRecord]:
        """Comparaisons passées, les plus récentes d'abord, sans leurs résultats."""
        return _service().list_comparisons(limit=query["limit"], offset=query["offset"])

    @blp.arguments(ComparisonFormSchema, location="form", error_status_code=VALIDATION_ERROR_STATUS)
    @blp.arguments(
        ComparisonFileSchema, location="files", error_status_code=VALIDATION_ERROR_STATUS
    )
    @blp.response(202, ComparisonSchema)
    @blp.alt_response(400, description="Fichier refusé : format, décodage, durée ou silence.")
    def post(self, form: dict[str, Any], files: dict[str, Any]) -> ComparisonRecord:
        """Fait tourner chaque modèle du registre des tâches choisies sur le même fichier.

        Répond 202 ; suivre le calcul avec GET /api/v1/compare/{id}.
        """
        try:
            return _service().create_comparison(files["file"], form["tasks"])
        except AnalysisRejectedError as error:
            abort(400, message=str(error))


@blp.route("/<comparison_id>")
class Comparison(MethodView):
    @blp.response(200, ComparisonSchema)
    @blp.alt_response(404, description="Comparaison introuvable.")
    def get(self, comparison_id: str) -> ComparisonRecord:
        """Statut et résultats d'une comparaison."""
        try:
            return _service().get_comparison(comparison_id)
        except ComparisonNotFoundError as error:
            abort(404, message=str(error))

    @blp.response(204)
    @blp.alt_response(404, description="Comparaison introuvable.")
    def delete(self, comparison_id: str) -> None:
        """Supprime une comparaison et son audio."""
        try:
            _service().delete_comparison(comparison_id)
        except ComparisonNotFoundError as error:
            abort(404, message=str(error))


@blp.route("/<comparison_id>/audio")
class ComparisonAudio(MethodView):
    @blp.response(200, description="Audio WAV 16 kHz mono.", content_type="audio/wav")
    @blp.alt_response(404, description="Comparaison introuvable ou audio pas encore converti.")
    def get(self, comparison_id: str) -> Response:
        """Audio converti de la comparaison, pour la réécoute."""
        service = _service()
        try:
            service.get_comparison(comparison_id)
        except ComparisonNotFoundError as error:
            abort(404, message=str(error))
        path = service.converted_audio_path(comparison_id)
        if not path.is_file():
            abort(404, message="Audio pas encore disponible : la comparaison n'est pas terminée.")
        return send_file(path, mimetype="audio/wav")


def _service() -> ComparisonService:
    service: ComparisonService = current_app.extensions["comparison_service"]
    return service
