"""Route GET /api/v1/analyses/{id}/gradcam (E7, EF-13, C14), en mode demo.

Le faux prédicteur n'a pas de réseau : la carte elle-même est testée avec les vrais modèles
(test_grad_cam_ml.py et test_real_models_ml.py). Ici, on vérifie les cas où il n'y a pas de
carte, et leurs messages en français.
"""

import io
from typing import Any

import numpy as np
import pytest
import soundfile as sf
from flask import Flask
from flask.testing import FlaskClient

from echolens.services.analysis_service import AnalysisService
from echolens.services.grad_cam_service import FAMILY_A_MESSAGE
from echolens.services.storage import AnalysisRecord, AnalysisStatus

ANALYSES_URL = "/api/v1/analyses"
SAMPLE_RATE = 16_000


def tone_wav(seconds: float = 3.0) -> bytes:
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    signal = 0.3 * np.sin(2 * np.pi * 440 * times)
    buffer = io.BytesIO()
    sf.write(buffer, signal.astype(np.float32), SAMPLE_RATE, format="WAV")
    return buffer.getvalue()


def sound_event_result() -> dict[str, Any]:
    return {
        "status": "done",
        "message": None,
        "label": "rain",
        "label_fr": "Pluie",
        "probabilities": [{"label": "rain", "label_fr": "Pluie", "probability": 1.0}],
        "model_id": "demo",
        "model_version": "0",
        "calibrated": False,
        "segments": [],
        "text": None,
    }


def add_analysis(
    app: Flask, analysis_id: str, status: AnalysisStatus, profile: str, results: dict | None
) -> None:
    service: AnalysisService = app.extensions["analysis_service"]
    record = AnalysisRecord(
        id=analysis_id,
        original_filename="son.wav",
        status=status,
        tasks=["sound_event", "emotion"],
        profile=profile,
        results=results,
    )
    with service.session_factory() as session:
        session.add(record)
        session.commit()


def gradcam(client: FlaskClient, analysis_id: str, task: str = "sound_event") -> Any:
    return client.get(f"{ANALYSES_URL}/{analysis_id}/gradcam?task={task}")


def test_unknown_analysis_is_404(client: FlaskClient) -> None:
    response = gradcam(client, "inconnue")

    assert response.status_code == 404


def test_unfinished_analysis_has_no_map(app: Flask, client: FlaskClient) -> None:
    add_analysis(app, "en-cours", AnalysisStatus.PROCESSING, "realtime", None)

    response = gradcam(client, "en-cours")

    assert response.status_code == 409
    assert "pas terminée" in response.get_json()["message"]


def test_quality_profile_has_no_map(app: Flask, client: FlaskClient) -> None:
    results = {"sound_event": sound_event_result()}
    add_analysis(app, "qualite", AnalysisStatus.DONE, "quality", results)

    response = gradcam(client, "qualite")

    assert response.status_code == 409
    assert response.get_json()["message"] == FAMILY_A_MESSAGE


def test_task_without_result_has_no_map(app: Flask, client: FlaskClient) -> None:
    emotion = sound_event_result()
    emotion.update({"status": "no_speech", "message": "Aucune parole détectée"})
    results = {"sound_event": sound_event_result(), "emotion": emotion}
    add_analysis(app, "sans-parole", AnalysisStatus.DONE, "realtime", results)

    response = gradcam(client, "sans-parole", task="emotion")

    assert response.status_code == 409
    assert response.get_json()["message"] == "Pas de carte : Aucune parole détectée."


@pytest.mark.ffmpeg
def test_demo_mode_has_no_map(client: FlaskClient) -> None:
    # Le vrai parcours : un son importé en profil Temps réel, analysé par le faux prédicteur.
    data = {
        "file": (io.BytesIO(tone_wav()), "son.wav"),
        "tasks": ["sound_event"],
        "profile": "realtime",
    }
    created = client.post(ANALYSES_URL, data=data, content_type="multipart/form-data").get_json()

    response = gradcam(client, created["id"])

    assert response.status_code == 409
    assert "mode démonstration" in response.get_json()["message"]


@pytest.mark.parametrize("task", ["transcription", "danse"])
def test_task_without_grad_cam_is_refused(client: FlaskClient, task: str) -> None:
    response = gradcam(client, "inconnue", task=task)

    assert response.status_code == 400
    assert "Tâche sans carte Grad-CAM" in response.get_json()["message"]


def test_grad_cam_route_is_documented(client: FlaskClient) -> None:
    spec = client.get("/api/v1/openapi.json").get_json()
    route = spec["paths"][f"{ANALYSES_URL}/{{analysis_id}}/gradcam"]["get"]
    parameters = {parameter["name"]: parameter for parameter in route["parameters"]}
    assert parameters["task"]["schema"]["enum"] == ["emotion", "sound_event"]
    assert {"200", "404", "409"} <= set(route["responses"])
