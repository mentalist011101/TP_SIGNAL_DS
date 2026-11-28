"""Routes /api/v1/compare (EF-15) : un même fichier dans chaque modèle, en mode demo.

Le faux prédicteur a un seul « modèle » (demo) dans les deux profils : il ne tourne qu'une fois
par tâche, avec ses deux profils notés. Le cas de deux modèles différents est testé avec un
prédicteur de test dans tests/unit/test_comparison.py.
"""

import io
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import soundfile as sf
from flask import Flask
from flask.testing import FlaskClient

COMPARE_URL = "/api/v1/compare"
SAMPLE_RATE = 16_000


def tone_wav(seconds: float = 6.0) -> bytes:
    """Sinusoïde de 5 kHz avec un bruit faible : un événement, aucune parole."""
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    noise = np.random.default_rng(0).normal(0.0, 0.005, size=times.size)
    signal = 0.3 * np.sin(2 * np.pi * 5_000 * times) + noise
    buffer = io.BytesIO()
    sf.write(buffer, signal.astype(np.float32), SAMPLE_RATE, format="WAV")
    return buffer.getvalue()


def compare(client: FlaskClient, tasks: list[str]) -> Any:
    data = {"file": (io.BytesIO(tone_wav()), "son.wav"), "tasks": tasks}
    return client.post(COMPARE_URL, data=data, content_type="multipart/form-data")


def comparison_folders(app: Flask) -> list[Path]:
    root = app.config["ECHOLENS_SETTINGS"].data_dir / "comparisons"
    if not root.exists():
        return []
    return sorted(root.iterdir())


@pytest.mark.ffmpeg
def test_each_model_runs_once_with_its_time(client: FlaskClient) -> None:
    response = compare(client, ["sound_event", "emotion"])

    assert response.status_code == 202
    comparison = response.get_json()
    assert comparison["status"] == "done"
    assert comparison["duration_s"] == pytest.approx(6.0)
    runs = comparison["results"]["sound_event"]
    assert [run["model_id"] for run in runs] == ["demo"]
    assert runs[0]["profiles"] == ["quality", "realtime"]
    assert runs[0]["compute_s"] >= 0.0
    assert runs[0]["result"]["status"] == "done"
    assert comparison["results"]["emotion"][0]["result"]["status"] == "no_speech"
    assert comparison["audio_url"] == f"{COMPARE_URL}/{comparison['id']}/audio"
    audio = client.get(comparison["audio_url"])
    assert audio.status_code == 200
    assert audio.mimetype == "audio/wav"


@pytest.mark.ffmpeg
def test_comparisons_are_listed_and_deleted(app: Flask, client: FlaskClient) -> None:
    comparison_id = compare(client, ["sound_event"]).get_json()["id"]

    listed = client.get(COMPARE_URL).get_json()
    assert [item["id"] for item in listed] == [comparison_id]
    assert "results" not in listed[0]

    assert client.delete(f"{COMPARE_URL}/{comparison_id}").status_code == 204
    assert comparison_folders(app) == []
    assert client.get(f"{COMPARE_URL}/{comparison_id}").status_code == 404


def test_speaker_is_not_comparable(client: FlaskClient) -> None:
    response = compare(client, ["speaker"])

    assert response.status_code == 400
    assert "Tâche non comparable" in response.get_json()["message"]


@pytest.mark.ffmpeg
def test_refused_file_leaves_nothing(app: Flask, client: FlaskClient) -> None:
    data = {"file": (io.BytesIO(b"pas un son"), "son.wav"), "tasks": ["sound_event"]}

    response = client.post(COMPARE_URL, data=data, content_type="multipart/form-data")

    assert response.status_code == 400
    assert comparison_folders(app) == []


def test_unknown_comparison_is_404(client: FlaskClient) -> None:
    assert client.get(f"{COMPARE_URL}/inconnue").status_code == 404
    assert client.delete(f"{COMPARE_URL}/inconnue").status_code == 404


def test_compare_routes_are_documented(client: FlaskClient) -> None:
    spec = client.get("/api/v1/openapi.json").get_json()
    assert {"get", "post"} <= set(spec["paths"][COMPARE_URL])
    assert {"get", "delete"} <= set(spec["paths"][f"{COMPARE_URL}/{{comparison_id}}"])
