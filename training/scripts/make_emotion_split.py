"""C4 : tire une seule fois le découpage des acteurs des jeux d'émotions (P1, règles Ly2).

Lit data/manifests/cremad.csv et data/manifests/ravdess.csv, et écrit
data/splits/emotion_split.csv (une ligne par acteur, sans audio), à versionner dans git.
Pas besoin des fichiers audio : tout est dans les manifestes.

Usage, depuis la racine du dépôt :
    uv run python training/scripts/make_emotion_split.py
"""

from __future__ import annotations

from collections import Counter

from echolens.config import REPO_ROOT
from echolens.core.data.manifest import load_manifest
from echolens.core.data.splits import (
    SpeakerSplit,
    check_no_speaker_leak,
    load_split_config,
    save_speaker_splits,
    split_emotion_speakers,
)

MANIFESTS_DIR = REPO_ROOT / "data" / "manifests"
OUTPUT_PATH = REPO_ROOT / "data" / "splits" / "emotion_split.csv"


def main() -> None:
    config = load_split_config()
    all_splits: list[SpeakerSplit] = []
    # Étape 1 : un tirage par jeu d'entraînement, chacun avec la même graine.
    for dataset in config.training_emotion_datasets:
        manifest_path = MANIFESTS_DIR / f"{dataset}.csv"
        rows = load_manifest(manifest_path)
        splits = split_emotion_speakers(rows, config)
        all_splits.extend(splits)
    # Étape 2 : contrôle de fuite avant d'écrire quoi que ce soit.
    check_no_speaker_leak(all_splits)
    save_speaker_splits(all_splits, OUTPUT_PATH)
    # Étape 3 : résumé à recopier dans le rapport (acteurs par jeu, partie et genre).
    counts: Counter[tuple[str, str, str]] = Counter()
    for speaker_split in all_splits:
        key = (speaker_split.dataset, speaker_split.split, speaker_split.gender)
        counts[key] += 1
    print(f"Découpage écrit dans {OUTPUT_PATH}")
    for key in sorted(counts):
        dataset, split, gender = key
        print(f"  {dataset:8} {split:10} {gender} : {counts[key]} acteurs")


if __name__ == "__main__":
    main()
