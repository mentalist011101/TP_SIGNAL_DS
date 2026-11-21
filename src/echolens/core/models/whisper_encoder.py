"""Encodeur gelé de Whisper : du signal aux moyennes par couche (C10, C13), avec torch.

Code partagé (R5) : le calcul des représentations sur Kaggle (echolens.training.encoders) et
l'application (prédicteur réel) passent le signal dans l'encodeur avec ces mêmes fonctions.
Règles (R7, Brique 4) : signal brut 16 kHz, log-Mel du feature extractor de Whisper complété
jusqu'à 30 s, model.eval(), torch.no_grad(), float32, moyenne sur les seules trames utiles.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import torch
from transformers import WhisperFeatureExtractor, WhisperModel

from echolens.core.models.whisper_frames import FloatArray, layer_means, whisper_useful_frames


@dataclass(frozen=True)
class WhisperEncoder:
    """Encodeur de Whisper prêt à l'emploi, avec ses réglages de trames."""

    # WhisperFeatureExtractor de transformers (non typé).
    feature_extractor: Any
    model: torch.nn.Module
    device: torch.device
    sample_rate: int
    # Une trame de sortie couvre 320 échantillons (20 ms) ; 1 500 trames pour 30 s.
    samples_per_output_frame: int
    max_output_frames: int


def load_whisper_encoder(
    checkpoint: str,
    revision: str,
    sample_rate: int,
    samples_per_output_frame: int,
    max_output_frames: int,
    device: torch.device,
) -> WhisperEncoder:
    """Charge le feature extractor et l'encodeur seul de Whisper, à une révision figée."""
    feature_extractor = WhisperFeatureExtractor.from_pretrained(checkpoint, revision=revision)
    whisper = WhisperModel.from_pretrained(checkpoint, revision=revision)
    # Encodeur seul : le décodeur (texte) ne sert pas à représenter l'audio.
    model: torch.nn.Module = whisper.get_encoder()
    # Encodeur gelé : mode évaluation (dropout coupé), poids en float32, sur l'appareil choisi.
    model.eval()
    model.to(device=device, dtype=torch.float32)
    return WhisperEncoder(
        feature_extractor=feature_extractor,
        model=model,
        device=device,
        sample_rate=sample_rate,
        samples_per_output_frame=samples_per_output_frame,
        max_output_frames=max_output_frames,
    )


def whisper_hidden_states(
    signal: FloatArray,
    feature_extractor: Any,
    model: torch.nn.Module,
    device: torch.device,
    sample_rate: int,
) -> FloatArray:
    """Sorties de toutes les couches (entrée comprise) : (couches, 1 500 trames, dimension)."""
    # Étape 1 : log-Mel de Whisper, complété jusqu'à 30 s : l'encodeur exige 3 000 trames.
    inputs = feature_extractor(
        signal, sampling_rate=sample_rate, padding="max_length", return_tensors="pt"
    )
    input_features = inputs["input_features"].to(device)
    # Étape 2 : passage dans l'encodeur gelé, sans calcul de gradient.
    with torch.no_grad():
        outputs = model(input_features, output_hidden_states=True)
    return stack_hidden_states(outputs.hidden_states)


def whisper_useful_layer_means(signal: FloatArray, encoder: WhisperEncoder) -> FloatArray:
    """Moyenne dans le temps de chaque couche, sur les seules trames utiles : (7, 512)."""
    useful_frames = whisper_useful_frames(
        len(signal), encoder.samples_per_output_frame, encoder.max_output_frames
    )
    hidden_states = whisper_hidden_states(
        signal, encoder.feature_extractor, encoder.model, encoder.device, encoder.sample_rate
    )
    return layer_means(hidden_states, useful_frames)


def stack_hidden_states(hidden_states: tuple[torch.Tensor, ...]) -> FloatArray:
    """Tuple de (1, temps, dimension), un par sortie de couche → (couches, temps, dimension)."""
    stacked = torch.stack(hidden_states, dim=0)
    single_clip = stacked[:, 0, :, :]
    as_numpy = single_clip.cpu().numpy()
    return np.asarray(as_numpy, dtype=np.float32)
