"""Évaluation du clonage de voix (EF-18, C35b) : la partie sans modèle, testée en CI.

Deux mesures sur les voix consentantes de l'équipe (configs/voice_cloning_eval.yaml) :
- ressemblance : cosinus ECAPA entre chaque clone et la voix de référence de la personne
  (moyenne normée des vecteurs de ses extraits, règle de C15). Deux témoins : les vraies
  phrases de la personne (ce qu'obtient sa vraie voix) et les clones des autres membres (ce
  qu'obtient une autre voix). La part des clones au-dessus du seuil « inconnu » de C15 dit si
  notre propre identification se laisse tromper ;
- intelligibilité : WER de Whisper sur les clones contre le texte demandé, normalisation P12.

Le notebook c35_evaluation_clonage.ipynb fait les calculs avec les modèles.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel, Field

from echolens.config import CONFIG_DIR, load_yaml
from echolens.core.speaker_id import VoiceVector, unit_vector
from echolens.training.transcription_eval import SentenceScore, error_rates

CLONING_EVAL_CONFIG_PATH = CONFIG_DIR / "voice_cloning_eval.yaml"


class CloningEvalConfig(BaseModel):
    """Contenu de configs/voice_cloning_eval.yaml."""

    consent_file: str
    reference_folder: str
    test_folder: str
    speaker_encoder: str
    transcription_model: str
    sentences: list[str] = Field(min_length=1)


@dataclass(frozen=True)
class TeamVoice:
    """Une personne de l'équipe : ses extraits de référence et ses vraies phrases témoins."""

    name: str
    reference_paths: list[Path]
    test_paths: list[Path]


class MissingConsentError(ValueError):
    """Un dossier de voix n'a pas de consentement écrit : on ne clone pas (ENF-10)."""


def load_cloning_eval_config(path: Path = CLONING_EVAL_CONFIG_PATH) -> CloningEvalConfig:
    """Lit configs/voice_cloning_eval.yaml."""
    content = load_yaml(path)
    return CloningEvalConfig(**content)


def find_team_voices(root: Path, config: CloningEvalConfig) -> list[TeamVoice]:
    """Un dossier par personne, dans l'ordre alphabétique ; refuse tout dossier sans
    consentement écrit, ou sans extrait de référence ou de test."""
    voices: list[TeamVoice] = []
    for folder in sorted(path for path in root.iterdir() if path.is_dir()):
        if not (folder / config.consent_file).is_file():
            raise MissingConsentError(
                f"{folder.name} : pas de {config.consent_file}, sa voix ne sera pas clonée."
            )
        references = sorted((folder / config.reference_folder).glob("*.wav"))
        tests = sorted((folder / config.test_folder).glob("*.wav"))
        if not references or not tests:
            raise ValueError(f"{folder.name} : il faut des WAV dans reference/ et dans test/.")
        voices.append(TeamVoice(name=folder.name, reference_paths=references, test_paths=tests))
    return voices


def cosine_scores(vectors: list[np.ndarray], voice: VoiceVector) -> list[float]:
    """Cosinus de chaque vecteur avec une voix de norme 1 (C15)."""
    scores: list[float] = []
    for vector in vectors:
        score = float(unit_vector(vector) @ voice)
        scores.append(score)
    return scores


def similarity_summary(scores: list[float], threshold: float) -> dict[str, float]:
    """Moyenne, minimum, maximum, et part des scores au-dessus du seuil « inconnu »."""
    values = np.array(scores, dtype=np.float64)
    accepted = values >= threshold
    return {
        "count": float(len(values)),
        "mean": float(values.mean()),
        "min": float(values.min()),
        "max": float(values.max()),
        "share_above_threshold": float(accepted.mean()),
    }


def wer_summary(scores: list[SentenceScore]) -> dict[str, Any]:
    """WER et CER sur toutes les phrases (total des erreurs / total des mots), et les phrases."""
    wer, cer = error_rates(scores)
    sentences = []
    for score in scores:
        sentences.append({"reference": score.reference, "hypothesis": score.hypothesis})
    return {"wer": wer, "cer": cer, "sentences": sentences}


def voice_report(
    clone_scores: list[float],
    real_scores: list[float],
    other_clone_scores: list[float],
    transcriptions: list[SentenceScore],
    threshold: float,
) -> dict[str, Any]:
    """Résultat d'une personne : ressemblance des clones et de ses deux témoins, puis WER.

    other_clone_scores : clones des AUTRES membres comparés à cette voix ; liste vide s'il n'y
    a qu'une personne.
    """
    report: dict[str, Any] = {
        "clones": similarity_summary(clone_scores, threshold),
        "real_sentences": similarity_summary(real_scores, threshold),
        "transcription": wer_summary(transcriptions),
    }
    if other_clone_scores:
        report["other_voices_clones"] = similarity_summary(other_clone_scores, threshold)
    return report
