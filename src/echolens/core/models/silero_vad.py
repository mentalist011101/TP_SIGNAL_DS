"""Silero VAD avec torch : probabilité de parole par tranche de 32 ms (C24, comparaison D5).

Code ml : seuls echolens.training et les notebooks l'importent, jamais le reste de core, pour
que la VAD de l'application reste utilisable sans torch.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import numpy.typing as npt
import torch
from silero_vad import load_silero_vad

from echolens.core.audio.io import TARGET_SAMPLE_RATE

FloatArray = npt.NDArray[np.float32]
# Silero VAD (version 5) n'accepte à 16 kHz que des tranches de 512 échantillons (32 ms).
SILERO_CHUNK_SAMPLES = 512


def load_silero_model() -> Any:
    """Charge Silero VAD, livré dans le paquet silero-vad (TorchScript, sans téléchargement)."""
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
