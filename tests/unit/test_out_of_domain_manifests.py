"""Tests des manifestes des jeux hors domaine (C16) : CaFE et OpenSLR 57.

Tous les fichiers audio sont de petits WAV de synthèse, jamais de vrais fichiers des jeux.
"""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from echolens.core.data import cafe
from echolens.core.data.cafe import build_cafe_manifest

SAMPLE_RATE = 16_000


def write_wav(path: Path, seconds: float = 0.5) -> None:
    """Petit WAV de synthèse (sinusoïde de 440 Hz), jamais un vrai fichier du jeu."""
    path.parent.mkdir(parents=True, exist_ok=True)
    times = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    signal = (0.3 * np.sin(2 * np.pi * 440 * times)).astype(np.float32)
    sf.write(path, signal, SAMPLE_RATE)


@pytest.fixture
def two_cafe_actors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deux acteurs de synthèse : 01 homme, 02 femme (le vrai tableau vient du Readme)."""
    monkeypatch.setattr(cafe, "GENDER_OF_ACTOR", {"01": "M", "02": "F"})


# --- CaFE ---


@pytest.mark.usefixtures("two_cafe_actors")
def test_cafe_fields(tmp_path: Path) -> None:
    # Dossiers aux noms quelconques : seuls les noms de fichiers sont lus.
    write_wav(tmp_path / "Col?re" / "Faible" / "01-C-1-1.wav", seconds=0.5)
    write_wav(tmp_path / "Neutre" / "02-N-1-3.wav", seconds=1.0)

    rows = build_cafe_manifest(tmp_path)

    assert len(rows) == 2
    first = rows[0]
    assert first.dataset == "cafe"
    assert first.path == "Col?re/Faible/01-C-1-1.wav"
    assert first.label == "C"
    assert first.speaker == "01"
    assert first.gender == "M"
    assert first.intensity == "1"
    assert first.duration_s == pytest.approx(0.5)
    assert rows[1].label == "N"
    assert rows[1].gender == "F"


@pytest.mark.usefixtures("two_cafe_actors")
def test_cafe_surprise_is_kept_in_the_manifest(tmp_path: Path) -> None:
    # Le manifeste garde l'étiquette d'origine (P9) ; la surprise est exclue plus tard (P2).
    write_wav(tmp_path / "01-S-2-1.wav")
    rows = build_cafe_manifest(tmp_path)
    assert rows[0].label == "S"


@pytest.mark.usefixtures("two_cafe_actors")
def test_cafe_malformed_name_is_rejected(tmp_path: Path) -> None:
    write_wav(tmp_path / "01-X-1-1.wav")
    with pytest.raises(ValueError, match="Nom de fichier CaFE inattendu"):
        build_cafe_manifest(tmp_path)


@pytest.mark.usefixtures("two_cafe_actors")
def test_cafe_neutral_with_strong_intensity_is_rejected(tmp_path: Path) -> None:
    write_wav(tmp_path / "01-N-2-1.wav")
    with pytest.raises(ValueError, match="neutre en intensité 1"):
        build_cafe_manifest(tmp_path)


@pytest.mark.usefixtures("two_cafe_actors")
def test_cafe_unknown_actor_is_rejected(tmp_path: Path) -> None:
    write_wav(tmp_path / "07-J-1-1.wav")
    with pytest.raises(ValueError, match="genre inconnu pour l'acteur 07"):
        build_cafe_manifest(tmp_path)


@pytest.mark.usefixtures("two_cafe_actors")
def test_cafe_empty_file_is_rejected(tmp_path: Path) -> None:
    empty = tmp_path / "01-J-1-1.wav"
    sf.write(empty, np.zeros(0, dtype=np.float32), SAMPLE_RATE)
    with pytest.raises(ValueError, match="vide"):
        build_cafe_manifest(tmp_path)


def test_cafe_without_wav_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Aucun fichier WAV"):
        build_cafe_manifest(tmp_path)
