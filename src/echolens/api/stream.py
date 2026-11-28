"""Route WebSocket du flux micro en direct : /ws/stream (EF-14, C23, D8).

Un WebSocket ne figure pas dans l'OpenAPI (/docs) : son protocole est décrit ici et dans
docs/api-flux-micro.md. La route ne fait que lire et écrire les messages ; le tampon, les
analyses et l'enregistrement vivent dans services.stream_service.

Navigateur → serveur :
- texte {"type": "start", "record": false} : premier message, obligatoire. Pour enregistrer la
  session dans l'historique : {"type": "start", "record": true,
  "consent": {"accepted": true, "version": "direct-v1"}} (ENF-10) ;
- binaire : PCM Int16 petit-boutiste, mono, 16 kHz, 1 s au plus par message ;
- texte {"type": "stop"} : fin de la session.

Serveur → navigateur :
- {"type": "ready", ...} : réglages du flux (W, H, tâches) ;
- {"type": "window", ...} : résultats de la fenêtre la plus récente, temps de calcul, RTF ;
- {"type": "saved", "analysis_id": ...} : à l'arrêt, si la session a été enregistrée ;
- {"type": "error", "message": ...} : message en français ; le serveur ferme ensuite.
"""

from __future__ import annotations

import json
from typing import Any

from flask import current_app
from flask_sock import Sock
from simple_websocket import ConnectionClosed

from echolens.services.analysis_service import AnalysisService
from echolens.services.stream_service import StreamError, StreamSession, parse_start

sock = Sock()


@sock.route("/ws/stream")
def stream(ws: Any) -> None:
    """Session du flux micro : start, morceaux de PCM, stop."""
    service: AnalysisService = current_app.extensions["analysis_service"]
    try:
        session = _open_session(ws, service)
        _receive_until_stop(ws, session)
        _finish(ws, session)
    except StreamError as error:
        _send(ws, {"type": "error", "message": str(error)})
    except ConnectionClosed:
        # Le navigateur a fermé la page : la session et son tampon sont simplement oubliés.
        return


def _open_session(ws: Any, service: AnalysisService) -> StreamSession:
    # Étape 1 : le premier message doit être « start », avec le choix d'enregistrer ou non.
    first = ws.receive()
    command = _read_command(first)
    if command.get("type") != "start":
        raise StreamError("Le flux doit commencer par un message « start ».")
    settings = service.result_context.inference_config.stream
    options = parse_start(command, settings)
    # Étape 2 : la session est prête ; on le dit au navigateur.
    session = StreamSession(service, options)
    _send(ws, session.ready_message())
    return session


def _receive_until_stop(ws: Any, session: StreamSession) -> None:
    # Chaque morceau reçu s'ajoute au tampon. Avant d'analyser, on lit aussi les morceaux déjà
    # arrivés pendant le calcul précédent : la fenêtre analysée est alors la plus récente.
    while True:
        message = ws.receive()
        if isinstance(message, str):
            _expect_stop(message)
            return
        session.receive(message)
        stop_received = _drain_pending(ws, session)
        window_message = session.analyze_ready_window()
        if window_message is not None:
            _send(ws, window_message)
        if stop_received:
            return


def _drain_pending(ws: Any, session: StreamSession) -> bool:
    # Lit sans attendre tous les messages déjà reçus ; vrai si « stop » était parmi eux.
    while True:
        pending = ws.receive(timeout=0)
        if pending is None:
            return False
        if isinstance(pending, str):
            _expect_stop(pending)
            return True
        session.receive(pending)


def _finish(ws: Any, session: StreamSession) -> None:
    # Enregistrement dans l'historique, seulement s'il a été demandé avec consentement.
    saved_message = session.finish()
    if saved_message is not None:
        _send(ws, saved_message)


def _expect_stop(text: str) -> None:
    command = _read_command(text)
    if command.get("type") != "stop":
        raise StreamError("Message inconnu : seul « stop » est attendu pendant le flux.")


def _read_command(message: Any) -> dict[str, Any]:
    if not isinstance(message, str):
        raise StreamError("Le flux doit commencer par un message « start » en texte.")
    try:
        command = json.loads(message)
    except json.JSONDecodeError as error:
        raise StreamError("Message illisible : le texte doit être du JSON.") from error
    if not isinstance(command, dict):
        raise StreamError("Message illisible : un objet JSON est attendu.")
    return command


def _send(ws: Any, message: dict[str, Any]) -> None:
    ws.send(json.dumps(message, ensure_ascii=False))
