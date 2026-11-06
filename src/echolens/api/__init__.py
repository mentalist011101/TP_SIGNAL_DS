"""Façade Flask : API REST v1 documentée (OpenAPI), WebSocket et service du front React compilé."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask, Response, abort, send_from_directory
from flask_smorest import Api
from werkzeug.exceptions import HTTPException

from echolens import __version__
from echolens.api.analyses import blp as analyses_blp
from echolens.api.errors import handle_http_error
from echolens.api.health import blp as health_blp
from echolens.config import AppSettings, load_settings
from echolens.services.analysis_service import AnalysisService
from echolens.services.storage import create_session_factory


def create_app(settings: AppSettings | None = None, **overrides: Any) -> Flask:
    """Fabrique de l'application Flask.

    ``overrides`` permet aux tests de surcharger la configuration Flask (par exemple TESTING).
    """
    settings = settings or load_settings()
    app = Flask(__name__, static_folder=None)
    app.config.update(
        API_TITLE="EchoLens API",
        API_VERSION=f"v{__version__}",
        OPENAPI_VERSION="3.0.3",
        OPENAPI_URL_PREFIX="/",
        OPENAPI_JSON_PATH="api/v1/openapi.json",
        OPENAPI_SWAGGER_UI_PATH="docs",
        OPENAPI_SWAGGER_UI_URL="https://cdn.jsdelivr.net/npm/swagger-ui-dist/",
        MAX_CONTENT_LENGTH=settings.max_upload_mb * 1024 * 1024,
        ECHOLENS_SETTINGS=settings,
    )
    app.config.update(overrides)

    # Base de données et service des analyses, partagés par toutes les requêtes (S2, S3).
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    session_factory = create_session_factory(settings.resolved_database_url())
    app.extensions["analysis_service"] = AnalysisService(settings, session_factory)

    api = Api(app)
    api.register_blueprint(health_blp)
    api.register_blueprint(analyses_blp)
    # Enregistré après Api(app) pour remplacer le gestionnaire de flask-smorest : toute erreur
    # porte ainsi un « message » en français (format décrit dans echolens.api.errors).
    app.register_error_handler(HTTPException, handle_http_error)

    _register_frontend(app, settings.web_dist_dir)
    return app


def _register_frontend(app: Flask, dist_dir: Path) -> None:
    """Sert le front React compilé ; une route inconnue renvoie index.html (routage côté client)."""

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def frontend(path: str) -> Response:
        if path.startswith(("api/", "ws/")):
            abort(404)
        if not (dist_dir / "index.html").is_file():
            return Response(
                "Front non compilé : lancez « make web-build » (ou « npm run build » dans web/).",
                status=503,
                mimetype="text/plain",
            )
        if path and (dist_dir / path).is_file():
            return send_from_directory(dist_dir, path)
        return send_from_directory(dist_dir, "index.html")
