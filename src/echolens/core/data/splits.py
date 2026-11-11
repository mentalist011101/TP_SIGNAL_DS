"""Découpages sans fuite : train, validation et test (décisions P1, P3, P7 ; règles Ly2).

Émotions (P1) : on répartit les ACTEURS, jamais les fichiers. Un même acteur dans le train et
dans le test permettrait au modèle de reconnaître sa voix au lieu de son émotion, et le score
serait gonflé. Les acteurs sont tirés au hasard une seule fois (graine fixe), séparément chez
les hommes et chez les femmes, puis le résultat est versionné dans data/splits/.

ESC-50 (P3) : les 5 folds officiels sont gardés tels quels ; au tour k, le fold k sert de test,
le fold suivant sert seulement au réglage, puis on réentraîne sur les 4 folds hors test.

Jeux hors domaine (P7) : CaFE, ACE, OpenSLR 57 et nos enregistrements sont toujours en test.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from echolens.config import CONFIG_DIR, load_yaml
from echolens.core.data.manifest import ManifestRow

SPLITS_CONFIG_PATH = CONFIG_DIR / "splits.yaml"
# Genre d'un acteur, comme dans la colonne gender des manifestes.
Gender = Literal["F", "M"]
Split = Literal["train", "validation", "test"]
SPLIT_COLUMNS = ["dataset", "speaker", "gender", "split"]
# Ordre fixe des genres pour le tirage : le résultat ne dépend pas de l'ordre des fichiers.
GENDER_ORDER: list[Gender] = ["F", "M"]


class SplitConfig(BaseModel):
    """Paramètres des découpages, lus dans configs/splits.yaml."""

    seed: int
    validation_ratio: float = Field(gt=0, lt=0.5)
    test_ratio: float = Field(gt=0, lt=0.5)
    training_emotion_datasets: list[str]
    test_only_datasets: list[str]
    esc50_fold_count: int = Field(gt=2)


class SpeakerSplit(BaseModel):
    """Une ligne du fichier de découpage : un acteur et la partie où il va."""

    dataset: str
    speaker: str
    gender: Gender
    split: Split


def load_split_config(path: Path = SPLITS_CONFIG_PATH) -> SplitConfig:
    """Lit configs/splits.yaml."""
    content = load_yaml(path)
    return SplitConfig(**content)


def split_emotion_speakers(rows: list[ManifestRow], config: SplitConfig) -> list[SpeakerSplit]:
    """Répartit les acteurs d'un jeu d'émotions entre train, validation et test (P1).

    rows est le manifeste d'un seul jeu (CREMA-D ou RAVDESS). Validation et test reçoivent
    chacun environ 15 % des acteurs, autant d'hommes que de femmes ; tous les autres vont en
    train. Le tirage est déterministe : même manifeste et même graine donnent le même résultat.
    """
    dataset = _single_dataset(rows)
    speakers_by_gender = _speakers_by_gender(rows)
    # Étape 1 : nombre d'acteurs par genre en validation et en test.
    speaker_count = len(_gender_of_speaker(rows))
    validation_per_gender = _count_per_gender(speaker_count, config.validation_ratio)
    test_per_gender = _count_per_gender(speaker_count, config.test_ratio)
    # Étape 2 : un tirage au hasard par genre, avec un générateur créé une seule fois.
    generator = random.Random(config.seed)
    result: list[SpeakerSplit] = []
    for gender in GENDER_ORDER:
        speakers = speakers_by_gender[gender]
        held_out = validation_per_gender + test_per_gender
        if len(speakers) <= held_out:
            raise ValueError(
                f"{dataset} : seulement {len(speakers)} acteurs {gender}, "
                f"il en faut plus de {held_out} pour remplir validation et test"
            )
        shuffled = list(speakers)
        generator.shuffle(shuffled)
        # Étape 3 : les premiers vont en test, les suivants en validation, le reste en train.
        for position, speaker in enumerate(shuffled):
            split = _split_for_position(position, test_per_gender, validation_per_gender)
            result.append(
                SpeakerSplit(dataset=dataset, speaker=speaker, gender=gender, split=split)
            )
    result.sort(key=_speaker_sort_key)
    return result


def save_speaker_splits(splits: list[SpeakerSplit], path: Path) -> None:
    """Écrit le découpage des acteurs en CSV (sans audio), pour le versionner (P1)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        # Fins de ligne « \n » : le fichier réécrit est identique, octet pour octet, à celui
        # versionné, quel que soit le système (le module csv écrit « \r\n » par défaut).
        writer = csv.DictWriter(handle, fieldnames=SPLIT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        for speaker_split in splits:
            writer.writerow(speaker_split.model_dump())


def load_speaker_splits(path: Path) -> list[SpeakerSplit]:
    """Lit un découpage des acteurs écrit par save_speaker_splits."""
    splits: list[SpeakerSplit] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            speaker_split = SpeakerSplit.model_validate(record)
            splits.append(speaker_split)
    return splits


def split_of_row(row: ManifestRow, splits: list[SpeakerSplit], config: SplitConfig) -> Split:
    """Partie d'un extrait : test pour un jeu hors domaine (P7), sinon celle de son acteur (P1).

    Lève ValueError si l'acteur n'a pas de partie : un extrait ne doit jamais être réparti
    par défaut, sinon il pourrait atterrir en train sans qu'on le voie.
    """
    if row.dataset in config.test_only_datasets:
        return "test"
    for speaker_split in splits:
        same_dataset = speaker_split.dataset == row.dataset
        same_speaker = speaker_split.speaker == row.speaker
        if same_dataset and same_speaker:
            return speaker_split.split
    raise ValueError(f"Aucune partie pour l'acteur {row.speaker} du jeu {row.dataset}")


class Esc50Round(BaseModel):
    """Rôle des folds d'ESC-50 pour un tour de validation croisée (P3)."""

    test_fold: int
    # Fold suivant : sert seulement à choisir le nombre d'époques et les hyperparamètres.
    validation_fold: int
    # Les 3 folds restants : entraînement pendant le réglage (avec early stopping).
    tuning_train_folds: list[int]
    # Les 4 folds hors test : entraînement final, réglages fixés, comme dans les articles.
    final_train_folds: list[int]


def esc50_round(test_fold: int, fold_count: int) -> Esc50Round:
    """Rôle des folds d'ESC-50 au tour test_fold (P3, décision de Luciano du 9 novembre).

    Étape 1, le réglage : on entraîne sur 3 folds et on choisit époques et hyperparamètres sur
    le fold suivant (1 après 5). Étape 2, l'entraînement final : on réentraîne sur les 4 folds
    hors test avec ces réglages fixés, puis on évalue sur le fold test_fold. On apprend ainsi
    sur 4 folds, comme tous les articles sur ESC-50, et nos scores restent comparables.
    Un modèle sans early stopping (MFCC + SVM) passe directement à l'étape 2.
    """
    if test_fold < 1 or test_fold > fold_count:
        raise ValueError(f"Fold de test {test_fold} hors de 1 à {fold_count}")
    validation_fold = test_fold % fold_count + 1
    final_train_folds: list[int] = []
    tuning_train_folds: list[int] = []
    for fold in range(1, fold_count + 1):
        if fold == test_fold:
            continue
        final_train_folds.append(fold)
        if fold != validation_fold:
            tuning_train_folds.append(fold)
    return Esc50Round(
        test_fold=test_fold,
        validation_fold=validation_fold,
        tuning_train_folds=tuning_train_folds,
        final_train_folds=final_train_folds,
    )


def check_no_speaker_leak(splits: list[SpeakerSplit]) -> None:
    """Vérifie qu'aucun acteur n'apparaît dans deux parties ; lève ValueError sinon (P1)."""
    split_of_speaker: dict[tuple[str, str], str] = {}
    for speaker_split in splits:
        key = (speaker_split.dataset, speaker_split.speaker)
        known_split = split_of_speaker.get(key)
        if known_split is None:
            split_of_speaker[key] = speaker_split.split
            continue
        raise ValueError(
            f"Fuite : l'acteur {speaker_split.speaker} de {speaker_split.dataset} est à la fois "
            f"en {known_split} et en {speaker_split.split}"
        )


def _count_per_gender(speaker_count: int, ratio: float) -> int:
    # 15 % des acteurs, répartis à égalité entre hommes et femmes :
    # CREMA-D 91 × 0,15 / 2 = 6,8 → 7 par genre ; RAVDESS 24 × 0,15 / 2 = 1,8 → 2 par genre.
    per_gender = round(speaker_count * ratio / 2)
    return max(per_gender, 1)


def _split_for_position(position: int, test_count: int, validation_count: int) -> Split:
    if position < test_count:
        return "test"
    if position < test_count + validation_count:
        return "validation"
    return "train"


def _single_dataset(rows: list[ManifestRow]) -> str:
    datasets = {row.dataset for row in rows}
    if len(datasets) != 1:
        raise ValueError(f"Un découpage se fait jeu par jeu ; reçu : {sorted(datasets)}")
    return next(iter(datasets))


def _gender_of_speaker(rows: list[ManifestRow]) -> dict[str, Gender]:
    # Chaque acteur doit avoir un genre, et un seul : sinon le tirage par genre est faux.
    gender_of_speaker: dict[str, Gender] = {}
    for row in rows:
        if row.speaker is None or row.gender is None:
            raise ValueError(f"Acteur ou genre manquant pour {row.path}")
        known_gender = gender_of_speaker.get(row.speaker)
        if known_gender is not None and known_gender != row.gender:
            raise ValueError(f"L'acteur {row.speaker} a deux genres dans le manifeste")
        gender_of_speaker[row.speaker] = row.gender
    return gender_of_speaker


def _speakers_by_gender(rows: list[ManifestRow]) -> dict[Gender, list[str]]:
    # Acteurs triés : le tirage part toujours de la même liste, quel que soit l'ordre des lignes.
    gender_of_speaker = _gender_of_speaker(rows)
    speakers_by_gender: dict[Gender, list[str]] = {"F": [], "M": []}
    for speaker in sorted(gender_of_speaker):
        gender = gender_of_speaker[speaker]
        speakers_by_gender[gender].append(speaker)
    return speakers_by_gender


def _speaker_sort_key(speaker_split: SpeakerSplit) -> tuple[str, str]:
    return (speaker_split.dataset, speaker_split.speaker)
