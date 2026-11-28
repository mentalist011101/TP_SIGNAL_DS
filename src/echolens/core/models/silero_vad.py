"""Silero VAD avec torch : la détection de parole de production (D5, C24).

Code ml : seuls echolens.services.silero_detector, echolens.training et les notebooks
l'importent, jamais le reste de core, pour que l'application tourne aussi sans torch
(webrtcvad en secours). Le modèle est le fichier TorchScript livré dans le paquet silero-vad
(version figée dans l'extra [ml]) : aucun téléchargement, l'application marche hors ligne.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
import torch

from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.core.audio.preprocess_config import VadConfig
from echolens.core.audio.segment import Segment, flags_to_segments, hysteresis_flags

FloatArray = npt.NDArray[np.float32]
# Silero VAD (versions 5 et 6) n'accepte à 16 kHz que des tranches de 512 échantillons (32 ms).
SILERO_CHUNK_SAMPLES = 512


def load_silero_model() -> Any:
    """Charge Silero VAD, livré dans le paquet silero-vad (TorchScript, sans téléchargement).

    Le paquet silero-vad appelle torch.set_num_threads(1) dès son import (silero_vad/model.py) :
    sans précaution, tous les modèles torch du processus tourneraient sur un seul fil, et les
    têtes Whisper du profil qualité iraient presque deux fois moins vite. On l'importe donc
    ici, puis on rétablit le nombre de fils d'avant l'import.
    """
    threads_before = torch.get_num_threads()
    from silero_vad import load_silero_vad

    torch.set_num_threads(threads_before)
    model = load_silero_vad(onnx=False)
    model.eval()
    return model


def silero_speech_probabilities(model: Any, signal: FloatArray) -> list[float]:
    """Probabilité de parole de chaque tranche entière de 32 ms d'un signal mono 16 kHz.

    La dernière tranche incomplète est ignorée, comme la dernière trame dans webrtcvad.
    """
    # Étape 1 : le modèle garde une mémoire d'une tranche à l'autre ; on la vide pour que
    # l'extrait précédent n'influence pas celui-ci.
    model.reset_states()
    chunk_count = len(signal) // SILERO_CHUNK_SAMPLES
    # Étape 2 : une probabilité par tranche, dans l'ordre du temps (la mémoire en dépend).
    probabilities: list[float] = []
    with torch.no_grad():
        for index in range(chunk_count):
            start = index * SILERO_CHUNK_SAMPLES
            chunk = np.ascontiguousarray(signal[start : start + SILERO_CHUNK_SAMPLES])
            chunk_tensor = torch.from_numpy(chunk)
            output = model(chunk_tensor, TARGET_SAMPLE_RATE)
            probabilities.append(float(output.item()))
    return probabilities


def silero_speech_segments(model: Any, signal: FloatArray, config: VadConfig) -> list[Segment]:
    """Zones de parole d'un signal mono 16 kHz avec Silero (D5) ; liste vide si aucune.

    Probabilité par tranche de 32 ms, décisions avec hystérésis (silero_threshold pour ouvrir,
    silero_end_threshold pour fermer), puis le même nettoyage des segments que webrtcvad.
    """
    probabilities = silero_speech_probabilities(model, signal)
    flags = hysteresis_flags(probabilities, config.silero_threshold, config.silero_end_threshold)
    chunk_s = SILERO_CHUNK_SAMPLES / TARGET_SAMPLE_RATE
    duration_s = len(signal) / TARGET_SAMPLE_RATE
    return flags_to_segments(flags, chunk_s, config, duration_s)
