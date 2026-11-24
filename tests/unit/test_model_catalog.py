"""Catalogue des modèles (EF-16) : mise en forme du registre pour l'interface."""

from pathlib import Path

from echolens.services.model_catalog import huggingface_url, list_models

REGISTRY_YAML = """
models:
  - id: tete-b
    task: emotion
    family: B
    profiles: [quality]
    version: 1.0.0
    weights: hf://equipe/tete-b
    revision: abc
    metrics: {f1_macro: 0.75, accuracy: 0.74}
    temperature: 1.1
    description: Tête calibrée
  - id: modele-local
    task: sound_event
    family: A
    profiles: [realtime]
    weights: ""
"""


def test_huggingface_url_from_hf_weights() -> None:
    assert huggingface_url("hf://equipe/tete-b") == "https://huggingface.co/equipe/tete-b"


def test_huggingface_url_is_none_for_other_weights() -> None:
    assert huggingface_url("") is None
    assert huggingface_url("s3://seau/poids") is None


def test_list_models_reads_registry_in_order(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text(REGISTRY_YAML, encoding="utf-8")
    models = list_models(path)
    assert [model["id"] for model in models] == ["tete-b", "modele-local"]
    calibrated = models[0]
    assert calibrated["f1_macro"] == 0.75
    assert calibrated["temperature"] == 1.1
    assert calibrated["calibrated"] is True
    assert calibrated["huggingface_url"] == "https://huggingface.co/equipe/tete-b"


def test_list_models_without_metrics_or_calibration(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text(REGISTRY_YAML, encoding="utf-8")
    uncalibrated = list_models(path)[1]
    assert uncalibrated["f1_macro"] is None
    assert uncalibrated["temperature"] is None
    assert uncalibrated["calibrated"] is False
    assert uncalibrated["huggingface_url"] is None
    assert uncalibrated["revision"] is None
