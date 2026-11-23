"""Route GET /api/v1/models (EF-16) : le catalogue lu dans configs/registry.yaml."""

from flask.testing import FlaskClient

from echolens.config import CONFIG_DIR
from echolens.core.models.registry import ModelRegistry


def test_models_lists_every_registry_entry(client: FlaskClient) -> None:
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    registry = ModelRegistry.from_yaml(CONFIG_DIR / "registry.yaml")
    expected_ids = [entry.id for entry in registry.models]
    returned_ids = [model["id"] for model in response.get_json()]
    assert returned_ids == expected_ids


def test_models_give_metrics_calibration_and_link(client: FlaskClient) -> None:
    models = client.get("/api/v1/models").get_json()
    by_id = {model["id"]: model for model in models}
    crnn = by_id["echolens-sound-event-crnn"]
    assert crnn["family"] == "A"
    assert crnn["task"] == "sound_event"
    assert crnn["profiles"] == ["realtime"]
    assert crnn["f1_macro"] == 0.8266
    assert crnn["temperature"] == 0.786
    assert crnn["calibrated"] is True
    assert (
        crnn["huggingface_url"] == "https://huggingface.co/Mentalist0101/echolens-sound-event-crnn"
    )


def test_models_route_is_in_openapi(client: FlaskClient) -> None:
    spec = client.get("/api/v1/openapi.json").get_json()
    assert "/api/v1/models" in spec["paths"]
    assert "Model" in spec["components"]["schemas"]
