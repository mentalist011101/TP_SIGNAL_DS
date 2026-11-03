"""Point de santé : permet au front et à la CI de vérifier que le serveur répond."""

from __future__ import annotations

from typing import Any

from flask.views import MethodView
from flask_smorest import Blueprint
from marshmallow import Schema, fields

from echolens import __version__

blp = Blueprint("health", __name__, url_prefix="/api/v1/health", description="État du serveur")


class HealthSchema(Schema):
    status = fields.String(required=True, metadata={"example": "ok"})
    version = fields.String(required=True, metadata={"example": "0.1.0"})


@blp.route("")
class Health(MethodView):
    @blp.response(200, HealthSchema)
    def get(self) -> dict[str, Any]:
        """Renvoie l'état du serveur et la version d'EchoLens."""
        return {"status": "ok", "version": __version__}
