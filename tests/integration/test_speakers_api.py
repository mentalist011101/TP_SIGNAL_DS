"""Routes /api/v1/speakers (EF-11, S6) et tâche speaker d'une analyse, en mode demo.

Le faux prédicteur donne un faux vecteur de voix (forme du spectre) : le même son est reconnu,
ce qui suffit à tester le parcours complet sans torch. La VAD est remplacée par une VAD de test :
Silero (installé avec l'extra ml) ne prend pas les voyelles de synthèse pour de la parole.
"""

import dataclasses
import io
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import soundfile as sf
from flask import Flask
from flask.testing import FlaskClient

from echolens.core.audio.segment import Segment
from echolens.core.inference import FloatArray
from echolens.services.analysis_service import AnalysisService

SPEAKERS_URL = "/api/v1/speakers"
ANALYSES_URL = "/api/v1/analyses"
SAMPLE_RATE = 16_000
# 3 s puis 5,5 s de parole : 8,5 s par extrait, sous les 10 s demandées pour un seul extrait.
SPEECH = [Segment(start_s=1.0, end_s=4.0), Segment(start_s=6.0, end_s=11.5)]


class FixedDetector:
    """VAD de test : toujours les mêmes zones de parole."""

    name = "fixe"

    def detect(self, signal: FloatArray) -> list[Segment]:
        return SPEECH


@pytest.fixture(autouse=True)
def fixed_detector(app: Flask) -> None:
    # Les analyses et l'enregistrement des voix partagent la même VAD.
    service: AnalysisService = app.extensions["analysis_service"]
    context = dataclasses.replace(service.result_context, speech_detector=FixedDetector())
    service.result_context = context
    service.speakers.context = context


def voiced_wav() -> bytes:
    """Voyelles de synthèse (140 Hz et harmoniques) de 1 à 4 s puis de 6 à 11,5 s."""
    times = np.arange(12 * SAMPLE_RATE) / SAMPLE_RATE
    fundamental = 140 * (1 + 0.05 * np.sin(2 * np.pi * 0.7 * times))
    phase = 2 * np.pi * np.cumsum(fundamental) / SAMPLE_RATE
    voiced = np.zeros_like(times)
    for harmonic in range(1, 25):
        voiced += np.sin(harmonic * phase) / harmonic
    syllables = np.clip(np.sin(2 * np.pi * 4 * times), 0, None) ** 0.5
    is_speaking = ((times > 1.0) & (times < 4.0)) | ((times > 6.0) & (times < 11.5))
    noise = np.random.default_rng(0).normal(0.0, 0.003, size=times.size)
    signal = 0.2 * voiced * syllables * is_speaking + noise
    buffer = io.BytesIO()
    sf.write(buffer, signal.astype(np.float32), SAMPLE_RATE, format="WAV")
    return buffer.getvalue()


def enroll(
    client: FlaskClient, name: str = "Awa", consent: str = "true", file_count: int = 2
) -> Any:
    files = []
    for position in range(file_count):
        files.append((io.BytesIO(voiced_wav()), f"voix_{position}.wav"))
    data = {"name": name, "consent": consent, "files": files}
    return client.post(SPEAKERS_URL, data=data, content_type="multipart/form-data")


def speaker_folders(app: Flask) -> list[Path]:
    root = app.config["ECHOLENS_SETTINGS"].data_dir / "speakers"
    if not root.exists():
        return []
    return sorted(root.iterdir())


@pytest.mark.ffmpeg
def test_speaker_is_enrolled_with_its_audio(app: Flask, client: FlaskClient) -> None:
    response = enroll(client)

    assert response.status_code == 201
    speaker = response.get_json()
    assert speaker["name"] == "Awa"
    assert speaker["audio_count"] == 2
    assert speaker["speech_s"] >= 10.0
    assert speaker["model_id"] == "demo"
    assert speaker["consent_version"] == "locuteurs-v1"
    assert "voice" not in speaker
    # L'audio converti est gardé (décision du 27 nov.), pas l'original.
    folder = speaker_folders(app)[0]
    assert sorted(path.name for path in folder.iterdir()) == [
        "enrollment_1.wav",
        "enrollment_2.wav",
    ]
    listed = client.get(SPEAKERS_URL).get_json()
    assert [item["name"] for item in listed] == ["Awa"]


def test_no_consent_means_nothing_is_kept(app: Flask, client: FlaskClient) -> None:
    response = enroll(client, consent="false")

    assert response.status_code == 400
    assert "Consentement requis" in response.get_json()["message"]
    assert speaker_folders(app) == []
    assert client.get(SPEAKERS_URL).get_json() == []


def test_missing_files_are_refused(client: FlaskClient) -> None:
    data = {"name": "Awa", "consent": "true"}
    response = client.post(SPEAKERS_URL, data=data, content_type="multipart/form-data")

    assert response.status_code == 400
    assert "au moins un extrait" in response.get_json()["message"]


@pytest.mark.ffmpeg
def test_too_little_speech_is_refused_and_not_kept(app: Flask, client: FlaskClient) -> None:
    response = enroll(client, file_count=1)

    assert response.status_code == 400
    assert "Pas assez de parole" in response.get_json()["message"]
    assert speaker_folders(app) == []


@pytest.mark.ffmpeg
def test_names_are_unique_whatever_the_case(client: FlaskClient) -> None:
    enroll(client, name="Awa")

    response = enroll(client, name="  awa ")

    assert response.status_code == 400
    assert "déjà" in response.get_json()["message"]


@pytest.mark.ffmpeg
def test_deleting_a_speaker_removes_its_audio(app: Flask, client: FlaskClient) -> None:
    speaker_id = enroll(client).get_json()["id"]

    response = client.delete(f"{SPEAKERS_URL}/{speaker_id}")

    assert response.status_code == 204
    assert speaker_folders(app) == []
    assert client.delete(f"{SPEAKERS_URL}/{speaker_id}").status_code == 404


@pytest.mark.ffmpeg
def test_analysis_names_the_enrolled_speaker(client: FlaskClient) -> None:
    speaker_id = enroll(client).get_json()["id"]
    data = {
        "file": (io.BytesIO(voiced_wav()), "conversation.wav"),
        "tasks": ["speaker"],
        "profile": "quality",
    }

    analysis = client.post(ANALYSES_URL, data=data, content_type="multipart/form-data").get_json()

    speaker = analysis["results"]["speaker"]
    assert speaker["status"] == "done"
    assert (speaker["label"], speaker["label_fr"]) == (speaker_id, "Awa")
    for segment in speaker["segments"]:
        assert segment["label_fr"] == "Awa"
        assert segment["score"] >= 0.5485


def test_speaker_routes_are_documented(client: FlaskClient) -> None:
    spec = client.get("/api/v1/openapi.json").get_json()
    assert {"get", "post"} <= set(spec["paths"][SPEAKERS_URL])
    assert "delete" in spec["paths"][f"{SPEAKERS_URL}/{{speaker_id}}"]
