"""C13 : latence CPU des modèles de production, et choix du profil temps réel (E6, ENF-01).

Pour chaque modèle de configs/registry.yaml, on mesure la chaîne complète d'une fenêtre, sans
le décodage du fichier : signal mono 16 kHz → features (encodeur Whisper ou log-Mel) →
standardisation → réseau → probabilités calibrées. 200 fenêtres de 2 s (flux micro, D8) et
200 de 5 s (analyse de fichier, D5), après quelques fenêtres de chauffe non comptées.

Règle du profil temps réel (ENF-01) : pour chaque tâche, le modèle dont le p95 sur 2 s est
sous H = 0,5 s ; si plusieurs passent, le meilleur F1 macro du registre. En effet, le flux
analyse une fenêtre W = 2 s toutes les H = 0,5 s : il faut finir le calcul avant la fenêtre
suivante, soit un temps de calcul < H, c'est-à-dire RTF = calcul / durée analysée < H / W.

Usage, depuis la racine du dépôt (extra [ml], modèles dans un dossier local ou sur Hugging
Face). Un modèle par processus, pour que la mémoire de l'un soit rendue avant le suivant (la
machine de référence n'a que 8 Go) ; chaque mesure s'ajoute à latency_cpu.json :
    uv run python training/scripts/measure_latency.py --models-dir <dossier> --model-id <id>
puis, une fois tous les modèles mesurés, la règle du profil temps réel :
    uv run python training/scripts/measure_latency.py --choose
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch

from echolens.config import REPO_ROOT, AppSettings
from echolens.core.audio import load_preprocess_config
from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.core.data.class_labels import load_class_labels
from echolens.core.models.production_config import WEIGHTS_FILE
from echolens.core.models.registry import ModelEntry, ModelRegistry
from echolens.services.model_predictor import ModelPredictor
from echolens.services.predictor import make_predictor

OUTPUT_PATH = REPO_ROOT / "training" / "results" / "latency_cpu.json"
WINDOW_DURATIONS_S = [2.0, 5.0]
MEASURED_WINDOWS = 200
WARMUP_WINDOWS = 5
SEED = 42


def main() -> None:
    arguments = _parse_arguments()
    settings = AppSettings(inference_backend="models", models_dir=arguments.models_dir)
    registry = ModelRegistry.from_yaml(settings.registry_path)
    stream = load_preprocess_config().windows.stream
    report = _previous_report()
    report["machine"] = _machine_description()
    report["stream_window_s"] = stream.window_s
    report["stream_hop_s"] = stream.hop_s
    report["rtf_limit"] = stream.hop_s / stream.window_s
    report["measured_windows"] = MEASURED_WINDOWS
    # Étape 1 : latence d'un modèle, sur des fenêtres de 2 s et de 5 s.
    if arguments.model_id is not None:
        entry = registry.get(arguments.model_id)
        predictor = make_predictor(settings, load_class_labels())
        if not isinstance(predictor, ModelPredictor):
            raise RuntimeError("Le prédicteur réel est nécessaire pour mesurer la latence")
        report["models"][entry.id] = _measure_model(predictor, entry, arguments.models_dir)
    # Étape 2 : profil temps réel, d'après le p95 sur des fenêtres de la taille du flux.
    if arguments.choose:
        choices = _realtime_choices(registry, report["models"], stream.window_s, stream.hop_s)
        report["realtime_choice"] = choices
    text = json.dumps(report, ensure_ascii=False, indent=2)
    OUTPUT_PATH.write_text(text + "\n", encoding="utf-8")
    _print_report(report)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Latence CPU des modèles de production (E6)")
    parser.add_argument("--models-dir", type=Path, default=None)
    parser.add_argument("--model-id", default=None)
    parser.add_argument("--choose", action="store_true")
    return parser.parse_args()


def _previous_report() -> dict[str, Any]:
    # Les mesures déjà faites (un modèle par processus) sont gardées et complétées.
    if not OUTPUT_PATH.exists():
        return {"models": {}}
    report: dict[str, Any] = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    return report


def _measure_model(
    predictor: ModelPredictor, entry: ModelEntry, models_dir: Path | None
) -> dict[str, Any]:
    f1_macro = entry.metrics.get("f1_macro")
    result: dict[str, Any] = {"task": entry.task.value, "f1_macro": f1_macro}
    for duration_s in WINDOW_DURATIONS_S:
        seconds = _window_latencies(predictor, entry, duration_s)
        p50 = float(np.percentile(seconds, 50))
        p95 = float(np.percentile(seconds, 95))
        result[f"{duration_s:g}s"] = {"p50_s": p50, "p95_s": p95, "rtf_p95": p95 / duration_s}
    result.update(_model_size(predictor, entry, models_dir))
    return result


def _window_latencies(predictor: ModelPredictor, entry: ModelEntry, duration_s: float) -> Any:
    # Fenêtres de bruit (graine fixe) : la durée du calcul ne dépend pas du contenu.
    generator = np.random.default_rng(SEED)
    sample_count = round(duration_s * TARGET_SAMPLE_RATE)
    latencies = []
    for index in range(WARMUP_WINDOWS + MEASURED_WINDOWS):
        noise = generator.normal(0.0, 0.1, size=sample_count)
        window = noise.astype(np.float32)
        start = time.perf_counter()
        predictor.predict_with(entry, [window])
        elapsed = time.perf_counter() - start
        # Les premières fenêtres (chauffe : allocations, caches) ne sont pas comptées.
        if index >= WARMUP_WINDOWS:
            latencies.append(elapsed)
    return np.array(latencies)


def _model_size(
    predictor: ModelPredictor, entry: ModelEntry, models_dir: Path | None
) -> dict[str, Any]:
    loaded = predictor.load(entry)
    own_parameters = sum(parameter.numel() for parameter in loaded.network.parameters())
    size: dict[str, Any] = {"parameters": own_parameters}
    if models_dir is not None:
        weights = models_dir / entry.id / WEIGHTS_FILE
        size["weights_mb"] = weights.stat().st_size / 1e6
    # La tête a besoin de l'encodeur Whisper : on compte aussi ses paramètres (partagés).
    total = own_parameters
    if loaded.encoder is not None:
        encoder_parameters = sum(
            parameter.numel() for parameter in loaded.encoder.model.parameters()
        )
        size["encoder_parameters"] = encoder_parameters
        total = own_parameters + encoder_parameters
    size["total_parameters"] = total
    return size


def _realtime_choices(
    registry: ModelRegistry, measures: dict[str, Any], window_s: float, hop_s: float
) -> dict[str, Any]:
    window_key = f"{window_s:g}s"
    choices: dict[str, Any] = {}
    for task in sorted({entry.task.value for entry in registry.models}):
        candidates = []
        for model_id, measure in measures.items():
            fast_enough = measure[window_key]["p95_s"] < hop_s
            if measure["task"] == task and fast_enough:
                candidates.append((measure["f1_macro"], model_id))
        # Le meilleur F1 parmi les modèles assez rapides ; aucun : pas de modèle temps réel.
        candidates.sort(reverse=True)
        chosen = None
        if candidates:
            chosen = candidates[0][1]
        choices[task] = chosen
    return choices


def _machine_description() -> dict[str, Any]:
    return {
        "processor": _processor_name(),
        "machine": platform.machine(),
        "system": f"{platform.system()} {platform.release()}",
        "logical_cpus": os.cpu_count(),
        "torch_threads": torch.get_num_threads(),
        "torch_version": torch.__version__,
        "python": platform.python_version(),
    }


def _processor_name() -> str:
    # platform.processor() ne donne qu'une famille sous Windows ; le nom commercial du
    # processeur est dans le registre de Windows.
    if platform.system() == "Windows":
        import winreg

        key_path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        return str(name).strip()
    return platform.processor()


def _print_report(report: dict[str, Any]) -> None:
    machine = report["machine"]
    print(f"Machine : {machine['processor']} ({machine['logical_cpus']} cœurs logiques)")
    for model_id, measure in report["models"].items():
        for duration_s in WINDOW_DURATIONS_S:
            values = measure[f"{duration_s:g}s"]
            p50_ms = values["p50_s"] * 1000
            p95_ms = values["p95_s"] * 1000
            print(f"  {model_id} {duration_s:g} s : p50 {p50_ms:.0f} ms, p95 {p95_ms:.0f} ms")
    print("Profil temps réel :", report.get("realtime_choice", "pas encore choisi"))


if __name__ == "__main__":
    main()
