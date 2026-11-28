"""Identification du locuteur par similarité cosinus (EF-11, C15), sans aucun modèle.

Fonctions pures, testées sans torch. Le modèle (ECAPA-TDNN) donne un vecteur de voix par
morceau de parole ; ici, on compare ces vecteurs avec la règle exacte de l'évaluation C15 (P11) :
- voix d'un locuteur enregistré = moyenne de ses vecteurs ramenés à une norme 1, puis ramenée
  elle-même à une norme 1 ;
- score d'un morceau contre une voix = produit scalaire de deux vecteurs de norme 1, soit la
  similarité cosinus (de −1 à 1) ;
- le meilleur score désigne le locuteur s'il atteint le seuil ; sinon, la voix est inconnue.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

VoiceVector = npt.NDArray[np.float64]


@dataclass(frozen=True)
class SpeakerMatch:
    """Décision pour un morceau : position de la voix reconnue (None : inconnu) et score."""

    index: int | None
    score: float


def unit_vector(vector: npt.NDArray[np.floating]) -> VoiceVector:
    """Le même vecteur ramené à une norme 1, pour que le produit scalaire soit un cosinus."""
    as_float64 = np.asarray(vector, dtype=np.float64)
    norm = np.linalg.norm(as_float64)
    if norm == 0.0:
        raise ValueError("Un vecteur de voix nul ne peut pas être normalisé.")
    return as_float64 / norm


def voice_print(vectors: Sequence[npt.NDArray[np.floating]]) -> VoiceVector:
    """Voix d'un locuteur : moyenne de ses vecteurs de norme 1, ramenée à une norme 1 (P11).

    Chaque morceau pèse autant, quelle que soit la norme brute de son vecteur.
    """
    if not vectors:
        raise ValueError("Il faut au moins un vecteur pour former une voix.")
    normalized = [unit_vector(vector) for vector in vectors]
    stacked = np.stack(normalized)
    mean_vector = stacked.mean(axis=0)
    return unit_vector(mean_vector)


def best_match(vector: VoiceVector, voices: list[VoiceVector], threshold: float) -> SpeakerMatch:
    """La voix la plus proche d'un morceau, si son score atteint le seuil (C15).

    voices : voix enregistrées, de norme 1 ; au moins une.
    """
    if not voices:
        raise ValueError("Aucune voix enregistrée à comparer.")
    # Étape 1 : un cosinus par voix enregistrée.
    morsel = unit_vector(vector)
    voice_matrix = np.stack(voices)
    scores = voice_matrix @ morsel
    # Étape 2 : la meilleure voix, gardée seulement si elle atteint le seuil « inconnu ».
    best_index = int(np.argmax(scores))
    best_score = float(scores[best_index])
    if best_score < threshold:
        return SpeakerMatch(index=None, score=best_score)
    return SpeakerMatch(index=best_index, score=best_score)


def speaking_shares(labels: list[str], durations_s: list[float]) -> dict[str, float]:
    """Part du temps de parole de chaque étiquette (locuteur ou « inconnu ») ; somme 1.

    Les étiquettes sont dans l'ordre de leur première apparition.
    """
    total_s = sum(durations_s)
    if total_s <= 0.0:
        raise ValueError("Le temps de parole total doit être positif.")
    seconds_by_label: dict[str, float] = {}
    for label, duration_s in zip(labels, durations_s, strict=True):
        previous = seconds_by_label.get(label, 0.0)
        seconds_by_label[label] = previous + duration_s
    shares: dict[str, float] = {}
    for label, seconds in seconds_by_label.items():
        shares[label] = seconds / total_s
    return shares
