"""Fixtures communes : signaux de synthèse et application Flask de test."""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from flask import Flask
from flask.testing import FlaskClient

from echolens.api import create_app
from echolens.config import AppSettings

FFMPEG_SKIP_REASON = "ffmpeg absent de cette machine : test sauté (la CI l'installe)"


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Saute les tests marqués « ffmpeg » quand ffmpeg n'est pas installé (D1)."""
    if shutil.which("ffmpeg") is not None:
        return
    skip_marker = pytest.mark.skip(reason=FFMPEG_SKIP_REASON)
    for item in items:
        if "ffmpeg" in item.keywords:
            item.add_marker(skip_marker)


@pytest.fixture
def sine_wave() -> np.ndarray:
    """Sinusoïde de 440 Hz, 1 s à 16 kHz, amplitude 0,5."""
    t = np.arange(16_000) / 16_000
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


@pytest.fixture
def stereo_wav_44k(tmp_path: Path) -> Path:
    """Fichier WAV stéréo à 44,1 kHz de 2 s, pour tester le décodage et le rééchantillonnage."""
    t = np.arange(2 * 44_100) / 44_100
    left = 0.3 * np.sin(2 * np.pi * 440 * t)
    right = 0.3 * np.sin(2 * np.pi * 880 * t)
    path = tmp_path / "stereo.wav"
    sf.write(path, np.stack([left, right], axis=1), 44_100)
    return path


@pytest.fixture
def app(tmp_path: Path) -> Iterator[Flask]:
    settings = AppSettings(
        data_dir=tmp_path, web_dist_dir=tmp_path / "dist", run_jobs_synchronously=True
    )
    yield create_app(settings, TESTING=True)


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()
