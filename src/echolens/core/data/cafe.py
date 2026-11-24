"""Manifeste de CaFE, version 48 kHz (936 fichiers, 12 acteurs, 7 émotions).

Le nom de chaque fichier porte l'acteur, l'émotion, l'intensité et la phrase, séparés par des
tirets, par exemple Colère/Faible/01-C-1-1.wav. Le genre des acteurs vient du Readme du jeu,
recopié dans GENDER_OF_ACTOR (6 hommes, 6 femmes). Les noms des dossiers ne sont jamais lus :
leurs accents peuvent être mal encodés selon l'outil qui décompresse l'archive ; seul le nom du
fichier compte. CaFE ne sert qu'au test hors domaine (P7) ; l'étiquette d'origine est gardée
telle quelle, surprise (S) comprise, et n'est exclue qu'au passage aux 6 classes (P2, P9).
"""

from __future__ import annotations

from pathlib import Path

from echolens.core.data.manifest import (
    Gender,
    ManifestRow,
    audio_duration_s,
    check_manifest,
)

DATASET_ID = "cafe"
NAME_FIELD_COUNT = 4
# Colère, Dégoût, Joie, Neutre, Peur, Surprise, Tristesse.
EMOTION_CODES = frozenset({"C", "D", "J", "N", "P", "S", "T"})
# 1 = faible, 2 = forte ; le neutre n'existe qu'en intensité 1.
INTENSITY_CODES = frozenset({"1", "2"})
NEUTRAL_CODE = "N"
NEUTRAL_INTENSITY = "1"
# Genre de chaque acteur, recopié du Readme de CaFE (« Odd : Man, Even : Woman ») : les
# acteurs impairs sont des hommes, les pairs des femmes. La version 1.1 du jeu a échangé les
# fichiers des acteurs 11 et 12 pour que cette règle soit vraie (Version-ChangeLog.txt).
GENDER_OF_ACTOR: dict[str, Gender] = {
    "01": "M",
    "02": "F",
    "03": "M",
    "04": "F",
    "05": "M",
    "06": "F",
    "07": "M",
    "08": "F",
    "09": "M",
    "10": "F",
    "11": "M",
    "12": "F",
}
# Fichiers défectueux connus de la copie utilisée (illisibles ou de 0 s), exclus du manifeste.
# Chaque entrée : le nom du fichier, et en commentaire ce qui ne va pas et où on l'a constaté.
# Vide tant qu'on n'a rien trouvé : tout autre fichier défectueux fait échouer la construction.
KNOWN_BAD_FILES: frozenset[str] = frozenset()


def build_cafe_manifest(dataset_root: Path) -> list[ManifestRow]:
    """Construit le manifeste de CaFE à partir de tous les WAV sous dataset_root (P9).

    Les WAV sont cherchés dans tous les sous-dossiers, sans lire le nom de ces dossiers.
    Lève ValueError (en français) pour un nom de fichier mal formé, un acteur sans genre
    connu, ou un fichier illisible ou vide absent de KNOWN_BAD_FILES.
    """
    audio_paths = sorted(dataset_root.rglob("*.wav"))
    if not audio_paths:
        raise ValueError(f"Aucun fichier WAV sous {dataset_root}")

    rows: list[ManifestRow] = []
    for audio_path in audio_paths:
        # Fichiers défectueux connus : exclus, et seulement eux.
        if audio_path.name in KNOWN_BAD_FILES:
            continue
        row = _row_from_file(audio_path, dataset_root)
        rows.append(row)

    check_manifest(rows)
    return rows


def cafe_gender(actor: str) -> Gender:
    """Genre d'un acteur de CaFE (« 01 » → « M » ou « F »), d'après le Readme du jeu."""
    if actor not in GENDER_OF_ACTOR:
        raise ValueError(f"CaFE : genre inconnu pour l'acteur {actor} (voir GENDER_OF_ACTOR)")
    return GENDER_OF_ACTOR[actor]


def _row_from_file(audio_path: Path, dataset_root: Path) -> ManifestRow:
    # Étape 1 : les champs utiles du nom (acteur, émotion, intensité).
    actor, emotion, intensity = _parse_cafe_name(audio_path.name)
    # Étape 2 : durée lue dans l'en-tête ; un fichier illisible ou vide lève une erreur.
    duration_s = audio_duration_s(audio_path)
    # Le chemin garde les dossiers tels qu'ils sont sur le disque, pour retrouver le fichier.
    relative_path = audio_path.relative_to(dataset_root).as_posix()
    return ManifestRow(
        dataset=DATASET_ID,
        path=relative_path,
        label=emotion,
        speaker=actor,
        gender=cafe_gender(actor),
        duration_s=duration_s,
        intensity=intensity,
    )


def _parse_cafe_name(file_name: str) -> tuple[str, str, str]:
    # 01-C-1-1.wav → acteur 01, émotion C, intensité 1 (la phrase n'est pas gardée).
    stem = Path(file_name).stem
    fields = stem.split("-")
    if len(fields) != NAME_FIELD_COUNT:
        raise ValueError(_bad_name_message(file_name))
    actor = fields[0]
    emotion = fields[1]
    intensity = fields[2]
    if not actor.isdigit() or emotion not in EMOTION_CODES or intensity not in INTENSITY_CODES:
        raise ValueError(_bad_name_message(file_name))
    # Le neutre n'a qu'une intensité : une autre valeur signale un nom mal formé.
    if emotion == NEUTRAL_CODE and intensity != NEUTRAL_INTENSITY:
        raise ValueError(_bad_name_message(file_name))
    return actor, emotion, intensity


def _bad_name_message(file_name: str) -> str:
    return (
        f"Nom de fichier CaFE inattendu : « {file_name} » (attendu : "
        "acteur-émotion-intensité-phrase.wav, par exemple 01-C-1-1.wav ; neutre en intensité 1)"
    )
