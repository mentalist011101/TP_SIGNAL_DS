"""Résultat de la tâche speaker (EF-11) : un nom ou « Inconnu » par morceau, avec le faux
prédicteur et une VAD de test."""

import numpy as np
import pytest

from echolens.core.audio.segment import Segment
from echolens.core.data.class_labels import load_class_labels
from echolens.core.inference import FloatArray, load_inference_config
from echolens.core.models.registry import Profile
from echolens.core.speaker_id import voice_print
from echolens.services.predictor import DemoPredictor, class_counts
from echolens.services.results import (
    NO_VOICE_MESSAGE,
    UNKNOWN_SPEAKER_FR,
    EnrolledVoice,
    ResultContext,
    build_results,
)

SAMPLE_RATE = 16_000


class FixedDetector:
    """VAD de test : renvoie toujours les mêmes zones de parole."""

    name = "fixe"

    def __init__(self, segments: list[Segment]) -> None:
        self.segments = segments

    def detect(self, signal: FloatArray) -> list[Segment]:
        return self.segments


def voiced(seconds: float, fundamental_hz: float) -> np.ndarray:
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    signal = np.zeros_like(times)
    for harmonic in range(1, 15):
        signal += np.sin(2 * np.pi * fundamental_hz * harmonic * times) / harmonic
    return (0.1 * signal).astype(np.float32)


def tone(seconds: float, frequency_hz: float) -> np.ndarray:
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    return (0.3 * np.sin(2 * np.pi * frequency_hz * times)).astype(np.float32)


def context(segments: list[Segment]) -> ResultContext:
    labels = load_class_labels()
    return ResultContext(
        predictor=DemoPredictor(class_counts(labels)),
        labels=labels,
        inference_config=load_inference_config(),
        speech_detector=FixedDetector(segments),
    )


def demo_voice(signal: np.ndarray, speaker_id: str, name: str) -> EnrolledVoice:
    vectors = DemoPredictor({}).embed_voices(Profile.QUALITY, [signal])
    return EnrolledVoice(
        speaker_id=speaker_id, name=name, voice=voice_print(vectors), model_id="demo"
    )


def test_each_piece_gets_a_name_or_unknown() -> None:
    # 0 à 3 s : la « voix » d'Awa ; 3 à 4 s : un son pur, loin de toute voix enregistrée.
    signal = np.concatenate([voiced(3.0, 120.0), tone(1.0, 440.0)])
    segments = [Segment(start_s=0.0, end_s=3.0), Segment(start_s=3.0, end_s=4.0)]
    voices = [demo_voice(voiced(3.0, 120.0), "id-awa", "Awa")]

    result = build_results(signal, ["speaker"], "quality", context(segments), voices)["speaker"]

    assert result["status"] == "done"
    names = [segment["label_fr"] for segment in result["segments"]]
    assert names == ["Awa", UNKNOWN_SPEAKER_FR]
    assert result["segments"][0]["label"] == "id-awa"
    assert result["segments"][0]["score"] == pytest.approx(1.0, abs=1e-6)
    assert result["segments"][1]["score"] < load_inference_config().speaker.threshold
    # Global : Awa parle 3 s sur 4.
    assert (result["label"], result["label_fr"]) == ("id-awa", "Awa")
    shares = [(entry["label_fr"], entry["probability"]) for entry in result["probabilities"]]
    assert shares == [("Awa", pytest.approx(0.75)), (UNKNOWN_SPEAKER_FR, pytest.approx(0.25))]
    assert result["calibrated"] is False


def test_voices_of_another_model_are_ignored() -> None:
    segments = [Segment(start_s=0.0, end_s=3.0)]
    other_model = EnrolledVoice(
        speaker_id="id-awa", name="Awa", voice=np.ones(192), model_id="ecapa-voxceleb"
    )

    result = build_results(
        voiced(3.0, 120.0), ["speaker"], "quality", context(segments), [other_model]
    )["speaker"]

    assert result["status"] == "unavailable"
    assert result["message"] == NO_VOICE_MESSAGE


def test_pieces_shorter_than_one_second_are_not_named() -> None:
    segments = [Segment(start_s=0.0, end_s=0.8)]
    voices = [demo_voice(voiced(3.0, 120.0), "id-awa", "Awa")]

    result = build_results(voiced(3.0, 120.0), ["speaker"], "quality", context(segments), voices)

    assert result["speaker"]["status"] == "no_speech"
