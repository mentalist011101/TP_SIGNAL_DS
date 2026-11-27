"""Carte Grad-CAM d'une analyse terminée, à superposer au spectrogramme (E7, EF-13, C14).

Décisions de C14 (27 nov.) :
- seuls les réseaux sur log-Mel (famille A, les CRNN du profil Temps réel) ont une carte. Pour
  une analyse en profil Qualité (têtes Whisper), on le dit au lieu d'expliquer un autre modèle
  que celui qui a donné le résultat ;
- la classe expliquée est la classe prédite pour chaque segment ;
- la carte d'une fenêtre est placée sur l'axe du temps du spectrogramme affiché (une colonne
  par trame de 10 ms), puis les cartes des fenêtres sont réunies (core.explain).

La carte est calculée à la première demande, puis gardée dans le dossier de l'analyse.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from echolens.core.audio import load_audio
from echolens.core.audio.segment import FloatArray, Segment, cut_window
from echolens.core.explain import MapPiece, combine_window_maps
from echolens.core.features import log_mel_spectrogram
from echolens.core.inference import segment_samples
from echolens.core.models.registry import Profile, Task
from echolens.services.analysis_service import AnalysisService
from echolens.services.predictor import ExplanationUnavailableError
from echolens.services.spectrogram_image import save_grad_cam_png
from echolens.services.storage import AnalysisRecord, AnalysisStatus

GRAD_CAM_TASKS = [Task.EMOTION.value, Task.SOUND_EVENT.value]
FAMILY_A_MESSAGE = (
    "Grad-CAM : modèles de la famille A seulement (CRNN du profil Temps réel). Relancez "
    "l'analyse en profil Temps réel pour voir la carte."
)


def grad_cam_path(service: AnalysisService, record: AnalysisRecord, task: str) -> Path:
    """PNG de la carte Grad-CAM d'une tâche de l'analyse, calculé une seule fois.

    Lève ExplanationUnavailableError (message en français) si la carte n'existe pas.
    """
    check_explainable(record, task)
    path = service.analysis_dir(record.id) / f"gradcam_{task}.png"
    if path.is_file():
        return path
    grad_map = analysis_grad_cam(service, record, Task(task))
    save_grad_cam_png(grad_map, path)
    return path


def check_explainable(record: AnalysisRecord, task: str) -> None:
    """Lève ExplanationUnavailableError si cette tâche de l'analyse n'a pas de carte possible."""
    if record.status != AnalysisStatus.DONE or record.results is None:
        raise ExplanationUnavailableError("L'analyse n'est pas terminée : pas encore de carte.")
    if task not in record.tasks:
        raise ExplanationUnavailableError(f"Tâche non demandée pour cette analyse : {task}.")
    result = record.results[task]
    if result["status"] != "done":
        raise ExplanationUnavailableError(f"Pas de carte : {result['message']}.")
    if record.profile != Profile.REALTIME:
        raise ExplanationUnavailableError(FAMILY_A_MESSAGE)


def analysis_grad_cam(service: AnalysisService, record: AnalysisRecord, task: Task) -> FloatArray:
    """Carte (bandes, trames) de tout l'audio, de la taille du spectrogramme affiché."""
    # Étape 1 : l'audio converti, et la taille de son spectrogramme (même calcul que l'image).
    signal = load_audio(service.converted_audio_path(record.id))
    config = service.feature_config
    band_count, total_frames = log_mel_spectrogram(signal, config).shape
    frames_per_second = config.sample_rate / config.hop_length
    # Étape 2 : une carte par segment du résultat, posée à la place de ce segment.
    predictor = service.result_context.predictor
    pieces = []
    results: dict[str, Any] = record.results or {}
    for segment in results[task.value]["segments"]:
        window = Segment(start_s=segment["start_s"], end_s=segment["end_s"])
        samples = _window_samples(service, signal, window, task)
        explanation = predictor.explain(task, Profile.REALTIME, samples)
        segment_first_frame = round(window.start_s * frames_per_second)
        first_frame = segment_first_frame + explanation.first_frame
        pieces.append(MapPiece(first_frame=first_frame, values=explanation.values))
    # Étape 3 : les cartes des fenêtres réunies sur tout l'audio, entre 0 et 1.
    return combine_window_maps(band_count, total_frames, pieces)


def _window_samples(
    service: AnalysisService, signal: FloatArray, window: Segment, task: Task
) -> FloatArray:
    # Le même son que celui qu'a vu le modèle (services.results) : fenêtre de 5 s complétée
    # par du silence pour les événements, morceau de parole tel quel pour les émotions.
    if task == Task.SOUND_EVENT:
        window_s = service.result_context.inference_config.sound_event.window_s
        return cut_window(signal, window, window_s)
    return segment_samples(signal, window)
