"""C25 : matrices de confusion sur CaFE du meilleur modèle de chaque famille (par script).

Lit training/results/c25_cafe_ood.json et écrit, dans report/figures/ :
- c25_cafe_confusion_famille_A.png (meilleur de CNN et CRNN) ;
- c25_cafe_confusion_famille_B.png (meilleur des têtes wav2vec 2.0, mHuBERT et Whisper).
« Meilleur » = F1 macro le plus haut sur CaFE. Les matrices sont normalisées par ligne : la case
(i, j) est la part des extraits de la vraie classe i prédits j.

Usage, depuis la racine du dépôt :
    uv run python training/scripts/c25_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from echolens.config import REPO_ROOT

RESULTS_PATH = REPO_ROOT / "training" / "results" / "c25_cafe_ood.json"
FIGURES_DIR = REPO_ROOT / "report" / "figures"


def best_model_of_family(models: dict[str, Any], family: str) -> str:
    """Identifiant du modèle de la famille qui a le plus haut F1 macro sur CaFE."""
    best_id = ""
    best_f1 = -1.0
    for model_id, result in models.items():
        if result["family"] != family:
            continue
        if result["macro_f1"] > best_f1:
            best_f1 = result["macro_f1"]
            best_id = model_id
    if best_id == "":
        raise ValueError(f"Aucun modèle de la famille {family}")
    return best_id


def draw_confusion(model_id: str, result: dict[str, Any], classes: list[str], path: Path) -> None:
    """Dessine la matrice de confusion normalisée d'un modèle et l'écrit en PNG."""
    matrix = np.array(result["confusion"], dtype=np.float64)
    figure, axis = plt.subplots(figsize=(5.5, 4.8))
    image = axis.imshow(matrix, vmin=0.0, vmax=1.0, cmap="Blues")
    axis.set_xticks(range(len(classes)), classes, rotation=45, ha="right")
    axis.set_yticks(range(len(classes)), classes)
    axis.set_xlabel("classe prédite")
    axis.set_ylabel("vraie classe")
    f1 = result["macro_f1"]
    axis.set_title(f"{model_id} sur CaFE (F1 macro {f1:.3f})")
    for row in range(len(classes)):
        for column in range(len(classes)):
            value = matrix[row, column]
            color = "white" if value > 0.5 else "black"
            label = f"{value:.2f}"
            axis.text(column, row, label, ha="center", va="center", color=color, fontsize=8)
    figure.colorbar(image, ax=axis, fraction=0.046)
    figure.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=200)
    plt.close(figure)


def main() -> None:
    content = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    classes = content["classes"]
    for family in ["A", "B"]:
        model_id = best_model_of_family(content["models"], family)
        path = FIGURES_DIR / f"c25_cafe_confusion_famille_{family}.png"
        draw_confusion(model_id, content["models"][model_id], classes, path)
        print(family, model_id, "→", path)


if __name__ == "__main__":
    main()
