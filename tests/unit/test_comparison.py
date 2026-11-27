"""compare_models (EF-15) : un passage par modèle, avec un prédicteur de test à deux modèles."""

import numpy as np

from echolens.core.audio.segment import Segment
from echolens.core.data.class_labels import load_class_labels
from echolens.core.inference import FloatArray, ProbabilityArray, load_inference_config
from echolens.core.models.registry import Profile, Task
from echolens.services.comparison_service import compare_models
from echolens.services.predictor import DemoPredictor, ModelInfo, class_counts
from echolens.services.results import ResultContext

SAMPLE_RATE = 16_000


class TwoModelPredictor(DemoPredictor):
    """Faux prédicteur avec un modèle différent par profil, qui compte ses appels."""

    def __init__(self) -> None:
        super().__init__(class_counts(load_class_labels()))
        self.calls: list[Profile] = []
        self.prepared: list[Profile] = []

    def prepare(self, task: Task, profile: Profile) -> None:
        self.prepared.append(profile)

    def model_info(self, task: Task, profile: Profile) -> ModelInfo:
        return ModelInfo(model_id=f"modele-{profile.value}", model_version="1", calibrated=True)

    def predict(
        self, task: Task, profile: Profile, windows: list[FloatArray]
    ) -> list[ProbabilityArray]:
        self.calls.append(profile)
        return super().predict(task, profile, windows)


class NoSpeechDetector:
    name = "aucune"

    def detect(self, signal: FloatArray) -> list[Segment]:
        return []


def test_each_profile_model_runs_on_the_same_audio() -> None:
    predictor = TwoModelPredictor()
    context = ResultContext(
        predictor=predictor,
        labels=load_class_labels(),
        inference_config=load_inference_config(),
        speech_detector=NoSpeechDetector(),
    )
    signal = np.zeros(6 * SAMPLE_RATE, dtype=np.float32)

    comparison = compare_models(signal, ["sound_event"], context)

    runs = comparison["sound_event"]
    assert [run["model_id"] for run in runs] == ["modele-quality", "modele-realtime"]
    assert [run["profiles"] for run in runs] == [["quality"], ["realtime"]]
    assert predictor.calls == [Profile.QUALITY, Profile.REALTIME]
    # Chaque modèle est chargé avant que son temps de calcul soit mesuré.
    assert predictor.prepared == [Profile.QUALITY, Profile.REALTIME]
    for run in runs:
        assert run["result"]["status"] == "done"
        assert run["result"]["model_id"] == run["model_id"]
        assert run["compute_s"] >= 0.0
