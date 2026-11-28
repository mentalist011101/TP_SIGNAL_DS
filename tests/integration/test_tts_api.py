"""Routes /api/v1/tts (EF-18, ENF-10, C35), en mode demo.

Le faux cloneur produit des voyelles de synthèse : on vérifie le parcours (consentement,
contrôles, marquage, suppression) sans XTTS. La VAD est une VAD de test, comme dans
test_speakers_api.py.
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

from echolens.api import create_app
from echolens.config import AppSettings
from echolens.core.audio.segment import Segment
from echolens.core.inference import FloatArray, load_inference_config
from echolens.core.models.registry import ModelRegistry, Task
from echolens.services.analysis_service import AnalysisService
from echolens.services.cloning_service import SYNTHETIC_TITLE
from echolens.services.xtts_cloner import XttsCloner

TTS_URL = "/api/v1/tts"
SPEAKERS_URL = "/api/v1/speakers"
SAMPLE_RATE = 16_000
SPEECH = [Segment(start_s=1.0, end_s=4.0), Segment(start_s=6.0, end_s=11.5)]


class FixedDetector:
    name = "fixe"

    def detect(self, signal: FloatArray) -> list[Segment]:
        return SPEECH


def use_fixed_detector(app: Flask) -> None:
    service: AnalysisService = app.extensions["analysis_service"]
    context = dataclasses.replace(service.result_context, speech_detector=FixedDetector())
    service.result_context = context
    service.speakers.context = context


@pytest.fixture(autouse=True)
def fixed_detector(app: Flask) -> None:
    use_fixed_detector(app)


def voice_wav() -> bytes:
    times = np.arange(12 * SAMPLE_RATE) / SAMPLE_RATE
    voiced = np.zeros_like(times)
    for harmonic in range(1, 20):
        voiced += np.sin(2 * np.pi * 140 * harmonic * times) / harmonic
    buffer = io.BytesIO()
    sf.write(buffer, (0.1 * voiced).astype(np.float32), SAMPLE_RATE, format="WAV")
    return buffer.getvalue()


def enroll(client: FlaskClient, name: str, cloning: bool) -> str:
    files = [(io.BytesIO(voice_wav()), "a.wav"), (io.BytesIO(voice_wav()), "b.wav")]
    data = {"name": name, "consent": "true", "cloning_consent": str(cloning).lower()}
    data["files"] = files
    response = client.post(SPEAKERS_URL, data=data, content_type="multipart/form-data")
    assert response.status_code == 201, response.get_json()
    speaker_id: str = response.get_json()["id"]
    return speaker_id


def clone(client: FlaskClient, speaker_id: str, text: str = "Bonjour à tous.") -> Any:
    return client.post(TTS_URL, json={"speaker_id": speaker_id, "text": text})


@pytest.mark.ffmpeg
def test_consenting_voice_is_cloned_and_marked(client: FlaskClient, tmp_path: Path) -> None:
    speaker_id = enroll(client, "Awa", cloning=True)
    assert client.get(SPEAKERS_URL).get_json()[0]["cloning_allowed"] is True

    response = clone(client, speaker_id)

    assert response.status_code == 202
    synthesis = response.get_json()
    assert synthesis["status"] == "done"
    assert synthesis["speaker_name"] == "Awa"
    assert synthesis["download_name"].startswith("voix_synthetique_Awa_")
    audio = client.get(synthesis["audio_url"])
    assert audio.status_code == 200
    path = tmp_path / "clone.wav"
    path.write_bytes(audio.data)
    # Métadonnées « voix synthétique » et bip de 1 kHz au début.
    with sf.SoundFile(path) as handle:
        assert handle.title == SYNTHETIC_TITLE
        assert "Voix synthétique" in handle.comment
        samples = handle.read(dtype="float32")
        sample_rate = handle.samplerate
    settings = load_inference_config().voice_cloning
    tone = samples[: round(settings.marker_duration_s * sample_rate)]
    spectrum = np.abs(np.fft.rfft(tone))
    frequencies = np.fft.rfftfreq(len(tone), d=1 / sample_rate)
    assert frequencies[int(np.argmax(spectrum))] == pytest.approx(1000, abs=10)
    assert [item["id"] for item in client.get(TTS_URL).get_json()] == [synthesis["id"]]


@pytest.mark.ffmpeg
def test_voice_without_cloning_consent_is_refused(client: FlaskClient) -> None:
    speaker_id = enroll(client, "Awa", cloning=False)

    response = clone(client, speaker_id)

    assert response.status_code == 403
    assert "pas accepté" in response.get_json()["message"]
    assert client.get(TTS_URL).get_json() == []


@pytest.mark.ffmpeg
@pytest.mark.parametrize("text", ["   ", "a" * 301])
def test_empty_or_long_text_is_refused(client: FlaskClient, text: str) -> None:
    speaker_id = enroll(client, "Awa", cloning=True)

    response = clone(client, speaker_id, text)

    assert response.status_code == 400


def test_unknown_speaker_is_404(client: FlaskClient) -> None:
    assert clone(client, "inconnu").status_code == 404


@pytest.mark.ffmpeg
def test_deleting_the_speaker_deletes_its_clones(client: FlaskClient) -> None:
    speaker_id = enroll(client, "Awa", cloning=True)
    synthesis_id = clone(client, speaker_id).get_json()["id"]

    client.delete(f"{SPEAKERS_URL}/{speaker_id}")

    assert client.get(f"{TTS_URL}/{synthesis_id}").status_code == 404
    assert client.get(TTS_URL).get_json() == []


@pytest.mark.ffmpeg
def test_deleting_a_clone_keeps_the_speaker(client: FlaskClient) -> None:
    speaker_id = enroll(client, "Awa", cloning=True)
    synthesis_id = clone(client, speaker_id).get_json()["id"]

    assert client.delete(f"{TTS_URL}/{synthesis_id}").status_code == 204

    assert client.get(f"{TTS_URL}/{synthesis_id}").status_code == 404
    assert len(client.get(SPEAKERS_URL).get_json()) == 1


@pytest.mark.ffmpeg
def test_unaccepted_license_is_503(tmp_path: Path) -> None:
    # Vrai cloneur (XTTS) sans la licence acceptée : refus immédiat, sans charger le modèle.
    settings = AppSettings(
        data_dir=tmp_path,
        web_dist_dir=tmp_path / "dist",
        run_jobs_synchronously=True,
        inference_backend="demo",
    )
    app = create_app(settings, TESTING=True)
    use_fixed_detector(app)
    registry = ModelRegistry.from_yaml(settings.registry_path)
    entry = registry.for_task(Task.VOICE_CLONING)[0]
    cloning_settings = load_inference_config().voice_cloning
    app.extensions["cloning_service"].cloner = XttsCloner(entry, cloning_settings, False)
    client = app.test_client()
    speaker_id = enroll(client, "Awa", cloning=True)

    response = clone(client, speaker_id)

    assert response.status_code == 503
    assert "Coqui Public Model License" in response.get_json()["message"]


def test_tts_routes_are_documented(client: FlaskClient) -> None:
    spec = client.get("/api/v1/openapi.json").get_json()
    assert {"get", "post"} <= set(spec["paths"][TTS_URL])
    assert "delete" in spec["paths"][f"{TTS_URL}/{{synthesis_id}}"]
