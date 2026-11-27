"""Routes du clonage de voix (EF-18, ENF-10, C35) : POST /api/v1/tts et les extraits gardés.

Les routes ne font que traduire HTTP ↔ service : toute la logique vit dans CloningService.
Erreurs au format commun (echolens.api.errors), « message » en français :
- 400 : texte vide ou trop long ;
- 403 : le locuteur n'a pas accepté le clonage ;
- 404 : locuteur ou extrait inconnu, ou audio pas encore prêt ;
- 503 : clonage indisponible (licence du modèle non acceptée, pas de modèle au registre).
"""

from __future__ import annotations

from flask import Response, current_app, send_file, url_for
from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields, validate

# abort de webargs (republié par flask-smorest) : typé NoReturn, ce qui satisfait mypy.
from webargs.flaskparser import abort

from echolens.services.cloning_service import (
    CloningForbiddenError,
    CloningRejectedError,
    CloningService,
    SynthesisNotFoundError,
)
from echolens.services.speaker_service import SpeakerNotFoundError
from echolens.services.storage import AnalysisStatus, SynthesisRecord
from echolens.services.voice_cloning import CloningUnavailableError

blp = Blueprint(
    "tts",
    __name__,
    url_prefix="/api/v1/tts",
    description="Clonage de voix consentantes, sortie marquée « voix synthétique » (EF-18)",
)

STATUSES = [status.value for status in AnalysisStatus]
VALIDATION_ERROR_STATUS = 400


class SynthesisSchema(Schema):
    """Un extrait de voix synthétique : qui, quoi, avec quel modèle, en combien de temps."""

    id = fields.String(required=True)
    created_at = fields.DateTime(required=True)
    speaker_id = fields.String(required=True)
    speaker_name = fields.String(required=True, metadata={"description": "Voix clonée."})
    text = fields.String(required=True, metadata={"description": "Texte dit par la voix."})
    status = fields.String(required=True, validate=validate.OneOf(STATUSES))
    error_message = fields.String(allow_none=True)
    model_id = fields.String(required=True)
    model_version = fields.String(required=True)
    duration_s = fields.Float(
        allow_none=True, metadata={"description": "Durée de l'extrait marqué (bip compris)."}
    )
    compute_s = fields.Float(
        allow_none=True, metadata={"description": "Temps de synthèse sur le serveur, en s."}
    )
    audio_url = fields.Method("get_audio_url", allow_none=True)
    download_name = fields.Method(
        "get_download_name",
        metadata={"description": "Nom de fichier proposé, qui commence par voix_synthetique."},
    )

    def get_audio_url(self, record: SynthesisRecord) -> str | None:
        if record.status != AnalysisStatus.DONE:
            return None
        return url_for("tts.SynthesisAudio", synthesis_id=record.id)

    def get_download_name(self, record: SynthesisRecord) -> str:
        return _service().download_name(record)


class SynthesisRequestSchema(Schema):
    """Demande de clonage."""

    speaker_id = fields.String(
        required=True,
        error_messages={"required": "Choisissez la voix à cloner (champ speaker_id)."},
        metadata={"description": "Locuteur enregistré qui a accepté le clonage."},
    )
    text = fields.String(
        required=True,
        error_messages={"required": "Écrivez le texte à faire dire (champ text)."},
        metadata={"description": "Texte en français, 300 caractères au plus."},
    )


@blp.route("")
class Syntheses(MethodView):
    @blp.response(200, SynthesisSchema(many=True))
    def get(self) -> list[SynthesisRecord]:
        """Extraits synthétiques gardés, les plus récents d'abord."""
        return _service().list_syntheses()

    @blp.arguments(
        SynthesisRequestSchema, location="json", error_status_code=VALIDATION_ERROR_STATUS
    )
    @blp.response(202, SynthesisSchema)
    @blp.alt_response(400, description="Texte vide ou trop long.")
    @blp.alt_response(403, description="Le locuteur n'a pas accepté le clonage.")
    @blp.alt_response(404, description="Locuteur introuvable.")
    @blp.alt_response(503, description="Clonage indisponible.")
    def post(self, request: dict[str, str]) -> SynthesisRecord:
        """Fait dire un texte à une voix consentante (XTTS-v2), en arrière-plan.

        Répond 202 ; suivre le calcul avec GET /api/v1/tts/{id}. L'audio commence par un bip
        et ses métadonnées disent « voix synthétique ».
        """
        try:
            return _service().clone(request["speaker_id"], request["text"])
        except CloningRejectedError as error:
            abort(400, message=str(error))
        except CloningForbiddenError as error:
            abort(403, message=str(error))
        except SpeakerNotFoundError as error:
            abort(404, message=str(error))
        except CloningUnavailableError as error:
            abort(503, message=str(error))


@blp.route("/<synthesis_id>")
class Synthesis(MethodView):
    @blp.response(200, SynthesisSchema)
    @blp.alt_response(404, description="Extrait introuvable.")
    def get(self, synthesis_id: str) -> SynthesisRecord:
        """Statut d'un extrait synthétique."""
        try:
            return _service().get_synthesis(synthesis_id)
        except SynthesisNotFoundError as error:
            abort(404, message=str(error))

    @blp.response(204)
    @blp.alt_response(404, description="Extrait introuvable.")
    def delete(self, synthesis_id: str) -> None:
        """Supprime un extrait synthétique et son audio."""
        try:
            _service().delete_synthesis(synthesis_id)
        except SynthesisNotFoundError as error:
            abort(404, message=str(error))


@blp.route("/<synthesis_id>/audio")
class SynthesisAudio(MethodView):
    @blp.response(200, description="WAV marqué « voix synthétique ».", content_type="audio/wav")
    @blp.alt_response(404, description="Extrait introuvable ou pas encore prêt.")
    def get(self, synthesis_id: str) -> Response:
        """Audio de l'extrait, avec le bip de marquage et ses métadonnées."""
        service = _service()
        try:
            record = service.get_synthesis(synthesis_id)
        except SynthesisNotFoundError as error:
            abort(404, message=str(error))
        path = service.audio_path(record)
        if not path.is_file():
            abort(404, message="Audio pas encore disponible : la synthèse n'est pas terminée.")
        return send_file(path, mimetype="audio/wav", download_name=service.download_name(record))


def _service() -> CloningService:
    service: CloningService = current_app.extensions["cloning_service"]
    return service
