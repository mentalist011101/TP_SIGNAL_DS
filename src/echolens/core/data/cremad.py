"""Manifeste de CREMA-D (7 442 extraits, 91 acteurs, 6 émotions).

Le nom de chaque fichier porte l'acteur, la phrase, l'émotion et l'intensité, par exemple
AudioWAV/1001_DFA_ANG_XX.wav. Le genre de l'acteur vient de VideoDemographics.csv, fourni
avec le jeu (colonne Sex). L'étiquette d'origine est gardée telle quelle (P9) ; le passage aux
6 classes communes se fait plus tard (P2).
"""

from __future__ import annotations

import csv
from pathlib import Path

from echolens.core.data.manifest import (
    Gender,
    ManifestRow,
    audio_duration_s,
    check_manifest,
)

DATASET_ID = "cremad"
AUDIO_FOLDER = "AudioWAV"
EMOTION_CODES = frozenset({"ANG", "DIS", "FEA", "HAP", "NEU", "SAD"})
INTENSITY_CODES = frozenset({"LO", "MD", "HI", "XX"})
# Valeurs de la colonne Sex de VideoDemographics.csv, vers le format du manifeste.
GENDER_CODES: dict[str, Gender] = {"Male": "M", "Female": "F"}
# Fichiers défectueux connus de la copie utilisée (illisibles ou de 0 s), exclus du manifeste.
# Chaque entrée : le nom du fichier, et en commentaire ce qui ne va pas et où on l'a constaté.
# Vide tant qu'on n'a rien trouvé : tout autre fichier défectueux fait échouer la construction.
KNOWN_BAD_FILES: frozenset[str] = frozenset()


def build_cremad_manifest(dataset_root: Path, demographics_path: Path) -> list[ManifestRow]:
    """Construit le manifeste de CREMA-D à partir des WAV de dataset_root/AudioWAV (P9).

    Lève ValueError (en français) pour un nom de fichier mal formé, un acteur absent de
    VideoDemographics.csv, ou un fichier illisible ou vide absent de KNOWN_BAD_FILES.
    """
    gender_of_actor = load_cremad_genders(demographics_path)
    audio_paths = sorted((dataset_root / AUDIO_FOLDER).glob("*.wav"))
    if not audio_paths:
        raise ValueError(f"Aucun fichier WAV dans {dataset_root / AUDIO_FOLDER}")

    rows: list[ManifestRow] = []
    for audio_path in audio_paths:
        # Fichiers défectueux connus : exclus, et seulement eux.
        if audio_path.name in KNOWN_BAD_FILES:
            continue
        row = _row_from_file(audio_path, gender_of_actor)
        rows.append(row)

    check_manifest(rows)
    return rows


def load_cremad_genders(demographics_path: Path) -> dict[str, Gender]:
    """Genre de chaque acteur (« 1001 » → « M »), lu dans VideoDemographics.csv."""
    gender_of_actor: dict[str, Gender] = {}
    # utf-8-sig : accepte un éventuel BOM en tête de fichier (CSV exporté depuis Excel).
    with demographics_path.open(encoding="utf-8-sig", newline="") as handle:
        for record in csv.DictReader(handle):
            actor = record["ActorID"].strip()
            sex = record["Sex"].strip()
            if sex not in GENDER_CODES:
                raise ValueError(f"Genre inattendu pour l'acteur {actor} : « {sex} »")
            gender_of_actor[actor] = GENDER_CODES[sex]
    return gender_of_actor


def _row_from_file(audio_path: Path, gender_of_actor: dict[str, Gender]) -> ManifestRow:
    # Étape 1 : les quatre champs du nom, acteur_phrase_émotion_intensité.
    actor, emotion, intensity = _parse_cremad_name(audio_path.name)
    # Étape 2 : le genre, qui n'est pas dans le nom mais dans VideoDemographics.csv.
    if actor not in gender_of_actor:
        raise ValueError(
            f"Acteur {actor} absent de VideoDemographics.csv (fichier {audio_path.name})"
        )
    # Étape 3 : durée lue dans l'en-tête ; un fichier illisible ou vide lève une erreur.
    duration_s = audio_duration_s(audio_path)
    return ManifestRow(
        dataset=DATASET_ID,
        path=f"{AUDIO_FOLDER}/{audio_path.name}",
        label=emotion,
        speaker=actor,
        gender=gender_of_actor[actor],
        duration_s=duration_s,
        intensity=intensity,
    )


def _parse_cremad_name(file_name: str) -> tuple[str, str, str]:
    # 1001_DFA_ANG_XX.wav → acteur 1001, émotion ANG, intensité XX (la phrase n'est pas gardée).
    stem = Path(file_name).stem
    fields = stem.split("_")
    if len(fields) != 4:
        raise ValueError(_bad_name_message(file_name))
    actor = fields[0]
    emotion = fields[2]
    intensity = fields[3]
    if not actor.isdigit() or emotion not in EMOTION_CODES or intensity not in INTENSITY_CODES:
        raise ValueError(_bad_name_message(file_name))
    return actor, emotion, intensity


def _bad_name_message(file_name: str) -> str:
    return (
        f"Nom de fichier CREMA-D inattendu : « {file_name} » "
        "(attendu : acteur_phrase_émotion_intensité.wav, par exemple 1001_DFA_ANG_XX.wav)"
    )
