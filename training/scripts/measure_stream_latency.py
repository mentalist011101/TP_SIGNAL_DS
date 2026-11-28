"""C23 : latence du flux micro en direct, de bout en bout, avec les vrais modèles (ENF-01, ENF-02).

L'application tourne avec les modèles du registre (profil temps réel) dans un vrai serveur, et
ce script joue le rôle du navigateur : il envoie de la parole en PCM Int16 à 16 kHz, par
morceaux de 100 ms, au rythme réel, par le WebSocket /ws/stream. Il garde, pour chaque
fenêtre :
- le temps de calcul donné par le serveur (critère de fin de C23 : p95 < H = 0,5 s) ;
- la latence perçue : arrivée du résultat moins envoi du dernier morceau de la fenêtre.

Les modèles du profil temps réel sont chargés et chauffés avant la mesure, comme avec
ECHOLENS_PRELOAD_MODELS en démo. Le client et le serveur tournent dans le même processus :
sur la machine de démo, le navigateur est un autre processus, ce qui ne peut qu'aider.

Usage, depuis la racine du dépôt (extra [ml], Internet pour télécharger les modèles une fois) :
    uv run python training/scripts/measure_stream_latency.py --audio <wav> [<wav> ...]
"""

from __future__ import annotations

import argparse
import json
import platform
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from simple_websocket import Client
from werkzeug.serving import make_server

from echolens.api import create_app
from echolens.config import REPO_ROOT, AppSettings
from echolens.core.audio import load_audio
from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.core.models.registry import Profile, Task
from echolens.services.analysis_service import AnalysisService
from echolens.services.results import build_results

RESULTS_PATH = REPO_ROOT / "training" / "results" / "c23_stream_latency.json"
CHUNK_S = 0.1
PAUSE_S = 0.3
WARMUP_WINDOWS = 5
INT16_MAX = 32767


def speech_signal(paths: list[Path], seconds: float) -> np.ndarray:
    """Les extraits mis bout à bout, séparés de PAUSE_S de silence, répétés jusqu'à `seconds`."""
    pause = np.zeros(int(PAUSE_S * TARGET_SAMPLE_RATE), dtype=np.float32)
    pieces = []
    for path in paths:
        pieces.append(load_audio(path))
        pieces.append(pause)
    one_pass = np.concatenate(pieces)
    repeats = int(np.ceil(seconds * TARGET_SAMPLE_RATE / len(one_pass)))
    looped = np.tile(one_pass, repeats)
    return looped[: int(seconds * TARGET_SAMPLE_RATE)]


def warm_up(service: AnalysisService) -> list[str]:
    """Charge les modèles du profil temps réel, puis analyse quelques fenêtres non comptées."""
    context = service.result_context
    tasks = context.inference_config.stream.tasks
    model_ids = []
    for task_name in tasks:
        info = context.predictor.model_info(Task(task_name), Profile.REALTIME)
        model_ids.append(info.model_id)
    window = np.zeros(int(2 * TARGET_SAMPLE_RATE), dtype=np.float32)
    window[: TARGET_SAMPLE_RATE // 2] = 0.1
    for _ in range(WARMUP_WINDOWS):
        build_results(window, tasks, Profile.REALTIME, context)
    return model_ids


def to_pcm16(samples: np.ndarray) -> bytes:
    clipped = np.clip(samples, -1.0, 1.0)
    return np.round(clipped * INT16_MAX).astype("<i2").tobytes()


def stream_speech(url: str, signal: np.ndarray) -> tuple[list[dict[str, Any]], list[float]]:
    """Envoie le signal au rythme réel ; renvoie les fenêtres reçues et les latences perçues."""
    chunk_samples = int(CHUNK_S * TARGET_SAMPLE_RATE)
    client = Client.connect(url)
    client.send(json.dumps({"type": "start", "record": False}))
    sent_ends: list[tuple[int, float]] = []
    windows: list[dict[str, Any]] = []
    latencies_ms: list[float] = []
    start = time.perf_counter()
    for index, first in enumerate(range(0, len(signal), chunk_samples)):
        # Étape 1 : attendre l'heure de ce morceau (rythme réel), puis l'envoyer.
        due = start + index * CHUNK_S
        time.sleep(max(0.0, due - time.perf_counter()))
        chunk = signal[first : first + chunk_samples]
        client.send(to_pcm16(chunk))
        sent_ends.append((first + len(chunk), time.perf_counter()))
        # Étape 2 : lire sans attendre les résultats déjà arrivés.
        collect(client, sent_ends, windows, latencies_ms, timeout=0)
    client.send(json.dumps({"type": "stop"}))
    collect(client, sent_ends, windows, latencies_ms, timeout=10)
    return windows, latencies_ms


def collect(
    client: Client,
    sent_ends: list[tuple[int, float]],
    windows: list[dict[str, Any]],
    latencies_ms: list[float],
    timeout: float,
) -> None:
    """Lit les messages disponibles ; pour chaque fenêtre, calcule sa latence perçue."""
    while True:
        try:
            text = client.receive(timeout=timeout)
        except Exception:
            return
        if text is None:
            return
        message = json.loads(text)
        if message["type"] != "window":
            continue
        arrived = time.perf_counter()
        end_sample = round(message["end_s"] * TARGET_SAMPLE_RATE)
        sent_at = next(when for sample, when in sent_ends if sample >= end_sample)
        windows.append(message)
        latencies_ms.append((arrived - sent_at) * 1000)


def summary(values: list[float]) -> dict[str, float]:
    array = np.array(values)
    return {
        "p50_ms": round(float(np.percentile(array, 50)), 1),
        "p95_ms": round(float(np.percentile(array, 95)), 1),
        "max_ms": round(float(array.max()), 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, nargs="+", required=True)
    parser.add_argument("--seconds", type=float, default=120.0)
    parser.add_argument("--models-dir", type=Path, default=None)
    parser.add_argument("--machine", default=platform.processor(), help="Nom du processeur")
    args = parser.parse_args()
    signal = speech_signal(args.audio, args.seconds)
    # Étape 1 : l'application avec les vrais modèles, dans un vrai serveur.
    data_dir = Path(tempfile.mkdtemp())
    settings = AppSettings(
        data_dir=data_dir,
        web_dist_dir=data_dir,
        inference_backend="models",
        models_dir=args.models_dir,
    )
    app = create_app(settings)
    service: AnalysisService = app.extensions["analysis_service"]
    model_ids = warm_up(service)
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # Étape 2 : la parole au rythme réel, puis les mesures.
    url = f"ws://127.0.0.1:{server.server_port}/ws/stream"
    windows, latencies_ms = stream_speech(url, signal)
    server.shutdown()
    write_results(args, service, model_ids, windows, latencies_ms)


def write_results(
    args: argparse.Namespace,
    service: AnalysisService,
    model_ids: list[str],
    windows: list[dict[str, Any]],
    latencies_ms: list[float],
) -> None:
    stream = service.result_context.inference_config.stream
    compute_ms = [window["compute_ms"] for window in windows]
    rtf = [window["rtf"] for window in windows]
    speech = [window for window in windows if window["speech"]]
    compute = summary(compute_ms)
    result = {
        "task": "C23",
        "machine": args.machine,
        # Fils de calcul de torch pendant la mesure.
        "torch_threads": torch.get_num_threads(),
        "torch": torch.__version__,
        "speech_detector": service.result_context.speech_detector.name,
        "models": model_ids,
        "audio": [path.name for path in args.audio],
        "seconds": args.seconds,
        "window_s": stream.window_s,
        "hop_s": stream.hop_s,
        "windows": len(windows),
        "windows_with_speech": len(speech),
        "skipped": sum(window["skipped"] for window in windows),
        "compute": compute,
        "rtf_p95": round(float(np.percentile(np.array(rtf), 95)), 3),
        "perceived_latency": summary(latencies_ms),
        "enf01_met": compute["p95_ms"] < stream.hop_s * 1000,
    }
    RESULTS_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
