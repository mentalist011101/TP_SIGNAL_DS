"""Faux prédicteur et construction des résultats d'une analyse (C13), sans modèle."""

from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, text

from echolens.config import AppSettings
from echolens.core.audio import load_preprocess_config
from echolens.core.data.class_labels import load_class_labels
from echolens.core.inference import load_inference_config
from echolens.core.models.registry import Profile, Task
from echolens.services.predictor import DemoPredictor, class_counts
from echolens.services.results import (
    NO_SPEECH_MESSAGE,
    UNAVAILABLE_MESSAGE,
    ResultContext,
    build_results,
)
from echolens.services.storage import create_session_factory

SAMPLE_RATE = 16_000


@pytest.fixture
def context() -> ResultContext:
    labels = load_class_labels()
    return ResultContext(
        predictor=DemoPredictor(class_counts(labels)),
        labels=labels,
        inference_config=load_inference_config(),
        vad_config=load_preprocess_config().vad,
    )


def tone(seconds: float, seed: int = 0) -> np.ndarray:
    """Sinusoïde de 5 kHz avec un bruit faible : webrtcvad n'y voit aucune parole.

    Choisie après mesure : webrtcvad prend pour de la parole la plupart des sinusoïdes fortes
    sous 4 kHz et le bruit blanc d'amplitude 0,05 ; celle-ci est rejetée quelle que soit la
    graine du bruit.
    """
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    noise = np.random.default_rng(seed).normal(0.0, 0.005, size=times.size)
    signal = 0.3 * np.sin(2 * np.pi * 5_000 * times) + noise
    return signal.astype(np.float32)


def voiced_speech(seconds: float) -> np.ndarray:
    """Voyelles de synthèse (140 Hz et harmoniques, 4 syllabes par seconde) de 1 à 4 s, puis
    de 6 à 11,5 s : webrtcvad y trouve deux zones de parole."""
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    fundamental = 140 * (1 + 0.05 * np.sin(2 * np.pi * 0.7 * times))
    phase = 2 * np.pi * np.cumsum(fundamental) / SAMPLE_RATE
    voiced = np.zeros_like(times)
    for harmonic in range(1, 25):
        voiced += np.sin(harmonic * phase) / harmonic
    syllables = np.clip(np.sin(2 * np.pi * 4 * times), 0, None) ** 0.5
    is_speaking = ((times > 1.0) & (times < 4.0)) | ((times > 6.0) & (times < 11.5))
    noise = np.random.default_rng(0).normal(0.0, 0.003, size=times.size)
    signal = 0.2 * voiced * syllables * is_speaking + noise
    return signal.astype(np.float32)


def test_demo_predictor_is_deterministic_and_sums_to_one() -> None:
    predictor = DemoPredictor({Task.SOUND_EVENT: 50})
    windows = [tone(5.0, seed=1), tone(5.0, seed=2)]
    first = predictor.predict(Task.SOUND_EVENT, Profile.QUALITY, windows)
    second = predictor.predict(Task.SOUND_EVENT, Profile.QUALITY, windows)
    for left, right in zip(first, second, strict=True):
        np.testing.assert_array_equal(left, right)
        assert left.shape == (50,)
        assert left.sum() == pytest.approx(1.0)
    # Deux audios différents donnent des probabilités différentes.
    assert not np.allclose(first[0], first[1])


def test_demo_predictor_says_demo_and_not_calibrated() -> None:
    predictor = DemoPredictor({Task.EMOTION: 6})
    info = predictor.model_info(Task.EMOTION, Profile.QUALITY)
    assert (info.model_id, info.model_version, info.calibrated) == ("demo", "0", False)
    assert predictor.supports(Task.EMOTION, Profile.REALTIME)
    assert not predictor.supports(Task.TRANSCRIPTION, Profile.QUALITY)


def test_unknown_backend_is_refused() -> None:
    with pytest.raises(ValidationError):
        AppSettings(inference_backend="whisper")


def test_tone_gives_sound_events_but_no_speech(context: ResultContext) -> None:
    results = build_results(tone(12.0), ["sound_event", "emotion"], "quality", context)
    events = results["sound_event"]
    assert events["status"] == "done"
    assert len(events["probabilities"]) == 50
    assert sum(entry["probability"] for entry in events["probabilities"]) == pytest.approx(1.0)
    assert events["label"] == events["probabilities"][0]["label"]
    assert len(events["segments"]) == 4
    emotion = results["emotion"]
    assert emotion["status"] == "no_speech"
    assert emotion["message"] == NO_SPEECH_MESSAGE
    assert emotion["label"] is None
    assert emotion["probabilities"] == []
    assert emotion["segments"] == []


def pure_sine(seconds: float, frequency_hz: float) -> np.ndarray:
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    signal = 0.3 * np.sin(2 * np.pi * frequency_hz * times)
    return signal.astype(np.float32)


def white_noise(seconds: float) -> np.ndarray:
    generator = np.random.default_rng(42)
    signal = generator.normal(0.0, 0.05, size=int(seconds * SAMPLE_RATE))
    return signal.astype(np.float32)


# Limite connue de webrtcvad, conservé faute d'option qui tienne les deux critères de C24
# (D5) : sur Kaggle, 3 s de « parole » sur 3 s pour ces deux signaux, à toutes les
# agressivités. strict=True : si la VAD change et que le test passe, pytest le signale.
@pytest.mark.xfail(strict=True, reason="webrtcvad prend une sinusoïde pure pour de la parole")
def test_pure_sine_gives_no_speech(context: ResultContext) -> None:
    emotion = build_results(pure_sine(3.0, 1000.0), ["emotion"], "quality", context)["emotion"]
    assert emotion["status"] == "no_speech"


@pytest.mark.xfail(strict=True, reason="webrtcvad prend le bruit blanc pour de la parole")
def test_white_noise_gives_no_speech(context: ResultContext) -> None:
    emotion = build_results(white_noise(3.0), ["emotion"], "quality", context)["emotion"]
    assert emotion["status"] == "no_speech"


def test_voiced_speech_is_still_detected(context: ResultContext) -> None:
    emotion = build_results(voiced_speech(12.0), ["emotion"], "quality", context)["emotion"]
    assert emotion["status"] == "done"
    assert len(emotion["segments"]) >= 1


def test_emotion_global_is_the_duration_weighted_mean_of_segments(
    context: ResultContext,
) -> None:
    emotion = build_results(voiced_speech(12.0), ["emotion"], "quality", context)["emotion"]
    assert emotion["status"] == "done"
    segments = emotion["segments"]
    assert len(segments) >= 2
    for segment in segments:
        assert segment["end_s"] - segment["start_s"] <= 5.0 + 1e-9
    # Recalcul à la main : Σ durée × probabilité / Σ durée, classe par classe.
    weighted_sums: dict[str, float] = {}
    total_duration = 0.0
    for segment in segments:
        duration = segment["end_s"] - segment["start_s"]
        total_duration += duration
        for entry in segment["probabilities"]:
            previous = weighted_sums.get(entry["label"], 0.0)
            weighted_sums[entry["label"]] = previous + duration * entry["probability"]
    for entry in emotion["probabilities"]:
        expected = weighted_sums[entry["label"]] / total_duration
        assert entry["probability"] == pytest.approx(expected, abs=1e-3)


def test_tasks_not_plugged_in_are_unavailable(context: ResultContext) -> None:
    results = build_results(tone(3.0), ["transcription", "speaker"], "realtime", context)
    for task in ["transcription", "speaker"]:
        assert results[task]["status"] == "unavailable"
        assert results[task]["message"] == UNAVAILABLE_MESSAGE
        assert results[task]["model_id"] is None


def test_old_database_without_results_column_is_refused_clearly(tmp_path: Path) -> None:
    url = f"sqlite:///{tmp_path / 'ancienne.db'}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE analyses (id VARCHAR(36) PRIMARY KEY, created_at DATETIME, "
                "original_filename VARCHAR(255), status VARCHAR(16), error_message VARCHAR, "
                "duration_s FLOAT, tasks JSON, profile VARCHAR(16))"
            )
        )
    with pytest.raises(RuntimeError, match="colonnes manquantes results"):
        create_session_factory(url)
