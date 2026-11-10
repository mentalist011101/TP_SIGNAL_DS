import re
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from echolens.core.data import cremad, ravdess
from echolens.core.data.cremad import build_cremad_manifest
from echolens.core.data.ravdess import build_ravdess_manifest, ravdess_gender

SAMPLE_RATE = 16_000
DEMOGRAPHICS_HEADER = "ActorID,Age,Sex,Race,Ethnicity\n"


def write_wav(path: Path, seconds: float = 0.5) -> None:
    """Petit WAV de synthèse (sinusoïde de 440 Hz), jamais un vrai fichier du jeu."""
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    signal = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, signal, SAMPLE_RATE)


def write_demographics(path: Path, actors: dict[str, str]) -> Path:
    """VideoDemographics.csv de synthèse : acteur → « Male » ou « Female »."""
    lines = [DEMOGRAPHICS_HEADER]
    for actor, sex in actors.items():
        lines.append(f"{actor},30,{sex},Caucasian,Not Hispanic\n")
    path.write_text("".join(lines), encoding="utf-8")
    return path


def test_cremad_fields(tmp_path: Path) -> None:
    write_wav(tmp_path / "AudioWAV" / "1001_DFA_ANG_XX.wav", seconds=0.5)
    write_wav(tmp_path / "AudioWAV" / "1002_IEO_SAD_HI.wav", seconds=1.0)
    demographics = write_demographics(tmp_path / "demo.csv", {"1001": "Male", "1002": "Female"})

    rows = build_cremad_manifest(tmp_path, demographics)

    assert len(rows) == 2
    first = rows[0]
    assert first.dataset == "cremad"
    assert first.path == "AudioWAV/1001_DFA_ANG_XX.wav"
    assert first.label == "ANG"
    assert first.speaker == "1001"
    assert first.gender == "M"
    assert first.intensity == "XX"
    assert first.duration_s == pytest.approx(0.5)
    assert rows[1].gender == "F"
    assert rows[1].intensity == "HI"


def test_cremad_malformed_name_is_rejected(tmp_path: Path) -> None:
    write_wav(tmp_path / "AudioWAV" / "1001_DFA_ANGRY.wav")
    demographics = write_demographics(tmp_path / "demo.csv", {"1001": "Male"})
    with pytest.raises(ValueError, match="Nom de fichier CREMA-D inattendu"):
        build_cremad_manifest(tmp_path, demographics)


def test_cremad_known_misnamed_file_is_read_with_its_official_name(tmp_path: Path) -> None:
    write_wav(tmp_path / "AudioWAV" / "1040_ITH_SAD_X.wav")
    demographics = write_demographics(tmp_path / "demo.csv", {"1040": "Male"})

    rows = build_cremad_manifest(tmp_path, demographics)

    # Le chemin garde le vrai nom du fichier ; l'intensité vient du nom officiel (XX).
    assert rows[0].path == "AudioWAV/1040_ITH_SAD_X.wav"
    assert rows[0].intensity == "XX"
    assert rows[0].label == "SAD"


def test_cremad_other_single_x_intensity_is_rejected(tmp_path: Path) -> None:
    write_wav(tmp_path / "AudioWAV" / "1041_ITH_SAD_X.wav")
    demographics = write_demographics(tmp_path / "demo.csv", {"1041": "Male"})
    with pytest.raises(ValueError, match="Nom de fichier CREMA-D inattendu"):
        build_cremad_manifest(tmp_path, demographics)


def test_cremad_actor_missing_from_demographics_is_rejected(tmp_path: Path) -> None:
    write_wav(tmp_path / "AudioWAV" / "1091_DFA_NEU_XX.wav")
    demographics = write_demographics(tmp_path / "demo.csv", {"1001": "Male"})
    with pytest.raises(ValueError, match="Acteur 1091 absent"):
        build_cremad_manifest(tmp_path, demographics)


def test_cremad_empty_file_fails_unless_known(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_wav(tmp_path / "AudioWAV" / "1001_DFA_ANG_XX.wav")
    empty_file = tmp_path / "AudioWAV" / "1001_DFA_DIS_XX.wav"
    empty_file.write_bytes(b"")
    demographics = write_demographics(tmp_path / "demo.csv", {"1001": "Male"})

    # Pas dans la liste : la construction échoue et nomme le fichier.
    with pytest.raises(ValueError, match=re.escape("1001_DFA_DIS_XX.wav")):
        build_cremad_manifest(tmp_path, demographics)

    # Dans la liste : le fichier est exclu, les autres restent.
    monkeypatch.setattr(cremad, "KNOWN_BAD_FILES", frozenset({"1001_DFA_DIS_XX.wav"}))
    rows = build_cremad_manifest(tmp_path, demographics)
    assert [row.path for row in rows] == ["AudioWAV/1001_DFA_ANG_XX.wav"]


def test_ravdess_fields(tmp_path: Path) -> None:
    write_wav(tmp_path / "Actor_01" / "03-01-05-01-01-01-01.wav", seconds=0.5)
    write_wav(tmp_path / "Actor_02" / "03-01-08-02-02-01-02.wav", seconds=1.0)

    rows = build_ravdess_manifest(tmp_path)

    assert len(rows) == 2
    first = rows[0]
    assert first.dataset == "ravdess"
    assert first.path == "Actor_01/03-01-05-01-01-01-01.wav"
    assert first.label == "05"
    assert first.speaker == "01"
    assert first.gender == "M"
    assert first.intensity == "01"
    assert first.duration_s == pytest.approx(0.5)
    # Surprise (08) est gardée : elle n'est exclue que plus tard (P2, P9).
    assert rows[1].label == "08"
    assert rows[1].gender == "F"


@pytest.mark.parametrize(("actor", "gender"), [("01", "M"), ("02", "F"), ("23", "M"), ("24", "F")])
def test_ravdess_gender_follows_actor_parity(actor: str, gender: str) -> None:
    assert ravdess_gender(actor) == gender


def test_ravdess_malformed_name_is_rejected(tmp_path: Path) -> None:
    write_wav(tmp_path / "Actor_01" / "03-01-05-01-01-01.wav")
    with pytest.raises(ValueError, match="Nom de fichier RAVDESS inattendu"):
        build_ravdess_manifest(tmp_path)


def test_ravdess_video_modality_is_rejected(tmp_path: Path) -> None:
    write_wav(tmp_path / "Actor_01" / "01-01-05-01-01-01-01.wav")
    with pytest.raises(ValueError, match="modalité 01"):
        build_ravdess_manifest(tmp_path)


def test_ravdess_song_channel_is_rejected(tmp_path: Path) -> None:
    write_wav(tmp_path / "Actor_01" / "03-02-05-01-01-01-01.wav")
    with pytest.raises(ValueError, match="canal 02"):
        build_ravdess_manifest(tmp_path)


def test_ravdess_empty_file_fails_unless_known(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    write_wav(tmp_path / "Actor_01" / "03-01-05-01-01-01-01.wav")
    empty_file = tmp_path / "Actor_01" / "03-01-06-01-01-01-01.wav"
    empty_file.write_bytes(b"")

    with pytest.raises(ValueError, match=re.escape("03-01-06-01-01-01-01.wav")):
        build_ravdess_manifest(tmp_path)

    monkeypatch.setattr(ravdess, "KNOWN_BAD_FILES", frozenset({"03-01-06-01-01-01-01.wav"}))
    rows = build_ravdess_manifest(tmp_path)
    assert [row.path for row in rows] == ["Actor_01/03-01-05-01-01-01-01.wav"]
