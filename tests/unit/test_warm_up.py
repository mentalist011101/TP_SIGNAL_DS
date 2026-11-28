"""Chauffe des modèles au préchargement (démo) : une inférence par modèle, puis la VAD."""

from echolens.core.audio.segment import FloatArray, Segment
from echolens.core.data.class_labels import load_class_labels
from echolens.core.inference import ProbabilityArray, load_inference_config
from echolens.core.models.registry import Profile, Task
from echolens.services.analysis_service import warm_up_models
from echolens.services.predictor import DemoPredictor, class_counts
from echolens.services.results import ResultContext


class CountingPredictor(DemoPredictor):
    """Faux prédicteur qui note chaque (tâche, profil) prédit et chaque transcription."""

    def __init__(self) -> None:
        super().__init__(class_counts(load_class_labels()))
        self.predicted: list[tuple[Task, Profile]] = []
        self.transcribed = 0

    def predict(
        self, task: Task, profile: Profile, windows: list[FloatArray]
    ) -> list[ProbabilityArray]:
        self.predicted.append((task, profile))
        return super().predict(task, profile, windows)

    def transcribe(self, profile: Profile, windows: list[FloatArray]) -> list[str]:
        self.transcribed += 1
        return super().transcribe(profile, windows)


class CountingDetector:
    name = "compte"

    def __init__(self) -> None:
        self.call_count = 0

    def detect(self, signal: FloatArray) -> list[Segment]:
        self.call_count += 1
        return []


def test_warm_up_runs_each_classification_model_once_and_the_vad() -> None:
    predictor = CountingPredictor()
    detector = CountingDetector()
    context = ResultContext(
        predictor=predictor,
        labels=load_class_labels(),
        inference_config=load_inference_config(),
        speech_detector=detector,
    )

    warm_up_models(context)

    expected = [
        (Task.EMOTION, Profile.QUALITY),
        (Task.EMOTION, Profile.REALTIME),
        (Task.SOUND_EVENT, Profile.QUALITY),
        (Task.SOUND_EVENT, Profile.REALTIME),
    ]
    assert predictor.predicted == expected
    assert detector.call_count == 1
    # La transcription n'est pas chauffée : trop longue sur un son sans parole.
    assert predictor.transcribed == 0
