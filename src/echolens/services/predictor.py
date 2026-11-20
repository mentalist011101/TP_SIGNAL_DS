"""Prédicteurs : ce qui transforme des fenêtres de signal en probabilités par classe (Brique 6).

Le reste de l'application ne connaît que l'interface Predictor. Le prédicteur utilisé est
choisi dans configs/app.yaml (inference_backend), jamais en dur. Ici, seul le faux prédicteur
« demo » existe : il permet de construire et de tester tout le contrat des résultats (API,
base, interface) avant de brancher les vrais modèles (C13, PR 2).
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from echolens.core.inference import FloatArray, ProbabilityArray
from echolens.core.models.registry import Task

DEMO_MODEL_ID = "demo"
DEMO_MODEL_VERSION = "0"
# Écart-type des scores tirés au hasard : plus il est grand, plus une classe domine.
DEMO_SCORE_SCALE = 2.0


@dataclass(frozen=True)
class ModelInfo:
    """Modèle qui a produit un résultat, pour la traçabilité (registre, S1)."""

    model_id: str
    model_version: str
    # Vrai si les probabilités ont été calibrées (temperature scaling, ENF-06).
    calibrated: bool


class Predictor(Protocol):
    """Ce que doit savoir faire tout prédicteur, faux ou vrai."""

    def supports(self, task: Task) -> bool:
        """Vrai si le prédicteur sait traiter cette tâche."""
        ...

    def model_info(self, task: Task) -> ModelInfo:
        """Identité du modèle utilisé pour cette tâche."""
        ...

    def predict(self, task: Task, windows: list[FloatArray]) -> list[ProbabilityArray]:
        """Une distribution de probabilités (somme 1) par fenêtre de signal mono 16 kHz."""
        ...


class DemoPredictor:
    """Faux prédicteur : probabilités au hasard, mais toujours les mêmes pour le même audio.

    Chaque fenêtre donne une graine (somme de contrôle CRC32 de ses échantillons) : deux
    analyses du même fichier donnent donc exactement les mêmes probabilités. Ces chiffres ne
    veulent rien dire ; model_id vaut « demo » pour que personne ne les prenne pour un résultat.
    """

    def __init__(self, class_counts: dict[Task, int]) -> None:
        # Nombre de classes de chaque tâche gérée (6 émotions, 50 classes d'ESC-50).
        self.class_counts = class_counts

    def supports(self, task: Task) -> bool:
        """Le faux prédicteur gère les tâches de classification (émotion, événement)."""
        return task in self.class_counts

    def model_info(self, task: Task) -> ModelInfo:
        """Toujours « demo », version « 0 », probabilités non calibrées."""
        return ModelInfo(model_id=DEMO_MODEL_ID, model_version=DEMO_MODEL_VERSION, calibrated=False)

    def predict(self, task: Task, windows: list[FloatArray]) -> list[ProbabilityArray]:
        """Une distribution déterministe par fenêtre."""
        class_count = self.class_counts[task]
        probabilities: list[ProbabilityArray] = []
        for window in windows:
            window_probabilities = _demo_probabilities(task, window, class_count)
            probabilities.append(window_probabilities)
        return probabilities


def make_predictor(backend: str, class_counts: dict[Task, int]) -> Predictor:
    """Crée le prédicteur choisi dans configs/app.yaml (inference_backend)."""
    if backend == DEMO_MODEL_ID:
        return DemoPredictor(class_counts)
    raise ValueError(f"Prédicteur inconnu dans configs/app.yaml : « {backend} »")


def _demo_probabilities(task: Task, window: FloatArray, class_count: int) -> ProbabilityArray:
    # Étape 1 : graine tirée du contenu de la fenêtre et du nom de la tâche (même audio →
    # même graine). CRC32 est stable d'une exécution à l'autre, contrairement à hash().
    content = task.value.encode("utf-8") + window.tobytes()
    seed = zlib.crc32(content)
    generator = np.random.default_rng(seed)
    # Étape 2 : un score par classe, puis softmax pour obtenir des probabilités de somme 1.
    scores = generator.normal(loc=0.0, scale=DEMO_SCORE_SCALE, size=class_count)
    exponentials = np.exp(scores - scores.max())
    probabilities = exponentials / exponentials.sum()
    return np.asarray(probabilities, dtype=np.float64)
