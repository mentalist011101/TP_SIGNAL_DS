"""Historique résumé : GET /api/v1/analyses ne renvoie que le premier choix de chaque tâche."""

import io
import json
from typing import Any

import numpy as np
import pytest
import soundfile as sf
from flask import Flask
from flask.testing import FlaskClient

from echolens.core.audio.segment import Segment
from echolens.core.inference import (
    duration_weighted_mean,
    emotion_windows,
    mean_probabilities,
    sound_event_windows,
)
from echolens.services.analysis_service import AnalysisService
from echolens.services.predictor import ModelInfo
from echolens.services.results import ResultContext, done_result, unavailable_result
from echolens.services.storage import AnalysisRecord, AnalysisStatus

ANALYSES_URL = "/api/v1/analyses"
SAMPLE_RATE = 16_000
HISTORY_SIZE = 100
LONGEST_AUDIO_S = 300.0
MAX_BYTES_PER_ANALYSIS = 2_000
# Clés du résultat complet qui ne doivent jamais apparaître dans l'historique.
DETAIL_ONLY_KEYS = ["segments", "probabilities", "spectrogram", "spectrogram_url", "audio_url"]


def noisy_tone_wav(seconds: float = 12.0) -> bytes:
    """Sinusoïde de 440 Hz avec du bruit, en WAV 16 kHz."""
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    noise = np.random.default_rng(0).normal(0.0, 0.05, size=times.size)
    signal = 0.3 * np.sin(2 * np.pi * 440 * times) + noise
    buffer = io.BytesIO()
    sf.write(buffer, signal.astype(np.float32), SAMPLE_RATE, format="WAV")
    return buffer.getvalue()


def all_keys(value: Any) -> set[str]:
    """Toutes les clés d'un JSON, à n'importe quelle profondeur."""
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            keys.update(all_keys(child))
    if isinstance(value, list):
        for child in value:
            keys.update(all_keys(child))
    return keys


def full_results(context: ResultContext, duration_s: float) -> dict[str, Any]:
    """Résultats complets d'un audio de duration_s, au format stocké en base (C13).

    Probabilités tirées au hasard : seule la taille compte ici. Fenêtres des événements tous
    les 2,5 s avec 50 classes, et parole sur tout l'audio pour les émotions : le pire cas.
    """
    rng = np.random.default_rng(0)
    info = ModelInfo(model_id="demo", model_version="0.0.0", calibrated=False)
    # Étape 1 : événements sonores, une liste de 50 probabilités par fenêtre.
    windows = sound_event_windows(duration_s, context.inference_config)
    window_probabilities = [rng.dirichlet(np.ones(50)) for _ in windows]
    overall = mean_probabilities(window_probabilities)
    classes = context.labels.esc50_classes
    sound_event = done_result(windows, window_probabilities, overall, classes, info)
    # Étape 2 : émotions, un morceau de 5 s au plus sur toute la durée.
    speech = [Segment(start_s=0.0, end_s=duration_s)]
    chunks = emotion_windows(speech, context.inference_config)
    chunk_probabilities = [rng.dirichlet(np.ones(6)) for _ in chunks]
    durations_s = [chunk.duration_s for chunk in chunks]
    overall = duration_weighted_mean(chunk_probabilities, durations_s)
    emotion = done_result(chunks, chunk_probabilities, overall, context.labels.emotions, info)
    return {
        "emotion": emotion,
        "sound_event": sound_event,
        "transcription": unavailable_result(),
        "speaker": unavailable_result(),
    }


def add_long_analyses(app: Flask, count: int) -> None:
    """Enregistre count analyses terminées de 5 min, les quatre tâches demandées."""
    service: AnalysisService = app.extensions["analysis_service"]
    results = full_results(service.result_context, LONGEST_AUDIO_S)
    with service.session_factory() as session:
        for index in range(count):
            record = AnalysisRecord(
                id=f"analyse-{index}",
                original_filename=f"enregistrement-{index}.wav",
                status=AnalysisStatus.DONE,
                duration_s=LONGEST_AUDIO_S,
                tasks=["emotion", "sound_event", "transcription", "speaker"],
                profile="quality",
                results=results,
            )
            session.add(record)
        session.commit()


@pytest.mark.ffmpeg
def test_history_has_first_choice_but_no_segments(client: FlaskClient) -> None:
    data = {
        "file": (io.BytesIO(noisy_tone_wav()), "son.wav"),
        "tasks": ["sound_event", "transcription"],
        "profile": "quality",
    }
    created = client.post(ANALYSES_URL, data=data, content_type="multipart/form-data").get_json()
    detail = client.get(f"{ANALYSES_URL}/{created['id']}").get_json()

    history = client.get(ANALYSES_URL).get_json()

    for key in DETAIL_ONLY_KEYS:
        assert key not in all_keys(history)
    summary = history[0]["results"]["sound_event"]
    full = detail["results"]["sound_event"]
    assert summary["label"] == full["label"]
    assert summary["label_fr"] == full["label_fr"]
    assert summary["probability"] == full["probabilities"][0]["probability"]
    assert summary["model_id"] == full["model_id"]
    assert history[0]["results"]["transcription"]["probability"] is None


def test_history_of_long_analyses_stays_under_2_kb_each(app: Flask, client: FlaskClient) -> None:
    add_long_analyses(app, HISTORY_SIZE)

    response = client.get(f"{ANALYSES_URL}?limit={HISTORY_SIZE}")

    analyses = response.get_json()
    assert len(analyses) == HISTORY_SIZE
    assert "segments" not in all_keys(analyses)
    for analysis in analyses:
        size = len(json.dumps(analysis, ensure_ascii=False).encode("utf-8"))
        assert size < MAX_BYTES_PER_ANALYSIS
    assert len(response.data) < HISTORY_SIZE * MAX_BYTES_PER_ANALYSIS


def test_detail_still_has_segments(app: Flask, client: FlaskClient) -> None:
    add_long_analyses(app, 1)

    detail = client.get(f"{ANALYSES_URL}/analyse-0").get_json()

    sound_event = detail["results"]["sound_event"]
    assert len(sound_event["segments"]) > 0
    assert len(sound_event["segments"][0]["probabilities"]) == 50
    assert detail["spectrogram"] is not None


def test_summary_schema_is_documented_in_openapi(client: FlaskClient) -> None:
    spec = client.get("/api/v1/openapi.json").get_json()
    schemas = spec["components"]["schemas"]
    list_response = spec["paths"][ANALYSES_URL]["get"]["responses"]["200"]
    list_schema = list_response["content"]["application/json"]["schema"]
    assert list_schema["items"]["$ref"].endswith("/AnalysisSummary")
    summary_fields = set(schemas["TaskSummary"]["properties"])
    assert "probability" in summary_fields
    assert "segments" not in summary_fields
