"""Manifeste de RAVDESS, partie parole (24 acteurs, 1 440 fichiers audio).

Le nom de chaque fichier porte sept codes : modalité-canal-émotion-intensité-phrase-
répétition-acteur, par exemple Actor_01/03-01-05-01-01-01-01.wav. Le genre se déduit du numéro
d'acteur : impair = homme, pair = femme (documentation de RAVDESS). L'étiquette d'origine est
gardée telle quelle, calme (02) et surprise (08) compris : elles sont exclues plus tard (P2, P9).
"""

from __future__ import annotations

from pathlib import Path

from echolens.core.data.manifest import (
    Gender,
    ManifestRow,
    audio_duration_s,
    check_manifest,
)

DATASET_ID = "ravdess"
# Modalité 03 = audio seul (01 et 02 sont des vidéos) ; canal 01 = parole (02 = chant).
AUDIO_ONLY_MODALITY = "03"
SPEECH_CHANNEL = "01"
NAME_FIELD_COUNT = 7
EMOTION_CODES = frozenset({"01", "02", "03", "04", "05", "06", "07", "08"})
INTENSITY_CODES = frozenset({"01", "02"})
# Fichiers défectueux connus de la copie utilisée (illisibles ou de 0 s), exclus du manifeste.
# Chaque entrée : le nom du fichier, et en commentaire ce qui ne va pas et où on l'a constaté.
# Vide tant qu'on n'a rien trouvé : tout autre fichier défectueux fait échouer la construction.
KNOWN_BAD_FILES: frozenset[str] = frozenset()


def build_ravdess_manifest(dataset_root: Path) -> list[ManifestRow]:
    """Construit le manifeste de RAVDESS à partir des WAV de dataset_root/Actor_XX (P9).

    Lève ValueError (en français) pour un nom mal formé, une modalité autre que 03 (audio
    seul), un canal autre que 01 (parole), ou un fichier illisible ou vide absent de
    KNOWN_BAD_FILES.
    """
    audio_paths = sorted(dataset_root.glob("Actor_*/*.wav"))
    if not audio_paths:
        raise ValueError(f"Aucun fichier WAV dans {dataset_root}/Actor_*")

    rows: list[ManifestRow] = []
    for audio_path in audio_paths:
        # Fichiers défectueux connus : exclus, et seulement eux.
        if audio_path.name in KNOWN_BAD_FILES:
            continue
        row = _row_from_file(audio_path, dataset_root)
        rows.append(row)

    check_manifest(rows)
    return rows


def ravdess_gender(actor: str) -> Gender:
    """Genre d'un acteur de RAVDESS : numéro impair = homme (M), pair = femme (F)."""
    actor_number = int(actor)
    if actor_number % 2 == 1:
        return "M"
    return "F"


def _row_from_file(audio_path: Path, dataset_root: Path) -> ManifestRow:
    # Étape 1 : les codes utiles du nom (émotion, intensité, acteur).
    emotion, intensity, actor = _parse_ravdess_name(audio_path.name)
    # Étape 2 : durée lue dans l'en-tête ; un fichier illisible ou vide lève une erreur.
    duration_s = audio_duration_s(audio_path)
    relative_path = audio_path.relative_to(dataset_root).as_posix()
    return ManifestRow(
        dataset=DATASET_ID,
        path=relative_path,
        label=emotion,
        speaker=actor,
        gender=ravdess_gender(actor),
        duration_s=duration_s,
        intensity=intensity,
    )


def _parse_ravdess_name(file_name: str) -> tuple[str, str, str]:
    # 03-01-05-01-01-01-01.wav → modalité, canal, émotion, intensité, phrase, répétition, acteur.
    stem = Path(file_name).stem
    fields = stem.split("-")
    if len(fields) != NAME_FIELD_COUNT:
        raise ValueError(_bad_name_message(file_name))
    modality = fields[0]
    channel = fields[1]
    emotion = fields[2]
    intensity = fields[3]
    actor = fields[6]
    if modality != AUDIO_ONLY_MODALITY:
        raise ValueError(
            f"RAVDESS : modalité {modality} dans « {file_name} », seule 03 (audio seul) est prise"
        )
    if channel != SPEECH_CHANNEL:
        raise ValueError(
            f"RAVDESS : canal {channel} dans « {file_name} », seul 01 (parole) est pris"
        )
    if emotion not in EMOTION_CODES or intensity not in INTENSITY_CODES or not actor.isdigit():
        raise ValueError(_bad_name_message(file_name))
    return emotion, intensity, actor


def _bad_name_message(file_name: str) -> str:
    return (
        f"Nom de fichier RAVDESS inattendu : « {file_name} » (attendu : sept codes "
        "modalité-canal-émotion-intensité-phrase-répétition-acteur, par exemple "
        "03-01-05-01-01-01-01.wav)"
    )
