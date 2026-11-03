"""Décodage audio par ffmpeg (décision D1) vers un signal mono 16 kHz en float32 (décision D2)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import numpy.typing as npt

TARGET_SAMPLE_RATE = 16_000


class AudioDecodeError(RuntimeError):
    """Le fichier n'a pas pu être décodé (format inconnu, fichier corrompu, ffmpeg absent)."""


class AudioTooLongError(ValueError):
    """L'audio dépasse la durée maximale autorisée (garde-fou D6)."""


def _ffmpeg_binary() -> str:
    binary = shutil.which("ffmpeg")
    if binary is None:
        raise AudioDecodeError("ffmpeg est introuvable : installez-le (dépendance système requise)")
    return binary


def load_audio(
    path: str | Path,
    sample_rate: int = TARGET_SAMPLE_RATE,
    max_seconds: float | None = None,
) -> npt.NDArray[np.float32]:
    """Décode n'importe quel format lisible par ffmpeg en signal mono float32 dans [-1, 1].

    Les canaux sont moyennés et le signal est rééchantillonné à ``sample_rate`` par ffmpeg.
    Lève ``AudioTooLongError`` si la durée dépasse ``max_seconds``.
    """
    source = Path(path)
    if not source.is_file():
        raise AudioDecodeError(f"Fichier introuvable : {source}")

    command = [
        _ffmpeg_binary(),
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-ac",
        "1",
        "-ar",
        str(sample_rate),
        "-f",
        "f32le",
        "-",
    ]
    result = subprocess.run(command, capture_output=True, check=False)
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise AudioDecodeError(f"Décodage impossible de {source.name} : {message}")

    signal = np.frombuffer(result.stdout, dtype=np.float32).copy()
    if signal.size == 0:
        raise AudioDecodeError(f"Aucun échantillon audio dans {source.name}")

    duration = signal.size / sample_rate
    if max_seconds is not None and duration > max_seconds:
        raise AudioTooLongError(
            f"Audio trop long : {duration:.1f} s (maximum autorisé : {max_seconds:.0f} s)"
        )
    return signal
