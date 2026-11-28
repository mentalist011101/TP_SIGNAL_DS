"""Export des résultats d'une analyse : GET /api/v1/analyses/{id}/export (EF-09, C26)."""

import csv
import io
import json
from collections import defaultdict
from datetime import UTC, datetime

import numpy as np
import pytest
import soundfile as sf
from flask import Flask
from flask.testing import FlaskClient

from echolens.services.analysis_service import AnalysisService
from echolens.services.export import CSV_COLUMNS
from echolens.services.results import build_results
from echolens.services.storage import AnalysisRecord, AnalysisStatus

ANALYSES_URL = "/api/v1/analyses"
SAMPLE_RATE = 16_000
ALL_TASKS = ["emotion", "sound_event", "transcription", "speaker"]
CREATED_AT = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)
UTF8_BOM = b"\xef\xbb\xbf"
PROBABILITY_TOLERANCE = 1e-6
MAX_PDF_BYTES = 2_000_000


def noisy_tone(seconds: float = 12.0) -> np.ndarray:
    """Sinusoïde de 440 Hz avec du bruit, mono 16 kHz float32."""
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    noise = np.random.default_rng(0).normal(0.0, 0.05, size=times.size)
    signal = 0.3 * np.sin(2 * np.pi * 440 * times) + noise
    return signal.astype(np.float32)


def add_analysis(app: Flask, analysis_id: str, status: AnalysisStatus) -> None:
    """Enregistre une analyse ; si elle est terminée, avec les résultats du faux prédicteur."""
    service: AnalysisService = app.extensions["analysis_service"]
    results = None
    duration_s = None
    if status == AnalysisStatus.DONE:
        results = build_results(noisy_tone(), ALL_TASKS, "quality", service.result_context)
        duration_s = 12.0
    record = AnalysisRecord(
        id=analysis_id,
        created_at=CREATED_AT,
        original_filename="Voix_dete.wav",
        status=status,
        duration_s=duration_s,
        tasks=ALL_TASKS,
        profile="quality",
        results=results,
    )
    with service.session_factory() as session:
        session.add(record)
        session.commit()


def export(client: FlaskClient, analysis_id: str, export_format: str) -> object:
    return client.get(f"{ANALYSES_URL}/{analysis_id}/export?format={export_format}")


def read_csv_rows(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """En-têtes et lignes du CSV exporté (le BOM est retiré par utf-8-sig)."""
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    columns = list(reader.fieldnames or [])
    return columns, rows


def probability_sums(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], float]:
    """Somme des probabilités pour chaque (tâche, scope, segment)."""
    sums: dict[tuple[str, str, str], float] = defaultdict(float)
    for row in rows:
        if row["probability"] == "":
            continue
        key = (row["task"], row["scope"], row["segment_index"])
        sums[key] += float(row["probability"])
    return sums


def test_json_export_is_the_detail(app: Flask, client: FlaskClient) -> None:
    add_analysis(app, "terminee", AnalysisStatus.DONE)

    response = export(client, "terminee", "json")

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    detail = client.get(f"{ANALYSES_URL}/terminee").get_json()
    exported = json.loads(response.data.decode("utf-8"))
    assert exported == detail
    # Indenté et UTF-8 : lisible tel quel, accents compris.
    assert b"\n  " in response.data


def test_csv_export_has_long_format(app: Flask, client: FlaskClient) -> None:
    add_analysis(app, "terminee", AnalysisStatus.DONE)

    response = export(client, "terminee", "csv")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.data.startswith(UTF8_BOM)
    columns, rows = read_csv_rows(response.data)
    assert columns == CSV_COLUMNS
    assert b"\r\n" not in response.data
    # Chaque groupe de probabilités (global ou segment) fait 1.
    sums = probability_sums(rows)
    assert ("sound_event", "global", "") in sums
    assert ("sound_event", "segment", "1") in sums
    for key, total in sums.items():
        assert total == pytest.approx(1.0, abs=PROBABILITY_TOLERANCE), key


def test_csv_has_one_row_for_an_unavailable_task(app: Flask, client: FlaskClient) -> None:
    # Le locuteur (EF-11) n'est pas encore branché : unavailable.
    add_analysis(app, "terminee", AnalysisStatus.DONE)

    response = export(client, "terminee", "csv")

    _, rows = read_csv_rows(response.data)
    speaker_rows = [row for row in rows if row["task"] == "speaker"]
    assert len(speaker_rows) == 1
    row = speaker_rows[0]
    assert row["label"] == "unavailable"
    assert row["analysis_id"] == "terminee"
    for column in CSV_COLUMNS:
        if column not in ("analysis_id", "task", "label"):
            assert row[column] == ""


def test_csv_rows_are_ordered_global_then_segments(app: Flask, client: FlaskClient) -> None:
    add_analysis(app, "terminee", AnalysisStatus.DONE)

    response = export(client, "terminee", "csv")

    _, rows = read_csv_rows(response.data)
    sound_rows = [row for row in rows if row["task"] == "sound_event"]
    first = sound_rows[0]
    assert first["scope"] == "global"
    assert first["rank"] == "1"
    assert first["segment_index"] == first["start_s"] == first["end_s"] == ""
    assert first["text"] == ""
    assert first["calibrated"] in ("true", "false")
    last = sound_rows[-1]
    assert last["scope"] == "segment"
    assert float(last["end_s"]) > float(last["start_s"])


def test_pdf_export_is_a_small_pdf(app: Flask, client: FlaskClient) -> None:
    add_analysis(app, "terminee", AnalysisStatus.DONE)

    response = export(client, "terminee", "pdf")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert 1_000 < len(response.data) < MAX_PDF_BYTES


@pytest.mark.parametrize("export_format", ["json", "csv", "pdf"])
def test_export_is_an_attachment_with_a_dated_name(
    app: Flask, client: FlaskClient, export_format: str
) -> None:
    add_analysis(app, "terminee", AnalysisStatus.DONE)

    response = export(client, "terminee", export_format)

    expected_name = f"echolens_Voix_dete_2026-11-20.{export_format}"
    disposition = response.headers["Content-Disposition"]
    assert disposition == f"attachment; filename={expected_name}"


def test_export_of_unknown_analysis_is_404(client: FlaskClient) -> None:
    response = export(client, "inconnue", "csv")

    assert response.status_code == 404
    assert "introuvable" in response.get_json()["message"]


def test_export_of_unfinished_analysis_is_409(app: Flask, client: FlaskClient) -> None:
    add_analysis(app, "en-attente", AnalysisStatus.PENDING)

    response = export(client, "en-attente", "pdf")

    assert response.status_code == 409
    message = response.get_json()["message"]
    assert "en attente" in message
    assert "terminée" in message


def test_unknown_export_format_is_422(app: Flask, client: FlaskClient) -> None:
    add_analysis(app, "terminee", AnalysisStatus.DONE)

    response = export(client, "terminee", "xls")

    assert response.status_code == 422
    assert "Format inconnu : « xls »" in response.get_json()["message"]


def test_missing_export_format_is_422(app: Flask, client: FlaskClient) -> None:
    add_analysis(app, "terminee", AnalysisStatus.DONE)

    response = client.get(f"{ANALYSES_URL}/terminee/export")

    assert response.status_code == 422
    assert "Choisissez un format" in response.get_json()["message"]


def test_export_route_is_documented(client: FlaskClient) -> None:
    spec = client.get("/api/v1/openapi.json").get_json()
    route = spec["paths"][f"{ANALYSES_URL}/{{analysis_id}}/export"]["get"]
    parameters = {parameter["name"]: parameter for parameter in route["parameters"]}
    assert parameters["format"]["schema"]["enum"] == ["json", "csv", "pdf"]
    assert {"200", "404", "409", "422"} <= set(route["responses"])


@pytest.mark.ffmpeg
def test_real_analysis_pdf_contains_the_spectrogram(client: FlaskClient) -> None:
    buffer = io.BytesIO()
    sf.write(buffer, noisy_tone(), SAMPLE_RATE, format="WAV")
    data = {"file": (io.BytesIO(buffer.getvalue()), "son.wav"), "tasks": ALL_TASKS}
    created = client.post(ANALYSES_URL, data=data, content_type="multipart/form-data").get_json()

    response = export(client, created["id"], "pdf")

    assert response.status_code == 200
    # Une image PNG intégrée se reconnaît à son objet /Image dans le PDF.
    assert b"/Image" in response.data
