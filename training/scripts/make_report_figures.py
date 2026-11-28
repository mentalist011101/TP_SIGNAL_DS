"""C28 : produit TOUTES les figures et tous les tableaux du rapport depuis training/results/*.json.

Décision E8 : un seul script, jamais de figure ou de chiffre copié d'ailleurs. Écrit :
- report/figures/*.png : les figures (préfixe fig_, et les matrices de confusion) ;
- report/tables/*.tex : les tableaux (tabular booktabs), à inclure avec \\input{tables/<nom>}.

Un JSON qui n'existe pas encore (C19, C25...) fait sauter ses figures avec un message ; un JSON
obligatoire manquant arrête le script. Le script peut tourner à tout moment : il suffit de le
relancer quand un nouveau JSON arrive.

Usage, depuis la racine du dépôt :
    uv run python training/scripts/make_report_figures.py
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter, ScalarFormatter

from echolens.config import REPO_ROOT
from echolens.training.report_assets import (
    best_cafe_model,
    best_of_family,
    decimal_fr,
    emotion_models,
    emotion_table_rows,
    esc50_models,
    esc50_table_rows,
    f1_mean_of,
    latency_rows,
    read_results,
    render_table,
    transcription_rows,
)

RESULTS_DIR = REPO_ROOT / "training" / "results"
FIGURES_DIR = REPO_ROOT / "report" / "figures"
TABLES_DIR = REPO_ROOT / "report" / "tables"

# Couleurs de la charte claire (docs/design.md) : famille A en gris encre, famille B en vert
# marque, référence en beige foncé. Le sens ne repose jamais sur la couleur seule (étiquettes).
INK = "#16181d"
INK_SOFT = "#55595f"
BRAND = "#4a7a3a"
REFERENCE = "#a39a85"
FAMILY_COLORS = {"A": INK_SOFT, "B": BRAND, "réf.": REFERENCE}
MODEL_COLORS = {
    "cnn": "#a3a7ae",
    "crnn": "#55595f",
    "wav2vec2-base": "#b7d5a8",
    "mhubert-147": "#4a7a3a",
    "whisper-base": "#2b4a21",
}
WHISPER_COLORS = {"base": INK_SOFT, "small": BRAND}
STRENGTH_COLORS = {"none": REFERENCE, "0.5": INK_SOFT, "0.8": BRAND, "1.0": "#b4400f"}
DPI = 200


def need(name: str) -> Any:
    """JSON obligatoire : arrête le script s'il manque."""
    content = read_results(RESULTS_DIR, name)
    if content is None:
        raise FileNotFoundError(f"training/results/{name} est obligatoire et n'existe pas")
    return content


def french_tick(value: float, _position: int) -> str:
    """Graduation à la française : 0,25 et non 0.25."""
    text = f"{value:g}"
    return text.replace(".", ",")


def use_french_decimals(figure: Any) -> None:
    """Virgule décimale sur les axes numériques. Les axes à étiquettes (noms de modèles,
    classes) gardent leurs étiquettes."""
    for axis in figure.axes:
        for scale in [axis.xaxis, axis.yaxis]:
            if isinstance(scale.get_major_formatter(), ScalarFormatter):
                scale.set_major_formatter(FuncFormatter(french_tick))


def save_figure(figure: Any, name: str) -> Path:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIGURES_DIR / name
    use_french_decimals(figure)
    figure.tight_layout()
    figure.savefig(path, dpi=DPI)
    plt.close(figure)
    return path


def save_table(name: str, text: str) -> Path:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    path = TABLES_DIR / name
    # Fins de ligne LF sur toutes les machines : sinon Windows écrit CRLF et le fichier change.
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def style_axis(axis: Any) -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.grid(axis="x", alpha=0.25)
    axis.set_axisbelow(True)


def draw_confusion(
    matrix: list[list[float]], classes: list[str], title: str, filename: str
) -> Path:
    """Matrice de confusion normalisée par ligne : case (i, j) = part de la classe i prédite j."""
    values = np.array(matrix, dtype=np.float64)
    figure, axis = plt.subplots(figsize=(5.2, 4.6))
    image = axis.imshow(values, vmin=0.0, vmax=1.0, cmap="Blues")
    axis.set_xticks(range(len(classes)), classes, rotation=45, ha="right")
    axis.set_yticks(range(len(classes)), classes)
    axis.set_xlabel("classe prédite")
    axis.set_ylabel("vraie classe")
    axis.set_title(title)
    for row in range(len(classes)):
        for column in range(len(classes)):
            value = values[row, column]
            color = "white" if value > 0.5 else INK
            axis.text(
                column, row, decimal_fr(value, 2), ha="center", va="center", color=color, fontsize=7
            )
    figure.colorbar(image, ax=axis, fraction=0.046)
    return save_figure(figure, filename)


def draw_f1_bars(models: list[dict[str, Any]], xlabel: str, filename: str) -> Path:
    """Barres horizontales de F1 macro (moyenne) avec écart-type, couleur par famille."""
    ordered = sorted(models, key=f1_mean_of)
    figure, axis = plt.subplots(figsize=(6.0, 0.55 * len(ordered) + 1.2))
    for position, model in enumerate(ordered):
        color = FAMILY_COLORS[model["family"]]
        axis.barh(position, model["f1_mean"], xerr=model["f1_std"], color=color, capsize=3)
        axis.text(
            model["f1_mean"] + model["f1_std"] + 0.01,
            position,
            decimal_fr(model["f1_mean"]),
            va="center",
            fontsize=8,
        )
    axis.set_yticks(range(len(ordered)), [f"{m['id']} ({m['family']})" for m in ordered])
    axis.set_xlim(0, 1)
    axis.set_xlabel(xlabel)
    style_axis(axis)
    return save_figure(figure, filename)


def emotions_assets() -> list[Path]:
    c11 = need("c11_family_b_emotions.json")
    cnn = need("emotions_family_a_cnn.json")
    crnn = need("emotions_family_a_crnn.json")
    comparisons = need("emotions_comparisons.json")
    classes = c11["classes"]
    models = emotion_models(c11, cnn, crnn, comparisons)
    paths = []
    # Tableau : F1 moyen ± écart-type des 3 graines, IC 95 % de la graine 42, accuracy.
    rows = emotion_table_rows(models)
    header = ["Modèle", "Fam.", "F1 macro (3 graines)", "IC 95 \\% (graine 42)", "Accuracy"]
    sources = [
        "c11_family_b_emotions.json",
        "emotions_family_a_cnn.json",
        "emotions_family_a_crnn.json",
        "emotions_comparisons.json",
    ]
    paths.append(
        save_table("emotions_in_domain.tex", render_table(sources, "@{}llccc@{}", header, rows))
    )
    # Figure 1 : F1 macro de chaque modèle.
    paths.append(
        draw_f1_bars(
            models, "F1 macro en domaine (moyenne ± écart-type, 3 graines)", "fig_emotions_f1.png"
        )
    )
    # Figure 2 : F1 par classe.
    figure, axis = plt.subplots(figsize=(7.0, 3.9))
    width = 0.8 / len(models)
    for index, model in enumerate(models):
        positions = np.arange(len(classes)) + index * width
        label = f"{model['id']} ({model['family']})"
        axis.bar(positions, model["per_class"], width, label=label, color=MODEL_COLORS[model["id"]])
    axis.set_xticks(np.arange(len(classes)) + 0.4 - width / 2, classes)
    axis.set_ylabel("F1 de la classe")
    axis.set_ylim(0, 1)
    axis.legend(fontsize=7, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12), frameon=False)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    paths.append(save_figure(figure, "fig_emotions_per_class.png"))
    # Figure 3 : F1 macro des femmes et des hommes (voir E4 pour le test de l'écart).
    figure, axis = plt.subplots(figsize=(6.0, 3.4))
    positions = np.arange(len(models))
    axis.bar(
        positions - 0.2, [m["by_gender"]["F"] for m in models], 0.4, label="femmes", color=BRAND
    )
    axis.bar(
        positions + 0.2, [m["by_gender"]["M"] for m in models], 0.4, label="hommes", color=INK_SOFT
    )
    axis.set_xticks(positions, [m["id"] for m in models], rotation=30, ha="right")
    axis.set_ylabel("F1 macro")
    # Axe jusqu'à 1 et légende sur une ligne en haut : elle ne cache plus aucune barre.
    axis.set_ylim(0, 1)
    axis.legend(ncol=2, loc="upper center", frameon=False)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    paths.append(save_figure(figure, "fig_emotions_gender.png"))
    # Figure 4 : matrice de confusion de la meilleure tête de la famille B (celle de la famille A
    # n'est pas dans les JSON : elle reste dans les sorties Kaggle de C12).
    best_b = best_of_family(models, "B")
    title = f"{best_b['id']}, émotions (test en domaine)"
    paths.append(
        draw_confusion(best_b["confusion"], classes, title, "fig_emotions_confusion_famille_B.png")
    )
    return paths


def esc50_assets() -> list[Path]:
    svm = need("esc50_mfcc_svm.json")
    cnn = need("esc50_family_a_cnn.json")
    crnn = need("esc50_family_a_crnn.json")
    c11 = need("c11_family_b_esc50.json")
    models = esc50_models(svm, cnn, crnn, c11)
    rows = esc50_table_rows(models)
    header = ["Modèle", "Fam.", "F1 macro (5 folds)", "Accuracy"]
    sources = [
        "esc50_mfcc_svm.json",
        "esc50_family_a_cnn.json",
        "esc50_family_a_crnn.json",
        "c11_family_b_esc50.json",
    ]
    paths = [save_table("esc50.tex", render_table(sources, "@{}llcc@{}", header, rows))]
    paths.append(
        draw_f1_bars(models, "F1 macro ESC-50 (moyenne ± écart-type, 5 folds)", "fig_esc50_f1.png")
    )
    best_b = best_of_family(models, "B")
    title = f"{best_b['id']}, 5 catégories ESC-50"
    filename = f"esc50_{best_b['id']}_confusion_categories.png"
    paths.append(draw_confusion(best_b["categories"], c11["category_names"], title, filename))
    return paths


def transcription_assets() -> list[Path]:
    c17 = need("c17_transcription.json")
    header = ["Modèle", "Corpus", "WER", "IC 95 \\% du WER", "CER", "IC 95 \\% du CER"]
    table = render_table(
        ["c17_transcription.json"], "@{}llrcrc@{}", header, transcription_rows(c17)
    )
    paths = [save_table("transcription.tex", table)]
    corpora = ["test", "yaounde_read"]
    labels = {"test": "test officiel", "yaounde_read": "Yaoundé (lu)"}
    names = list(c17["gpu_float16"])
    figure, axis = plt.subplots(figsize=(5.6, 3.4))
    width = 0.8 / len(names)
    for index, name in enumerate(names):
        values = []
        errors = [[], []]
        for corpus in corpora:
            wer = c17["gpu_float16"][name][corpus]["wer"]
            values.append(100 * wer["value"])
            errors[0].append(100 * (wer["value"] - wer["low"]))
            errors[1].append(100 * (wer["high"] - wer["value"]))
        positions = np.arange(len(corpora)) + index * width
        color = WHISPER_COLORS.get(name, INK)
        label = f"Whisper {name}"
        axis.bar(positions, values, width, yerr=errors, capsize=3, label=label, color=color)
    axis.set_xticks(np.arange(len(corpora)) + 0.4 - width / 2, [labels[c] for c in corpora])
    axis.set_ylabel("WER (%), IC 95 %")
    axis.legend()
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    paths.append(save_figure(figure, "fig_wer.png"))
    return paths


def latency_assets() -> list[Path]:
    latency = need("latency_cpu.json")
    header = [
        "Modèle",
        "F1 macro",
        "Poids (Mo)",
        "p50 2 s (ms)",
        "p95 2 s (ms)",
        "RTF p95 2 s",
        "RTF p95 5 s",
    ]
    table = render_table(["latency_cpu.json"], "@{}lrrrrrr@{}", header, latency_rows(latency))
    paths = [save_table("latence.tex", table)]
    names = list(latency["models"])
    limit = latency["rtf_limit"]
    figure, axis = plt.subplots(figsize=(6.0, 3.0))
    positions = np.arange(len(names))
    axis.barh(
        positions - 0.2,
        [latency["models"][n]["2s"]["rtf_p95"] for n in names],
        0.4,
        label="fenêtre de 2 s",
        color=BRAND,
    )
    axis.barh(
        positions + 0.2,
        [latency["models"][n]["5s"]["rtf_p95"] for n in names],
        0.4,
        label="fenêtre de 5 s",
        color=INK_SOFT,
    )
    limit_label = f"limite temps réel ({decimal_fr(limit, 2)})"
    axis.axvline(limit, color="#b4400f", linestyle="--", label=limit_label)
    axis.set_yticks(positions, [n.removeprefix("echolens-") for n in names], fontsize=8)
    axis.set_xlabel("RTF au 95e centile (temps de calcul / durée du son)")
    axis.legend(fontsize=7)
    style_axis(axis)
    paths.append(save_figure(figure, "fig_latence.png"))
    return paths


def vad_assets() -> list[Path]:
    benchmark = need("c24_vad_benchmark.json")
    config = benchmark["benchmark_config"]
    figure, axis = plt.subplots(figsize=(5.6, 4.0))
    for option in benchmark["options"]:
        selected = option["name"] == benchmark["selected"]
        axis.scatter(
            100 * option["false_positive_rate"],
            100 * option["speech_recall"],
            color=BRAND if selected else INK_SOFT,
            s=60 if selected else 20,
            zorder=3 if selected else 2,
        )
        if selected:
            axis.annotate(
                option["name"],
                (100 * option["false_positive_rate"], 100 * option["speech_recall"]),
                xytext=(8, -14),
                textcoords="offset points",
                fontsize=8,
            )
    max_false = 100 * config["max_false_positive_rate"]
    min_recall = 100 * config["min_speech_recall"]
    axis.axvline(
        max_false,
        color="#b4400f",
        linestyle="--",
        label=f"au plus {max_false:g} % de faux positifs",
    )
    axis.axhline(
        min_recall, color="#b4400f", linestyle=":", label=f"au moins {min_recall:g} % de parole"
    )
    axis.legend(fontsize=7, loc="lower right")
    axis.set_xlabel("faux positifs sur ESC-50 non vocal (%)")
    axis.set_ylabel("parole retrouvée (%)")
    axis.set_title("VAD : réglages essayés (C24)")
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    return [save_figure(figure, "fig_vad.png")]


def ablation_assets() -> list[Path]:
    """C19 : F1 des émotions et WER selon le SNR, pour chaque force de débruitage (E3)."""
    content = read_results(RESULTS_DIR, "c19_denoising_ablation.json")
    if content is None:
        return []
    strengths = content["config"]["strengths"]
    snrs = content["config"]["snr_db"]
    names = ["propre" if snr is None else f"{snr:g} dB" for snr in snrs]
    positions = np.arange(len(snrs))
    figure, axes = plt.subplots(1, 2, figsize=(9.5, 3.6), sharex=True)
    panels = [("wer", "WER (↓)", axes[0]), ("emotion_f1", "F1 macro des émotions (↑)", axes[1])]
    for metric, title, axis in panels:
        for index, strength in enumerate(strengths):
            key = "none" if strength is None else str(strength)
            values = []
            lows = []
            highs = []
            for snr in snrs:
                cell = f"{key}|{'clean' if snr is None else snr}"
                value, low, high = content["cells"][cell][metric]
                values.append(value)
                lows.append(value - low)
                highs.append(high - value)
            label = "sans" if strength is None else f"force {strength}"
            axis.errorbar(
                positions + (index - 1.5) * 0.06,
                values,
                yerr=[lows, highs],
                marker="o",
                capsize=3,
                label=label,
                color=STRENGTH_COLORS[key],
            )
        axis.set_title(title)
        axis.set_xticks(positions, names)
        axis.set_xlabel("niveau de bruit (SNR)")
        axis.grid(alpha=0.25)
    axes[0].legend(fontsize=8)
    return [save_figure(figure, "fig_denoising_ablation.png")]


def cafe_assets() -> list[Path]:
    """C25 : F1 en domaine contre F1 sur CaFE, et confusions du meilleur de chaque famille."""
    content = read_results(RESULTS_DIR, "c25_cafe_ood.json")
    if content is None:
        return []
    models = content["models"]
    names = list(models)
    figure, axis = plt.subplots(figsize=(6.4, 3.6))
    positions = np.arange(len(names))
    axis.bar(
        positions - 0.2,
        [models[n]["in_domain_f1_mean"] for n in names],
        0.4,
        label="en domaine",
        color=INK_SOFT,
    )
    cafe = [models[n]["macro_f1"] for n in names]
    errors = [
        [models[n]["macro_f1"] - models[n]["macro_f1_ci"][0] for n in names],
        [models[n]["macro_f1_ci"][1] - models[n]["macro_f1"] for n in names],
    ]
    axis.bar(
        positions + 0.2,
        cafe,
        0.4,
        yerr=errors,
        capsize=3,
        label="CaFE (IC 95 %, acteurs)",
        color=BRAND,
    )
    axis.set_xticks(positions, names, rotation=30, ha="right")
    axis.set_ylabel("F1 macro")
    axis.legend()
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    paths = [save_figure(figure, "fig_cafe_f1.png")]
    for family in ["A", "B"]:
        best = best_cafe_model(models, family)
        title = f"{best} sur CaFE (F1 macro {decimal_fr(models[best]['macro_f1'])})"
        paths.append(
            draw_confusion(
                models[best]["confusion"],
                content["classes"],
                title,
                f"c25_cafe_confusion_famille_{family}.png",
            )
        )
    return paths


TASKS: list[tuple[str, Callable[[], list[Path]]]] = [
    ("émotions", emotions_assets),
    ("ESC-50", esc50_assets),
    ("transcription", transcription_assets),
    ("latence", latency_assets),
    ("VAD", vad_assets),
    ("débruitage (C19), optionnel", ablation_assets),
    ("CaFE (C25), optionnel", cafe_assets),
]


def main() -> None:
    written: list[Path] = []
    for name, task in TASKS:
        paths = task()
        if not paths:
            print(f"- {name} : JSON absent, ignoré")
        for path in paths:
            print(f"- {name} : {path.relative_to(REPO_ROOT)}")
        written.extend(paths)
    print(f"{len(written)} fichiers écrits")


if __name__ == "__main__":
    sys.exit(main())
