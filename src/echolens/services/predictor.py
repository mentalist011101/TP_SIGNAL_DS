"""Prédicteurs : ce qui transforme des fenêtres de signal en probabilités par classe, en
texte pour la transcription, ou en vecteur de voix pour le locuteur (Brique 6).

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

from echolens.config import CONFIG_DIR, AppSettings
from echolens.core.data.class_labels import ClassLabels
from echolens.core.features import FeatureConfig, log_mel_spectrogram
from echolens.core.inference import FloatArray, ProbabilityArray, load_inference_config
from echolens.core.models.registry import ModelRegistry, Profile, Task
from echolens.core.speaker_id import VoiceVector

DEMO_MODEL_ID = "demo"
DEMO_MODEL_VERSION = "0"
# Écart-type des scores tirés au hasard : plus il est grand, plus une classe domine.
DEMO_SCORE_SCALE = 2.0
# Texte factice de chaque segment de parole en mode demo (aucun modèle de transcription).
DEMO_TRANSCRIPTION = "Transcription de démonstration"


class ExplanationUnavailableError(ValueError):
    """Pas de carte Grad-CAM possible ; le message, en français, s'affiche tel quel."""


@dataclass(frozen=True)
class WindowExplanation:
    """Carte Grad-CAM d'une fenêtre (bandes, trames), sur les seules trames réelles du son.

    first_frame : place de la première colonne dans la fenêtre (le modèle voit la partie
    centrale d'une fenêtre trop longue).
    """

    values: FloatArray
    first_frame: int


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

    def embed_voices(self, profile: Profile, windows: list[FloatArray]) -> list[VoiceVector]:
        """Un vecteur de voix par morceau de parole mono 16 kHz, dans le même ordre (EF-11)."""
        ...

    def explain(self, task: Task, profile: Profile, window: FloatArray) -> WindowExplanation:
        """Carte Grad-CAM de la classe prédite sur une fenêtre (E7, EF-13).

        Lève ExplanationUnavailableError si le modèle n'est pas un réseau sur log-Mel.
        """
        ...


class DemoPredictor:
    """Faux prédicteur : probabilités au hasard, mais toujours les mêmes pour le même audio.

    Chaque fenêtre donne une graine (somme de contrôle CRC32 de ses échantillons) : deux
    analyses du même fichier donnent donc exactement les mêmes probabilités. Ces chiffres ne
    veulent rien dire ; model_id vaut « demo » pour que personne ne les prenne pour un résultat.
    """

    def __init__(
        self, class_counts: dict[Task, int], feature_config: FeatureConfig | None = None
    ) -> None:
        # Nombre de classes de chaque tâche gérée (6 émotions, 50 classes d'ESC-50).
        self.class_counts = class_counts
        # Log-Mel du faux vecteur de voix : le module unique de features (R5).
        if feature_config is None:
            feature_config = FeatureConfig.from_yaml(CONFIG_DIR / "features.yaml")
        self.feature_config = feature_config

    def supports(self, task: Task, profile: Profile) -> bool:
        """Le faux prédicteur gère la classification, la transcription et le locuteur, dans
        les deux profils."""
        if task in (Task.TRANSCRIPTION, Task.SPEAKER):
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

    def embed_voices(self, profile: Profile, windows: list[FloatArray]) -> list[VoiceVector]:
        """Faux vecteur de voix, sans modèle : la forme moyenne du spectre de chaque morceau.

        Le même son donne le même vecteur, deux sons différents des vecteurs différents : la
        page Locuteurs se teste sans torch. Ce n'est pas une voix (model_id « demo »).
        """
        vectors: list[VoiceVector] = []
        for window in windows:
            vector = _demo_voice(window, self.feature_config)
            vectors.append(vector)
        return vectors

    def explain(self, task: Task, profile: Profile, window: FloatArray) -> WindowExplanation:
        """Le faux prédicteur n'a pas de réseau : aucune carte à montrer."""
        raise ExplanationUnavailableError(
            "Grad-CAM indisponible en mode démonstration : aucun vrai modèle n'est chargé."
        )


def make_predictor(settings: AppSettings, labels: ClassLabels) -> Predictor:
    """Crée le prédicteur choisi par inference_backend (configs/app.yaml).

    « demo » : faux prédicteur, sans torch. « models » : vrais modèles du registre ; torch
    n'est importé qu'à ce moment-là, si bien que le mode demo et la CI s'en passent.
    """
    feature_config = FeatureConfig.from_yaml(settings.features_path)
    if settings.inference_backend == DEMO_MODEL_ID:
        return DemoPredictor(class_counts(labels), feature_config)
    from echolens.services.model_predictor import ModelPredictor

    registry = ModelRegistry.from_yaml(settings.registry_path)
    transcription_settings = load_inference_config().transcription
    predictor = ModelPredictor(
        registry,
        labels,
        feature_config,
        settings.features_path,
        settings.models_dir,
        transcription_settings,
        settings.data_dir / "model_cache",
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


def _demo_voice(window: FloatArray, feature_config: FeatureConfig) -> VoiceVector:
    # Étape 1 : niveau moyen de chaque bande Mel sur le morceau (R5).
    log_mel = log_mel_spectrogram(window, feature_config)
    band_means = log_mel.mean(axis=1, dtype=np.float64)
    # Étape 2 : on retire le niveau général pour ne garder que la forme du spectre ; sinon tous
    # les sons, en dB négatifs, auraient des vecteurs presque parallèles.
    shape = band_means - band_means.mean()
    return np.asarray(shape, dtype=np.float64)
