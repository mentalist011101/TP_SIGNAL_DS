"""Vecteurs de voix réels : ECAPA-TDNN de SpeechBrain, le modèle mesuré en C15 (EF-11).

Importé seulement par le prédicteur réel, au premier vecteur de voix ou au préchargement : le
mode demo et la CI se passent de speechbrain (extra [ml]). Le modèle est gelé, sur CPU, en mode
eval ; il reçoit le signal mono 16 kHz tel quel, comme dans l'évaluation C15 (sans débruitage).
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import numpy as np
import torch
from huggingface_hub import snapshot_download
from speechbrain.inference.speaker import EncoderClassifier
from speechbrain.utils.fetching import LocalStrategy

from echolens.core.inference import FloatArray
from echolens.core.models.registry import ModelEntry
from echolens.core.speaker_id import VoiceVector

HF_PREFIX = "hf://"
# Les modèles tournent sur CPU : c'est la machine de référence de l'application (ENF-01).
DEVICE = "cpu"


class SpeakerEncoderLoadError(RuntimeError):
    """Le modèle de voix ne peut pas être chargé ; le message dit pourquoi, en français."""


class SpeakerEncoder:
    """Calcule les vecteurs de voix avec le modèle du registre (tâche speaker)."""

    def __init__(self, cache_dir: Path) -> None:
        # Copie des fichiers du modèle pour SpeechBrain (voir _load_model).
        self.cache_dir = cache_dir
        self._models: dict[str, Any] = {}
        # Deux analyses en parallèle (S2) ne doivent ni charger le modèle deux fois, ni
        # l'appeler en même temps.
        self._lock = threading.Lock()

    def embed(self, entry: ModelEntry, windows: list[FloatArray]) -> list[VoiceVector]:
        """Un vecteur de 192 valeurs par morceau de parole mono 16 kHz, dans le même ordre."""
        model = self.load(entry)
        vectors: list[VoiceVector] = []
        for window in windows:
            vector = self._embed_window(model, window)
            vectors.append(vector)
        return vectors

    def load(self, entry: ModelEntry) -> Any:
        """Le modèle prêt à calculer, chargé une seule fois puis gardé en mémoire (S1)."""
        with self._lock:
            if entry.id not in self._models:
                self._models[entry.id] = self._load_model(entry)
            return self._models[entry.id]

    def _embed_window(self, model: Any, window: FloatArray) -> VoiceVector:
        # Un lot d'un seul morceau, forme (1, échantillons) ; sortie (1, 1, 192).
        inputs = torch.from_numpy(window).unsqueeze(0)
        with self._lock, torch.no_grad():
            output = model.encode_batch(inputs)
        vector = output[0, 0].numpy()
        return np.asarray(vector, dtype=np.float64)

    def _load_model(self, entry: ModelEntry) -> Any:
        if not entry.weights.startswith(HF_PREFIX) or not entry.revision:
            raise SpeakerEncoderLoadError(
                f"{entry.id} : dépôt Hugging Face et révision attendus dans configs/registry.yaml"
            )
        # Étape 1 : le dépôt à sa révision figée (cache Hugging Face) ; SpeechBrain ne sait
        # pas choisir une révision lui-même, comme en C15.
        repo_id = entry.weights.removeprefix(HF_PREFIX)
        local_dir = snapshot_download(repo_id=repo_id, revision=entry.revision)
        # Étape 2 : construction du modèle. COPY plutôt que les liens symboliques par défaut de
        # SpeechBrain : Windows les refuse sans droits d'administrateur.
        savedir = self.cache_dir / entry.id
        model = EncoderClassifier.from_hparams(
            source=local_dir,
            savedir=str(savedir),
            run_opts={"device": DEVICE},
            local_strategy=LocalStrategy.COPY,
        )
        # Modèle gelé : mode eval (dropout et normalisation de lot figés).
        model.eval()
        return model
