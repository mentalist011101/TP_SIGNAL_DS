"""Choix automatique de la VAD (D5, C24), sans torch : webrtcvad en secours."""

import importlib.util
import logging

import numpy as np
import pytest

from echolens.core.audio.preprocess_config import load_preprocess_config
from echolens.services import speech_detection
from echolens.services.speech_detection import (
    WebrtcvadDetector,
    make_speech_detector,
    silero_is_installed,
)

SAMPLE_RATE = 16_000


def pretend_torch_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    real_find_spec = importlib.util.find_spec

    def find_spec_without_torch(name: str) -> object:
        if name == "torch":
            return None
        return real_find_spec(name)

    monkeypatch.setattr(speech_detection.importlib.util, "find_spec", find_spec_without_torch)


def test_without_torch_webrtcvad_is_chosen_and_logged(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    pretend_torch_is_missing(monkeypatch)
    assert silero_is_installed() is False
    with caplog.at_level(logging.INFO, logger="echolens"):
        detector = make_speech_detector(load_preprocess_config().vad)
    assert isinstance(detector, WebrtcvadDetector)
    assert detector.name == "webrtcvad"
    assert "webrtcvad (secours)" in caplog.text


def test_webrtcvad_detector_finds_nothing_in_silence() -> None:
    detector = WebrtcvadDetector(load_preprocess_config().vad)
    assert detector.detect(np.zeros(2 * SAMPLE_RATE, dtype=np.float32)) == []
