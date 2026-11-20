"""Résultats d'une analyse : un objet par tâche demandée (EF-05, EF-06, EF-12, D5).

Pour chaque tâche, on découpe l'audio en segments, le prédicteur donne des probabilités par
segment, puis le résultat global est calculé à partir de ces segments. Les deux sont gardés :
le global pour les cartes de la page Résultat, les segments pour la frise temporelle (EF-12).

Trois statuts par tâche :
- done : résultat calculé ;
- no_speech : émotion demandée, mais la VAD n'a trouvé aucune parole ; on ne prédit rien
  plutôt que d'inventer une émotion à de la pluie ou à un moteur ;
- unavailable : tâche pas encore branchée (transcription, locuteur) ; l'analyse réussit quand
  même.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.core.audio.preprocess_config import VadConfig
from echolens.core.audio.segment import Segment, cut_window, detect_speech
from echolens.core.data.class_labels import ClassLabel, ClassLabels
from echolens.core.inference import (
    FloatArray,
    InferenceConfig,
    ProbabilityArray,
    duration_weighted_mean,
    emotion_windows,
    mean_probabilities,
    ranked_probabilities,
    segment_samples,
    sound_event_windows,
)
from echolens.core.models.registry import Profile, Task
from echolens.services.predictor import ModelInfo, Predictor

STATUS_DONE = "done"
STATUS_NO_SPEECH = "no_speech"
STATUS_UNAVAILABLE = "unavailable"
NO_SPEECH_MESSAGE = "Aucune parole détectée"
UNAVAILABLE_MESSAGE = "Disponible prochainement"
# Bornes des segments arrondies à la milliseconde : 11,559999999 s devient 11,56 s.
TIME_DECIMALS = 3


@dataclass(frozen=True)
class ResultContext:
    """Ce qu'il faut pour calculer les résultats : prédicteur, classes et découpage."""

    predictor: Predictor
    labels: ClassLabels
    inference_config: InferenceConfig
    vad_config: VadConfig


def build_results(
    signal: FloatArray, tasks: list[str], profile: str, context: ResultContext
) -> dict[str, Any]:
    """Un objet par tâche demandée, prêt à être stocké en JSON et renvoyé par l'API.

    Le profil (EF-07) choisit le modèle de chaque tâche : qualité ou temps réel.
    """
    results: dict[str, Any] = {}
    for task_name in tasks:
        task = Task(task_name)
        results[task.value] = task_result(signal, task, Profile(profile), context)
    return results


def task_result(
    signal: FloatArray, task: Task, profile: Profile, context: ResultContext
) -> dict[str, Any]:
    """Résultat d'une tâche : calculé, « aucune parole » ou « disponible prochainement »."""
    if not context.predictor.supports(task, profile):
        return unavailable_result()
    if task == Task.SOUND_EVENT:
        return sound_event_result(signal, profile, context)
    if task == Task.EMOTION:
        return emotion_result(signal, profile, context)
    return unavailable_result()


def sound_event_result(
    signal: FloatArray, profile: Profile, context: ResultContext
) -> dict[str, Any]:
    """Événements sonores : fenêtres de 5 s à 50 % de recouvrement, global = moyenne (D5)."""
    config = context.inference_config
    # Étape 1 : fenêtres qui couvrent tout l'audio ; un audio court est complété par du silence.
    duration_s = len(signal) / TARGET_SAMPLE_RATE
    windows = sound_event_windows(duration_s, config)
    window_signals = []
    for window in windows:
        samples = cut_window(signal, window, config.sound_event.window_s)
        window_signals.append(samples)
    # Étape 2 : probabilités par fenêtre, puis moyenne simple (fenêtres de même durée).
    probabilities = context.predictor.predict(Task.SOUND_EVENT, profile, window_signals)
    overall = mean_probabilities(probabilities)
    info = context.predictor.model_info(Task.SOUND_EVENT, profile)
    classes = context.labels.esc50_classes
    return done_result(windows, probabilities, overall, classes, info)


def emotion_result(signal: FloatArray, profile: Profile, context: ResultContext) -> dict[str, Any]:
    """Émotions : segments de parole de la VAD, 5 s au plus, global pondéré par la durée (D5)."""
    info = context.predictor.model_info(Task.EMOTION, profile)
    # Étape 1 : zones de parole, coupées en morceaux de 5 s au plus.
    speech_segments = detect_speech(signal, context.vad_config)
    windows = emotion_windows(speech_segments, context.inference_config)
    # Étape 2 : pas de parole, pas d'émotion. On le dit au lieu d'inventer une prédiction.
    if not windows:
        return no_speech_result(info)
    window_signals = []
    for window in windows:
        samples = segment_samples(signal, window)
        window_signals.append(samples)
    # Étape 3 : probabilités par morceau, puis moyenne pondérée par la durée.
    probabilities = context.predictor.predict(Task.EMOTION, profile, window_signals)
    durations_s = [window.duration_s for window in windows]
    overall = duration_weighted_mean(probabilities, durations_s)
    classes = context.labels.emotions
    return done_result(windows, probabilities, overall, classes, info)


def done_result(
    windows: list[Segment],
    window_probabilities: list[ProbabilityArray],
    overall: ProbabilityArray,
    classes: list[ClassLabel],
    info: ModelInfo,
) -> dict[str, Any]:
    """Résultat calculé : classe la plus probable, toutes les probabilités, segments."""
    ranking = ranked_probabilities(overall, classes)
    best = ranking[0]
    segments = []
    for window, probabilities in zip(windows, window_probabilities, strict=True):
        segments.append(_segment_result(window, probabilities, classes))
    return {
        "status": STATUS_DONE,
        "message": None,
        "label": best.label,
        "label_fr": best.label_fr,
        "probabilities": [entry.model_dump() for entry in ranking],
        "model_id": info.model_id,
        "model_version": info.model_version,
        "calibrated": info.calibrated,
        "segments": segments,
    }


def no_speech_result(info: ModelInfo) -> dict[str, Any]:
    """Émotion demandée sur un audio sans parole : aucune prédiction, un message."""
    return {
        "status": STATUS_NO_SPEECH,
        "message": NO_SPEECH_MESSAGE,
        "label": None,
        "label_fr": None,
        "probabilities": [],
        "model_id": info.model_id,
        "model_version": info.model_version,
        "calibrated": info.calibrated,
        "segments": [],
    }


def unavailable_result() -> dict[str, Any]:
    """Tâche pas encore branchée : aucun modèle, un message, et l'analyse continue."""
    return {
        "status": STATUS_UNAVAILABLE,
        "message": UNAVAILABLE_MESSAGE,
        "label": None,
        "label_fr": None,
        "probabilities": [],
        "model_id": None,
        "model_version": None,
        "calibrated": None,
        "segments": [],
    }


def class_counts(labels: ClassLabels) -> dict[Task, int]:
    """Nombre de classes de chaque tâche de classification, lu dans configs/labels.yaml."""
    return {Task.EMOTION: len(labels.emotions), Task.SOUND_EVENT: len(labels.esc50_classes)}


def _segment_result(
    window: Segment, probabilities: ProbabilityArray, classes: list[ClassLabel]
) -> dict[str, Any]:
    ranking = ranked_probabilities(probabilities, classes)
    best = ranking[0]
    return {
        "start_s": round(window.start_s, TIME_DECIMALS),
        "end_s": round(window.end_s, TIME_DECIMALS),
        "label": best.label,
        "label_fr": best.label_fr,
        "probabilities": [entry.model_dump() for entry in ranking],
    }
