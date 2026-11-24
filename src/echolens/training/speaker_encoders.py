"""Vecteurs de voix pour l'évaluation du locuteur (C15) : ECAPA-TDNN et mHuBERT.

Ce module importe torch, speechbrain et transformers (extra [ml], sur Kaggle). Les scores sont
calculés sans torch dans echolens.training.speaker_eval, testé en CI.

Chaque phrase est lue par load_audio (mono 16 kHz float32, D1, D2), sans débruitage ni VAD,
puis coupée à max_seconds (configs/speaker.yaml) pour borner la mémoire du GPU.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from huggingface_hub import snapshot_download
from speechbrain.inference.speaker import EncoderClassifier

from echolens.core.audio import load_audio
from echolens.core.data.manifest import ManifestRow, audio_path
from echolens.core.data.speaker_enrollment import SpeakerConfig, SpeakerEncoderConfig
from echolens.training.embeddings import EncoderConfig
from echolens.training.encoders import LoadedEncoder, embed_ssl, load_encoder
from echolens.training.speaker_eval import EmbeddingsByPath

# Affiche l'avancement tous les PROGRESS_EVERY extraits.
PROGRESS_EVERY = 1000


def load_ecapa(config: SpeakerEncoderConfig, savedir: Path, device: torch.device) -> Any:
    """Charge ECAPA-TDNN (SpeechBrain), gelé, à la révision figée dans configs/speaker.yaml."""
    # Étape 1 : téléchargement du dépôt à la révision exacte. SpeechBrain ne sait pas choisir une
    # révision lui-même : on lui donne ensuite le dossier local.
    local_dir = snapshot_download(repo_id=config.checkpoint, revision=config.revision)
    # Étape 2 : construction du modèle à partir de ce dossier.
    model = EncoderClassifier.from_hparams(
        source=local_dir,
        savedir=str(savedir),
        run_opts={"device": str(device)},
    )
    # Encodeur gelé : mode évaluation (dropout et normalisation de lot figés).
    model.eval()
    return model


def load_ssl(config: SpeakerEncoderConfig, sample_rate: int, device: torch.device) -> LoadedEncoder:
    """Charge mHuBERT avec le même code que pour les émotions (C10)."""
    if config.revision is None:
        raise ValueError(f"{config.id} : la révision doit être figée dans configs/speaker.yaml")
    ssl_config = EncoderConfig(
        id=config.id, checkpoint=config.checkpoint, revision=config.revision, kind="ssl"
    )
    return load_encoder(ssl_config, sample_rate, device)


def embed_ecapa(signal: np.ndarray, model: Any, device: torch.device) -> np.ndarray:
    """Vecteur ECAPA d'une phrase : 192 valeurs."""
    # Étape 1 : un lot d'une seule phrase, forme (1, échantillons).
    batch = torch.from_numpy(signal).unsqueeze(0).to(device)
    # Étape 2 : passage dans l'encodeur, sans calcul de gradient ; sortie (1, 1, 192).
    with torch.no_grad():
        output = model.encode_batch(batch)
    vector: np.ndarray = output.squeeze().cpu().numpy()
    return vector.astype(np.float32)


def embed_rows(
    rows: list[ManifestRow],
    datasets_dir: Path,
    encoder: Any,
    encoder_config: SpeakerEncoderConfig,
    config: SpeakerConfig,
    device: torch.device,
) -> EmbeddingsByPath:
    """Vecteur de chaque phrase, rangé par chemin ; mHuBERT donne (couches, dimension)."""
    start = time.perf_counter()
    max_samples = int(config.max_seconds * config.sample_rate)
    result: EmbeddingsByPath = {}
    for position, row in enumerate(rows):
        path = audio_path(row, datasets_dir)
        signal = load_audio(path, sample_rate=config.sample_rate)
        # Seul le début des très longs extraits est gardé (max_seconds).
        signal = signal[:max_samples]
        if encoder_config.kind == "ecapa":
            result[row.path] = embed_ecapa(signal, encoder, device)
        else:
            result[row.path] = embed_ssl(signal, encoder)
        _print_progress(position + 1, len(rows), encoder_config.id, start)
    return result


def _print_progress(done: int, total: int, encoder_id: str, start: float) -> None:
    if done % PROGRESS_EVERY != 0 and done != total:
        return
    seconds = time.perf_counter() - start
    print(f"{encoder_id} : {done} / {total} extraits ({seconds:.0f} s)")
