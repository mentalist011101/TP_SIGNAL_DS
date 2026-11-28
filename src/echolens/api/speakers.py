"""Routes des locuteurs enregistrés (EF-11, S6) : liste, enregistrement avec consentement,
suppression.

Les routes ne font que traduire HTTP ↔ service : toute la logique vit dans SpeakerService.
Erreurs au format commun (echolens.api.errors), « message » en français :
- 400 : consentement absent, nom vide, déjà pris ou trop long, extrait refusé (format,
  décodage, silence), pas assez de parole ;
- 404 : locuteur inconnu ;
- 413 : envoi plus gros que max_upload_mb.
"""

from __future__ import annotations

from typing import Any

from flask import current_app
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_smorest.fields import Upload
from marshmallow import Schema, fields, validate

# abort de webargs (republié par flask-smorest) : typé NoReturn, ce qui satisfait mypy.
from webargs.flaskparser import abort

from echolens.services.speaker_service import (
    MAX_NAME_LENGTH,
    SpeakerNotFoundError,
    SpeakerRejectedError,
    SpeakerService,
)
from echolens.services.storage import SpeakerRecord

blp = Blueprint(
    "speakers",
    __name__,
    url_prefix="/api/v1/speakers",
    description="Locuteurs enregistrés, avec consentement (EF-11)",
)

# Les erreurs de validation des paramètres renvoient 400, comme les contrôles de l'audio.
VALIDATION_ERROR_STATUS = 400


class SpeakerSchema(Schema):
    """Un locuteur enregistré, sans sa voix (le vecteur reste sur le serveur)."""

    id = fields.String(required=True)
    name = fields.String(required=True)
    created_at = fields.DateTime(required=True, metadata={"description": "Date d'enregistrement."})
    speech_s = fields.Float(
        required=True, metadata={"description": "Secondes de parole qui forment la voix."}
    )
    segment_count = fields.Integer(
        required=True, metadata={"description": "Nombre de morceaux de parole (1 à 5 s)."}
    )
    audio_count = fields.Integer(
        required=True, metadata={"description": "Nombre d'extraits envoyés et gardés."}
    )
    model_id = fields.String(
        required=True,
        metadata={
            "description": "Modèle qui a calculé la voix (registre) ; « demo » pour le faux "
            "prédicteur. Une voix n'est comparée qu'aux analyses faites avec ce modèle."
        },
    )
    model_version = fields.String(required=True)
    consent_version = fields.String(
        required=True, metadata={"description": "Version du texte de consentement accepté."}
    )
    cloning_allowed = fields.Boolean(
        required=True,
        metadata={
            "description": "Vrai si la personne a aussi accepté que sa voix soit clonée "
            "(seconde case, C35) : seule une telle voix est proposée par la page Cloner."
        },
    )


class SpeakerFormSchema(Schema):
    """Champs texte du formulaire d'enregistrement."""

    name = fields.String(
        required=True,
        validate=validate.Length(
            max=MAX_NAME_LENGTH, error="Nom trop long : {max} caractères au plus."
        ),
        error_messages={"required": "Donnez un nom au locuteur (champ name)."},
        metadata={"description": "Nom affiché dans les résultats, unique."},
    )
    consent = fields.Boolean(
        required=True,
        error_messages={
            "required": "Consentement requis (champ consent).",
            "invalid": "Le champ consent doit valoir true ou false.",
        },
        metadata={
            "description": "true si la personne accepte que sa voix et ses extraits soient "
            "gardés par EchoLens pour la reconnaître (S6) ; sinon rien n'est enregistré."
        },
    )
    cloning_consent = fields.Boolean(
        load_default=False,
        error_messages={"invalid": "Le champ cloning_consent doit valoir true ou false."},
        metadata={
            "description": "true si la personne accepte AUSSI que sa voix soit clonée par "
            "XTTS-v2 (EF-18, ENF-10) ; false par défaut."
        },
    )


class SpeakerFilesSchema(Schema):
    """Extraits de voix du formulaire d'enregistrement."""

    files = fields.List(
        Upload(),
        required=True,
        validate=validate.Length(min=1, error="Ajoutez au moins un extrait de voix."),
        error_messages={"required": "Ajoutez au moins un extrait de voix (champ files)."},
        metadata={
            "description": "Un ou plusieurs extraits (micro ou fichiers : wav, mp3, flac, ogg, "
            "webm ou m4a) ; répéter le champ ; au moins 10 s de parole au total."
        },
    )


@blp.route("")
class Speakers(MethodView):
    @blp.response(200, SpeakerSchema(many=True))
    def get(self) -> list[SpeakerRecord]:
        """Liste les locuteurs enregistrés, par ordre alphabétique."""
        return _service().list_speakers()

    @blp.arguments(SpeakerFormSchema, location="form", error_status_code=VALIDATION_ERROR_STATUS)
    @blp.arguments(SpeakerFilesSchema, location="files", error_status_code=VALIDATION_ERROR_STATUS)
    @blp.response(201, SpeakerSchema)
    @blp.alt_response(
        400, description="Consentement absent, nom refusé, extrait refusé, ou trop peu de parole."
    )
    def post(self, form: dict[str, Any], files: dict[str, Any]) -> SpeakerRecord:
        """Enregistre la voix d'un locuteur, avec son consentement (EF-11, S6).

        La VAD garde les morceaux de parole de 1 à 5 s ; la voix est la moyenne normée de
        leurs vecteurs (C15). Il faut au moins 10 s de parole, extraits réunis.
        """
        try:
            return _service().enroll(
                form["name"], form["consent"], files["files"], form["cloning_consent"]
            )
        except SpeakerRejectedError as error:
            abort(400, message=str(error))


@blp.route("/<speaker_id>")
class Speaker(MethodView):
    @blp.response(204)
    @blp.alt_response(404, description="Locuteur introuvable.")
    def delete(self, speaker_id: str) -> None:
        """Supprime un locuteur : sa voix et ses extraits."""
        try:
            _service().delete_speaker(speaker_id)
        except SpeakerNotFoundError as error:
            abort(404, message=str(error))


def _service() -> SpeakerService:
    service: SpeakerService = current_app.extensions["speaker_service"]
    return service
