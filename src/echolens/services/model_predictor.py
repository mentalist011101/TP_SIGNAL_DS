"""Prédicteur réel : les modèles du registre, chargés une seule fois (C13, S1, E2, ENF-06).

Seul module des services qui importe torch : il n'est importé que si inference_backend vaut
« models » (configs/app.yaml ou ECHOLENS_INFERENCE_BACKEND). Avec « demo », l'application et
la CI fonctionnent sans torch.

Pour chaque fenêtre, la chaîne est exactement celle de l'entraînement (R5) :
- tête de la famille B : encodeur Whisper gelé → moyenne de chaque couche sur les trames
  utiles → standardisation avec les statistiques du train (R4) → tête → scores ;
- CRNN : log-Mel de echolens.core.features → standardisation par bande (R4) → réseau → scores.
Puis probabilités calibrées : softmax(scores / T) (E2, ENF-06). Tout se fait en mode eval et
sous torch.no_grad().
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from huggingface_hub import hf_hub_download

from echolens.core.data.class_labels import ClassLabels
from echolens.core.features import FeatureConfig, log_mel_spectrogram
from echolens.core.frame_windows import centered_start, frame_window, window_frame_count
from echolens.core.inference import FloatArray, ProbabilityArray
from echolens.core.models.family_a import SpectrogramCnn, SpectrogramCrnn
from echolens.core.models.heads import LayerWeightedHead
from echolens.core.models.production_config import (
    CONFIG_FILE,
    WEIGHTS_FILE,
    EncoderReference,
    ProductionModelConfig,
    config_fingerprint,
    load_production_config,
)
from echolens.core.models.registry import ModelEntry, ModelRegistry, Profile, Task
from echolens.core.models.storage import load_weights
from echolens.core.models.whisper_encoder import (
    WhisperEncoder,
    load_whisper_encoder,
    whisper_useful_layer_means,
)
from echolens.services.predictor import ModelInfo

HF_PREFIX = "hf://"
# Réseaux de la famille A, qui lisent le log-Mel (les têtes lisent l'encodeur Whisper).
SPECTROGRAM_ARCHITECTURES = ("cnn", "crnn")
# Les modèles tournent sur CPU : c'est la machine de référence de l'application (ENF-01).
DEVICE = torch.device("cpu")


class ModelLoadError(RuntimeError):
    """Un modèle du registre ne peut pas être chargé ; le message dit pourquoi, en français."""


@dataclass(frozen=True)
class LoadedModel:
    """Un modèle prêt à prédire : réseau en mode eval, standardisation, température."""

    config: ProductionModelConfig
    network: torch.nn.Module
    mean: FloatArray
    std: FloatArray
    # Encodeur Whisper partagé par les têtes de la famille B ; None pour le CRNN.
    encoder: WhisperEncoder | None


class ModelPredictor:
    """Prédicteur qui utilise les modèles déclarés dans configs/registry.yaml."""

    def __init__(
        self,
        registry: ModelRegistry,
        labels: ClassLabels,
        feature_config: FeatureConfig,
        features_path: Path,
        models_dir: Path | None,
    ) -> None:
        self.registry = registry
        self.labels = labels
        self.feature_config = feature_config
        self.features_path = features_path
        # Dossier local de modèles (<dossier>/<id>/config.json et model.safetensors) ; None :
        # téléchargement depuis Hugging Face, à la révision figée du registre (cache local).
        self.models_dir = models_dir
        self._models: dict[str, LoadedModel] = {}
        self._encoders: dict[tuple[str, str], WhisperEncoder] = {}
        # Deux analyses en parallèle (S2) ne doivent pas charger le même modèle deux fois.
        self._lock = threading.Lock()

    def supports(self, task: Task, profile: Profile) -> bool:
        """Vrai si le registre a un modèle pour cette tâche dans ce profil."""
        return self.registry.model_for(task, profile) is not None

    def model_info(self, task: Task, profile: Profile) -> ModelInfo:
        """Identifiant et version du registre ; probabilités calibrées par la température."""
        entry = self._entry(task, profile)
        return ModelInfo(model_id=entry.id, model_version=entry.version, calibrated=True)

    def predict(
        self, task: Task, profile: Profile, windows: list[FloatArray]
    ) -> list[ProbabilityArray]:
        """Probabilités calibrées de chaque fenêtre, avec le modèle de ce profil."""
        entry = self._entry(task, profile)
        return self.predict_with(entry, windows)

    def predict_with(self, entry: ModelEntry, windows: list[FloatArray]) -> list[ProbabilityArray]:
        """Probabilités calibrées de chaque fenêtre avec un modèle précis du registre.

        Sert aussi à mesurer la latence de chaque modèle, quel que soit son profil (E6).
        """
        loaded = self.load(entry)
        temperature = loaded.config.calibration.temperature
        probabilities: list[ProbabilityArray] = []
        for window in windows:
            scores = self._scores(loaded, window)
            window_probabilities = calibrated_probabilities(scores, temperature)
            probabilities.append(window_probabilities)
        return probabilities

    def preload(self) -> None:
        """Charge tous les modèles de classification du registre (préchauffage, S1)."""
        for entry in self.registry.models:
            if entry.task in (Task.EMOTION, Task.SOUND_EVENT):
                self.load(entry)

    def _entry(self, task: Task, profile: Profile) -> ModelEntry:
        entry = self.registry.model_for(task, profile)
        if entry is None:
            raise ModelLoadError(f"Aucun modèle {task.value} en profil {profile.value}")
        return entry

    def _scores(self, loaded: LoadedModel, window: FloatArray) -> torch.Tensor:
        if loaded.config.architecture in SPECTROGRAM_ARCHITECTURES:
            return self._spectrogram_scores(loaded, window)
        return self._head_scores(loaded, window)

    def _head_scores(self, loaded: LoadedModel, window: FloatArray) -> torch.Tensor:
        # Étape 1 : moyenne de chaque couche de Whisper, sur les seules trames utiles.
        encoder = _require_encoder(loaded)
        means = whisper_useful_layer_means(window, encoder)
        # Étape 2 : standardisation avec les statistiques de l'entraînement de la tête (R4).
        standardized = (means - loaded.mean) / loaded.std
        as_float32 = standardized.astype(np.float32)
        inputs = torch.from_numpy(as_float32).unsqueeze(0)
        with torch.no_grad():
            scores: torch.Tensor = loaded.network(inputs)
        return scores[0]

    def _spectrogram_scores(self, loaded: LoadedModel, window: FloatArray) -> torch.Tensor:
        # Étape 1 : log-Mel par le module unique de features (R5), ramené à la longueur de la
        # fenêtre du modèle : fenêtre centrale, ou silence ajouté à la fin (comme au test).
        log_mel = log_mel_spectrogram(window, self.feature_config)
        window_frames = window_frame_count(loaded.config.window_s, self.feature_config)
        length = log_mel.shape[1]
        start = centered_start(length, window_frames)
        silence_db = self.feature_config.db_floor
        fixed = frame_window(log_mel, length, start, window_frames, silence_db)
        # Étape 2 : standardisation par bande avec les statistiques de l'entraînement (R4).
        band_count = len(loaded.mean)
        centered = fixed - loaded.mean.reshape(band_count, 1)
        standardized = centered / loaded.std.reshape(band_count, 1)
        as_float32 = standardized.astype(np.float32)
        inputs = torch.from_numpy(as_float32).unsqueeze(0)
        with torch.no_grad():
            output = loaded.network(inputs)
        scores: torch.Tensor = output.logits[0]
        return scores

    def load(self, entry: ModelEntry) -> LoadedModel:
        """Le modèle prêt à prédire, chargé une seule fois puis gardé en mémoire (S1)."""
        with self._lock:
            if entry.id not in self._models:
                self._models[entry.id] = self._load_model(entry)
            return self._models[entry.id]

    def _load_model(self, entry: ModelEntry) -> LoadedModel:
        # Étape 1 : les deux fichiers, depuis le dossier local ou Hugging Face (cache).
        config_path, weights_path = self._model_files(entry)
        config = load_production_config(config_path)
        self._check_config(entry, config)
        # Étape 2 : le réseau construit à partir de config.json, puis ses poids safetensors.
        network = _build_network(config)
        load_weights(network, weights_path)
        # Étape 3 : statistiques de standardisation et encodeur (famille B seulement).
        mean = np.asarray(config.standardization_mean, dtype=np.float32)
        std = np.asarray(config.standardization_std, dtype=np.float32)
        encoder = None
        if config.encoder is not None:
            encoder = self._encoder(config.encoder)
        return LoadedModel(config=config, network=network, mean=mean, std=std, encoder=encoder)

    def _encoder(self, reference: EncoderReference) -> WhisperEncoder:
        # Un seul encodeur Whisper en mémoire pour les deux têtes (même dépôt, même révision).
        key = (reference.checkpoint, reference.revision)
        if key not in self._encoders:
            self._encoders[key] = load_whisper_encoder(
                reference.checkpoint,
                reference.revision,
                reference.sample_rate,
                reference.samples_per_output_frame,
                reference.max_output_frames,
                DEVICE,
            )
        return self._encoders[key]

    def _model_files(self, entry: ModelEntry) -> tuple[Path, Path]:
        if self.models_dir is not None:
            folder = self.models_dir / entry.id
            return folder / CONFIG_FILE, folder / WEIGHTS_FILE
        if not entry.weights.startswith(HF_PREFIX) or not entry.revision:
            raise ModelLoadError(
                f"{entry.id} : ni dossier local de modèles, ni dépôt Hugging Face avec sa "
                "révision dans configs/registry.yaml"
            )
        repo_id = entry.weights.removeprefix(HF_PREFIX)
        config_file = hf_hub_download(repo_id, CONFIG_FILE, revision=entry.revision)
        weights_file = hf_hub_download(repo_id, WEIGHTS_FILE, revision=entry.revision)
        return Path(config_file), Path(weights_file)

    def _check_config(self, entry: ModelEntry, config: ProductionModelConfig) -> None:
        # Les classes du modèle doivent être celles de configs/labels.yaml, dans le même ordre.
        expected = self._expected_labels(entry.task)
        if config.labels != expected:
            raise ModelLoadError(f"{entry.id} : classes différentes de configs/labels.yaml")
        # Un réseau sur log-Mel n'est valable qu'avec le log-Mel exact de son entraînement (R5).
        if config.architecture in SPECTROGRAM_ARCHITECTURES:
            current = config_fingerprint(self.features_path)
            if config.features_sha256 != current:
                raise ModelLoadError(
                    f"{entry.id} : configs/features.yaml a changé depuis l'entraînement du "
                    "réseau ; il faut le réentraîner avec les nouvelles features"
                )

    def _expected_labels(self, task: Task) -> list[str]:
        if task == Task.EMOTION:
            return [class_label.id for class_label in self.labels.emotions]
        return [class_label.id for class_label in self.labels.esc50_classes]


def calibrated_probabilities(scores: torch.Tensor, temperature: float) -> ProbabilityArray:
    """softmax(scores / T) : T > 1 adoucit des probabilités trop sûres d'elles (E2)."""
    scaled = scores / temperature
    probabilities = torch.softmax(scaled.double(), dim=0)
    return np.asarray(probabilities.numpy(), dtype=np.float64)


def _build_network(config: ProductionModelConfig) -> torch.nn.Module:
    class_count = len(config.labels)
    if config.architecture in SPECTROGRAM_ARCHITECTURES:
        if config.network is None:
            raise ModelLoadError(f"{config.model_id} : forme du réseau absente de config.json")
        if config.architecture == "cnn":
            return SpectrogramCnn(class_count, config.network)
        return SpectrogramCrnn(class_count, config.network)
    if config.head is None:
        raise ModelLoadError(f"{config.model_id} : forme de la tête absente de config.json")
    head = config.head
    return LayerWeightedHead(
        head.layer_count, head.dimension, head.hidden_size, class_count, head.dropout
    )


def _require_encoder(loaded: LoadedModel) -> WhisperEncoder:
    if loaded.encoder is None:
        raise ModelLoadError(f"{loaded.config.model_id} : encodeur absent de config.json")
    return loaded.encoder
