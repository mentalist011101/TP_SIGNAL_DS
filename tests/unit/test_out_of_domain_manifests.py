"""Tests des manifestes des jeux hors domaine (C16) : CaFE et OpenSLR 57.

Tous les fichiers audio sont de petits WAV de synthèse, jamais de vrais fichiers des jeux.
"""

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from echolens.core.data import cafe
from echolens.core.data.cafe import build_cafe_manifest
from echolens.core.data.openslr57 import (
    build_openslr57_manifest,
    parse_transcript_line,
    speaker_gender,
)

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


# --- OpenSLR 57 ---


def write_text(path: Path, lines: list[str]) -> None:
    """Petit fichier de transcriptions de synthèse, une ligne par extrait."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_small_openslr57(root: Path) -> None:
    """Arborescence réduite qui reprend les quatre formes d'identifiants du vrai jeu."""
    write_wav(root / "speech/test/ca16/gabon_f_024/gabon_f_024_001.wav")
    write_wav(root / "speech/dev/niger_west_african_fr/niger_sys1_1/niger_sys1_1_088.wav")
    write_wav(root / "speech/train/ca16/002/afc-gabon_16.06.11_002_conv_0023.wav")
    write_wav(root / "speech/train/yaounde/answers/ctell1-01/ctell1-01-001.wav")
    write_text(root / "transcripts/test/ca16/prompts.txt", ["gabon_f_024_001 Bonjour, à tous."])
    write_text(
        root / "transcripts/dev/niger_west_african_fr/transcripts.txt",
        ["niger_west_african_fr/niger_sys1_1/niger_sys1_1_088.wav il fait beau"],
    )
    write_text(
        root / "transcripts/train/ca16_conv/transcripts.txt",
        ["afc-gabon_16.06.11_002_conv_0023.tdf oui merci"],
    )


def test_openslr57_fields(tmp_path: Path) -> None:
    make_small_openslr57(tmp_path)

    rows = build_openslr57_manifest(tmp_path)
    by_speaker = {row.speaker: row for row in rows}

    assert len(rows) == 4
    test_row = by_speaker["gabon_f_024"]
    assert test_row.dataset == "openslr57"
    assert test_row.path == "speech/test/ca16/gabon_f_024/gabon_f_024_001.wav"
    assert test_row.official_split == "test"
    assert test_row.subset == "ca16"
    assert test_row.gender == "F"
    assert test_row.label is None
    # Le texte reste tel qu'écrit dans le jeu (P9) : ponctuation et accents gardés.
    assert test_row.transcript == "Bonjour, à tous."
    assert by_speaker["niger_sys1_1"].subset == "niger"
    assert by_speaker["niger_sys1_1"].transcript == "il fait beau"
    assert by_speaker["002"].transcript == "oui merci"


def test_openslr57_missing_transcript_and_gender_stay_empty(tmp_path: Path) -> None:
    make_small_openslr57(tmp_path)

    rows = build_openslr57_manifest(tmp_path)
    by_speaker = {row.speaker: row for row in rows}

    yaounde_row = by_speaker["ctell1-01"]
    assert yaounde_row.subset == "yaounde"
    assert yaounde_row.official_split == "train"
    assert yaounde_row.transcript is None
    assert yaounde_row.gender is None


def test_openslr57_transcripts_of_another_split_are_not_used(tmp_path: Path) -> None:
    write_wav(tmp_path / "speech/test/ca16/chad_m_001/chad_m_001_001.wav")
    write_text(tmp_path / "transcripts/train/ca16_read/conditioned.txt", ["chad_m_001_001 non"])

    rows = build_openslr57_manifest(tmp_path)

    assert rows[0].transcript is None


def test_openslr57_conflicting_transcripts_raise(tmp_path: Path) -> None:
    write_wav(tmp_path / "speech/test/ca16/chad_m_001/chad_m_001_001.wav")
    write_text(tmp_path / "transcripts/test/ca16/a.txt", ["chad_m_001_001 premier texte"])
    write_text(tmp_path / "transcripts/test/ca16/b.txt", ["chad_m_001_001 autre texte"])

    with pytest.raises(ValueError, match="deux transcriptions différentes"):
        build_openslr57_manifest(tmp_path)


def test_openslr57_unknown_subset_raises(tmp_path: Path) -> None:
    write_wav(tmp_path / "speech/test/inconnu/x/x_001.wav")

    with pytest.raises(ValueError, match="sous-corpus inconnu"):
        build_openslr57_manifest(tmp_path)


def test_openslr57_without_wav_raises(tmp_path: Path) -> None:
    (tmp_path / "speech").mkdir()

    with pytest.raises(ValueError, match="Aucun fichier WAV"):
        build_openslr57_manifest(tmp_path)


def test_parse_transcript_line_forms() -> None:
    wav_form = parse_transcript_line("dossier/abc_001.wav  le texte  ")
    tdf_form = parse_transcript_line("abc_002.tdf texte")
    bare_form = parse_transcript_line("abc_003 texte")

    assert wav_form == ("abc_001", "le texte")
    assert tdf_form == ("abc_002", "texte")
    assert bare_form == ("abc_003", "texte")
    assert parse_transcript_line("") is None
    assert parse_transcript_line("abc_004") is None


def test_speaker_gender() -> None:
    assert speaker_gender("cameroon_m_006") == "M"
    assert speaker_gender("gabon_f_024") == "F"
    assert speaker_gender("ctell1-01") is None
    assert speaker_gender("niger_sys1_1") is None
