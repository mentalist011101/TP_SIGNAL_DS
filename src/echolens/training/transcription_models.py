"""C17a : transcription d'une phrase avec faster-whisper (CTranslate2), code ml.

Importé seulement par le notebook c17_transcription et le script de latence : le reste du
dépôt n'en dépend pas. Tous les réglages de décodage viennent de configs/transcription.yaml et
sont passés explicitement.
"""

from __future__ import annotations

import ctranslate2
from faster_whisper import WhisperModel
from huggingface_hub import snapshot_download

from echolens.core.audio.segment import FloatArray
from echolens.training.transcription_eval import TranscriptionEvalConfig, TranscriptionModel


def load_whisper(
    model: TranscriptionModel, device: str, compute_type: str, config: TranscriptionEvalConfig
) -> WhisperModel:
    """Télécharge les poids à la révision figée, puis charge le modèle sur device.

    device : « cuda » (float16) ou « cpu » (int8). La graine de CTranslate2 fixe le tirage des
    températures de repli, pour que deux exécutions donnent le même texte.
    """
    # Étape 1 : poids exactement à la révision du fichier de configuration.
    local_path = snapshot_download(repo_id=model.repo_id, revision=model.revision)
    # Étape 2 : graine des tirages aléatoires de CTranslate2.
    ctranslate2.set_random_seed(config.seed)
    # Étape 3 : modèle prêt à transcrire.
    return WhisperModel(
        local_path,
        device=device,
        compute_type=compute_type,
        cpu_threads=config.cpu_threads,
    )


def transcribe(whisper: WhisperModel, signal: FloatArray, config: TranscriptionEvalConfig) -> str:
    """Transcrit un signal mono 16 kHz (load_audio, D1, D2) et renvoie le texte brut."""
    # faster-whisper renvoie un générateur : le calcul n'a lieu que pendant la boucle.
    segments, _ = whisper.transcribe(
        signal,
        language=config.language,
        beam_size=config.beam_size,
        temperature=config.temperature,
        vad_filter=config.vad_filter,
        condition_on_previous_text=config.condition_on_previous_text,
    )
    texts: list[str] = []
    for segment in segments:
        texts.append(segment.text.strip())
    return " ".join(texts)
