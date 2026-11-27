"""Découpage de l'audio pour l'inférence et résultat global (Brique 6, D5), sans aucun modèle.

Fonctions pures, testées sans torch. Pour chaque tâche, on découpe l'audio en fenêtres, le
modèle donne des probabilités par fenêtre, puis on en déduit le résultat global :
- événements sonores : fenêtres fixes de 5 s avec 50 % de recouvrement ; global = moyenne
  simple des fenêtres (elles ont toutes la même durée) ;
- émotions : segments de parole de la VAD, coupés en morceaux de 5 s au plus ; global =
  moyenne pondérée par la durée, pour qu'un morceau de 0,5 s pèse dix fois moins qu'un de 5 s ;
- transcription : segments de parole de la VAD, coupés en morceaux de 30 s au plus ; un texte
  par morceau, sans probabilités.
Une moyenne de distributions de probabilité somme encore à 1 (combinaison convexe).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field

from echolens.config import CONFIG_DIR, load_yaml
from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.core.audio.segment import Segment, sliding_windows
from echolens.core.data.class_labels import ClassLabel

INFERENCE_CONFIG_PATH = CONFIG_DIR / "inference.yaml"
FloatArray = npt.NDArray[np.float32]
ProbabilityArray = npt.NDArray[np.float64]


class SoundEventWindows(BaseModel):
    """Fenêtres fixes des événements sonores (D5)."""

    window_s: float = Field(gt=0)
    hop_s: float = Field(gt=0)


class EmotionWindows(BaseModel):
    """Durée maximale d'un morceau de parole envoyé au modèle d'émotion."""

    max_window_s: float = Field(gt=0)


class TranscriptionSettings(BaseModel):
    """Découpage de la parole et réglages du décodage de la transcription (EF-10, C17b)."""

    max_window_s: float = Field(gt=0)
    language: str
    beam_size: int = Field(gt=0)
    vad_filter: bool
    condition_on_previous_text: bool
    temperature: list[float] = Field(min_length=1)


class StreamSettings(BaseModel):
    """Flux micro en direct (EF-14, D8) : fenêtres, limites et enregistrement consenti."""

    window_s: float = Field(gt=0)
    hop_s: float = Field(gt=0)
    max_message_s: float = Field(gt=0)
    latency_history: int = Field(gt=0)
    silent_level_dbfs: float
    tasks: list[str] = Field(min_length=1)
    recording_tasks: list[str] = Field(min_length=1)
    recording_profile: str
    consent_version: str = Field(min_length=1)


class InferenceConfig(BaseModel):
    """Contenu de configs/inference.yaml."""

    sound_event: SoundEventWindows
    emotion: EmotionWindows
    transcription: TranscriptionSettings
    stream: StreamSettings


class RankedProbability(BaseModel):
    """Probabilité d'une classe, avec son identifiant et son libellé français."""

    label: str
    label_fr: str
    probability: float


def load_inference_config(path: Path = INFERENCE_CONFIG_PATH) -> InferenceConfig:
    """Lit configs/inference.yaml."""
    content = load_yaml(path)
    return InferenceConfig(**content)


def sound_event_windows(duration_s: float, config: InferenceConfig) -> list[Segment]:
    """Fenêtres de 5 s, décalées de 2,5 s, qui couvrent tout l'audio (D5).

    Un audio de 5 s ou moins donne une seule fenêtre, de 0 à sa durée : il sera complété par
    du silence au moment de couper le signal (cut_window).
    """
    window_s = config.sound_event.window_s
    hop_s = config.sound_event.hop_s
    return sliding_windows(duration_s, window_s, hop_s)


def split_long_segment(segment: Segment, max_window_s: float) -> list[Segment]:
    """Coupe un segment en morceaux égaux de max_window_s au plus (12 s → 3 morceaux de 4 s).

    Des morceaux égaux plutôt que « 5 s, 5 s, puis le reste » : on évite un dernier morceau
    minuscule (10,1 s donnerait 5, 5 et 0,1 s), trop court pour reconnaître une émotion.
    """
    # Calcul en millisecondes entières : 10,0 / 5,0 ne doit pas donner 2,0000001 morceaux.
    duration_ms = round(segment.duration_s * 1000)
    max_ms = round(max_window_s * 1000)
    piece_count = math.ceil(duration_ms / max_ms)
    piece_s = segment.duration_s / piece_count
    pieces: list[Segment] = []
    for index in range(piece_count):
        start_s = segment.start_s + index * piece_s
        end_s = start_s + piece_s
        pieces.append(Segment(start_s=start_s, end_s=end_s))
    # Dernier morceau calé exactement sur la fin du segment (pas d'écart d'arrondi).
    last = pieces[-1]
    pieces[-1] = Segment(start_s=last.start_s, end_s=segment.end_s)
    return pieces


def emotion_windows(speech_segments: list[Segment], config: InferenceConfig) -> list[Segment]:
    """Morceaux de parole envoyés au modèle d'émotion, dans l'ordre du temps (D5).

    Liste vide si la VAD n'a trouvé aucune parole : il n'y a alors rien à prédire.
    """
    windows: list[Segment] = []
    for segment in speech_segments:
        pieces = split_long_segment(segment, config.emotion.max_window_s)
        windows.extend(pieces)
    return windows


def transcription_windows(speech_segments: list[Segment], config: InferenceConfig) -> list[Segment]:
    """Morceaux de parole envoyés au transcripteur, dans l'ordre du temps (EF-10).

    Un segment de parole = une transcription ; un segment plus long que 30 s est coupé en
    morceaux égaux. Liste vide si la VAD n'a trouvé aucune parole.
    """
    windows: list[Segment] = []
    for segment in speech_segments:
        pieces = split_long_segment(segment, config.transcription.max_window_s)
        windows.extend(pieces)
    return windows


def segment_samples(signal: FloatArray, segment: Segment) -> FloatArray:
    """Échantillons du signal mono 16 kHz entre segment.start_s et segment.end_s."""
    start = round(segment.start_s * TARGET_SAMPLE_RATE)
    end = round(segment.end_s * TARGET_SAMPLE_RATE)
    samples = signal[start:end]
    return np.asarray(samples, dtype=np.float32)


def mean_probabilities(window_probabilities: list[ProbabilityArray]) -> ProbabilityArray:
    """Résultat global des événements : moyenne simple des probabilités des fenêtres."""
    stacked = np.stack(window_probabilities)
    mean = stacked.mean(axis=0)
    return np.asarray(mean, dtype=np.float64)


def duration_weighted_mean(
    window_probabilities: list[ProbabilityArray], durations_s: list[float]
) -> ProbabilityArray:
    """Résultat global des émotions : moyenne pondérée par la durée de chaque morceau.

    global = Σ durée_i × p_i / Σ durée_i. Un long passage en colère compte plus qu'un « oui »
    neutre de 0,3 s.
    """
    stacked = np.stack(window_probabilities)
    weights = np.asarray(durations_s, dtype=np.float64)
    weighted_mean = np.average(stacked, axis=0, weights=weights)
    return np.asarray(weighted_mean, dtype=np.float64)


def ranked_probabilities(
    probabilities: ProbabilityArray, classes: list[ClassLabel]
) -> list[RankedProbability]:
    """Probabilités de toutes les classes, de la plus probable à la moins probable.

    Lève ValueError si le nombre de probabilités n'est pas le nombre de classes : la case i
    doit correspondre à la classe i de configs/labels.yaml.
    """
    if len(probabilities) != len(classes):
        raise ValueError(
            f"{len(probabilities)} probabilités pour {len(classes)} classes : "
            "le modèle et configs/labels.yaml ne concordent pas"
        )
    ranking: list[RankedProbability] = []
    for index, class_label in enumerate(classes):
        probability = float(probabilities[index])
        entry = RankedProbability(
            label=class_label.id, label_fr=class_label.label_fr, probability=probability
        )
        ranking.append(entry)
    # Tri stable : à probabilité égale, l'ordre de labels.yaml est gardé.
    ranking.sort(key=_probability_of, reverse=True)
    return ranking


def _probability_of(entry: RankedProbability) -> float:
    return entry.probability
