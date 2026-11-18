"""Passage des extraits dans les encodeurs gelés de la famille B (C10, Brique 4, R7).

Seul module qui importe torch et transformers (extra [ml], installés d'office sur Kaggle).
Les calculs purs (trames utiles de Whisper, moyennes par couche, fichiers) sont dans
echolens.training.embeddings, testés en CI sans torch.

Règles (R7, Brique 4) : signal brut 16 kHz de load_audio, extrait entier, sans débruitage ni
VAD ; normalisation du feature extractor de chaque modèle ; un extrait à la fois, sans
remplissage ni masque d'attention ; model.eval(), torch.no_grad(), float32.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import transformers
from transformers import AutoFeatureExtractor, AutoModel, WhisperModel

from echolens.core.audio import load_audio
from echolens.core.data.manifest import ManifestRow, audio_path
from echolens.training.embeddings import (
    EmbeddingMetadata,
    EncoderConfig,
    FloatArray,
    layer_means,
    whisper_useful_frames,
)

# Affiche l'avancement tous les PROGRESS_EVERY extraits.
PROGRESS_EVERY = 500


@dataclass(frozen=True)
class LoadedEncoder:
    """Un encodeur prêt à l'emploi : configuration, feature extractor et modèle gelé."""

    config: EncoderConfig
    # Feature extractor de transformers (Wav2Vec2FeatureExtractor ou WhisperFeatureExtractor).
    feature_extractor: Any
    model: torch.nn.Module
    device: torch.device
    sample_rate: int


@dataclass(frozen=True)
class WhisperEmbedding:
    """Les deux moyennes d'un extrait, tirées d'un seul passage dans l'encodeur Whisper."""

    useful_mean: FloatArray
    padded_mean: FloatArray
    # Part des 1 500 trames de sortie qui viennent du vrai signal.
    useful_share: float


@dataclass(frozen=True)
class ManifestEmbeddings:
    """Représentations de toutes les lignes d'un manifeste, dans le même ordre."""

    # (extraits, couches, dimension) ; pour Whisper, moyenne sur les trames utiles.
    embeddings: FloatArray
    # Whisper seulement : moyenne sur les 1 500 trames, remplissage compris.
    padded: FloatArray | None
    # Whisper seulement : part moyenne des trames utiles.
    mean_useful_frame_share: float | None
    compute_seconds: float


def load_encoder(config: EncoderConfig, sample_rate: int, device: torch.device) -> LoadedEncoder:
    """Charge un encodeur gelé et son feature extractor, à la révision figée de la config."""
    feature_extractor = AutoFeatureExtractor.from_pretrained(
        config.checkpoint, revision=config.revision
    )
    model = _load_model(config)
    # Encodeur gelé : mode évaluation (dropout coupé), poids en float32, sur le GPU choisi.
    model.eval()
    model.to(device=device, dtype=torch.float32)
    return LoadedEncoder(
        config=config,
        feature_extractor=feature_extractor,
        model=model,
        device=device,
        sample_rate=sample_rate,
    )


def feature_extractor_normalizes(encoder: LoadedEncoder) -> bool:
    """Valeur de do_normalize du feature extractor (moyenne 0, variance 1 par extrait).

    Le feature extractor de Whisper n'a pas cet attribut : il ne normalise le signal que
    si on le lui demande à l'appel, ce que l'on ne fait pas. On renvoie alors False.
    """
    value = getattr(encoder.feature_extractor, "do_normalize", False)
    return bool(value)


def embed_ssl(signal: FloatArray, encoder: LoadedEncoder) -> FloatArray:
    """Moyennes par couche d'un extrait pour wav2vec 2.0 ou mHuBERT : (13, 768)."""
    # Étape 1 : normalisation du feature extractor, sur l'extrait entier, sans remplissage.
    inputs = encoder.feature_extractor(
        signal, sampling_rate=encoder.sample_rate, padding=False, return_tensors="pt"
    )
    input_values = inputs["input_values"].to(encoder.device)
    # Étape 2 : un seul extrait, donc aucun masque d'attention (wav2vec2-base n'en utilise pas).
    with torch.no_grad():
        outputs = encoder.model(input_values, output_hidden_states=True)
    # Étape 3 : toutes les sorties de couches, entrée comprise, moyennées dans le temps.
    hidden_states = _stack_hidden_states(outputs.hidden_states)
    return layer_means(hidden_states)


def embed_whisper(signal: FloatArray, encoder: LoadedEncoder) -> WhisperEmbedding:
    """Moyennes par couche d'un extrait pour l'encodeur Whisper : (7, 512), deux versions."""
    samples_per_frame, max_frames = _whisper_frame_settings(encoder.config)
    # Étape 1 : trames utiles (50 par seconde) ; refuse un extrait de plus de 30 s.
    useful_frames = whisper_useful_frames(len(signal), samples_per_frame, max_frames)
    # Étape 2 : log-Mel de Whisper, complété jusqu'à 30 s : l'encodeur exige 3 000 trames.
    inputs = encoder.feature_extractor(
        signal, sampling_rate=encoder.sample_rate, padding="max_length", return_tensors="pt"
    )
    input_features = inputs["input_features"].to(encoder.device)
    with torch.no_grad():
        outputs = encoder.model(input_features, output_hidden_states=True)
    hidden_states = _stack_hidden_states(outputs.hidden_states)
    # Étape 3 : moyenne sur les seules trames utiles (Brique 4) et, à part, sur les 1 500
    # trames, pour mesurer l'effet du remplissage.
    useful_mean = layer_means(hidden_states, useful_frames)
    padded_mean = layer_means(hidden_states)
    useful_share = useful_frames / max_frames
    return WhisperEmbedding(
        useful_mean=useful_mean, padded_mean=padded_mean, useful_share=useful_share
    )


def embed_manifest(
    rows: list[ManifestRow], datasets_dir: Path, encoder: LoadedEncoder
) -> ManifestEmbeddings:
    """Représentations de chaque ligne du manifeste, dans l'ordre, un extrait à la fois."""
    start = time.perf_counter()
    means: list[FloatArray] = []
    padded_means: list[FloatArray] = []
    useful_shares: list[float] = []
    for position, row in enumerate(rows):
        # Même entrée que l'application : mono 16 kHz float32 (D1, D2), extrait entier.
        path = audio_path(row, datasets_dir)
        signal = load_audio(path, sample_rate=encoder.sample_rate)
        if encoder.config.kind == "ssl":
            means.append(embed_ssl(signal, encoder))
        else:
            whisper = embed_whisper(signal, encoder)
            means.append(whisper.useful_mean)
            padded_means.append(whisper.padded_mean)
            useful_shares.append(whisper.useful_share)
        _print_progress(position + 1, len(rows), encoder.config.id)
    seconds = time.perf_counter() - start
    return _collect(means, padded_means, useful_shares, seconds)


def make_metadata(
    encoder: LoadedEncoder, dataset: str, result: ManifestEmbeddings, padded: bool
) -> EmbeddingMetadata:
    """Métadonnées d'un fichier de représentations (version « utile » ou « avec remplissage »)."""
    embeddings = result.embeddings
    if padded and result.padded is not None:
        embeddings = result.padded
    clip_count, layer_count, dimension = embeddings.shape
    return EmbeddingMetadata(
        encoder_id=encoder.config.id,
        checkpoint=encoder.config.checkpoint,
        revision=encoder.config.revision,
        dataset=dataset,
        padded=padded,
        torch_version=torch.__version__,
        transformers_version=transformers.__version__,
        do_normalize=feature_extractor_normalizes(encoder),
        layer_count=layer_count,
        dimension=dimension,
        clip_count=clip_count,
        gpu=device_name(encoder.device),
        compute_seconds=result.compute_seconds,
        sample_rate=encoder.sample_rate,
        mean_useful_frame_share=result.mean_useful_frame_share,
    )


def device_name(device: torch.device) -> str:
    """Nom lisible du processeur de calcul (« Tesla T4 » ou « cpu »)."""
    if device.type == "cuda":
        return str(torch.cuda.get_device_name(device))
    return str(device.type)


def _load_model(config: EncoderConfig) -> torch.nn.Module:
    if config.kind == "whisper":
        # Encodeur seul : le décodeur (texte) ne sert pas à représenter l'audio.
        whisper = WhisperModel.from_pretrained(config.checkpoint, revision=config.revision)
        encoder: torch.nn.Module = whisper.get_encoder()
        return encoder
    model: torch.nn.Module = AutoModel.from_pretrained(config.checkpoint, revision=config.revision)
    return model


def _stack_hidden_states(hidden_states: tuple[torch.Tensor, ...]) -> FloatArray:
    # Tuple de (1, temps, dimension), un par sortie de couche → (couches, temps, dimension).
    stacked = torch.stack(hidden_states, dim=0)
    single_clip = stacked[:, 0, :, :]
    as_numpy = single_clip.cpu().numpy()
    return np.asarray(as_numpy, dtype=np.float32)


def _whisper_frame_settings(config: EncoderConfig) -> tuple[int, int]:
    # EncoderConfig garantit ces deux valeurs pour Whisper ; ce test sert au typage.
    if config.samples_per_output_frame is None or config.max_output_frames is None:
        raise ValueError(f"{config.id} : réglages de trames Whisper manquants")
    return config.samples_per_output_frame, config.max_output_frames


def _collect(
    means: list[FloatArray],
    padded_means: list[FloatArray],
    useful_shares: list[float],
    seconds: float,
) -> ManifestEmbeddings:
    embeddings = np.stack(means).astype(np.float32)
    padded = None
    mean_share = None
    if padded_means:
        padded = np.stack(padded_means).astype(np.float32)
        mean_share = float(np.mean(useful_shares))
    return ManifestEmbeddings(
        embeddings=embeddings,
        padded=padded,
        mean_useful_frame_share=mean_share,
        compute_seconds=seconds,
    )


def _print_progress(done: int, total: int, encoder_id: str) -> None:
    if done % PROGRESS_EVERY == 0 or done == total:
        print(f"{encoder_id} : {done} / {total} extraits")
