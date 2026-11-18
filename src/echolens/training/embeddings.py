"""Représentations des encodeurs gelés de la famille B : calculs et fichiers (C10, Brique 4).

Ce module n'importe jamais torch : la CI n'installe pas l'extra [ml], et ses fonctions sont
testées sans lui. Le passage dans les encodeurs est dans echolens.training.encoders.

Pour chaque extrait, on garde la moyenne dans le temps de CHAQUE couche (hidden_states,
entrée comprise) : un tableau (couches, dimension). La tête de C11 apprend ensuite une somme
pondérée des couches. On peut la faire après la moyenne, car les deux opérations commutent :
moyenne_t(Σ_l w_l·h_l,t) = Σ_l w_l·moyenne_t(h_l,t). On calcule donc les moyennes une seule
fois (R6), et chaque essai de tête ne coûte que quelques secondes.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field, model_validator

from echolens.config import CONFIG_DIR, load_yaml
from echolens.core.data.manifest import ManifestRow

EMBEDDINGS_CONFIG_PATH = CONFIG_DIR / "embeddings.yaml"
EMBEDDINGS_FILE = "embeddings.npy"
INDEX_FILE = "index.csv"
METADATA_FILE = "metadata.json"
INDEX_COLUMNS = ["dataset", "path"]

FloatArray = npt.NDArray[np.float32]


class EncoderConfig(BaseModel):
    """Un encodeur gelé : identifiant court, dépôt Hugging Face et révision figée."""

    id: str
    checkpoint: str
    revision: str = Field(min_length=40, max_length=40)
    kind: Literal["ssl", "whisper"]
    # Whisper seulement : échantillons par trame de sortie, et trames de sortie pour 30 s.
    samples_per_output_frame: int | None = Field(default=None, gt=0)
    max_output_frames: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def check_whisper_frames(self) -> EncoderConfig:
        """Un encodeur Whisper doit dire comment compter ses trames utiles."""
        frames_missing = self.samples_per_output_frame is None or self.max_output_frames is None
        if self.kind == "whisper" and frames_missing:
            raise ValueError(
                f"{self.id} : samples_per_output_frame et max_output_frames sont obligatoires "
                "pour un encodeur Whisper"
            )
        return self


class EmbeddingsConfig(BaseModel):
    """Contenu de configs/embeddings.yaml."""

    sample_rate: int = Field(gt=0)
    encoders: list[EncoderConfig] = Field(min_length=1)
    datasets: list[str] = Field(min_length=1)


class EmbeddingMetadata(BaseModel):
    """Ce qu'il faut savoir pour réutiliser et citer un fichier de représentations."""

    encoder_id: str
    checkpoint: str
    revision: str
    dataset: str
    # Vrai pour la version Whisper « avec remplissage » (moyenne sur les 1 500 trames).
    padded: bool
    torch_version: str
    transformers_version: str
    do_normalize: bool
    layer_count: int
    dimension: int
    clip_count: int
    gpu: str
    compute_seconds: float
    sample_rate: int
    # Whisper seulement : part moyenne des trames utiles sur les 1 500 trames de sortie.
    mean_useful_frame_share: float | None = None


@dataclass(frozen=True)
class EmbeddingFiles:
    """Contenu d'un dossier de représentations, relu par load_embeddings."""

    embeddings: FloatArray
    index: list[tuple[str, str]]
    metadata: EmbeddingMetadata


def manifest_index(rows: list[ManifestRow]) -> list[tuple[str, str]]:
    """Couples (dataset, path) des lignes du manifeste, dans le même ordre."""
    index: list[tuple[str, str]] = []
    for row in rows:
        index.append((row.dataset, row.path))
    return index


def load_embeddings_config(path: Path = EMBEDDINGS_CONFIG_PATH) -> EmbeddingsConfig:
    """Lit configs/embeddings.yaml."""
    content = load_yaml(path)
    return EmbeddingsConfig(**content)


def whisper_useful_frames(sample_count: int, samples_per_frame: int, max_frames: int) -> int:
    """Nombre de trames de sortie de l'encodeur Whisper qui viennent du vrai signal.

    L'encodeur reçoit toujours 30 s : le feature extractor complète l'extrait par du
    silence. Une trame de sortie couvre samples_per_frame échantillons (320, soit 20 ms) :
    on garde ceil(sample_count / samples_per_frame) trames, au moins 1, au plus max_frames.
    Un extrait plus long que 30 s serait coupé par le feature extractor : on le refuse.
    """
    max_samples = samples_per_frame * max_frames
    if sample_count > max_samples:
        raise ValueError(
            f"Extrait trop long pour l'encodeur Whisper : {sample_count} échantillons, "
            f"maximum {max_samples} (30 s à 16 kHz)"
        )
    # Division entière arrondie vers le haut : une trame à moitié remplie compte.
    frame_count = (sample_count + samples_per_frame - 1) // samples_per_frame
    return max(frame_count, 1)


def layer_means(hidden_states: FloatArray, frame_count: int | None = None) -> FloatArray:
    """Moyenne dans le temps de chaque couche : (couches, temps, dimension) → (couches, dimension).

    Avec frame_count, seules les frame_count premières trames comptent (trames utiles de
    Whisper) ; sans, toutes les trames.
    """
    kept = hidden_states
    if frame_count is not None:
        kept = hidden_states[:, :frame_count, :]
    means = kept.mean(axis=1)
    return np.asarray(means, dtype=np.float32)


def save_embeddings(
    directory: Path,
    embeddings: FloatArray,
    index: list[tuple[str, str]],
    metadata: EmbeddingMetadata,
) -> None:
    """Écrit embeddings.npy (extraits, couches, dimension), index.csv et metadata.json.

    Les lignes de embeddings.npy et de index.csv sont dans l'ordre du manifeste.
    """
    if len(embeddings) != len(index):
        raise ValueError(f"{len(embeddings)} représentations pour {len(index)} lignes d'index")
    directory.mkdir(parents=True, exist_ok=True)
    np.save(directory / EMBEDDINGS_FILE, embeddings.astype(np.float32))
    with (directory / INDEX_FILE).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(INDEX_COLUMNS)
        for dataset, path in index:
            writer.writerow([dataset, path])
    metadata_text = json.dumps(metadata.model_dump(), ensure_ascii=False, indent=2)
    (directory / METADATA_FILE).write_text(metadata_text, encoding="utf-8")


def load_embeddings(directory: Path) -> EmbeddingFiles:
    """Relit un dossier écrit par save_embeddings."""
    embeddings = np.load(directory / EMBEDDINGS_FILE)
    index: list[tuple[str, str]] = []
    with (directory / INDEX_FILE).open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            index.append((record["dataset"], record["path"]))
    metadata_text = (directory / METADATA_FILE).read_text(encoding="utf-8")
    metadata = EmbeddingMetadata.model_validate_json(metadata_text)
    return EmbeddingFiles(embeddings=embeddings, index=index, metadata=metadata)


def mean_cosine_of_random_pairs(vectors: FloatArray, pair_count: int, seed: int) -> float:
    """Similarité cosinus moyenne entre pair_count paires d'extraits distincts, tirées au hasard.

    Diagnostic du remplissage de Whisper : si la moyenne inclut 30 s de silence, tous les
    extraits se ressemblent, et la similarité moyenne monte vers 1.
    """
    generator = np.random.default_rng(seed)
    similarities: list[float] = []
    for _ in range(pair_count):
        first, second = generator.choice(len(vectors), size=2, replace=False)
        similarity = _cosine(vectors[first], vectors[second])
        similarities.append(similarity)
    return float(np.mean(similarities))


def _cosine(first: FloatArray, second: FloatArray) -> float:
    dot_product = float(np.dot(first, second))
    norms = float(np.linalg.norm(first) * np.linalg.norm(second))
    return dot_product / norms
