"""Analyse de bout en bout avec les vrais modèles de production (C13), hors CI (extra [ml]).

Les modèles viennent du dossier ECHOLENS_MODELS_DIR, ou de Hugging Face si le registre donne
leurs dépôts. L'extrait est téléchargé depuis le dépôt public d'ESC-50 : des chants d'oiseaux
(classe 14, chirping_birds), du fold 1.
"""

import io
import os
import urllib.request
from pathlib import Path
from typing import Any

import pytest

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
