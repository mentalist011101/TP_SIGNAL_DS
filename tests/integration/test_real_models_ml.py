"""Analyse de bout en bout avec les vrais modèles de production (C13), hors CI (extra [ml]).

Les modèles viennent du dossier ECHOLENS_MODELS_DIR, ou de Hugging Face si le registre donne
leurs dépôts. L'extrait d'événement vient du dépôt public d'ESC-50 : des chants
d'oiseaux (classe 14, chirping_birds), du fold 1. L'émotion en temps réel est testée sur des
voyelles de synthèse.
"""

import io
import os
import urllib.request
from pathlib import Path
from typing import Any

import matplotlib.image
import numpy as np
import pytest
import soundfile as sf

pytest.importorskip("torch")
pytest.importorskip("transformers")

from echolens.api import create_app
from echolens.config import CONFIG_DIR, AppSettings
from echolens.core.models.registry import ModelRegistry

pytestmark = [pytest.mark.ml, pytest.mark.slow, pytest.mark.ffmpeg]

CLIP_URL = "https://github.com/karolpiczak/ESC-50/raw/master/audio/1-100038-A-14.wav"
EXPECTED_CLASS = "chirping_birds"


def models_dir() -> Path | None:
    value = os.environ.get("ECHOLENS_MODELS_DIR")
    if value:
        return Path(value)
    registry = ModelRegistry.from_yaml(CONFIG_DIR / "registry.yaml")
    published = all(entry.weights and entry.revision for entry in registry.models)
    if not published:
        pytest.skip("Modèles introuvables : définir ECHOLENS_MODELS_DIR ou publier les dépôts")
    return None


def analyse(client: Any, clip: bytes, profile: str) -> dict[str, Any]:
    data = {"file": (io.BytesIO(clip), "oiseaux.wav"), "tasks": ["sound_event"], "profile": profile}
    response = client.post("/api/v1/analyses", data=data, content_type="multipart/form-data")
    assert response.status_code == 202
    analysis: dict[str, Any] = response.get_json()
    return analysis


@pytest.mark.parametrize("profile", ["quality", "realtime"])
def test_real_models_recognise_an_esc50_clip(tmp_path: Path, profile: str) -> None:
    settings = AppSettings(
        data_dir=tmp_path,
        web_dist_dir=tmp_path / "dist",
        run_jobs_synchronously=True,
        inference_backend="models",
        models_dir=models_dir(),
    )
    client = create_app(settings, TESTING=True).test_client()
    with urllib.request.urlopen(CLIP_URL, timeout=60) as response:
        clip = response.read()
    analysis = analyse(client, clip, profile)
    assert analysis["status"] == "done", analysis["error_message"]
    events = analysis["results"]["sound_event"]
    assert events["status"] == "done"
    assert events["label"] == EXPECTED_CLASS
    assert events["calibrated"] is True
    assert events["model_id"].startswith("echolens-sound-event-")
    assert sum(entry["probability"] for entry in events["probabilities"]) == pytest.approx(1.0)


def voiced_speech_wav(seconds: float = 6.0) -> bytes:
    """Voyelles de synthèse (140 Hz et harmoniques, 4 syllabes par seconde) de 1 à 5 s : webrtcvad
    y trouve de la parole, donc l'émotion est bien calculée (et non « aucune parole »)."""
    sample_rate = 16_000
    times = np.arange(int(seconds * sample_rate)) / sample_rate
    fundamental = 140 * (1 + 0.05 * np.sin(2 * np.pi * 0.7 * times))
    phase = 2 * np.pi * np.cumsum(fundamental) / sample_rate
    voiced = np.zeros_like(times)
    for harmonic in range(1, 25):
        voiced += np.sin(harmonic * phase) / harmonic
    syllables = np.clip(np.sin(2 * np.pi * 4 * times), 0, None) ** 0.5
    is_speaking = (times > 1.0) & (times < 5.0)
    noise = np.random.default_rng(0).normal(0.0, 0.003, size=times.size)
    signal = 0.2 * voiced * syllables * is_speaking + noise
    buffer = io.BytesIO()
    sf.write(buffer, signal.astype(np.float32), sample_rate, format="WAV")
    return buffer.getvalue()


def test_realtime_profile_gives_a_calibrated_emotion(tmp_path: Path) -> None:
    settings = AppSettings(
        data_dir=tmp_path,
        web_dist_dir=tmp_path / "dist",
        run_jobs_synchronously=True,
        inference_backend="models",
        models_dir=models_dir(),
    )
    client = create_app(settings, TESTING=True).test_client()
    data = {
        "file": (io.BytesIO(voiced_speech_wav()), "voix.wav"),
        "tasks": ["emotion"],
        "profile": "realtime",
    }
    response = client.post("/api/v1/analyses", data=data, content_type="multipart/form-data")
    assert response.status_code == 202
    analysis = response.get_json()
    assert analysis["status"] == "done", analysis["error_message"]
    emotion = analysis["results"]["emotion"]
    assert emotion["status"] == "done"
    assert emotion["calibrated"] is True
    # Le modèle temps réel est un réseau de la famille A, pas la tête whisper-base (qualité).
    assert emotion["model_id"] in ("echolens-emotion-cnn", "echolens-emotion-crnn")
    assert emotion["label"] in ["neutral", "happy", "sad", "angry", "fear", "disgust"]
    assert sum(entry["probability"] for entry in emotion["probabilities"]) == pytest.approx(1.0)


def test_realtime_analysis_has_a_grad_cam_map(tmp_path: Path) -> None:
    # C14 (E7, EF-13) : la carte du CRNN a exactement la taille de l'image du spectrogramme.
    settings = AppSettings(
        data_dir=tmp_path,
        web_dist_dir=tmp_path / "dist",
        run_jobs_synchronously=True,
        inference_backend="models",
        models_dir=models_dir(),
    )
    client = create_app(settings, TESTING=True).test_client()
    with urllib.request.urlopen(CLIP_URL, timeout=60) as response:
        clip = response.read()
    analysis = analyse(client, clip, "realtime")
    assert analysis["status"] == "done", analysis["error_message"]

    response = client.get(f"/api/v1/analyses/{analysis['id']}/gradcam?task=sound_event")

    assert response.status_code == 200
    assert response.mimetype == "image/png"
    grad_map = matplotlib.image.imread(io.BytesIO(response.data))
    spectrogram = matplotlib.image.imread(io.BytesIO(client.get(analysis["spectrogram_url"]).data))
    assert grad_map.shape[:2] == spectrogram.shape[:2]
