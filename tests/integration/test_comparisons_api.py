"""Route GET /api/v1/comparisons : les tableaux de la page Comparer, lus dans training/results."""

from flask.testing import FlaskClient


def test_comparisons_give_both_classification_tasks(client: FlaskClient) -> None:
    response = client.get("/api/v1/comparisons")
    assert response.status_code == 200
    body = response.get_json()
    tasks = [table["task"] for table in body["classification"]]
    assert tasks == ["sound_event", "emotion"]


def test_comparisons_read_the_real_esc50_results(client: FlaskClient) -> None:
    body = client.get("/api/v1/comparisons").get_json()
    sound_event = body["classification"][0]
    by_model = {row["model"]: row for row in sound_event["models"]}
    # Valeurs de training/results/esc50_mfcc_svm.json et esc50_family_a_crnn.json.
    assert round(by_model["mfcc_svm"]["f1_macro_mean"], 4) == 0.4029
    assert round(by_model["crnn"]["f1_macro_mean"], 4) == 0.8266
    assert by_model["crnn"]["family"] == "A"
    assert len(sound_event["tests"]) > 0


def test_comparisons_give_transcription_and_latency(client: FlaskClient) -> None:
    body = client.get("/api/v1/comparisons").get_json()
    models = {row["model"] for row in body["transcription"]}
    assert models == {"Whisper base", "Whisper small"}
    realtime = [row["model"] for row in body["latency"] if row["realtime"]]
    assert "echolens-sound-event-crnn" in realtime


def test_comparisons_route_is_in_openapi(client: FlaskClient) -> None:
    spec = client.get("/api/v1/openapi.json").get_json()
    assert "/api/v1/comparisons" in spec["paths"]
    assert "Comparisons" in spec["components"]["schemas"]
