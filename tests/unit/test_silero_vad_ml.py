"""Silero, VAD de production (D5, C24) : tests avec torch (marqueur ml, hors CI).

Les mêmes signaux que les tests en échec attendu de webrtcvad (test_results.py) : ici la
sinusoïde pure et le bruit blanc donnent bien no_speech, et la parole de synthèse reste
détectée.
"""

import logging
import socket
import subprocess
import sys

import numpy as np
import pytest

from echolens.core.audio import load_preprocess_config
from echolens.core.data.class_labels import load_class_labels
from echolens.core.inference import load_inference_config
from echolens.services.predictor import DemoPredictor, class_counts
from echolens.services.results import ResultContext, build_results
from echolens.services.speech_detection import make_speech_detector

pytest.importorskip("torch")
pytest.importorskip("silero_vad")

from echolens.services.silero_detector import SileroDetector

pytestmark = pytest.mark.ml

SAMPLE_RATE = 16_000


@pytest.fixture(scope="module")
def silero() -> SileroDetector:
    return SileroDetector(load_preprocess_config().vad)


@pytest.fixture
def context(silero: SileroDetector) -> ResultContext:
    labels = load_class_labels()
    return ResultContext(
        predictor=DemoPredictor(class_counts(labels)),
        labels=labels,
        inference_config=load_inference_config(),
        speech_detector=silero,
    )


def pure_sine(seconds: float, frequency_hz: float) -> np.ndarray:
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    signal = 0.3 * np.sin(2 * np.pi * frequency_hz * times)
    return signal.astype(np.float32)


def white_noise(seconds: float) -> np.ndarray:
    generator = np.random.default_rng(42)
    signal = generator.normal(0.0, 0.05, size=int(seconds * SAMPLE_RATE))
    return signal.astype(np.float32)


def voice_between_silences() -> np.ndarray:
    # Voix de synthèse de 1,5 s (de 1,0 à 2,5 s) : fondamentale de 150 Hz et ses harmoniques
    # (amplitude 1/k), modulée à 4 Hz, le rythme des syllabes ; 1 s de silence de chaque côté.
    times = np.arange(int(1.5 * SAMPLE_RATE)) / SAMPLE_RATE
    tone = np.zeros_like(times)
    for harmonic in range(1, 11):
        tone += np.sin(2 * np.pi * 150 * harmonic * times) / harmonic
    envelope = 0.5 * (1 - np.cos(2 * np.pi * 4 * times))
    voice = tone * envelope
    voice = 0.3 * voice / np.max(np.abs(voice))
    silence = np.zeros(SAMPLE_RATE)
    signal = np.concatenate([silence, voice, silence])
    return signal.astype(np.float32)


@pytest.mark.parametrize("frequency_hz", [440.0, 1000.0, 3000.0])
def test_pure_sine_gives_no_speech(context: ResultContext, frequency_hz: float) -> None:
    signal = pure_sine(3.0, frequency_hz)
    emotion = build_results(signal, ["emotion"], "quality", context)["emotion"]
    assert emotion["status"] == "no_speech"


def test_white_noise_gives_no_speech(context: ResultContext) -> None:
    emotion = build_results(white_noise(3.0), ["emotion"], "quality", context)["emotion"]
    assert emotion["status"] == "no_speech"


def test_synthetic_voice_is_still_detected(context: ResultContext) -> None:
    signal = voice_between_silences()
    emotion = build_results(signal, ["emotion"], "quality", context)["emotion"]
    assert emotion["status"] == "done"
    segments = emotion["segments"]
    assert len(segments) >= 1
    # La voix dure de 1,0 à 2,5 s : le segment trouvé doit être dedans, à la marge près.
    assert segments[0]["start_s"] >= 0.8
    assert segments[-1]["end_s"] <= 2.7


def test_silero_loads_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    # Toute connexion réseau échoue : le modèle doit venir du paquet installé (Docker, démo).
    def refuse_connection(*args: object, **kwargs: object) -> None:
        raise OSError("réseau coupé pour le test")

    monkeypatch.setattr(socket.socket, "connect", refuse_connection)
    detector = SileroDetector(load_preprocess_config().vad)
    silence = np.zeros(SAMPLE_RATE, dtype=np.float32)
    assert detector.detect(silence) == []


def test_with_torch_silero_is_chosen_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="echolens"):
        detector = make_speech_detector(load_preprocess_config().vad)
    assert detector.name == "silero"
    assert "VAD : Silero (seuil 0.40, fin 0.25)" in caplog.text


# Script lancé dans un nouveau processus : l'import de silero-vad n'y a pas encore eu lieu.
THREADS_SCRIPT = """
import torch
torch.set_num_threads(2)
from echolens.core.audio import load_preprocess_config
from echolens.services.silero_detector import SileroDetector
SileroDetector(load_preprocess_config().vad)
print(torch.get_num_threads())
"""


def test_loading_silero_keeps_torch_threads() -> None:
    # Le paquet silero-vad met torch sur un seul fil dès son import : le chargement doit
    # rétablir le réglage d'avant, sinon les têtes Whisper vont presque deux fois moins vite.
    completed = subprocess.run(
        [sys.executable, "-c", THREADS_SCRIPT], capture_output=True, text=True, check=True
    )
    last_line = completed.stdout.strip().splitlines()[-1]
    assert last_line == "2"
