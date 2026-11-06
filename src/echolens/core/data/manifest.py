"""Manifestes de données : un fichier CSV par jeu, une ligne par extrait audio.

C'est le contrat partagé par le téléchargement, les découpages et l'entraînement : chacun lit et
écrit les manifestes avec ce module, jamais à la main. Le manifeste ne contient que des
métadonnées (pas d'audio) et garde l'étiquette d'origine du jeu ; la correspondance vers nos
classes communes est une décision séparée (P2).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

# Ordre fixe des colonnes dans tous les fichiers CSV.
MANIFEST_COLUMNS = [
    "dataset",
    "path",
    "label",
    "speaker",
    "gender",
    "duration_s",
    "fold",
    "intensity",
    "source",
    "transcript",
]


class ManifestRow(BaseModel):
    """Une ligne de manifeste : un extrait audio et ses métadonnées d'origine."""

    # Identifiant du jeu, tel que dans configs/datasets.yaml (ex. « esc50 »).
    dataset: str = Field(min_length=1)
    # Chemin du fichier audio, relatif à la racine du jeu.
    path: str = Field(min_length=1)
    # Étiquette d'origine, telle qu'écrite dans le jeu (ex. « ANG » pour CREMA-D).
    # Vide pour les jeux sans classe, comme OpenSLR 57 (transcription).
    label: str | None = None
    speaker: str | None = None
    gender: Literal["F", "M"] | None = None
    duration_s: float = Field(gt=0)
    fold: int | None = None
    # Code d'intensité d'origine, tel quel (ex. « HI » pour CREMA-D).
    intensity: str | None = None
    # Enregistrement d'origine (ex. src_file d'ESC-50) : deux lignes de même source
    # ne doivent jamais être séparées entre deux folds.
    source: str | None = None
    # Texte prononcé, pour calculer le WER.
    transcript: str | None = None


def load_manifest(path: Path) -> list[ManifestRow]:
    """Lit un manifeste CSV ; une cellule vide devient None."""
    rows: list[ManifestRow] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for record in reader:
            # Une cellule vide signifie « valeur absente » : pydantic convertit le reste
            # (texte → entier pour fold, texte → réel pour duration_s) et le valide.
            values: dict[str, str | None] = {}
            for column in MANIFEST_COLUMNS:
                cell = record[column]
                if cell == "":
                    values[column] = None
                else:
                    values[column] = cell
            row = ManifestRow.model_validate(values)
            rows.append(row)
    return rows


def save_manifest(rows: list[ManifestRow], path: Path) -> None:
    """Écrit un manifeste CSV, colonnes dans l'ordre fixe ; None devient une cellule vide."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_COLUMNS)
        writer.writeheader()
        for row in rows:
            values = row.model_dump()
            # Le CSV n'a pas de valeur « absente » : on écrit une cellule vide.
            for column in MANIFEST_COLUMNS:
                if values[column] is None:
                    values[column] = ""
            writer.writerow(values)


def check_manifest(rows: list[ManifestRow]) -> None:
    """Vérifie la cohérence d'un manifeste ; lève ValueError au premier problème trouvé.

    Règles : un seul jeu par manifeste, chaque chemin une seule fois, et une même source
    jamais répartie sur deux folds (sinon le même enregistrement serait à la fois en
    entraînement et en test, P3).
    """
    _check_single_dataset(rows)
    _check_unique_paths(rows)
    _check_sources_stay_in_one_fold(rows)


def _check_single_dataset(rows: list[ManifestRow]) -> None:
    datasets = {row.dataset for row in rows}
    if len(datasets) > 1:
        names = ", ".join(sorted(datasets))
        raise ValueError(f"Le manifeste mélange plusieurs jeux : {names}")


def _check_unique_paths(rows: list[ManifestRow]) -> None:
    seen_paths: set[str] = set()
    for row in rows:
        if row.path in seen_paths:
            raise ValueError(f"Chemin en double dans le manifeste : {row.path}")
        seen_paths.add(row.path)


def _check_sources_stay_in_one_fold(rows: list[ManifestRow]) -> None:
    fold_of_source: dict[str, int] = {}
    for row in rows:
        if row.source is None or row.fold is None:
            continue
        known_fold = fold_of_source.get(row.source)
        if known_fold is None:
            fold_of_source[row.source] = row.fold
            continue
        if known_fold != row.fold:
            raise ValueError(
                f"La source {row.source} apparaît dans les folds {known_fold} et {row.fold}"
            )
