"""Brique 1 : ingestion et prétraitement du signal audio."""

from echolens.core.audio.denoise import denoise
from echolens.core.audio.io import AudioDecodeError, AudioTooLongError, load_audio
from echolens.core.audio.preprocess import is_silent, peak_limit, preprocess, rms_normalize
from echolens.core.audio.preprocess_config import PreprocessConfig, load_preprocess_config
from echolens.core.audio.segment import (
    Segment,
    cut_window,
    detect_speech,
    flags_to_segments,
    sliding_windows,
    speech_flags,
)

__all__ = [
    "AudioDecodeError",
    "AudioTooLongError",
    "PreprocessConfig",
    "Segment",
    "cut_window",
    "denoise",
    "detect_speech",
    "flags_to_segments",
    "is_silent",
    "load_audio",
    "load_preprocess_config",
    "peak_limit",
    "preprocess",
    "rms_normalize",
    "sliding_windows",
    "speech_flags",
]
