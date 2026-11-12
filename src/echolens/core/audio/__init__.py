"""Brique 1 : ingestion et prétraitement du signal audio."""

from echolens.core.audio.io import AudioDecodeError, AudioTooLongError, load_audio
from echolens.core.audio.preprocess import (
    denoise,
    detect_speech,
    is_silent,
    peak_limit,
    preprocess,
    rms_normalize,
    sliding_windows,
)

__all__ = [
    "AudioDecodeError",
    "AudioTooLongError",
    "denoise",
    "detect_speech",
    "is_silent",
    "load_audio",
    "peak_limit",
    "preprocess",
    "rms_normalize",
    "sliding_windows",
]
