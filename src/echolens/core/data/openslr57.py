"""Manifeste d'OpenSLR 57, African Accented French (16 656 fichiers, environ 22 h).

Les audios sont rangés dans speech/<découpage>/<sous-corpus>/.../<locuteur>/<fichier>.wav, et
les transcriptions dans transcripts/<découpage>/..., en fichiers texte : une ligne par extrait,
l'identifiant de l'extrait d'abord, puis le texte. L'identifiant prend plusieurs formes selon le
sous-corpus (chemin .wav, nom .tdf ou nom nu) : on n'en garde que le nom sans extension, qui est
celui du fichier audio. OpenSLR 57 ne sert qu'à l'évaluation : WER et locuteur (P10, P11).

Le texte est gardé tel qu'écrit dans le jeu (P9) : sa normalisation fait partie du calcul du WER
(P12). Un extrait sans transcription garde une transcription vide. Le genre n'est connu que pour
les locuteurs dont le dossier le dit (« cameroon_m_006 ») ; il reste vide pour les autres.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from echolens.core.data.manifest import (
    Gender,
    ManifestRow,
    audio_duration_s,
    check_manifest,
)

DATASET_ID = "openslr57"
SPEECH_FOLDER = "speech"
TRANSCRIPTS_FOLDER = "transcripts"
OfficialSplit = Literal["train", "dev", "devtest", "test"]
OFFICIAL_SPLITS: tuple[OfficialSplit, ...] = ("train", "dev", "devtest", "test")
# Dossier d'un sous-corpus sous speech/<découpage>/ → nom court du sous-corpus.
SUBSET_OF_FOLDER = {
    "ca16": "ca16",
    "yaounde": "yaounde",
    "niger_west_african_fr": "niger",
}
# Lettre du genre dans un dossier de locuteur comme « gabon_f_024 » → format du manifeste.
GENDER_LETTERS: dict[str, Gender] = {"m": "M", "f": "F"}
SPEAKER_NAME_FIELD_COUNT = 3
# Extensions qui suivent parfois l'identifiant d'un extrait dans les transcriptions.
TRANSCRIPT_ID_EXTENSIONS = (".wav", ".tdf")
# Fichiers défectueux connus (illisibles ou de 0 s), exclus du manifeste ; vide pour l'instant.
KNOWN_BAD_FILES: frozenset[str] = frozenset()


def build_openslr57_manifest(dataset_root: Path) -> list[ManifestRow]:
    """Construit le manifeste d'OpenSLR 57 ; dataset_root contient speech/ et transcripts/.

    Une ligne par fichier audio des quatre découpages officiels (P10). Lève ValueError pour un
    sous-corpus inconnu, une transcription contradictoire, ou un fichier illisible ou vide.
    """
    rows: list[ManifestRow] = []
    for official_split in OFFICIAL_SPLITS:
        # Les transcriptions d'un découpage ne servent qu'aux audios de ce découpage.
        transcripts = load_transcripts(dataset_root / TRANSCRIPTS_FOLDER / official_split)
        split_folder = dataset_root / SPEECH_FOLDER / official_split
        audio_paths = sorted(split_folder.rglob("*.wav"))
        for audio_path in audio_paths:
            if audio_path.name in KNOWN_BAD_FILES:
                continue
            row = _row_from_file(audio_path, dataset_root, official_split, transcripts)
            rows.append(row)

    if not rows:
        raise ValueError(f"Aucun fichier WAV sous {dataset_root / SPEECH_FOLDER}")
    check_manifest(rows)
    return rows


def load_transcripts(folder: Path) -> dict[str, str]:
    """Lit tous les fichiers .txt d'un dossier de transcriptions : identifiant → texte.

    L'identifiant est le nom de l'extrait sans dossier ni extension. Lève ValueError si un même
    extrait reçoit deux textes différents.
    """
    transcripts: dict[str, str] = {}
    for text_path in sorted(folder.rglob("*.txt")):
        lines = text_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            parsed = parse_transcript_line(line)
            if parsed is None:
                continue
            utterance_id, text = parsed
            known_text = transcripts.get(utterance_id)
            if known_text is not None and known_text != text:
                raise ValueError(
                    f"OpenSLR 57 : deux transcriptions différentes pour {utterance_id} "
                    f"({text_path.name})"
                )
            transcripts[utterance_id] = text
    return transcripts


def parse_transcript_line(line: str) -> tuple[str, str] | None:
    """Sépare une ligne en (identifiant, texte) ; None pour une ligne vide ou sans texte.

    Formes rencontrées : « niger_sys1_1/niger_sys1_1_088.wav texte »,
    « afc-gabon_16.06.11_002_conv_0023.tdf texte », « cameroon_m_006_001 texte ».
    """
    cleaned = line.strip()
    parts = cleaned.split(maxsplit=1)
    if len(parts) != 2:
        return None
    first_word = parts[0]
    text = parts[1].strip()
    # On retire les dossiers puis l'extension connue. Path(...).stem ne convient pas : les noms
    # contiennent des points (« afc-gabon_16.06.12_019_read_0017 ») qu'il prendrait pour une
    # extension.
    utterance_id = Path(first_word).name
    for extension in TRANSCRIPT_ID_EXTENSIONS:
        if utterance_id.endswith(extension):
            utterance_id = utterance_id.removesuffix(extension)
    return utterance_id, text


def speaker_gender(speaker: str) -> Gender | None:
    """Genre écrit dans le nom du dossier du locuteur (« gabon_f_024 » → « F »), sinon None."""
    fields = speaker.split("_")
    if len(fields) != SPEAKER_NAME_FIELD_COUNT:
        return None
    letter = fields[1]
    return GENDER_LETTERS.get(letter)


def _row_from_file(
    audio_path: Path,
    dataset_root: Path,
    official_split: OfficialSplit,
    transcripts: dict[str, str],
) -> ManifestRow:
    # Étape 1 : le sous-corpus, lu dans le dossier juste sous speech/<découpage>/.
    split_folder = dataset_root / SPEECH_FOLDER / official_split
    path_in_split = audio_path.relative_to(split_folder)
    subset = _subset_of(path_in_split.parts[0], audio_path)
    # Étape 2 : le locuteur est le dossier qui contient le fichier.
    speaker = audio_path.parent.name
    # Étape 3 : durée lue dans l'en-tête ; un fichier illisible ou vide lève une erreur.
    duration_s = audio_duration_s(audio_path)
    relative_path = audio_path.relative_to(dataset_root).as_posix()
    return ManifestRow(
        dataset=DATASET_ID,
        path=relative_path,
        speaker=speaker,
        gender=speaker_gender(speaker),
        duration_s=duration_s,
        official_split=official_split,
        subset=subset,
        transcript=transcripts.get(audio_path.stem),
    )


def _subset_of(folder_name: str, audio_path: Path) -> str:
    """Nom court du sous-corpus ; lève ValueError pour un dossier inconnu."""
    if folder_name not in SUBSET_OF_FOLDER:
        raise ValueError(f"OpenSLR 57 : sous-corpus inconnu « {folder_name} » ({audio_path})")
    return SUBSET_OF_FOLDER[folder_name]
