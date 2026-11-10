"""Manifeste d'ESC-50 (2 000 extraits de 5 s, 50 classes, 5 folds officiels).

Toutes les informations viennent de meta/esc50.csv, fourni avec le jeu : nom du fichier,
fold officiel, classe (category) et enregistrement d'origine (src_file). Les folds ne sont
jamais recalculés (P3).
"""

from __future__ import annotations

import csv
from pathlib import Path

import soundfile as sf

from echolens.core.data.manifest import ManifestRow, check_manifest

DATASET_ID = "esc50"
METADATA_FILE = Path("meta") / "esc50.csv"
AUDIO_FOLDER = "audio"
# Exceptions du jeu officiel : ces 4 enregistrements Freesound ont servi à deux classes
# voisines (clock_alarm / clock_tick, hen / rooster) placées dans deux folds différents
# (9 extraits). On garde les folds officiels pour rester comparable à la littérature (P3) ;
# toute autre source répartie sur deux folds reste refusée.
KNOWN_CROSS_FOLD_SOURCES = frozenset({"131943", "134049", "209698", "234879"})


def build_esc50_manifest(dataset_root: Path) -> list[ManifestRow]:
    """Construit le manifeste d'ESC-50 à partir de dataset_root/meta/esc50.csv (P3).

    La durée est lue dans l'en-tête de chaque WAV, sans décoder l'audio. Lève ValueError
    si le manifeste est incohérent, par exemple une même source répartie sur deux folds.
    """
    rows: list[ManifestRow] = []
    metadata_path = dataset_root / METADATA_FILE
    with metadata_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for record in reader:
            row = _row_from_record(record, dataset_root)
            rows.append(row)

    # Contrôle final : chemins uniques, et chaque source dans un seul fold (P3), sauf les
    # exceptions connues du jeu officiel.
    check_manifest(rows, allowed_cross_fold_sources=KNOWN_CROSS_FOLD_SOURCES)
    return rows


def _row_from_record(record: dict[str, str], dataset_root: Path) -> ManifestRow:
    # Étape 1 : chemin relatif à la racine du jeu, comme dans tous les manifestes.
    relative_path = f"{AUDIO_FOLDER}/{record['filename']}"
    # Étape 2 : durée lue dans l'en-tête du WAV (nombre d'échantillons / fréquence).
    info = sf.info(str(dataset_root / relative_path))
    duration_s = info.frames / info.samplerate
    return ManifestRow(
        dataset=DATASET_ID,
        path=relative_path,
        label=record["category"],
        duration_s=duration_s,
        fold=int(record["fold"]),
        source=record["src_file"],
    )
