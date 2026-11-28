"""C28 : lignes de tableaux et gabarit LaTeX du rapport, calculés depuis training/results/*.json.

Calcul pur (pas de matplotlib) : le script training/scripts/make_report_figures.py dessine les
figures et écrit les tableaux (décision E8 : un seul script produit tableaux et figures). Chaque
tableau écrit cite en commentaire les fichiers JSON d'où viennent ses chiffres.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

Row = list[str]
EXCLUDED_B_VARIANTS = ("whisper-base-padded",)  # variante d'ablation de C10, hors des tableaux


def fr(value: float, digits: int = 3) -> str:
    """Nombre à la française pour LaTeX : virgule décimale protégée, 0,769 s'écrit 0{,}769."""
    text = f"{value:.{digits}f}"
    return text.replace(".", "{,}")


def decimal_fr(value: float, digits: int = 3) -> str:
    """Nombre à la française pour une figure (texte simple, hors LaTeX) : 0,754."""
    text = f"{value:.{digits}f}"
    return text.replace(".", ",")


def fr_pm(mean: float, std: float, digits: int = 3) -> str:
    """« moyenne ± écart-type » en mode mathématique."""
    return f"${fr(mean, digits)} \\pm {fr(std, digits)}$"


def fr_interval(low: float, high: float, digits: int = 3) -> str:
    """Intervalle « [bas ; haut] » en mode mathématique."""
    return f"$[{fr(low, digits)}\\,;\\,{fr(high, digits)}]$"


def fr_percent(value: float, digits: int = 1) -> str:
    """Un taux (0,2792) en pourcentage à la française : 27{,}9\\,\\%."""
    return f"{fr(100.0 * value, digits)}\\,\\%"


def latex_escape(text: str) -> str:
    """Échappe les caractères spéciaux de LaTeX dans un identifiant de modèle."""
    return text.replace("_", "\\_").replace("&", "\\&").replace("%", "\\%")


def read_results(results_dir: Path, name: str) -> Any | None:
    """Contenu d'un JSON de training/results/, ou None s'il n'existe pas (encore)."""
    path = results_dir / name
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def render_table(sources: list[str], column_spec: str, header: Row, rows: list[Row]) -> str:
    """Tableau booktabs prêt à être inclus avec \\input{tables/<nom>}.

    La première ligne est un commentaire qui cite les JSON sources (règle de report/README.md).
    La légende et l'étiquette sont écrites dans la section qui inclut le tableau.
    """
    lines = ["% Généré par training/scripts/make_report_figures.py, ne pas modifier à la main."]
    lines.append("% Source : " + ", ".join(f"training/results/{name}" for name in sources))
    lines.append(f"\\begin{{tabular}}{{{column_spec}}}")
    lines.append("\\toprule")
    lines.append(" & ".join(header) + " \\\\")
    lines.append("\\midrule")
    for row in rows:
        lines.append(" & ".join(row) + " \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    return "\n".join(lines) + "\n"


def emotion_models(
    c11: dict[str, Any], cnn: dict[str, Any], crnn: dict[str, Any], comparisons: dict[str, Any]
) -> list[dict[str, Any]]:
    """Modèles d'émotion en domaine : famille, F1 macro (moyenne, écart-type des 3 graines),
    IC 95 % de la graine 42, accuracy, F1 par classe, F1 par genre."""
    # IC du CNN et du CRNN : ils sont dans la comparaison CNN contre CRNN (graine 42).
    first = comparisons["comparisons"][0]
    intervals = {first["model_a"]: first["macro_f1_a_ci"], first["model_b"]: first["macro_f1_b_ci"]}
    models: list[dict[str, Any]] = []
    for name, content in [("cnn", cnn), ("crnn", crnn)]:
        summary = content["summary"]
        models.append(
            {
                "id": name,
                "family": "A",
                "f1_mean": summary["macro_f1"]["mean"],
                "f1_std": summary["macro_f1"]["std"],
                "ci": intervals[name],
                "accuracy": summary["accuracy"]["mean"],
                "per_class": content["seeds"][0]["test"]["f1_per_class"],
                "by_gender": mean_by_gender(summary["macro_f1_by_gender"]),
                "confusion": None,
            }
        )
    for name, content in c11["models"].items():
        if name in EXCLUDED_B_VARIANTS:
            continue
        gender = mean_by_gender(content["macro_f1_by_gender"])
        models.append(
            {
                "id": name,
                "family": "B",
                "f1_mean": content["macro_f1"]["mean"],
                "f1_std": content["macro_f1"]["std"],
                "ci": content["macro_f1_ci"],
                "accuracy": content["accuracy"]["mean"],
                "per_class": content["f1_per_class"],
                "by_gender": gender,
                "confusion": content["confusion"],
            }
        )
    return models


def mean_by_gender(by_gender: dict[str, Any]) -> dict[str, float]:
    """F1 moyen des 3 graines pour chaque genre : {"F": 0,69, "M": 0,55}.

    Les deux familles utilisent la moyenne des graines, pour être comparables sur la figure.
    """
    means: dict[str, float] = {}
    for gender, values in by_gender.items():
        means[gender] = values["mean"]
    return means


def f1_mean_of(model: dict[str, Any]) -> float:
    """F1 macro moyen d'un modèle : sert de clé de tri."""
    return float(model["f1_mean"])


def best_of_family(models: list[dict[str, Any]], family: str) -> dict[str, Any]:
    """Le modèle de la famille qui a le F1 macro moyen le plus haut."""
    best: dict[str, Any] | None = None
    for model in models:
        if model["family"] != family:
            continue
        if best is None or model["f1_mean"] > best["f1_mean"]:
            best = model
    if best is None:
        raise ValueError(f"Aucun modèle de la famille {family}")
    return best


def best_cafe_model(models: dict[str, Any], family: str) -> str:
    """Identifiant du modèle de la famille qui a le F1 macro le plus haut sur CaFE (C25)."""
    best_id = ""
    best_f1 = -1.0
    for model_id, result in models.items():
        if result["family"] != family:
            continue
        if result["macro_f1"] > best_f1:
            best_f1 = result["macro_f1"]
            best_id = model_id
    if best_id == "":
        raise ValueError(f"Aucun modèle de la famille {family} sur CaFE")
    return best_id


def emotion_table_rows(models: list[dict[str, Any]]) -> list[Row]:
    """Lignes du tableau des émotions en domaine."""
    rows: list[Row] = []
    for model in models:
        rows.append(
            [
                latex_escape(model["id"]),
                model["family"],
                fr_pm(model["f1_mean"], model["f1_std"]),
                fr_interval(model["ci"][0], model["ci"][1]),
                fr(model["accuracy"]),
            ]
        )
    return rows


def esc50_models(
    svm: dict[str, Any], cnn: dict[str, Any], crnn: dict[str, Any], c11: dict[str, Any]
) -> list[dict[str, Any]]:
    """Modèles ESC-50 : F1 macro (moyenne, écart-type sur les 5 folds) et accuracy."""
    models: list[dict[str, Any]] = [
        {
            "id": "mfcc_svm",
            "family": "réf.",
            "f1_mean": svm["macro_f1_mean"],
            "f1_std": svm["macro_f1_std"],
            "accuracy": svm["accuracy_mean"],
            "categories": None,
        }
    ]
    for name, content in [("cnn", cnn), ("crnn", crnn)]:
        models.append(
            {
                "id": name,
                "family": "A",
                "f1_mean": content["macro_f1_mean"],
                "f1_std": content["macro_f1_std"],
                "accuracy": content["accuracy_mean"],
                "categories": None,
            }
        )
    for name, content in c11["models"].items():
        if name in EXCLUDED_B_VARIANTS:
            continue
        models.append(
            {
                "id": name,
                "family": "B",
                "f1_mean": content["macro_f1"]["mean"],
                "f1_std": content["macro_f1"]["std"],
                "accuracy": content["accuracy"]["mean"],
                "categories": content["confusion_categories"],
            }
        )
    return models


def esc50_table_rows(models: list[dict[str, Any]]) -> list[Row]:
    rows: list[Row] = []
    for model in models:
        rows.append(
            [
                latex_escape(model["id"]),
                model["family"],
                fr_pm(model["f1_mean"], model["f1_std"]),
                fr(model["accuracy"]),
            ]
        )
    return rows


def transcription_rows(c17: dict[str, Any]) -> list[Row]:
    """WER et CER de chaque modèle Whisper sur chaque corpus, avec leur IC 95 %."""
    corpus_names = {"test": "test officiel", "yaounde_read": "Yaoundé (lu)"}
    rows: list[Row] = []
    for model_name, corpora in c17["gpu_float16"].items():
        for corpus, scores in corpora.items():
            wer = scores["wer"]
            cer = scores["cer"]
            rows.append(
                [
                    f"Whisper {model_name}",
                    corpus_names.get(corpus, latex_escape(corpus)),
                    fr_percent(wer["value"]),
                    fr_interval(100 * wer["low"], 100 * wer["high"], 1),
                    fr_percent(cer["value"]),
                    fr_interval(100 * cer["low"], 100 * cer["high"], 1),
                ]
            )
    return rows


def latency_rows(latency: dict[str, Any]) -> list[Row]:
    """Latence p50, p95 et RTF p95 de chaque modèle du registre, sur fenêtres de 2 s et 5 s."""
    rows: list[Row] = []
    for name, content in latency["models"].items():
        two = content["2s"]
        five = content["5s"]
        rows.append(
            [
                latex_escape(name.removeprefix("echolens-")),
                fr(content["f1_macro"]),
                fr(content["weights_mb"], 2),
                fr(1000 * two["p50_s"], 0),
                fr(1000 * two["p95_s"], 0),
                fr(two["rtf_p95"], 3),
                fr(five["rtf_p95"], 3),
            ]
        )
    return rows
