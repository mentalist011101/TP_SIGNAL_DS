"""Format unique des erreurs de l'API : toujours un champ « message » en français.

Corps d'une réponse d'erreur :
    code    : code HTTP (400, 404, 413…)
    status  : nom du code HTTP en anglais (« Bad Request »)
    message : phrase en français, affichable telle quelle par l'interface
    errors  : détail complet des erreurs de validation des paramètres (seulement dans ce cas)
"""

from __future__ import annotations

from typing import Any

from flask import current_app
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from echolens.config import AppSettings

# Message par défaut quand l'erreur n'en porte pas (route inconnue, erreur interne…).
DEFAULT_MESSAGES = {
    400: "Requête invalide.",
    404: "Ressource introuvable.",
    405: "Méthode HTTP non autorisée pour cette adresse.",
    500: "Erreur interne du serveur : réessayez plus tard.",
}
FALLBACK_MESSAGE = "La requête n'a pas pu aboutir."


def handle_http_error(error: HTTPException) -> tuple[dict[str, Any], int, dict[str, str]]:
    """Gestionnaire Flask de toutes les erreurs HTTP : construit le corps décrit plus haut."""
    status_code = error.code or 500
    payload: dict[str, Any] = {"code": status_code, "status": error.name}

    # Étape 1 : informations ajoutées par abort(..., message=...) ou par la validation webargs.
    data = getattr(error, "data", None)
    if data is None:
        data = {}
    errors = data.get("errors")
    if errors is None:
        errors = data.get("messages")
    if errors is not None:
        payload["errors"] = errors

    # Étape 2 : le message, du plus précis au plus général.
    if "message" in data:
        payload["message"] = data["message"]
    elif isinstance(error, RequestEntityTooLarge):
        payload["message"] = _too_large_message()
    elif errors is not None:
        payload["message"] = _first_error_message(errors)
    else:
        payload["message"] = DEFAULT_MESSAGES.get(status_code, FALLBACK_MESSAGE)

    headers = data.get("headers")
    if headers is None:
        headers = {}
    return payload, status_code, headers


def _too_large_message() -> str:
    settings: AppSettings = current_app.config["ECHOLENS_SETTINGS"]
    return f"Fichier trop volumineux : {settings.max_upload_mb} Mo maximum."


def _first_error_message(errors: Any) -> str:
    # Les erreurs de validation sont imbriquées, par exemple
    # {"form": {"tasks": {"1": ["Tâche inconnue : « danse »…"]}}} : on descend jusqu'au
    # premier texte trouvé.
    if isinstance(errors, str):
        return errors
    if isinstance(errors, list) and errors:
        return _first_error_message(errors[0])
    if isinstance(errors, dict) and errors:
        first_value = next(iter(errors.values()))
        return _first_error_message(first_value)
    return DEFAULT_MESSAGES[400]
