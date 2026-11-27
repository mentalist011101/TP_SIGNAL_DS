"""Prédicteurs : ce qui transforme des fenêtres de signal en probabilités par classe, ou en
texte pour la transcription (Brique 6).

Le reste de l'application ne connaît que l'interface Predictor. Le prédicteur utilisé est
choisi dans configs/app.yaml (inference_backend), jamais en dur :
- « demo » : faux prédicteur déterministe, sans torch (développement du front, CI) ;
- « models » : vrais modèles du registre (echolens.services.model_predictor, C13).
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from echolens.config import AppSettings
from echolens.core.data.class_labels import ClassLabels
from echolens.core.features import FeatureConfig
from echolens.core.inference import FloatArray, ProbabilityArray, load_inference_config
from echolens.core.models.registry import ModelRegistry, Profile, Task

DEMO_MODEL_ID = "demo"
DEMO_MODEL_VERSION = "0"
# Écart-type des scores tirés au hasard : plus il est grand, plus une classe domine.
DEMO_SCORE_SCALE = 2.0
# Texte factice de chaque segment de parole en mode demo (aucun modèle de transcription).
DEMO_TRANSCRIPTION = "Transcription de démonstration"


@dataclass(frozen=True)
class ModelInfo:
    """Modèle qui a produit un résultat, pour la traçabilité (registre, S1)."""

    model_id: str
    model_version: str
    # Vrai si les probabilités ont été calibrées (temperature scaling, ENF-06) ; toujours faux
    # pour la transcription, qui ne donne pas de probabilités.
    calibrated: bool


class Predictor(Protocol):
    """Ce que doit savoir faire tout prédicteur, faux ou vrai."""

    def supports(self, task: Task, profile: Profile) -> bool:
        """Vrai si le prédicteur a un modèle pour cette tâche dans ce profil (EF-07)."""
        ...

    def model_info(self, task: Task, profile: Profile) -> ModelInfo:
        """Identité du modèle utilisé pour cette tâche dans ce profil."""
        ...

    def predict(
        self, task: Task, profile: Profile, windows: list[FloatArray]
    ) -> list[ProbabilityArray]:
        """Une distribution de probabilités (somme 1) par fenêtre de signal mono 16 kHz."""
        ...

    def transcribe(self, profile: Profile, windows: list[FloatArray]) -> list[str]:
        """Un texte par morceau de parole mono 16 kHz, dans le même ordre (EF-10)."""
        ...

    def prepare(self, task: Task, profile: Profile) -> None:
        """Charge le modèle de cette tâche dans ce profil, sans rien prédire : un temps de
        calcul mesuré ensuite ne compte pas le chargement (comparaison, EF-15)."""
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

    def supports(self, task: Task, profile: Profile) -> bool:
        """Le faux prédicteur gère la classification et la transcription, dans les deux profils."""
        if task == Task.TRANSCRIPTION:
            return True
        return task in self.class_counts

    def model_info(self, task: Task, profile: Profile) -> ModelInfo:
        """Toujours « demo », version « 0 », probabilités non calibrées."""
        return ModelInfo(model_id=DEMO_MODEL_ID, model_version=DEMO_MODEL_VERSION, calibrated=False)

    def predict(
        self, task: Task, profile: Profile, windows: list[FloatArray]
    ) -> list[ProbabilityArray]:
        """Une distribution déterministe par fenêtre (le profil ne change rien)."""
        class_count = self.class_counts[task]
        probabilities: list[ProbabilityArray] = []
        for window in windows:
            window_probabilities = _demo_probabilities(task, window, class_count)
            probabilities.append(window_probabilities)
        return probabilities

    def transcribe(self, profile: Profile, windows: list[FloatArray]) -> list[str]:
        """Le même texte factice pour chaque morceau, sans modèle : le front et la CI ont un
        texte à montrer sans torch ni faster-whisper. model_id « demo » dit qu'il ne veut rien
        dire."""
        texts: list[str] = []
        for _ in windows:
            texts.append(DEMO_TRANSCRIPTION)
        return texts

    def prepare(self, task: Task, profile: Profile) -> None:
        """Rien à charger : le faux prédicteur n'a pas de modèle."""


def make_predictor(settings: AppSettings, labels: ClassLabels) -> Predictor:
    """Crée le prédicteur choisi par inference_backend (configs/app.yaml).

    « demo » : faux prédicteur, sans torch. « models » : vrais modèles du registre ; torch
    n'est importé qu'à ce moment-là, si bien que le mode demo et la CI s'en passent.
    """
    if settings.inference_backend == DEMO_MODEL_ID:
        return DemoPredictor(class_counts(labels))
    from echolens.services.model_predictor import ModelPredictor

    registry = ModelRegistry.from_yaml(settings.registry_path)
    feature_config = FeatureConfig.from_yaml(settings.features_path)
    transcription_settings = load_inference_config().transcription
    predictor = ModelPredictor(
        registry,
        labels,
        feature_config,
        settings.features_path,
        settings.models_dir,
        transcription_settings,
    )
    # Préchauffage pour la démo : les modèles sont chargés au démarrage, pas à la 1re analyse.
    if settings.preload_models:
        predictor.preload()
    return predictor


def class_counts(labels: ClassLabels) -> dict[Task, int]:
    """Nombre de classes de chaque tâche de classification, lu dans configs/labels.yaml."""
    return {Task.EMOTION: len(labels.emotions), Task.SOUND_EVENT: len(labels.esc50_classes)}


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
