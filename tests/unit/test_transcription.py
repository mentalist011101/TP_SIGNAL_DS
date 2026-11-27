"""Transcription dans l'application (EF-10, C17b), avec un faux transcripteur, sans modèle."""

import numpy as np
import pytest

from echolens.config import CONFIG_DIR, load_yaml
from echolens.core.audio.segment import Segment
from echolens.core.data.class_labels import load_class_labels
from echolens.core.inference import (
    FloatArray,
    ProbabilityArray,
    load_inference_config,
    transcription_windows,
)
from echolens.core.models.registry import ModelRegistry, Profile, Task
from echolens.services.predictor import DemoPredictor, ModelInfo, class_counts
from echolens.services.results import (
    NO_SPEECH_MESSAGE,
    ResultContext,
    build_results,
    join_texts,
)

SAMPLE_RATE = 16_000
MAX_WINDOW_S = 30.0
# Réglages du décodage qui doivent être les mêmes dans l'application et dans l'évaluation C17a.
DECODING_KEYS = ["language", "beam_size", "vad_filter", "condition_on_previous_text", "temperature"]


class FixedDetector:
    """VAD de test : renvoie toujours les mêmes zones de parole, et compte ses appels."""

    name = "fixe"

    def __init__(self, segments: list[Segment]) -> None:
        self.segments = segments
        self.call_count = 0

    def detect(self, signal: FloatArray) -> list[Segment]:
        self.call_count += 1
        return self.segments


class FakeTranscriber:
    """Faux prédicteur : « mot 1 », « mot 2 »… un texte par morceau, dans l'ordre reçu.

    Il garde la durée de chaque morceau reçu, pour vérifier ce qu'on lui envoie.
    """

    def __init__(self, texts: list[str] | None = None) -> None:
        self.texts = texts
        self.received_durations_s: list[float] = []

    def supports(self, task: Task, profile: Profile) -> bool:
        return True

    def model_info(self, task: Task, profile: Profile) -> ModelInfo:
        return ModelInfo(model_id="faux-whisper", model_version="1.0.0", calibrated=False)

    def predict(
        self, task: Task, profile: Profile, windows: list[FloatArray]
    ) -> list[ProbabilityArray]:
        raise AssertionError("la transcription ne demande pas de probabilités")

    def transcribe(self, profile: Profile, windows: list[FloatArray]) -> list[str]:
        texts = []
        for index, window in enumerate(windows, start=1):
            self.received_durations_s.append(len(window) / SAMPLE_RATE)
            texts.append(f"mot {index}")
        if self.texts is not None:
            return self.texts
        return texts


def make_context(segments: list[Segment], transcriber: FakeTranscriber) -> ResultContext:
    return ResultContext(
        predictor=transcriber,
        labels=load_class_labels(),
        inference_config=load_inference_config(),
        speech_detector=FixedDetector(segments),
    )


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)


def test_short_segments_are_kept_whole() -> None:
    config = load_inference_config()
    speech = [Segment(start_s=1.0, end_s=4.0), Segment(start_s=6.0, end_s=36.0)]

    windows = transcription_windows(speech, config)

    assert windows == speech


def test_long_segment_is_cut_in_equal_pieces_of_at_most_30_s() -> None:
    config = load_inference_config()
    speech = [Segment(start_s=2.0, end_s=72.0)]

    windows = transcription_windows(speech, config)

    # 70 s → 3 morceaux égaux de 23,3 s, qui couvrent exactement le segment.
    assert len(windows) == 3
    for window in windows:
        assert window.duration_s <= MAX_WINDOW_S
        assert window.duration_s == pytest.approx(70.0 / 3)
    assert windows[0].start_s == 2.0
    assert windows[-1].end_s == 72.0
    assert windows[1].start_s == pytest.approx(windows[0].end_s)


def test_no_speech_segment_gives_no_speech() -> None:
    transcriber = FakeTranscriber()
    context = make_context([], transcriber)

    result = build_results(silence(5.0), ["transcription"], "quality", context)["transcription"]

    assert result["status"] == "no_speech"
    assert result["message"] == NO_SPEECH_MESSAGE
    assert result["text"] is None
    assert result["segments"] == []
    assert result["model_id"] == "faux-whisper"
    # Rien n'est envoyé au modèle quand il n'y a pas de parole.
    assert transcriber.received_durations_s == []


def test_text_is_joined_and_timestamps_are_segment_bounds() -> None:
    speech = [Segment(start_s=0.5, end_s=2.25), Segment(start_s=3.0, end_s=7.125)]
    transcriber = FakeTranscriber()
    context = make_context(speech, transcriber)

    result = build_results(silence(8.0), ["transcription"], "realtime", context)["transcription"]

    assert result["status"] == "done"
    assert result["text"] == "mot 1 mot 2"
    starts = [segment["start_s"] for segment in result["segments"]]
    ends = [segment["end_s"] for segment in result["segments"]]
    assert starts == [0.5, 3.0]
    assert ends == [2.25, 7.125]
    texts = [segment["text"] for segment in result["segments"]]
    assert texts == ["mot 1", "mot 2"]
    # Le transcripteur a reçu exactement les échantillons de chaque segment.
    assert transcriber.received_durations_s == pytest.approx([1.75, 4.125])


def test_transcription_has_no_class_and_no_probabilities() -> None:
    context = make_context([Segment(start_s=0.0, end_s=2.0)], FakeTranscriber())

    result = build_results(silence(3.0), ["transcription"], "quality", context)["transcription"]

    assert result["label"] is None
    assert result["label_fr"] is None
    assert result["probabilities"] == []
    assert result["calibrated"] is False
    segment = result["segments"][0]
    assert segment["label"] is None
    assert segment["probabilities"] == []


def test_long_speech_is_sent_in_pieces_of_at_most_30_s() -> None:
    transcriber = FakeTranscriber()
    context = make_context([Segment(start_s=0.0, end_s=65.0)], transcriber)

    result = build_results(silence(65.0), ["transcription"], "quality", context)["transcription"]

    assert len(result["segments"]) == 3
    for duration_s in transcriber.received_durations_s:
        assert duration_s <= MAX_WINDOW_S
    assert result["segments"][-1]["end_s"] == 65.0


def test_empty_texts_are_skipped_when_joining() -> None:
    assert join_texts(["Bonjour", "", "à tous"]) == "Bonjour à tous"
    assert join_texts(["", ""]) == ""


def demo_context(detector: FixedDetector) -> ResultContext:
    """Faux prédicteur de l'application (émotion et transcription), VAD de test."""
    labels = load_class_labels()
    return ResultContext(
        predictor=DemoPredictor(class_counts(labels)),
        labels=labels,
        inference_config=load_inference_config(),
        speech_detector=detector,
    )


def test_vad_runs_once_for_emotion_and_transcription() -> None:
    detector = FixedDetector([Segment(start_s=0.5, end_s=3.0)])
    context = demo_context(detector)

    results = build_results(silence(4.0), ["emotion", "transcription"], "quality", context)

    assert detector.call_count == 1
    # Les deux tâches lisent les mêmes zones de parole.
    emotion_segment = results["emotion"]["segments"][0]
    text_segment = results["transcription"]["segments"][0]
    assert (emotion_segment["start_s"], emotion_segment["end_s"]) == (0.5, 3.0)
    assert (text_segment["start_s"], text_segment["end_s"]) == (0.5, 3.0)


def test_vad_does_not_run_without_a_speech_task() -> None:
    detector = FixedDetector([Segment(start_s=0.5, end_s=3.0)])
    context = demo_context(detector)

    build_results(silence(4.0), ["sound_event", "speaker"], "quality", context)

    assert detector.call_count == 0


def test_app_decoding_matches_the_c17a_evaluation() -> None:
    # Une seule vérité : l'application (configs/inference.yaml) décode comme l'évaluation C17a
    # (configs/transcription.yaml), sinon les WER des fiches ne la décrivent plus.
    evaluation = load_yaml(CONFIG_DIR / "transcription.yaml")
    application = load_yaml(CONFIG_DIR / "inference.yaml")["transcription"]
    for key in DECODING_KEYS:
        assert application[key] == evaluation[key], key


def test_app_models_are_the_evaluated_revisions() -> None:
    # Mêmes poids que ceux mesurés par C17a : dépôt et révision de chaque modèle du registre.
    evaluation = load_yaml(CONFIG_DIR / "transcription.yaml")
    evaluated = {}
    for model in evaluation["models"]:
        evaluated[model["repo_id"]] = model["revision"]
    registry = ModelRegistry.from_yaml(CONFIG_DIR / "registry.yaml")
    entries = registry.for_task(Task.TRANSCRIPTION)
    assert len(entries) == 2
    for entry in entries:
        repo_id = entry.weights.removeprefix("hf://")
        assert evaluated[repo_id] == entry.revision, entry.id
