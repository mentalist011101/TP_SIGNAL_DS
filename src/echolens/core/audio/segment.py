"""Segmentation (décisions D5, D8) : zones de parole avec webrtcvad, et fenêtres glissantes."""

from __future__ import annotations

import numpy as np
import numpy.typing as npt
import webrtcvad
from pydantic import BaseModel

from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.core.audio.preprocess_config import VadConfig

FloatArray = npt.NDArray[np.float32]
# Plus grande valeur d'un échantillon PCM 16 bits signé.
INT16_MAX = 32767


class Segment(BaseModel):
    """Portion d'audio, de start_s à end_s, en secondes."""

    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        """Durée du segment, en secondes."""
        return self.end_s - self.start_s


def speech_flags(signal: FloatArray, config: VadConfig) -> list[bool]:
    """Décide, trame par trame, s'il y a de la parole (webrtcvad, D5).

    webrtcvad lit du PCM 16 bits par trames de 10, 20 ou 30 ms. La dernière trame
    incomplète est ignorée : webrtcvad refuse une trame plus courte.
    """
    # Étape 1 : passage en PCM 16 bits, le seul format que lit webrtcvad.
    clipped = np.clip(signal, -1.0, 1.0)
    pcm = (clipped * INT16_MAX).astype(np.int16)
    # Étape 2 : découpage en trames entières de frame_ms.
    frame_length = TARGET_SAMPLE_RATE * config.frame_ms // 1000
    frame_count = len(pcm) // frame_length
    # Étape 3 : une décision parole / non-parole par trame.
    vad = webrtcvad.Vad(config.aggressiveness)
    flags: list[bool] = []
    for index in range(frame_count):
        start = index * frame_length
        frame = pcm[start : start + frame_length]
        is_speech = bool(vad.is_speech(frame.tobytes(), TARGET_SAMPLE_RATE))
        flags.append(is_speech)
    return flags


def flags_to_segments(
    flags: list[bool], frame_s: float, config: VadConfig, duration_s: float
) -> list[Segment]:
    """Transforme les décisions par trame en segments de parole nettoyés (D5).

    Fonction pure, en 5 étapes : suites de trames de parole, fusion des écarts courts,
    suppression des segments trop courts, marge autour de chaque segment, rognage à l'audio.
    """
    segments = _speech_runs(flags, frame_s)
    segments = _merge_close_segments(segments, config.merge_gap_ms)
    segments = _drop_short_segments(segments, config.min_segment_ms)
    segments = _add_padding(segments, config.padding_ms)
    return _clip_to_audio(segments, duration_s)


def detect_speech(signal: FloatArray, config: VadConfig) -> list[Segment]:
    """Repère les zones de parole d'un signal mono 16 kHz (D5) ; liste vide si aucune."""
    flags = speech_flags(signal, config)
    frame_s = config.frame_ms / 1000
    duration_s = len(signal) / TARGET_SAMPLE_RATE
    return flags_to_segments(flags, frame_s, config, duration_s)


def sliding_windows(duration_s: float, window_s: float, hop_s: float) -> list[Segment]:
    """Découpe une durée en fenêtres de window_s décalées de hop_s (D5, D8).

    Si la dernière fenêtre ne tombe pas pile sur la fin, une fenêtre de plus est alignée sur
    la fin de l'audio, plutôt que complétée par des zéros. Un audio plus court qu'une fenêtre
    donne une seule fenêtre. Les calculs se font en millisecondes entières, pour qu'une
    erreur d'arrondi (0,1 + 0,2 ≠ 0,3) n'ajoute ni ne retire une fenêtre.
    """
    duration_ms = _to_ms(duration_s)
    window_ms = _to_ms(window_s)
    hop_ms = _to_ms(hop_s)
    if hop_ms <= 0:
        raise ValueError(f"Décalage de fenêtre trop petit : {hop_s} s")
    if duration_ms <= window_ms:
        return [Segment(start_s=0.0, end_s=duration_s)]
    windows: list[Segment] = []
    start_ms = 0
    while start_ms + window_ms <= duration_ms:
        windows.append(Segment(start_s=start_ms / 1000, end_s=(start_ms + window_ms) / 1000))
        start_ms += hop_ms
    last_end_ms = _to_ms(windows[-1].end_s)
    if last_end_ms < duration_ms:
        windows.append(Segment(start_s=duration_s - window_s, end_s=duration_s))
    return windows


def cut_window(signal: FloatArray, segment: Segment, window_s: float) -> FloatArray:
    """Extrait la fenêtre qui commence à segment.start_s, longue de window_s.

    Seul un audio plus court que window_s est complété par des zéros, à la fin. Sinon la
    fenêtre est prise dans l'audio, et ramenée en arrière si elle dépasse la fin.
    """
    window_length = round(window_s * TARGET_SAMPLE_RATE)
    if len(signal) < window_length:
        missing = window_length - len(signal)
        padded: FloatArray = np.pad(signal, (0, missing)).astype(np.float32)
        return padded
    start = round(segment.start_s * TARGET_SAMPLE_RATE)
    start = min(start, len(signal) - window_length)
    window: FloatArray = signal[start : start + window_length].astype(np.float32)
    return window


def _speech_runs(flags: list[bool], frame_s: float) -> list[Segment]:
    # Étape 1 : chaque suite de trames « parole » devient un segment.
    runs: list[Segment] = []
    run_start: int | None = None
    for index, is_speech in enumerate(flags):
        if is_speech and run_start is None:
            run_start = index
        if not is_speech and run_start is not None:
            runs.append(Segment(start_s=run_start * frame_s, end_s=index * frame_s))
            run_start = None
    if run_start is not None:
        runs.append(Segment(start_s=run_start * frame_s, end_s=len(flags) * frame_s))
    return runs


def _merge_close_segments(segments: list[Segment], max_gap_ms: int) -> list[Segment]:
    # Étape 2 : un écart plus court que max_gap_ms est une pause dans la phrase, pas une fin.
    merged: list[Segment] = []
    for segment in segments:
        if not merged:
            merged.append(segment)
            continue
        previous = merged[-1]
        gap_ms = _to_ms(segment.start_s - previous.end_s)
        if gap_ms < max_gap_ms:
            merged[-1] = Segment(start_s=previous.start_s, end_s=segment.end_s)
        else:
            merged.append(segment)
    return merged


def _drop_short_segments(segments: list[Segment], min_duration_ms: int) -> list[Segment]:
    # Étape 3 : un segment trop court est un clic ou un bruit bref, pas de la parole.
    kept: list[Segment] = []
    for segment in segments:
        if _to_ms(segment.duration_s) >= min_duration_ms:
            kept.append(segment)
    return kept


def _add_padding(segments: list[Segment], padding_ms: int) -> list[Segment]:
    # Étape 4 : marge pour ne pas couper les débuts et fins de mots. Deux segments gardés
    # sont séparés d'au moins merge_gap_ms (300) : leurs marges (2 × 100) ne se touchent pas.
    padding_s = padding_ms / 1000
    padded: list[Segment] = []
    for segment in segments:
        start_s = segment.start_s - padding_s
        end_s = segment.end_s + padding_s
        padded.append(Segment(start_s=start_s, end_s=end_s))
    return padded


def _clip_to_audio(segments: list[Segment], duration_s: float) -> list[Segment]:
    # Étape 5 : la marge ne doit pas sortir de l'audio (avant 0 ou après la fin).
    clipped: list[Segment] = []
    for segment in segments:
        start_s = max(segment.start_s, 0.0)
        end_s = min(segment.end_s, duration_s)
        clipped.append(Segment(start_s=start_s, end_s=end_s))
    return clipped


def _to_ms(seconds: float) -> int:
    return round(seconds * 1000)
