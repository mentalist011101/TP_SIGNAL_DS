"""C17a : latence de la transcription sur la machine de référence (CPU seul, int8).

L'audio est une sortie du notebook c17_transcription : des phrases de Yaoundé mises bout à bout,
coupées à 30 s (c17_latency_30s.wav). Il n'est jamais commité. Pour chaque modèle de
configs/transcription.yaml : un premier passage non compté (chargement des poids en mémoire,
premières allocations), puis latency_runs essais ; on garde la médiane et le RTF = temps de
calcul / durée de l'audio. RTF < 1 : la transcription va plus vite que l'audio.

Usage, depuis la racine du dépôt (extra [ml]) :
    uv run python training/scripts/measure_transcription_latency.py --audio <c17_latency_30s.wav>
Le résultat est ajouté au champ latency_cpu de training/results/c17_transcription.json.
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from pathlib import Path
from typing import Any

from echolens.config import REPO_ROOT
from echolens.core.audio import load_audio
from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.core.audio.segment import FloatArray
from echolens.training.transcription_eval import (
    TranscriptionEvalConfig,
    TranscriptionModel,
    load_transcription_eval_config,
)
from echolens.training.transcription_models import load_whisper, transcribe

RESULTS_PATH = REPO_ROOT / "training" / "results" / "c17_transcription.json"


def measure_model(
    model: TranscriptionModel, signal: FloatArray, config: TranscriptionEvalConfig
) -> dict[str, Any]:
    """Temps de transcription d'un modèle sur CPU en int8 : essais, médiane et RTF."""
    whisper = load_whisper(model, "cpu", "int8", config)
    # Étape 1 : premier passage non compté.
    transcribe(whisper, signal, config)
    # Étape 2 : essais chronométrés.
    durations: list[float] = []
    for _ in range(config.latency_runs):
        start = time.perf_counter()
        transcribe(whisper, signal, config)
        durations.append(time.perf_counter() - start)
    # Étape 3 : médiane, et RTF = temps de calcul / durée de l'audio.
    median_s = statistics.median(durations)
    audio_s = len(signal) / TARGET_SAMPLE_RATE
    return {
        "runs_s": [round(duration, 2) for duration in durations],
        "median_s": round(median_s, 2),
        "rtf": round(median_s / audio_s, 3),
    }


def main() -> None:
    """Mesure tous les modèles et écrit latency_cpu dans les résultats de C17a."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--machine", default=platform.processor())
    arguments = parser.parse_args()

    config = load_transcription_eval_config()
    signal = load_audio(arguments.audio)
    audio_s = len(signal) / TARGET_SAMPLE_RATE
    measures: dict[str, Any] = {}
    for model in config.models:
        measures[model.id] = measure_model(model, signal, config)
        print(model.id, measures[model.id])

    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    results["latency_cpu"] = {
        "machine": arguments.machine,
        "device": "cpu",
        "compute_type": "int8",
        "cpu_threads": config.cpu_threads,
        "audio_s": round(audio_s, 2),
        "runs": config.latency_runs,
        "models": measures,
    }
    text = json.dumps(results, indent=2, ensure_ascii=False) + "\n"
    RESULTS_PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
