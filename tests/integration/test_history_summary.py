"""Historique résumé : GET /api/v1/analyses ne renvoie que le premier choix de chaque tâche.

Le résumé est lu dans la table analysis_summaries ; la colonne results n'est jamais lue.
"""

import io
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import soundfile as sf
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import Engine, create_engine, event, func, select, text

from echolens.api import create_app
from echolens.config import AppSettings
from echolens.core.audio.segment import Segment
from echolens.core.inference import (
    duration_weighted_mean,
    emotion_windows,
    mean_probabilities,
    sound_event_windows,
)
from echolens.services.analysis_service import AnalysisService
from echolens.services.predictor import ModelInfo
from echolens.services.results import (
    ResultContext,
    done_result,
    summarize_results,
    unavailable_result,
)
from echolens.services.storage import AnalysisRecord, AnalysisStatus, AnalysisSummaryRecord

ANALYSES_URL = "/api/v1/analyses"
SAMPLE_RATE = 16_000
HISTORY_SIZE = 100
LONGEST_AUDIO_S = 300.0
MAX_BYTES_PER_ANALYSIS = 2_000
# Clés du résultat complet qui ne doivent jamais apparaître dans l'historique.
DETAIL_ONLY_KEYS = ["segments", "probabilities", "spectrogram", "spectrogram_url", "audio_url"]


def noisy_tone_wav(seconds: float = 12.0) -> bytes:
    """Sinusoïde de 440 Hz avec du bruit, en WAV 16 kHz."""
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    noise = np.random.default_rng(0).normal(0.0, 0.05, size=times.size)
    signal = 0.3 * np.sin(2 * np.pi * 440 * times) + noise
    buffer = io.BytesIO()
    sf.write(buffer, signal.astype(np.float32), SAMPLE_RATE, format="WAV")
    return buffer.getvalue()


def post_tone(client: FlaskClient, tasks: list[str]) -> None:
    data = {"file": (io.BytesIO(noisy_tone_wav()), "son.wav"), "tasks": tasks, "profile": "quality"}
    client.post(ANALYSES_URL, data=data, content_type="multipart/form-data")


def all_keys(value: Any) -> set[str]:
    """Toutes les clés d'un JSON, à n'importe quelle profondeur."""
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            keys.update(all_keys(child))
    if isinstance(value, list):
        for child in value:
            keys.update(all_keys(child))
    return keys


def full_results(context: ResultContext, duration_s: float) -> dict[str, Any]:
    """Résultats complets d'un audio de duration_s, au format stocké en base (C13).

    Probabilités tirées au hasard : seule la taille compte ici. Fenêtres des événements tous
    les 2,5 s avec 50 classes, et parole sur tout l'audio pour les émotions : le pire cas.
    """
    rng = np.random.default_rng(0)
    info = ModelInfo(model_id="demo", model_version="0.0.0", calibrated=False)
    # Étape 1 : événements sonores, une liste de 50 probabilités par fenêtre.
    windows = sound_event_windows(duration_s, context.inference_config)
    window_probabilities = [rng.dirichlet(np.ones(50)) for _ in windows]
    overall = mean_probabilities(window_probabilities)
    classes = context.labels.esc50_classes
    sound_event = done_result(windows, window_probabilities, overall, classes, info)
    # Étape 2 : émotions, un morceau de 5 s au plus sur toute la durée.
    speech = [Segment(start_s=0.0, end_s=duration_s)]
    chunks = emotion_windows(speech, context.inference_config)
    chunk_probabilities = [rng.dirichlet(np.ones(6)) for _ in chunks]
    durations_s = [chunk.duration_s for chunk in chunks]
    overall = duration_weighted_mean(chunk_probabilities, durations_s)
    emotion = done_result(chunks, chunk_probabilities, overall, context.labels.emotions, info)
    return {
        "emotion": emotion,
        "sound_event": sound_event,
        "transcription": unavailable_result(),
        "speaker": unavailable_result(),
    }


def done_record(analysis_id: str, results: dict[str, Any]) -> AnalysisRecord:
    """Analyse terminée de 5 min, avec ses résultats complets et sans résumé."""
    return AnalysisRecord(
        id=analysis_id,
        original_filename=f"{analysis_id}.wav",
        status=AnalysisStatus.DONE,
        duration_s=LONGEST_AUDIO_S,
        tasks=list(results),
        profile="quality",
        results=results,
    )


def add_long_analyses(app: Flask, count: int) -> None:
    """Enregistre count analyses terminées de 5 min avec leur résumé, les quatre tâches."""
    service: AnalysisService = app.extensions["analysis_service"]
    results = full_results(service.result_context, LONGEST_AUDIO_S)
    summary = summarize_results(results)
    with service.session_factory() as session:
        for index in range(count):
            analysis_id = f"analyse-{index}"
            record = done_record(analysis_id, results)
            record.summary_row = AnalysisSummaryRecord(analysis_id=analysis_id, summary=summary)
            session.add(record)
        session.commit()


def history_by_id(client: FlaskClient) -> dict[str, dict[str, Any]]:
    """Analyses de GET /api/v1/analyses, rangées par identifiant."""
    history = client.get(f"{ANALYSES_URL}?limit={HISTORY_SIZE}").get_json()
    by_id = {}
    for analysis in history:
        by_id[analysis["id"]] = analysis
    return by_id


def assert_summary_matches_detail(client: FlaskClient, analysis: dict[str, Any]) -> None:
    """Le résumé de l'historique reprend le premier choix du détail, tâche par tâche."""
    detail = client.get(f"{ANALYSES_URL}/{analysis['id']}").get_json()
    summary_results = analysis["results"]
    detail_results = detail["results"]
    assert set(summary_results) == set(detail_results)
    for task, full in detail_results.items():
        summary = summary_results[task]
        # Premier élément de la liste triée, ou rien si la tâche n'a pas de résultat.
        first_probability = None
        if full["probabilities"]:
            first_probability = full["probabilities"][0]["probability"]
        assert summary["status"] == full["status"]
        assert summary["label"] == full["label"]
        assert summary["label_fr"] == full["label_fr"]
        assert summary["probability"] == first_probability
        assert summary["model_id"] == full["model_id"]


def engine_of(app: Flask) -> Engine:
    service: AnalysisService = app.extensions["analysis_service"]
    engine: Engine = service.session_factory.kw["bind"]
    return engine


def record_sql_statements(engine: Engine) -> list[str]:
    """Liste remplie, à partir de maintenant, avec chaque requête SQL envoyée à la base, et
    « COMMIT » à chaque validation de transaction."""
    statements: list[str] = []

    def remember_statement(connection: Any, cursor: Any, statement: str, *args: Any) -> None:
        statements.append(statement)

    def remember_commit(connection: Any) -> None:
        statements.append("COMMIT")

    event.listen(engine, "before_cursor_execute", remember_statement)
    event.listen(engine, "commit", remember_commit)
    return statements


def summary_row_count(engine: Engine) -> int:
    count_query = select(func.count()).select_from(AnalysisSummaryRecord)
    with engine.connect() as connection:
        count: int = connection.scalar(count_query)
    return count


def create_old_database(database_path: Path, results: dict[str, Any]) -> None:
    """Base d'avant la table analysis_summaries, avec une analyse terminée et une en cours."""
    engine = create_engine(f"sqlite:///{database_path}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE analyses (id VARCHAR(36) PRIMARY KEY, created_at DATETIME, "
                "original_filename VARCHAR(255), status VARCHAR(16), error_message VARCHAR, "
                "duration_s FLOAT, tasks JSON, profile VARCHAR(16), results JSON)"
            )
        )
        insert = text(
            "INSERT INTO analyses VALUES (:id, '2026-11-24 10:00:00', 'son.wav', :status, "
            "NULL, 30.0, :tasks, 'quality', :results)"
        )
        tasks = json.dumps(list(results))
        done = {"id": "terminee", "status": "done", "tasks": tasks, "results": json.dumps(results)}
        connection.execute(insert, done)
        pending = {"id": "en-cours", "status": "pending", "tasks": tasks, "results": None}
        connection.execute(insert, pending)
    engine.dispose()


@pytest.mark.ffmpeg
def test_history_has_first_choice_but_no_segments(client: FlaskClient) -> None:
    post_tone(client, ["sound_event", "emotion", "transcription"])

    history = client.get(ANALYSES_URL).get_json()

    for key in DETAIL_ONLY_KEYS:
        assert key not in all_keys(history)
    assert_summary_matches_detail(client, history[0])
    assert history[0]["results"]["transcription"]["probability"] is None


@pytest.mark.ffmpeg
def test_results_and_summary_are_written_in_one_transaction(
    app: Flask, client: FlaskClient
) -> None:
    statements = record_sql_statements(engine_of(app))

    post_tone(client, ["sound_event"])

    # Repère la mise à jour de results et l'insertion du résumé dans la suite des requêtes.
    results_update = -1
    summary_insert = -1
    for index, statement in enumerate(statements):
        if statement.startswith("UPDATE analyses") and "results=" in statement:
            results_update = index
        if statement.startswith("INSERT INTO analysis_summaries"):
            summary_insert = index
    assert results_update >= 0
    assert summary_insert >= 0
    # Aucune validation entre les deux : elles font partie de la même transaction.
    first = min(results_update, summary_insert)
    last = max(results_update, summary_insert)
    assert "COMMIT" not in statements[first:last]


def test_history_of_long_analyses_stays_under_2_kb_each(app: Flask, client: FlaskClient) -> None:
    add_long_analyses(app, HISTORY_SIZE)

    response = client.get(f"{ANALYSES_URL}?limit={HISTORY_SIZE}")

    analyses = response.get_json()
    assert len(analyses) == HISTORY_SIZE
    assert "segments" not in all_keys(analyses)
    for analysis in analyses:
        size = len(json.dumps(analysis, ensure_ascii=False).encode("utf-8"))
        assert size < MAX_BYTES_PER_ANALYSIS
    assert len(response.data) < HISTORY_SIZE * MAX_BYTES_PER_ANALYSIS


def test_detail_still_has_segments(app: Flask, client: FlaskClient) -> None:
    add_long_analyses(app, 1)

    detail = client.get(f"{ANALYSES_URL}/analyse-0").get_json()

    sound_event = detail["results"]["sound_event"]
    assert len(sound_event["segments"]) > 0
    assert len(sound_event["segments"][0]["probabilities"]) == 50
    assert detail["spectrogram"] is not None


def test_summary_schema_is_documented_in_openapi(client: FlaskClient) -> None:
    spec = client.get("/api/v1/openapi.json").get_json()
    schemas = spec["components"]["schemas"]
    list_response = spec["paths"][ANALYSES_URL]["get"]["responses"]["200"]
    list_schema = list_response["content"]["application/json"]["schema"]
    assert list_schema["items"]["$ref"].endswith("/AnalysisSummary")
    summary_fields = set(schemas["TaskSummary"]["properties"])
    assert "probability" in summary_fields
    assert "segments" not in summary_fields


def test_history_query_does_not_read_results(app: Flask, client: FlaskClient) -> None:
    add_long_analyses(app, 3)
    statements = record_sql_statements(engine_of(app))

    client.get(ANALYSES_URL)

    selects = [statement for statement in statements if statement.startswith("SELECT")]
    assert len(selects) == 1
    assert "LEFT OUTER JOIN analysis_summaries" in selects[0]
    assert "analysis_summaries.summary" in selects[0]
    assert "analyses.results" not in selects[0]


def test_delete_removes_the_summary_row(app: Flask, client: FlaskClient) -> None:
    add_long_analyses(app, 1)
    assert summary_row_count(engine_of(app)) == 1

    response = client.delete(f"{ANALYSES_URL}/analyse-0")

    assert response.status_code == 204
    assert summary_row_count(engine_of(app)) == 0


def test_old_database_is_filled_at_startup(app: Flask, tmp_path: Path) -> None:
    # Étape 1 : une base d'avant la table analysis_summaries, avec une analyse terminée et
    # une analyse en cours.
    service: AnalysisService = app.extensions["analysis_service"]
    results = full_results(service.result_context, 30.0)
    old_dir = tmp_path / "ancienne"
    old_dir.mkdir()
    create_old_database(old_dir / "echolens.db", results)

    # Étape 2 : démarrage de la nouvelle version sur cette base.
    settings = AppSettings(data_dir=old_dir, web_dist_dir=old_dir / "dist")
    upgraded_app = create_app(settings, TESTING=True)
    client = upgraded_app.test_client()

    # Étape 3 : l'analyse terminée a son résumé, l'analyse en cours n'en a pas.
    assert summary_row_count(engine_of(upgraded_app)) == 1
    history = history_by_id(client)
    assert_summary_matches_detail(client, history["terminee"])
    assert history["en-cours"]["results"] is None


def test_half_filled_database_only_completes_missing_summaries(app: Flask, tmp_path: Path) -> None:
    # Étape 1 : deux analyses terminées ; seule la seconde a déjà un résumé, volontairement
    # vide, pour voir s'il est réécrit.
    service: AnalysisService = app.extensions["analysis_service"]
    results = full_results(service.result_context, 30.0)
    with service.session_factory() as session:
        session.add(done_record("sans-resume", results))
        with_summary = done_record("avec-resume", results)
        with_summary.summary_row = AnalysisSummaryRecord(analysis_id="avec-resume", summary={})
        session.add(with_summary)
        session.commit()

    # Étape 2 : redémarrage sur la même base.
    settings = AppSettings(data_dir=tmp_path, web_dist_dir=tmp_path / "dist")
    restarted_app = create_app(settings, TESTING=True)
    client = restarted_app.test_client()

    # Étape 3 : seul le résumé manquant est calculé, l'autre n'est pas touché.
    assert summary_row_count(engine_of(restarted_app)) == 2
    history = history_by_id(client)
    assert_summary_matches_detail(client, history["sans-resume"])
    assert history["avec-resume"]["results"] == {}
