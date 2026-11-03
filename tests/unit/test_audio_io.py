from pathlib import Path

import numpy as np
import pytest

from echolens.core.audio.io import AudioDecodeError, AudioTooLongError, load_audio


def test_load_audio_resamples_to_mono_16k(stereo_wav_44k: Path) -> None:
    signal = load_audio(stereo_wav_44k)
    assert signal.dtype == np.float32
    assert signal.ndim == 1
    # 2 s à 16 kHz = 32 000 échantillons (tolérance pour le filtre de rééchantillonnage).
    assert abs(signal.size - 32_000) <= 64


def test_load_audio_rejects_too_long(stereo_wav_44k: Path) -> None:
    with pytest.raises(AudioTooLongError):
        load_audio(stereo_wav_44k, max_seconds=1.0)


def test_load_audio_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(AudioDecodeError):
        load_audio(tmp_path / "absent.wav")


def test_load_audio_rejects_non_audio(tmp_path: Path) -> None:
    fake = tmp_path / "texte.wav"
    fake.write_text("ceci n'est pas un fichier audio", encoding="utf-8")
    with pytest.raises(AudioDecodeError):
        load_audio(fake)
