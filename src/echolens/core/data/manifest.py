"""Manifestes de données : un fichier CSV par jeu, une ligne par extrait audio.

C'est le contrat partagé par le téléchargement, les découpages et l'entraînement : chacun lit et
écrit les manifestes avec ce module, jamais à la main. Le manifeste ne contient que des
métadonnées (pas d'audio) et garde l'étiquette d'origine du jeu ; la correspondance vers nos
classes communes est une décision séparée (P2).
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
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
    "official_split",
    "subset",
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
    # Fold officiel d'ESC-50 (1 à 5, P3).
    fold: int | None = None
    # Découpage officiel d'origine (OpenSLR 57 : dossier speech/<split>).
    official_split: Literal["train", "dev", "devtest", "test"] | None = None
    # Sous-corpus d'origine (ex. « yaounde », « ca16 », « niger » pour OpenSLR 57).
    subset: str | None = None
    # Code d'intensité d'origine, tel quel (ex. « HI » pour CREMA-D).
    intensity: str | None = None
    # Enregistrement d'origine (ex. src_file d'ESC-50) : deux lignes de même source
    # ne doivent jamais être séparées entre deux folds.
    source: str | None = None
    # Texte prononcé tel qu'écrit dans le jeu, sans normalisation : la normalisation
    # (casse, ponctuation) fait partie du calcul du WER, pas du manifeste.
    transcript: str | None = None


def load_manifest(path: Path) -> list[ManifestRow]:
    """Lit un manifeste CSV ; une cellule vide devient None.

    Lève ValueError si l'en-tête ne correspond pas exactement à MANIFEST_COLUMNS.
    """
    rows: list[ManifestRow] = []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        # Étape 1 : vérifier l'en-tête avant toute ligne, pour refuser un fichier modifié
        # à la main (colonne renommée, séparateur « ; » d'Excel) avec un message clair.
        header = reader.fieldnames
        _check_header(header, path)
        # Étape 2 : lire les lignes une par une.
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


def dataset_root(dataset_id: str, datasets_dir: Path) -> Path:
    """Renvoie le dossier racine d'un jeu : <datasets_dir>/<id du jeu>.

    Sur Kaggle, datasets_dir vaut /kaggle/input et chaque jeu est un dataset privé nommé
    exactement comme son identifiant dans configs/datasets.yaml.
    """
    return datasets_dir / dataset_id


def audio_path(row: ManifestRow, datasets_dir: Path) -> Path:
    """Renvoie le chemin complet du fichier audio d'une ligne de manifeste."""
    root = dataset_root(row.dataset, datasets_dir)
    return root / row.path


def check_manifest(
    rows: list[ManifestRow], allowed_cross_fold_sources: frozenset[str] = frozenset()
) -> None:
    """Vérifie la cohérence d'un manifeste ; lève ValueError au premier problème trouvé.

    Règles : un seul jeu par manifeste, chaque chemin une seule fois, et une même source
    jamais répartie sur deux folds (sinon le même enregistrement serait à la fois en
    entraînement et en test, P3). allowed_cross_fold_sources liste les exceptions connues
    d'un jeu dont les folds officiels ne respectent pas cette règle (voir esc50.py).
    """
    _check_single_dataset(rows)
    _check_unique_paths(rows)
    _check_sources_stay_in_one_fold(rows, allowed_cross_fold_sources)


def _check_header(header: Sequence[str] | None, path: Path) -> None:
    if header is None:
        header = []
    header_columns = list(header)
    if header_columns == MANIFEST_COLUMNS:
        return
    missing = [column for column in MANIFEST_COLUMNS if column not in header_columns]
    unexpected = [column for column in header_columns if column not in MANIFEST_COLUMNS]
    missing_text = _join_or_none(missing)
    unexpected_text = _join_or_none(unexpected)
    raise ValueError(
        f"En-tête invalide dans {path}. "
        f"Colonnes manquantes : {missing_text}. "
        f"Colonnes inattendues : {unexpected_text}. "
        f"Ordre attendu : {','.join(MANIFEST_COLUMNS)}. "
        "Les manifestes sont générés par les scripts : ne jamais les éditer à la main "
        "(ni dans Excel), régénérez-les."
    )


def _join_or_none(columns: list[str]) -> str:
    if not columns:
        return "aucune"
    return ", ".join(columns)


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


def _check_sources_stay_in_one_fold(
    rows: list[ManifestRow], allowed_cross_fold_sources: frozenset[str]
) -> None:
    fold_of_source: dict[str, int] = {}
    for row in rows:
        if row.source is None or row.fold is None:
            continue
        if row.source in allowed_cross_fold_sources:
            continue
        known_fold = fold_of_source.get(row.source)
        if known_fold is None:
            fold_of_source[row.source] = row.fold
            continue
        if known_fold != row.fold:
            raise ValueError(
                f"La source {row.source} apparaît dans les folds {known_fold} et {row.fold}"
            )
