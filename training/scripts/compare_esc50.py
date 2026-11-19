"""C9 : comparaisons sur ESC-50 entre la famille A, la référence SVM et la famille B (P8, E5).

Lit les prédictions de test réunies des 5 folds (2 000 extraits, format path, fold, target,
prediction) téléchargées depuis les sorties Kaggle, et écrit
training/results/esc50_comparisons.json :
- CNN contre CRNN ;
- le meilleur des deux (F1 macro moyen sur les 5 tours) contre la référence MFCC + SVM ;
- le meilleur des deux contre le meilleur encodeur de la famille B, si son dossier de sortie
  C11 est donné (c11/esc50/<encodeur>/fold<k>/test_seed42.npz : probabilités des extraits du
  fold k, dans l'ordre du manifeste).
Chaque comparaison : test de McNemar et F1 macro avec son intervalle bootstrap à 95 %.

Usage, depuis la racine du dépôt :
    uv run python training/scripts/compare_esc50.py --predictions-dir <dossier des CSV>
    (ajouter --family-b-dir <sortie C11>/c11/esc50/<encodeur> --family-b-name <encodeur>)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from echolens.config import CONFIG_DIR, REPO_ROOT
from echolens.core.data.manifest import load_manifest
from echolens.training.esc50_svm import esc50_target
from echolens.training.evaluation import ClipPrediction, EvaluationConfig, load_predictions
from echolens.training.family_a_report import compare_models

RESULTS_DIR = REPO_ROOT / "training" / "results"
OUTPUT_PATH = RESULTS_DIR / "esc50_comparisons.json"
SVM_PREDICTIONS = "esc50_mfcc_svm_test_predictions.csv"
MANIFEST_PATH = REPO_ROOT / "data" / "manifests" / "esc50.csv"
FAMILY_A = ["cnn", "crnn"]
FOLD_COUNT = 5


def main() -> None:
    arguments = _parse_arguments()
    config = EvaluationConfig.from_yaml(CONFIG_DIR / "evaluation.yaml")
    predictions_dir: Path = arguments.predictions_dir
    # Étape 1 : prédictions de la graine 42 des deux réseaux, et du SVM.
    family_a = {}
    for architecture in FAMILY_A:
        path = predictions_dir / f"esc50_{architecture}_test_predictions_seed42.csv"
        family_a[architecture] = load_predictions(path)
    svm = load_predictions(predictions_dir / SVM_PREDICTIONS)
    # Étape 2 : le meilleur des deux réseaux, au F1 macro moyen sur les 5 tours (P3).
    best = _best_architecture()
    comparisons = [
        compare_models("cnn", family_a["cnn"], "crnn", family_a["crnn"], config),
        compare_models(best, family_a[best], "mfcc_svm", svm, config),
    ]
    # Étape 3 : famille B, seulement si ses prédictions sont fournies.
    if arguments.family_b_dir is not None:
        family_b = _family_b_predictions(arguments.family_b_dir)
        name_b = arguments.family_b_name
        comparisons.append(compare_models(best, family_a[best], name_b, family_b, config))
    report: dict[str, Any] = {"best_family_a": best, "comparisons": comparisons}
    OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for comparison in comparisons:
        _print_comparison(comparison)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Comparaisons McNemar sur ESC-50 (P8)")
    parser.add_argument("--predictions-dir", type=Path, required=True)
    parser.add_argument("--family-b-dir", type=Path, default=None)
    parser.add_argument("--family-b-name", default="famille_b")
    return parser.parse_args()


def _family_b_predictions(directory: Path) -> list[ClipPrediction]:
    # Les lignes de test_seed42.npz du fold k suivent l'ordre du manifeste dans ce fold.
    rows = load_manifest(MANIFEST_PATH)
    predictions: list[ClipPrediction] = []
    for fold in range(1, FOLD_COUNT + 1):
        fold_rows = [row for row in rows if row.fold == fold]
        with np.load(directory / f"fold{fold}" / "test_seed42.npz") as content:
            targets = content["targets"]
            probabilities = content["probabilities"]
        predicted = probabilities.argmax(axis=1)
        for position, row in enumerate(fold_rows):
            target = int(targets[position])
            if target != esc50_target(row.path):
                raise ValueError(f"Classe différente du manifeste pour {row.path}")
            item = ClipPrediction(row.path, fold, target, int(predicted[position]))
            predictions.append(item)
    return predictions


def _best_architecture() -> str:
    best = FAMILY_A[0]
    best_score = -1.0
    for architecture in FAMILY_A:
        path = RESULTS_DIR / f"esc50_family_a_{architecture}.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        score = report["macro_f1_mean"]
        if score > best_score:
            best = architecture
            best_score = score
    return best


def _print_comparison(comparison: dict[str, Any]) -> None:
    name_a = comparison["model_a"]
    name_b = comparison["model_b"]
    print(f"{name_a} contre {name_b} ({comparison['clip_count']} extraits)")
    print(f"  F1 macro {name_a} : {comparison['macro_f1_a']:.3f}, IC {comparison['macro_f1_a_ci']}")
    print(f"  F1 macro {name_b} : {comparison['macro_f1_b']:.3f}, IC {comparison['macro_f1_b_ci']}")
    print(
        f"  les deux justes {comparison['both_right']}, seul {name_a} {comparison['only_a_right']}"
    )
    print(f"  seul {name_b} {comparison['only_b_right']}, les deux faux {comparison['both_wrong']}")
    print(f"  McNemar : statistique {comparison['statistic']}, p = {comparison['p_value']:.2e}")


if __name__ == "__main__":
    main()
