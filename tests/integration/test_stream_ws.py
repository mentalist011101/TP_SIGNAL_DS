"""Flux micro en direct par WebSocket (EF-14, C23, D8), en mode demo, avec un vrai serveur.

Le client de test de Flask ne parle pas WebSocket : l'application tourne dans un vrai serveur
werkzeug, sur un port libre, et le test s'y connecte avec le client de simple-websocket. La VAD
est remplacée par des zones de parole fixées, pour un résultat qui ne dépend pas du détecteur.
"""

import dataclasses
import json
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from flask import Flask
from simple_websocket import Client
from sqlalchemy import func, select
from werkzeug.serving import make_server

from echolens.api import create_app
from echolens.config import AppSettings
from echolens.core.audio.segment import FloatArray, Segment
from echolens.services.analysis_service import AnalysisService
from echolens.services.storage import AnalysisRecord, RecordingConsentRecord

SAMPLE_RATE = 16_000
CHUNK_S = 0.1
RECEIVE_TIMEOUT_S = 30


class FixedDetector:
    """VAD de test : de la parole sur toute la fenêtre."""

    name = "fixe"

    def detect(self, signal: FloatArray) -> list[Segment]:
        duration_s = len(signal) / SAMPLE_RATE
        return [Segment(start_s=0.0, end_s=duration_s)]


@pytest.fixture
def stream_app(tmp_path: Path) -> Flask:
    settings = AppSettings(
        data_dir=tmp_path, web_dist_dir=tmp_path / "dist", run_jobs_synchronously=True
    )
    app = create_app(settings, TESTING=True)
    service: AnalysisService = app.extensions["analysis_service"]
    context = dataclasses.replace(service.result_context, speech_detector=FixedDetector())
    service.result_context = context
    return app


@pytest.fixture
def server_url(stream_app: Flask) -> Iterator[str]:
    """Adresse ws:// d'un vrai serveur qui sert l'application, arrêté après le test."""
    server = make_server("127.0.0.1", 0, stream_app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"ws://127.0.0.1:{server.server_port}/ws/stream"
    server.shutdown()


def tone_pcm(seconds: float) -> bytes:
    """Sinusoïde de 220 Hz avec du bruit, en PCM Int16 petit-boutiste (format de D8)."""
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    noise = np.random.default_rng(0).normal(0.0, 0.02, size=times.size)
    signal = 0.3 * np.sin(2 * np.pi * 220 * times) + noise
    samples = np.clip(signal * 32_767, -32_768, 32_767).astype("<i2")
    return samples.tobytes()


def send_audio(client: Client, seconds: float) -> None:
    """Envoie `seconds` de son par morceaux de 100 ms, comme le navigateur."""
    pcm = tone_pcm(seconds)
    chunk_bytes = int(CHUNK_S * SAMPLE_RATE) * 2
    for start in range(0, len(pcm), chunk_bytes):
        client.send(pcm[start : start + chunk_bytes])


def receive_all(client: Client) -> list[dict[str, Any]]:
    """Tous les messages du serveur jusqu'à la fermeture de la connexion."""
    messages = []
    while True:
        try:
            text = client.receive(timeout=RECEIVE_TIMEOUT_S)
        except Exception:
            return messages
        if text is None:
            return messages
        messages.append(json.loads(text))


def close_if_open(client: Client) -> None:
    # Le serveur ferme la connexion après « stop » ou une erreur : rien à fermer alors.
    if client.connected:
        client.close()


def run_session(url: str, start: dict[str, Any], seconds: float) -> list[dict[str, Any]]:
    client = Client.connect(url)
    client.send(json.dumps(start))
    send_audio(client, seconds)
    client.send(json.dumps({"type": "stop"}))
    messages = receive_all(client)
    close_if_open(client)
    return messages


def of_type(messages: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [message for message in messages if message["type"] == kind]


def row_count(app: Flask, table: type) -> int:
    service: AnalysisService = app.extensions["analysis_service"]
    with service.session_factory() as session:
        count: int = session.scalar(select(func.count()).select_from(table))
    return count


def test_stream_sends_ready_then_windows(server_url: str) -> None:
    messages = run_session(server_url, {"type": "start", "record": False}, seconds=3.0)

    assert messages[0]["type"] == "ready"
    assert messages[0]["window_s"] == 2.0
    assert messages[0]["hop_s"] == 0.5
    windows = of_type(messages, "window")
    # 3 s de son : une fenêtre à 2 s, puis au plus deux de plus (2,5 et 3 s), moins celles
    # sautées si le calcul a pris du retard.
    assert 1 <= len(windows) <= 3
    first = windows[0]
    assert set(first["results"]) == {"emotion", "sound_event"}
    assert first["results"]["emotion"]["model_id"] == "demo"
    assert first["results"]["sound_event"]["probability"] > 0
    assert first["speech"] is True
    assert first["silent"] is False
    assert first["level_dbfs"] > -30
    assert first["compute_ms"] > 0
    assert first["rtf"] == pytest.approx(first["compute_ms"] / 2000, abs=1e-3)
    assert first["compute_p95_ms"] >= first["compute_p50_ms"]
    assert of_type(messages, "saved") == []


def test_silent_microphone_is_reported(server_url: str) -> None:
    # Un micro muet envoie des zéros : le serveur le dit, au lieu d'afficher des résultats
    # qui ne veulent rien dire.
    client = Client.connect(server_url)
    client.send(json.dumps({"type": "start", "record": False}))
    silent_chunk = bytes(int(CHUNK_S * SAMPLE_RATE) * 2)
    for _ in range(25):
        client.send(silent_chunk)
    client.send(json.dumps({"type": "stop"}))
    messages = receive_all(client)
    close_if_open(client)

    windows = of_type(messages, "window")
    assert windows[0]["silent"] is True
    assert windows[0]["level_dbfs"] == -200.0


def test_stream_without_consent_stores_nothing(stream_app: Flask, server_url: str) -> None:
    run_session(server_url, {"type": "start", "record": False}, seconds=2.5)

    assert row_count(stream_app, AnalysisRecord) == 0


def test_recording_with_consent_becomes_an_analysis(stream_app: Flask, server_url: str) -> None:
    start = {"type": "start", "record": True, "consent": {"accepted": True, "version": "direct-v1"}}

    messages = run_session(server_url, start, seconds=3.0)

    saved = of_type(messages, "saved")
    assert len(saved) == 1
    assert saved[0]["truncated"] is False
    service: AnalysisService = stream_app.extensions["analysis_service"]
    record = service.get_analysis(saved[0]["analysis_id"])
    assert record.original_filename.startswith("direct_")
    assert record.tasks == ["emotion", "sound_event", "transcription"]
    assert record.profile == "quality"
    assert record.duration_s == pytest.approx(3.0, abs=0.05)
    assert row_count(stream_app, RecordingConsentRecord) == 1


def test_recording_without_consent_is_refused(stream_app: Flask, server_url: str) -> None:
    # Le serveur répond dès le « start » et ferme : le navigateur n'envoie aucun son.
    client = Client.connect(server_url)
    client.send(json.dumps({"type": "start", "record": True}))
    messages = receive_all(client)
    close_if_open(client)

    assert messages == [
        {
            "type": "error",
            "message": "Enregistrement refusé : cochez la case qui dit que vous avez lu et "
            "accepté l'enregistrement de votre voix.",
        }
    ]
    assert row_count(stream_app, AnalysisRecord) == 0


def test_stream_must_start_with_start(server_url: str) -> None:
    client = Client.connect(server_url)
    client.send(tone_pcm(0.1))
    messages = receive_all(client)
    close_if_open(client)

    assert messages[0]["type"] == "error"
    assert "start" in messages[0]["message"]


def test_deleting_a_recorded_analysis_deletes_its_consent(
    stream_app: Flask, server_url: str
) -> None:
    start = {"type": "start", "record": True, "consent": {"accepted": True, "version": "direct-v1"}}
    saved = of_type(run_session(server_url, start, seconds=2.5), "saved")
    service: AnalysisService = stream_app.extensions["analysis_service"]

    service.delete_analysis(saved[0]["analysis_id"])

    assert row_count(stream_app, RecordingConsentRecord) == 0
