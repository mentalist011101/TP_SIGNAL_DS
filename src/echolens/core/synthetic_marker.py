"""Marquage audible d'une voix synthétique (EF-18, ENF-10, C35), sans aucun modèle.

Avant la voix clonée, on ajoute un bip : un son pur de quelques centaines de millisecondes,
puis un court silence. Un bip ne ressemble à aucune voix : n'importe qui l'entend, et il reste
dans le signal même si le fichier est copié sans ses métadonnées. Les métadonnées et le nom du
fichier sont posés par le service (echolens.services.cloning_service).

Le bip commence et finit en douceur (fenêtre de Hann) : couper net une sinusoïde produit un
« clic ». Fonctions pures, testées sans torch.
"""

from __future__ import annotations

import numpy as np

from echolens.core.inference import FloatArray, VoiceCloningSettings


def marker_tone(sample_rate: int, settings: VoiceCloningSettings) -> FloatArray:
    """Bip de marquage : sinusoïde de marker_frequency_hz, adoucie par une fenêtre de Hann."""
    # Étape 1 : instants du bip, en secondes.
    sample_count = round(settings.marker_duration_s * sample_rate)
    times = np.arange(sample_count) / sample_rate
    # Étape 2 : la sinusoïde, puis la fenêtre qui la fait monter et descendre sans clic.
    sine = settings.marker_amplitude * np.sin(2 * np.pi * settings.marker_frequency_hz * times)
    window = np.hanning(sample_count)
    tone = sine * window
    return np.asarray(tone, dtype=np.float32)


def mark_synthetic(
    speech: FloatArray, sample_rate: int, settings: VoiceCloningSettings
) -> FloatArray:
    """Voix synthétique précédée du bip, puis de marker_gap_s secondes de silence."""
    tone = marker_tone(sample_rate, settings)
    gap_count = round(settings.marker_gap_s * sample_rate)
    gap = np.zeros(gap_count, dtype=np.float32)
    speech_float32 = np.asarray(speech, dtype=np.float32)
    marked = np.concatenate([tone, gap, speech_float32])
    return np.asarray(marked, dtype=np.float32)
