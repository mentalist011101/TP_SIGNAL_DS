"""Transcription avec le vrai modèle whisper-base (C17b), hors CI (extra [ml]).

Le modèle est téléchargé depuis Hugging Face (Systran/faster-whisper-base, révision figée du
registre), ou lu dans ECHOLENS_MODELS_DIR. La VAD est Silero, comme dans l'application.
"""

import numpy as np
import pytest

pytest.importorskip("torch")
pytest.importorskip("faster_whisper")
pytest.importorskip("silero_vad")

from echolens.config import CONFIG_DIR, AppSettings
from echolens.core.audio import load_preprocess_config
from echolens.core.data.class_labels import load_class_labels
from echolens.core.inference import load_inference_config
from echolens.core.models.registry import ModelRegistry, Profile, Task
from echolens.services.predictor import make_predictor
from echolens.services.results import ResultContext, build_results
from echolens.services.speech_detection import make_speech_detector
from echolens.services.whisper_transcriber import WhisperTranscriber

pytestmark = [pytest.mark.ml, pytest.mark.slow]

SAMPLE_RATE = 16_000


def test_whisper_base_model_loads() -> None:
    registry = ModelRegistry.from_yaml(CONFIG_DIR / "registry.yaml")
    entry = registry.model_for(Task.TRANSCRIPTION, Profile.REALTIME)
    assert entry is not None
    assert entry.id == "echolens-transcription-whisper-base"
    transcriber = WhisperTranscriber(load_inference_config().transcription, None)

    model = transcriber.load(entry)

    # Chargé une seule fois : le second appel rend le même objet.
    assert transcriber.load(entry) is model


def test_silence_gives_no_speech_with_the_real_models() -> None:
    settings = AppSettings(inference_backend="models")
    labels = load_class_labels()
    context = ResultContext(
        predictor=make_predictor(settings, labels),
        labels=labels,
        inference_config=load_inference_config(),
        speech_detector=make_speech_detector(load_preprocess_config().vad),
    )
    silence = np.zeros(5 * SAMPLE_RATE, dtype=np.float32)

    results = build_results(silence, ["transcription"], "realtime", context)
    result = results["transcription"]

    assert context.speech_detector.name == "silero"
    assert result["status"] == "no_speech"
    assert result["model_id"] == "echolens-transcription-whisper-base"
    assert result["text"] is None
