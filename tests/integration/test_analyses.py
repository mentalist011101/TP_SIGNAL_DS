import io
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import soundfile as sf
from flask.testing import FlaskClient

from echolens.api import create_app
from echolens.config import AppSettings
from echolens.services.analysis_service import INTERRUPTED_MESSAGE, AnalysisService
from echolens.services.storage import AnalysisRecord, AnalysisStatus

ANALYSES_URL = "/api/v1/analyses"


def make_client(tmp_path: Path, **settings: Any) -> FlaskClient:
    app_settings = AppSettings(
        data_dir=tmp_path, web_dist_dir=tmp_path / "dist", run_jobs_synchronously=True, **settings
    )
    app = create_app(app_settings, TESTING=True)
    return app.test_client()


def stereo_sine_wav(
    seconds: float = 2.0, sample_rate: int = 44_100, file_format: str = "WAV"
) -> bytes:
    """Audio stéréo de synthèse à 44,1 kHz (WAV par défaut), pour vérifier la conversion."""
    t = np.arange(int(seconds * sample_rate)) / sample_rate
    left = 0.3 * np.sin(2 * np.pi * 440 * t)
    right = 0.3 * np.sin(2 * np.pi * 660 * t)
    buffer = io.BytesIO()
    sf.write(buffer, np.stack([left, right], axis=1), sample_rate, format=file_format)
    return buffer.getvalue()


def silent_wav() -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, np.zeros(16_000, dtype=np.float32), 16_000, format="WAV")
    return buffer.getvalue()


def post_audio(
    client: FlaskClient,
    content: bytes,
    filename: str = "voix.wav",
    tasks: list[str] | None = None,
) -> Any:
    if tasks is None:
        tasks = ["emotion", "speaker"]
    data = {"file": (io.BytesIO(content), filename), "tasks": tasks, "profile": "quality"}
    return client.post(ANALYSES_URL, data=data, content_type="multipart/form-data")


@pytest.mark.ffmpeg
def test_valid_import_is_done_with_correct_duration(client: FlaskClient) -> None:
    response = post_audio(client, stereo_sine_wav(seconds=2.0))
    assert response.status_code == 202
    analysis = response.get_json()
    assert analysis["status"] == "done"
    assert analysis["duration_s"] == pytest.approx(2.0, abs=0.01)
    assert analysis["tasks"] == ["emotion", "speaker"]
    assert analysis["profile"] == "quality"
    assert analysis["original_filename"] == "voix.wav"
    assert analysis["error_message"] is None
    assert analysis["created_at"].endswith("+00:00")
    assert analysis["audio_url"] == f"{ANALYSES_URL}/{analysis['id']}/audio"

    fetched = client.get(f"{ANALYSES_URL}/{analysis['id']}").get_json()
    assert fetched == analysis


@pytest.mark.ffmpeg
def test_history_contains_the_analysis(client: FlaskClient) -> None:
    first = post_audio(client, stereo_sine_wav()).get_json()
    second = post_audio(client, stereo_sine_wav()).get_json()

    history = client.get(ANALYSES_URL).get_json()
    ids = [analysis["id"] for analysis in history]
    assert ids == [second["id"], first["id"]]

    page = client.get(f"{ANALYSES_URL}?limit=1&offset=1").get_json()
    assert [analysis["id"] for analysis in page] == [first["id"]]


@pytest.mark.ffmpeg
def test_audio_is_served_as_16k_mono_wav(client: FlaskClient) -> None:
    analysis = post_audio(client, stereo_sine_wav(seconds=2.0)).get_json()

    response = client.get(analysis["audio_url"])
    assert response.status_code == 200
    assert response.mimetype == "audio/wav"
    signal, sample_rate = sf.read(io.BytesIO(response.data))
    assert sample_rate == 16_000
    assert signal.ndim == 1


@pytest.mark.ffmpeg
def test_delete_removes_analysis_and_files(client: FlaskClient, tmp_path: Path) -> None:
    analysis = post_audio(client, stereo_sine_wav()).get_json()
    url = f"{ANALYSES_URL}/{analysis['id']}"

    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404
    assert not (tmp_path / "analyses" / analysis["id"]).exists()


@pytest.mark.ffmpeg
def test_processing_error_marks_analysis_failed(
    client: FlaskClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_conversion(self: AnalysisService, analysis_id: str) -> float:
        raise RuntimeError("disque plein")

    monkeypatch.setattr(AnalysisService, "_convert_audio", broken_conversion)
    analysis = post_audio(client, stereo_sine_wav()).get_json()
    assert analysis["status"] == "failed"
    assert "disque plein" in analysis["error_message"]
    assert analysis["audio_url"] is None


def test_unknown_extension_is_rejected(client: FlaskClient) -> None:
    response = post_audio(client, b"pas de l'audio", filename="notes.txt")
    assert response.status_code == 400
    assert "Format non pris en charge" in response.get_json()["message"]
    assert client.get(ANALYSES_URL).get_json() == []


@pytest.mark.ffmpeg
def test_corrupted_file_is_rejected(client: FlaskClient, tmp_path: Path) -> None:
    response = post_audio(client, b"ceci n'est pas un wav", filename="casse.wav")
    assert response.status_code == 400
    assert "illisible" in response.get_json()["message"]
    assert client.get(ANALYSES_URL).get_json() == []
    assert list((tmp_path / "analyses").iterdir()) == []


@pytest.mark.ffmpeg
def test_too_long_audio_is_rejected(tmp_path: Path) -> None:
    client = make_client(tmp_path, max_audio_seconds=1.0)
    response = post_audio(client, stereo_sine_wav(seconds=2.0))
    assert response.status_code == 400
    assert "trop long" in response.get_json()["message"]


@pytest.mark.ffmpeg
def test_silent_audio_is_rejected(client: FlaskClient) -> None:
    response = post_audio(client, silent_wav())
    assert response.status_code == 400
    assert "silencieux" in response.get_json()["message"]


def test_unknown_task_is_rejected(client: FlaskClient) -> None:
    response = post_audio(client, stereo_sine_wav(), tasks=["emotion", "danse"])
    assert response.status_code == 400
    body = response.get_json()
    assert body["message"].startswith("Tâche inconnue : « danse »")
    assert "tasks" in body["errors"]["form"]


def test_missing_file_is_rejected(client: FlaskClient) -> None:
    data = {"tasks": ["emotion"], "profile": "quality"}
    response = client.post(ANALYSES_URL, data=data, content_type="multipart/form-data")
    assert response.status_code == 400
    body = response.get_json()
    assert body["message"] == "Aucun fichier reçu (champ file)."
    assert "file" in body["errors"]["files"]


def test_invalid_page_size_has_french_message(client: FlaskClient) -> None:
    response = client.get(f"{ANALYSES_URL}?limit=abc")
    assert response.status_code == 400
    assert response.get_json()["message"] == "limit doit être un nombre entier."


def test_unknown_api_route_has_french_message(client: FlaskClient) -> None:
    response = client.get("/api/v1/inexistant")
    assert response.status_code == 404
    assert response.get_json()["message"] == "Ressource introuvable."


@pytest.mark.ffmpeg
@pytest.mark.parametrize(
    ("sent_name", "file_format", "kept_name"),
    [("音声メモ.wav", "WAV", "audio.wav"), ("تسجيل.mp3", "MP3", "audio.mp3")],
)
def test_non_latin_filenames_are_accepted(
    client: FlaskClient, sent_name: str, file_format: str, kept_name: str
) -> None:
    content = stereo_sine_wav(file_format=file_format)
    response = post_audio(client, content, filename=sent_name)
    assert response.status_code == 202
    analysis = response.get_json()
    assert analysis["status"] == "done"
    assert analysis["original_filename"] == kept_name


def test_non_latin_filename_with_bad_extension_is_rejected(client: FlaskClient) -> None:
    response = post_audio(client, b"du texte", filename="音声メモ.txt")
    assert response.status_code == 400
    assert "Format non pris en charge : « 音声メモ.txt »" in response.get_json()["message"]


def test_restart_fails_interrupted_analyses(tmp_path: Path) -> None:
    settings = AppSettings(data_dir=tmp_path, web_dist_dir=tmp_path / "dist")
    first_app = create_app(settings, TESTING=True)
    service: AnalysisService = first_app.extensions["analysis_service"]
    record = AnalysisRecord(
        id="interrompue",
        original_filename="voix.wav",
        status=AnalysisStatus.PROCESSING,
        tasks=["emotion"],
        profile="quality",
    )
    with service.session_factory() as session:
        session.add(record)
        session.commit()

    restarted_client = create_app(settings, TESTING=True).test_client()
    analysis = restarted_client.get(f"{ANALYSES_URL}/interrompue").get_json()
    assert analysis["status"] == "failed"
    assert analysis["error_message"] == INTERRUPTED_MESSAGE


def test_too_large_upload_returns_413_in_french(tmp_path: Path) -> None:
    client = make_client(tmp_path, max_upload_mb=1)
    two_megabytes = bytes(2 * 1024 * 1024)
    response = post_audio(client, two_megabytes)
    assert response.status_code == 413
    assert response.get_json()["message"] == "Fichier trop volumineux : 1 Mo maximum."


def test_unknown_analysis_is_404(client: FlaskClient) -> None:
    response = client.get(f"{ANALYSES_URL}/inconnue")
    assert response.status_code == 404
    assert "introuvable" in response.get_json()["message"]


def test_analysis_routes_are_documented(client: FlaskClient) -> None:
    paths = client.get("/api/v1/openapi.json").get_json()["paths"]
    assert "/api/v1/analyses" in paths
    assert "/api/v1/analyses/{analysis_id}" in paths
    assert "/api/v1/analyses/{analysis_id}/audio" in paths
