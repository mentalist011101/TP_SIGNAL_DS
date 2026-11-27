"""Mot de passe d'accès pour une instance publique (S6, ENF-10) : tout le site derrière une
authentification HTTP Basic, activée seulement si access_password est défini.

Sur une URL publique, n'importe qui pourrait sinon enregistrer une voix ou en cloner une. Le
navigateur affiche sa propre fenêtre de connexion ; tout nom d'utilisateur est accepté, seul le
mot de passe compte. La route de santé reste ouverte : les plateformes d'hébergement
l'interrogent pour savoir si le serveur est en vie. À utiliser derrière HTTPS (Codespaces,
Render) : en HTTP simple, le mot de passe circulerait en clair.
"""

from __future__ import annotations

import hmac

from flask import Flask, Response, request

HEALTH_PATH = "/api/v1/health"
REALM = 'Basic realm="EchoLens", charset="UTF-8"'
REFUSED_MESSAGE = "Accès protégé : entrez le mot de passe de l'équipe EchoLens."


def require_password(app: Flask, password: str) -> None:
    """Refuse toute requête sans le bon mot de passe (401), sauf la route de santé."""

    @app.before_request
    def check_password() -> Response | None:
        if request.path == HEALTH_PATH:
            return None
        credentials = request.authorization
        if credentials is not None and _same_text(credentials.password, password):
            return None
        return Response(
            REFUSED_MESSAGE, status=401, mimetype="text/plain", headers={"WWW-Authenticate": REALM}
        )


def _same_text(sent: str | None, expected: str) -> bool:
    # Comparaison en temps constant : la durée de la réponse ne révèle rien du mot de passe.
    if sent is None:
        return False
    return hmac.compare_digest(sent.encode("utf-8"), expected.encode("utf-8"))
