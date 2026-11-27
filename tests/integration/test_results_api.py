"""Contrat des résultats dans GET /api/v1/analyses/{id} (C13), avec le faux prédicteur."""

import io
from typing import Any

import numpy as np
import pytest
import soundfile as sf
from flask import Flask
from flask.testing import FlaskClient

from echolens.services.analysis_service import AnalysisService
from echolens.services.storage import AnalysisRecord, AnalysisStatus

ANALYSES_URL = "/api/v1/analyses"
SAMPLE_RATE = 16_000


def tone_wav(seconds: float = 12.0) -> bytes:
    """Sinusoïde de 5 kHz avec un bruit faible, en WAV 16 kHz : aucune parole pour webrtcvad."""
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    noise = np.random.default_rng(0).normal(0.0, 0.005, size=times.size)
    signal = 0.3 * np.sin(2 * np.pi * 5_000 * times) + noise
    buffer = io.BytesIO()
    sf.write(buffer, signal.astype(np.float32), SAMPLE_RATE, format="WAV")
    return buffer.getvalue()


def analyse(client: FlaskClient, tasks: list[str]) -> dict[str, Any]:
    data = {"file": (io.BytesIO(tone_wav()), "son.wav"), "tasks": tasks, "profile": "quality"}
    response = client.post(ANALYSES_URL, data=data, content_type="multipart/form-data")
    assert response.status_code == 202
    analysis: dict[str, Any] = response.get_json()
    return analysis


def probability_sum(entries: list[dict[str, Any]]) -> float:
    return sum(entry["probability"] for entry in entries)


@pytest.mark.ffmpeg
def test_tone_gives_full_sound_event_result_and_no_speech(client: FlaskClient) -> None:
    analysis = analyse(client, ["sound_event", "emotion"])
    assert analysis["status"] == "done"
    results = analysis["results"]
    # Seules les tâches demandées sont présentes.
    assert set(results) == {"sound_event", "emotion"}

    events = results["sound_event"]
    assert events["status"] == "done"
    assert events["message"] is None
    assert (events["model_id"], events["model_version"], events["calibrated"]) == (
        "demo",
        "0",
        False,
    )
    assert len(events["probabilities"]) == 50
    assert probability_sum(events["probabilities"]) == pytest.approx(1.0)
    first, second = events["probabilities"][0], events["probabilities"][1]
    assert first["probability"] >= second["probability"]
    assert (events["label"], events["label_fr"]) == (first["label"], first["label_fr"])
    # 12 s : fenêtres 0-5, 2,5-7,5, 5-10 et 7-12.
    bounds = [(segment["start_s"], segment["end_s"]) for segment in events["segments"]]
    assert bounds == [(0.0, 5.0), (2.5, 7.5), (5.0, 10.0), (7.0, 12.0)]
    for segment in events["segments"]:
        assert probability_sum(segment["probabilities"]) == pytest.approx(1.0)

    emotion = results["emotion"]
    assert emotion["status"] == "no_speech"
    assert emotion["message"] == "Aucune parole détectée"
    assert emotion["label"] is None
    assert emotion["probabilities"] == []
    assert emotion["segments"] == []


@pytest.mark.ffmpeg
def test_speaker_is_unavailable_but_the_analysis_succeeds(client: FlaskClient) -> None:
    analysis = analyse(client, ["speaker", "transcription", "sound_event"])
    assert analysis["status"] == "done"
    speaker = analysis["results"]["speaker"]
    assert speaker["status"] == "unavailable"
    assert speaker["message"] == "Disponible prochainement"
    assert speaker["model_id"] is None
    # Pas de parole dans la sinusoïde de 5 kHz : la transcription ne s'invente pas de texte.
    transcription = analysis["results"]["transcription"]
    assert transcription["status"] == "no_speech"
    assert transcription["text"] is None
    assert analysis["results"]["sound_event"]["status"] == "done"


@pytest.mark.ffmpeg
def test_same_file_twice_gives_the_same_probabilities(client: FlaskClient) -> None:
    first = analyse(client, ["sound_event"])
    second = analyse(client, ["sound_event"])
    assert first["id"] != second["id"]
    assert first["results"] == second["results"]


@pytest.mark.parametrize("status", [AnalysisStatus.PENDING, AnalysisStatus.PROCESSING])
def test_unfinished_analysis_has_null_results(
    app: Flask, client: FlaskClient, status: AnalysisStatus
) -> None:
    service: AnalysisService = app.extensions["analysis_service"]
    record = AnalysisRecord(
        id=f"analyse-{status.value}",
        original_filename="son.wav",
        status=status,
        tasks=["sound_event"],
        profile="quality",
    )
    with service.session_factory() as session:
        session.add(record)
        session.commit()
    analysis = client.get(f"{ANALYSES_URL}/analyse-{status.value}").get_json()
    assert analysis["status"] == status.value
    assert analysis["results"] is None


def test_results_schemas_are_documented_in_openapi(client: FlaskClient) -> None:
    spec = client.get("/api/v1/openapi.json").get_json()
    schemas = spec["components"]["schemas"]
    assert {"Results", "TaskResult", "SegmentResult", "ClassProbability"} <= set(schemas)
    status_field = schemas["TaskResult"]["properties"]["status"]
    assert status_field["enum"] == ["done", "no_speech", "unavailable"]
