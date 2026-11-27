"""Transcription dans l'API, en mode demo (EF-10, EF-12, C17b) : contrat, export CSV et PDF.

La VAD de l'application est remplacée par un détecteur aux zones de parole fixées : le
résultat ne dépend ni de webrtcvad (CI) ni de Silero (extra [ml]).
"""

import csv
import dataclasses
import io
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pytest
import soundfile as sf
from flask import Flask
from flask.testing import FlaskClient

from echolens.core.audio.segment import FloatArray, Segment
from echolens.services.analysis_service import AnalysisService
from echolens.services.predictor import DEMO_TRANSCRIPTION
from echolens.services.results import build_results
from echolens.services.storage import AnalysisRecord, AnalysisStatus, fill_missing_summaries

ANALYSES_URL = "/api/v1/analyses"
SAMPLE_RATE = 16_000
TASKS = ["emotion", "transcription"]
SPEECH = [Segment(start_s=0.5, end_s=3.0), Segment(start_s=4.0, end_s=9.5)]


class FixedDetector:
    """VAD de test : toujours les mêmes zones de parole."""

    name = "fixe"

    def detect(self, signal: FloatArray) -> list[Segment]:
        return SPEECH


def use_fixed_detector(app: Flask) -> AnalysisService:
    """Remplace la VAD de l'application par FixedDetector ; renvoie le service."""
    service: AnalysisService = app.extensions["analysis_service"]
    context = dataclasses.replace(service.result_context, speech_detector=FixedDetector())
    service.result_context = context
    return service


def noise(seconds: float = 10.0) -> np.ndarray:
    generator = np.random.default_rng(0)
    signal = generator.normal(0.0, 0.05, size=int(seconds * SAMPLE_RATE))
    return signal.astype(np.float32)


def add_analysis(app: Flask, results: dict[str, Any] | None = None) -> None:
    """Analyse terminée, avec les résultats donnés ou ceux du mode demo."""
    service = use_fixed_detector(app)
    if results is None:
        results = build_results(noise(), TASKS, "quality", service.result_context)
    record = AnalysisRecord(
        id="parole",
        created_at=datetime(2026, 11, 25, 10, 0, tzinfo=UTC),
        original_filename="entretien.wav",
        status=AnalysisStatus.DONE,
        duration_s=10.0,
        tasks=TASKS,
        profile="quality",
        results=results,
    )
    with service.session_factory() as session:
        session.add(record)
        session.commit()
    # Résumé pour l'historique, calculé comme au démarrage de l'application.
    fill_missing_summaries(service.session_factory)


def csv_rows(content: bytes) -> list[dict[str, str]]:
    text = content.decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def test_transcription_contract_in_demo_mode(app: Flask, client: FlaskClient) -> None:
    add_analysis(app)

    detail = client.get(f"{ANALYSES_URL}/parole").get_json()

    transcription = detail["results"]["transcription"]
    assert transcription["status"] == "done"
    assert transcription["model_id"] == "demo"
    assert transcription["label"] is None
    assert transcription["label_fr"] is None
    assert transcription["probabilities"] == []
    assert transcription["text"] == f"{DEMO_TRANSCRIPTION} {DEMO_TRANSCRIPTION}"
    segments = transcription["segments"]
    assert [(segment["start_s"], segment["end_s"]) for segment in segments] == [
        (0.5, 3.0),
        (4.0, 9.5),
    ]
    for segment in segments:
        assert segment["text"] == DEMO_TRANSCRIPTION
        assert segment["probabilities"] == []
        assert segment["label"] is None


def test_other_tasks_have_null_text(app: Flask, client: FlaskClient) -> None:
    add_analysis(app)

    detail = client.get(f"{ANALYSES_URL}/parole").get_json()

    emotion = detail["results"]["emotion"]
    assert emotion["text"] is None
    for segment in emotion["segments"]:
        assert segment["text"] is None


def test_results_saved_before_text_existed_give_null_text(app: Flask, client: FlaskClient) -> None:
    # Résultats enregistrés avant C17b : aucune clé text, ni sur la tâche ni sur les segments.
    service = use_fixed_detector(app)
    results = build_results(noise(), ["emotion"], "quality", service.result_context)
    emotion = results["emotion"]
    del emotion["text"]
    for segment in emotion["segments"]:
        del segment["text"]
    add_analysis(app, results)

    detail = client.get(f"{ANALYSES_URL}/parole").get_json()

    assert detail["results"]["emotion"]["text"] is None
    assert detail["results"]["emotion"]["segments"][0]["text"] is None


def test_history_summary_of_a_transcription(app: Flask, client: FlaskClient) -> None:
    add_analysis(app)

    history = client.get(ANALYSES_URL).get_json()

    summary = history[0]["results"]["transcription"]
    assert summary["status"] == "done"
    assert summary["label"] is None
    assert summary["probability"] is None


def test_csv_export_has_the_transcription_text(app: Flask, client: FlaskClient) -> None:
    add_analysis(app)

    response = client.get(f"{ANALYSES_URL}/parole/export?format=csv")

    rows = csv_rows(response.data)
    transcription_rows = [row for row in rows if row["task"] == "transcription"]
    assert len(transcription_rows) == 3
    full_text = transcription_rows[0]
    assert full_text["scope"] == "global"
    assert full_text["text"] == f"{DEMO_TRANSCRIPTION} {DEMO_TRANSCRIPTION}"
    assert full_text["start_s"] == full_text["probability"] == full_text["rank"] == ""
    first_segment = transcription_rows[1]
    assert first_segment["scope"] == "segment"
    assert first_segment["segment_index"] == "1"
    assert (first_segment["start_s"], first_segment["end_s"]) == ("0.5", "3.0")
    assert first_segment["text"] == DEMO_TRANSCRIPTION
    assert first_segment["label"] == first_segment["probability"] == ""
    # Les autres tâches gardent une colonne text vide.
    emotion_rows = [row for row in rows if row["task"] == "emotion"]
    assert {row["text"] for row in emotion_rows} == {""}


def test_pdf_export_with_a_transcription_is_generated(app: Flask, client: FlaskClient) -> None:
    add_analysis(app)

    response = client.get(f"{ANALYSES_URL}/parole/export?format=pdf")

    assert response.status_code == 200
    assert response.data.startswith(b"%PDF")


def test_text_fields_are_documented_in_openapi(client: FlaskClient) -> None:
    schemas = client.get("/api/v1/openapi.json").get_json()["components"]["schemas"]
    task_text = schemas["TaskResult"]["properties"]["text"]
    segment_text = schemas["SegmentResult"]["properties"]["text"]
    assert task_text["type"] == "string"
    assert task_text["nullable"] is True
    assert segment_text["nullable"] is True
    assert schemas["SegmentResult"]["properties"]["label"]["nullable"] is True


@pytest.mark.ffmpeg
def test_imported_audio_is_transcribed_in_demo_mode(app: Flask, client: FlaskClient) -> None:
    use_fixed_detector(app)
    buffer = io.BytesIO()
    sf.write(buffer, noise(), SAMPLE_RATE, format="WAV")
    data = {"file": (io.BytesIO(buffer.getvalue()), "son.wav"), "tasks": ["transcription"]}

    analysis = client.post(ANALYSES_URL, data=data, content_type="multipart/form-data").get_json()

    transcription = analysis["results"]["transcription"]
    assert transcription["status"] == "done"
    assert len(transcription["segments"]) == len(SPEECH)
