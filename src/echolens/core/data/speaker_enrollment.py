"""Découpage pour l'identification du locuteur (P11, C15).

Pour reconnaître une voix, il faut l'avoir entendue avant : on ne sépare donc pas les
locuteurs, on sépare leurs PHRASES. Pour chaque locuteur, 5 phrases tirées au hasard servent
à « enregistrer » sa voix, les autres servent au test (P11).

Les locuteurs sont ensuite répartis en deux groupes. Le groupe de calibration sert à choisir le
seuil « locuteur inconnu » (et, pour mHuBERT, la couche) ; le groupe d'évaluation sert à mesurer
les scores avec ce seuil. Choisir et mesurer sur les mêmes voix gonflerait le score (P11).

Un locuteur est identifié par « sous-corpus/dossier » : le même dossier ca16 (« 002 ») apparaît
dans train et dans devtest, et c'est la même personne (même date d'enregistrement).
"""

from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from echolens.config import CONFIG_DIR, load_yaml
from echolens.core.data.manifest import ManifestRow

SPEAKER_CONFIG_PATH = CONFIG_DIR / "speaker.yaml"
SpeakerGroup = Literal["calibration", "evaluation"]
# Ordre d'attribution des groupes : un locuteur sur deux dans chaque sous-corpus.
GROUP_ORDER: list[SpeakerGroup] = ["calibration", "evaluation"]
ENROLLMENT_COLUMNS = ["speaker", "subset", "group", "role", "path"]


class SpeakerEncoderConfig(BaseModel):
    """Un encodeur de voix : identifiant court, dépôt Hugging Face et révision figée."""

    id: str
    checkpoint: str
    revision: str | None = None
    kind: Literal["ecapa", "ssl"]


class SpeakerConfig(BaseModel):
    """Paramètres de l'évaluation du locuteur, lus dans configs/speaker.yaml."""

    seed: int
    enrollment_per_speaker: int = Field(gt=0)
    min_utterances_per_speaker: int = Field(gt=0)
    sample_rate: int = Field(gt=0)
    max_seconds: float = Field(gt=0)
    encoders: list[SpeakerEncoderConfig]


class SpeakerUtterances(BaseModel):
    """Un locuteur gardé : son groupe, ses phrases d'enregistrement et ses phrases de test."""

    speaker: str
    subset: str
    group: SpeakerGroup
    enrollment_paths: list[str]
    test_paths: list[str]


def load_speaker_config(path: Path = SPEAKER_CONFIG_PATH) -> SpeakerConfig:
    """Lit configs/speaker.yaml."""
    content = load_yaml(path)
    return SpeakerConfig(**content)


def speaker_key(row: ManifestRow) -> str:
    """Identifiant unique d'un locuteur : « sous-corpus/dossier » (ca16/002, yaounde/ctell1-01)."""
    if row.speaker is None:
        raise ValueError(f"Locuteur manquant pour {row.path}")
    return f"{row.subset}/{row.speaker}"


def split_enrollment(rows: list[ManifestRow], config: SpeakerConfig) -> list[SpeakerUtterances]:
    """Sépare les phrases de chaque locuteur entre enregistrement et test, puis forme les groupes.

    Les locuteurs qui ont moins de min_utterances_per_speaker phrases sont écartés (P11).
    Le tirage est déterministe : même manifeste et même graine donnent le même résultat.
    """
    paths_by_speaker = _paths_by_speaker(rows)
    subset_of_speaker = _subset_of_speaker(rows)
    group_of_speaker = _assign_groups(paths_by_speaker, subset_of_speaker, config)
    # Un seul générateur, créé une fois, parcouru dans l'ordre alphabétique des locuteurs.
    generator = random.Random(config.seed)
    result: list[SpeakerUtterances] = []
    for speaker in sorted(group_of_speaker):
        paths = sorted(paths_by_speaker[speaker])
        enrollment = generator.sample(paths, config.enrollment_per_speaker)
        enrollment_set = set(enrollment)
        test = [path for path in paths if path not in enrollment_set]
        item = SpeakerUtterances(
            speaker=speaker,
            subset=subset_of_speaker[speaker],
            group=group_of_speaker[speaker],
            enrollment_paths=sorted(enrollment),
            test_paths=test,
        )
        result.append(item)
    return result


def save_enrollment(speakers: list[SpeakerUtterances], path: Path) -> None:
    """Écrit le découpage P11 en CSV (une ligne par phrase, sans audio), pour le versionner."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(ENROLLMENT_COLUMNS)
        for speaker in speakers:
            for audio in speaker.enrollment_paths:
                writer.writerow(
                    [speaker.speaker, speaker.subset, speaker.group, "enrollment", audio]
                )
            for audio in speaker.test_paths:
                writer.writerow([speaker.speaker, speaker.subset, speaker.group, "test", audio])


def _paths_by_speaker(rows: list[ManifestRow]) -> dict[str, list[str]]:
    paths_by_speaker: dict[str, list[str]] = {}
    for row in rows:
        key = speaker_key(row)
        paths_by_speaker.setdefault(key, []).append(row.path)
    return paths_by_speaker


def _subset_of_speaker(rows: list[ManifestRow]) -> dict[str, str]:
    subset_of_speaker: dict[str, str] = {}
    for row in rows:
        subset_of_speaker[speaker_key(row)] = str(row.subset)
    return subset_of_speaker


def _assign_groups(
    paths_by_speaker: dict[str, list[str]],
    subset_of_speaker: dict[str, str],
    config: SpeakerConfig,
) -> dict[str, SpeakerGroup]:
    # Étape 1 : locuteurs gardés (assez de phrases), rangés par sous-corpus.
    speakers_by_subset: dict[str, list[str]] = {}
    for speaker in sorted(paths_by_speaker):
        if len(paths_by_speaker[speaker]) < config.min_utterances_per_speaker:
            continue
        subset = subset_of_speaker[speaker]
        speakers_by_subset.setdefault(subset, []).append(speaker)
    # Étape 2 : dans chaque sous-corpus, ordre tiré au hasard, puis un locuteur sur deux dans
    # chaque groupe. Les deux groupes ont ainsi les mêmes accents et la même taille.
    generator = random.Random(config.seed)
    group_of_speaker: dict[str, SpeakerGroup] = {}
    for subset in sorted(speakers_by_subset):
        speakers = speakers_by_subset[subset]
        generator.shuffle(speakers)
        for position, speaker in enumerate(speakers):
            group_index = position % len(GROUP_ORDER)
            group_of_speaker[speaker] = GROUP_ORDER[group_index]
    return group_of_speaker
