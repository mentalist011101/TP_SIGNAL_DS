"""Routes des analyses (S4) : import, statut, historique, audio, spectrogramme, suppression.

Les routes ne font que traduire HTTP ↔ service : toute la logique vit dans AnalysisService.

Format des erreurs (identique pour toutes les routes, voir echolens.api.errors) :

    {"code": 400, "status": "Bad Request", "message": "L'audio est silencieux : …"}

- « message » est toujours présent, en français, et s'affiche tel quel dans l'interface.
- 400 : fichier refusé (format, décodage, durée, silence) ou paramètre invalide. Pour un
  paramètre invalide, « message » reprend la première erreur trouvée et « errors » donne le
  détail complet, par exemple {"form": {"tasks": {"1": ["Tâche inconnue : « danse »…"]}}}.
- 404 : analyse inconnue, ou audio ou spectrogramme pas encore disponible.
- 413 : fichier plus gros que max_upload_mb.
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from flask import Response, current_app, send_file, url_for
from flask.views import MethodView
from flask_smorest import Blueprint
from flask_smorest.fields import Upload
from marshmallow import Schema, fields, validate

# abort de webargs (republié par flask-smorest) : typé NoReturn, ce qui satisfait mypy.
from webargs.flaskparser import abort

from echolens.core.features import FeatureConfig, mel_axis_position
from echolens.core.models.registry import Profile, Task
from echolens.services.analysis_service import (
    AnalysisNotFoundError,
    AnalysisRejectedError,
    AnalysisService,
)
from echolens.services.spectrogram_image import colormap_stops
from echolens.services.storage import AnalysisRecord, AnalysisStatus

blp = Blueprint(
    "analyses", __name__, url_prefix="/api/v1/analyses", description="Import et suivi des analyses"
)

# Tâches qu'une analyse de fichier peut demander (le clonage de voix a sa propre route).
ANALYSIS_TASKS = [Task.EMOTION, Task.SOUND_EVENT, Task.TRANSCRIPTION, Task.SPEAKER]
PROFILES = [Profile.QUALITY, Profile.REALTIME]
STATUSES = [status.value for status in AnalysisStatus]
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
# Les erreurs de validation des paramètres renvoient 400, comme les contrôles du fichier.
VALIDATION_ERROR_STATUS = 400


class FrequencyTickSchema(Schema):
    """Une graduation de l'axe des fréquences de l'image."""

    hz = fields.Float(metadata={"description": "Fréquence de la graduation, en Hz."})
    position = fields.Float(
        metadata={"description": "Hauteur relative depuis le bas de l'image : 0 en bas, 1 en haut."}
    )


class SpectrogramInfoSchema(Schema):
    """Ce qu'il faut au front pour tracer les axes et la légende de l'image (EF-04, U6)."""

    n_mels = fields.Integer(
        metadata={"description": "Nombre de bandes Mel : hauteur de l'image en pixels (R2)."}
    )
    f_min_hz = fields.Float(
        metadata={
            "description": "Limite basse du banc de filtres Mel, en Hz (bas de l'axe). "
            "Ce n'est pas la fréquence centrale d'une bande."
        }
    )
    f_max_hz = fields.Float(
        metadata={
            "description": "Limite haute du banc de filtres Mel, en Hz (haut de l'axe). "
            "Ce n'est pas la fréquence centrale d'une bande."
        }
    )
    frequency_ticks = fields.List(
        fields.Nested(FrequencyTickSchema),
        metadata={
            "description": "Graduations de l'axe des fréquences. position = hauteur relative "
            "depuis le bas ; l'axe suit l'échelle Mel, ne pas interpoler linéairement entre "
            "f_min_hz et f_max_hz."
        },
    )
    frame_step_s = fields.Float(
        metadata={
            "description": "Durée d'une colonne de pixels, en secondes (hop_length / "
            "sample_rate, soit 0,01 s) : axe du temps."
        }
    )
    db_min = fields.Float(
        metadata={
            "description": "Niveau en dB de la couleur la plus sombre (bas de la légende) ; "
            "tout ce qui est plus faible a cette couleur."
        }
    )
    db_max = fields.Float(
        metadata={
            "description": "Niveau en dB de la couleur la plus claire (haut de la légende) ; "
            "tout ce qui est plus fort a cette couleur."
        }
    )
    colormap = fields.String(
        metadata={"description": "Nom de la palette matplotlib utilisée (par exemple magma)."}
    )
    colormap_stops = fields.List(
        fields.String(),
        metadata={
            "description": "Couleurs de la légende, de db_min à db_max, pour un dégradé CSS "
            "(format « #rrggbb », de la plus sombre à la plus claire)."
        },
    )


class AnalysisSchema(Schema):
    """Analyse renvoyée au front (contrat consommé par l'interface, C7)."""

    id = fields.String(metadata={"description": "Identifiant unique de l'analyse (UUID)."})
    created_at = fields.Method(
        "get_created_at",
        metadata={
            "type": "string",
            "format": "date-time",
            "description": "Date et heure de création de l'analyse, en UTC (ISO 8601, +00:00).",
        },
    )
    original_filename = fields.String(
        metadata={"description": "Nom du fichier importé, nettoyé (caractères sûrs uniquement)."}
    )
    status = fields.String(
        validate=validate.OneOf(STATUSES),
        metadata={
            "description": "Statut du traitement : pending (en attente), processing (en cours), "
            "done (terminé) ou failed (échec, voir error_message)."
        },
    )
    error_message = fields.String(
        allow_none=True,
        metadata={
            "description": "Raison de l'échec en français si status vaut failed, sinon null."
        },
    )
    duration_s = fields.Float(
        allow_none=True,
        metadata={"description": "Durée de l'audio en secondes ; null tant que status ≠ done."},
    )
    tasks = fields.List(
        fields.String(validate=validate.OneOf(ANALYSIS_TASKS)),
        metadata={
            "description": "Tâches demandées : emotion, sound_event, transcription, speaker."
        },
    )
    profile = fields.String(
        validate=validate.OneOf(PROFILES),
        metadata={"description": "Profil : quality (fichier importé) ou realtime (flux micro)."},
    )
    audio_url = fields.Method(
        "get_audio_url",
        metadata={
            "type": "string",
            "nullable": True,
            "description": "URL de l'audio converti (WAV 16 kHz mono) pour afficher la forme "
            "d'onde ; null tant que status ≠ done.",
        },
    )
    spectrogram_url = fields.Method(
        "get_spectrogram_url",
        metadata={
            "type": "string",
            "nullable": True,
            "description": "URL de l'image PNG du spectrogramme log-Mel (graves en bas) ; "
            "null tant que status ≠ done.",
        },
    )
    spectrogram = fields.Nested(
        SpectrogramInfoSchema,
        allow_none=True,
        metadata={
            "description": "Axes et échelle de couleurs de l'image du spectrogramme ; "
            "null tant que status ≠ done."
        },
    )

    def get_attribute(self, obj: Any, attr: str, default: Any) -> Any:
        # marshmallow lit chaque champ sur l'objet avec cette méthode. AnalysisRecord n'a pas
        # de champ « spectrogram » : ses informations viennent de features.yaml.
        if attr == "spectrogram":
            return _spectrogram_info(obj)
        return super().get_attribute(obj, attr, default)

    def get_created_at(self, record: AnalysisRecord) -> str:
        created_at = record.created_at
        # SQLite relit les dates sans fuseau ; elles sont enregistrées en UTC, on le rend explicite
        # pour que le front affiche la bonne heure locale.
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=UTC)
        return created_at.isoformat()

    def get_audio_url(self, record: AnalysisRecord) -> str | None:
        if record.status != AnalysisStatus.DONE:
            return None
        return url_for("analyses.AnalysisAudio", analysis_id=record.id)

    def get_spectrogram_url(self, record: AnalysisRecord) -> str | None:
        if record.status != AnalysisStatus.DONE:
            return None
        return url_for("analyses.AnalysisSpectrogram", analysis_id=record.id)


class AnalysisFormSchema(Schema):
    """Champs texte du formulaire d'import."""

    tasks = fields.List(
        fields.String(
            validate=validate.OneOf(
                ANALYSIS_TASKS, error="Tâche inconnue : « {input} ». Tâches possibles : {choices}."
            )
        ),
        required=True,
        validate=validate.Length(min=1, error="Choisissez au moins une tâche."),
        error_messages={"required": "Choisissez au moins une tâche (champ tasks)."},
        metadata={
            "description": "Tâches à effectuer ; répéter le champ pour en demander plusieurs."
        },
    )
    profile = fields.String(
        load_default=Profile.QUALITY.value,
        validate=validate.OneOf(PROFILES, error="Profil inconnu : « {input} »."),
        metadata={"description": "quality (par défaut) ou realtime."},
    )


class AnalysisFileSchema(Schema):
    """Fichier audio du formulaire d'import."""

    file = Upload(
        required=True,
        error_messages={"required": "Aucun fichier reçu (champ file)."},
        metadata={
            "description": "Fichier audio : wav, mp3, flac, ogg, webm ou m4a, 5 min maximum."
        },
    )


class HistoryQuerySchema(Schema):
    """Pagination de l'historique."""

    limit = fields.Integer(
        load_default=DEFAULT_PAGE_SIZE,
        validate=validate.Range(
            min=1, max=MAX_PAGE_SIZE, error="limit doit être compris entre {min} et {max}."
        ),
        error_messages={"invalid": "limit doit être un nombre entier."},
        metadata={"description": "Nombre maximal d'analyses renvoyées."},
    )
    offset = fields.Integer(
        load_default=0,
        validate=validate.Range(min=0, error="offset doit être positif ou nul."),
        error_messages={"invalid": "offset doit être un nombre entier."},
        metadata={"description": "Nombre d'analyses à sauter (pagination)."},
    )


@blp.route("")
class Analyses(MethodView):
    @blp.arguments(HistoryQuerySchema, location="query", error_status_code=VALIDATION_ERROR_STATUS)
    @blp.response(200, AnalysisSchema(many=True))
    def get(self, query: dict[str, int]) -> list[AnalysisRecord]:
        """Historique des analyses, les plus récentes d'abord."""
        return _service().list_analyses(limit=query["limit"], offset=query["offset"])

    @blp.arguments(AnalysisFormSchema, location="form", error_status_code=VALIDATION_ERROR_STATUS)
    @blp.arguments(AnalysisFileSchema, location="files", error_status_code=VALIDATION_ERROR_STATUS)
    @blp.response(202, AnalysisSchema)
    @blp.alt_response(400, description="Fichier refusé : format, décodage, durée ou silence.")
    def post(self, form: dict[str, Any], files: dict[str, Any]) -> AnalysisRecord:
        """Importe un audio, le contrôle et lance son analyse en arrière-plan.

        Répond 202 : l'analyse est acceptée ; suivre son statut avec GET /api/v1/analyses/{id}.
        """
        try:
            return _service().create_analysis(files["file"], form["tasks"], form["profile"])
        except AnalysisRejectedError as error:
            abort(400, message=str(error))


@blp.route("/<analysis_id>")
class Analysis(MethodView):
    @blp.response(200, AnalysisSchema)
    @blp.alt_response(404, description="Analyse introuvable.")
    def get(self, analysis_id: str) -> AnalysisRecord:
        """Statut d'une analyse (à interroger jusqu'à done ou failed)."""
        try:
            return _service().get_analysis(analysis_id)
        except AnalysisNotFoundError as error:
            abort(404, message=str(error))

    @blp.response(204)
    @blp.alt_response(404, description="Analyse introuvable.")
    def delete(self, analysis_id: str) -> None:
        """Supprime une analyse et ses fichiers."""
        try:
            _service().delete_analysis(analysis_id)
        except AnalysisNotFoundError as error:
            abort(404, message=str(error))


@blp.route("/<analysis_id>/audio")
class AnalysisAudio(MethodView):
    @blp.response(200, description="Audio WAV 16 kHz mono.", content_type="audio/wav")
    @blp.alt_response(404, description="Analyse introuvable ou audio pas encore converti.")
    def get(self, analysis_id: str) -> Response:
        """Audio converti en 16 kHz mono, pour afficher la forme d'onde."""
        service = _service()
        try:
            service.get_analysis(analysis_id)
        except AnalysisNotFoundError as error:
            abort(404, message=str(error))
        path = service.converted_audio_path(analysis_id)
        if not path.is_file():
            abort(404, message="Audio pas encore disponible : l'analyse n'est pas terminée.")
        return send_file(path, mimetype="audio/wav")


@blp.route("/<analysis_id>/spectrogram")
class AnalysisSpectrogram(MethodView):
    @blp.response(200, description="Image PNG du spectrogramme log-Mel.", content_type="image/png")
    @blp.alt_response(404, description="Analyse introuvable ou spectrogramme pas encore prêt.")
    def get(self, analysis_id: str) -> Response:
        """Spectrogramme log-Mel en PNG : une colonne par trame de 10 ms, graves en bas (EF-04)."""
        service = _service()
        try:
            service.get_analysis(analysis_id)
        except AnalysisNotFoundError as error:
            abort(404, message=str(error))
        # Image absente : analyse pas encore terminée, ou importée avant l'ajout du spectrogramme.
        path = service.spectrogram_path(analysis_id)
        if not path.is_file():
            abort(
                404,
                message="Spectrogramme indisponible : l'analyse n'est pas terminée, "
                "ou elle a été importée avant l'ajout du spectrogramme.",
            )
        return send_file(path, mimetype="image/png")


def _service() -> AnalysisService:
    service: AnalysisService = current_app.extensions["analysis_service"]
    return service


def _spectrogram_info(record: AnalysisRecord) -> dict[str, Any] | None:
    if record.status != AnalysisStatus.DONE:
        return None
    config: FeatureConfig = _service().feature_config
    # Graduations placées sur l'échelle Mel de l'image (R2), une par fréquence de features.yaml.
    frequency_ticks = []
    for tick_hz in config.display_frequency_ticks_hz:
        position = mel_axis_position(tick_hz, config)
        frequency_ticks.append({"hz": tick_hz, "position": position})
    # Durée d'une colonne de pixels : un pas de STFT (10 ms).
    frame_step_s = config.hop_length / config.sample_rate
    return {
        "n_mels": config.n_mels,
        "f_min_hz": config.f_min,
        "f_max_hz": config.f_max,
        "frequency_ticks": frequency_ticks,
        "frame_step_s": frame_step_s,
        "db_min": config.display_db_min,
        "db_max": config.display_db_max,
        "colormap": config.display_colormap,
        "colormap_stops": colormap_stops(config, config.display_legend_stops),
    }
