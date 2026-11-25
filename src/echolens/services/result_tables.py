"""Tableaux de la page Comparer : les résultats des expériences, lus dans training/results/.

Aucun modèle n'est chargé et rien n'est recalculé : on relit les JSON écrits par les notebooks
Kaggle et on les met en forme. Un fichier absent fait seulement disparaître ses lignes.

Quatre tableaux :
- événements sonores (ESC-50) et émotions : un modèle par ligne, F1 macro et accuracy de test
  (moyenne ± écart-type sur les tours ou les graines), intervalle de confiance quand il existe ;
- tests de McNemar entre deux modèles (P8, E5) ;
- transcription : WER et CER de Whisper base et small (C17) ;
- latence sur CPU des modèles de production (E6).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from echolens.config import CONFIG_DIR, load_yaml

COMPARISONS_CONFIG_PATH = CONFIG_DIR / "comparisons.yaml"

# Fichiers lus, tels que les notebooks les écrivent.
ESC50_SVM_FILE = "esc50_mfcc_svm.json"
ESC50_FAMILY_A_FILES = {"cnn": "esc50_family_a_cnn.json", "crnn": "esc50_family_a_crnn.json"}
ESC50_FAMILY_B_FILE = "c11_family_b_esc50.json"
ESC50_TESTS_FILE = "esc50_comparisons.json"
EMOTION_FAMILY_A_FILES = {
    "cnn": "emotions_family_a_cnn.json",
    "crnn": "emotions_family_a_crnn.json",
}
EMOTION_FAMILY_B_FILE = "c11_family_b_emotions.json"
EMOTION_TESTS_FILE = "emotions_comparisons.json"
TRANSCRIPTION_FILE = "c17_transcription.json"
LATENCY_FILE = "latency_cpu.json"

# Protocole de chaque tableau, affiché sous son titre.
ESC50_PROTOCOL = "ESC-50, 2 000 extraits, 5 folds officiels : moyenne ± écart-type des 5 tours (P3)"
EMOTION_PROTOCOL = (
    "CREMA-D + RAVDESS, 1 324 extraits d'acteurs jamais vus : "
    "moyenne ± écart-type de 3 graines (P1)"
)

# Corpus de la transcription, dans l'ordre d'affichage, avec leur nom lisible.
TRANSCRIPTION_CORPORA = {
    "test": "OpenSLR 57, test officiel",
    "yaounde_read": "OpenSLR 57, Yaoundé (lu)",
}


def read_json(path: Path) -> dict[str, Any] | None:
    """Contenu d'un fichier de résultats, ou None s'il n'existe pas."""
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    content: dict[str, Any] = json.loads(text)
    return content


def model_row(model_key: str, scores: dict[str, Any], names: dict[str, Any]) -> dict[str, Any]:
    """Une ligne du tableau d'une tâche, à partir des scores déjà extraits d'un fichier."""
    identity = names.get(model_key, {"label": model_key, "family": "?"})
    return {
        "model": model_key,
        "label": identity["label"],
        "family": identity["family"],
        "f1_macro_mean": scores["f1_mean"],
        "f1_macro_std": scores["f1_std"],
        "accuracy_mean": scores["accuracy_mean"],
        "accuracy_std": scores["accuracy_std"],
        "f1_macro_ci": scores.get("ci"),
    }


def flat_scores(content: dict[str, Any]) -> dict[str, Any]:
    """Scores écrits à plat : macro_f1_mean, macro_f1_std… (SVM, famille A sur ESC-50)."""
    return {
        "f1_mean": content["macro_f1_mean"],
        "f1_std": content["macro_f1_std"],
        "accuracy_mean": content["accuracy_mean"],
        "accuracy_std": content["accuracy_std"],
    }


def nested_scores(block: dict[str, Any]) -> dict[str, Any]:
    """Scores écrits en blocs : macro_f1 {mean, std}… (famille B, famille A sur les émotions)."""
    return {
        "f1_mean": block["macro_f1"]["mean"],
        "f1_std": block["macro_f1"]["std"],
        "accuracy_mean": block["accuracy"]["mean"],
        "accuracy_std": block["accuracy"]["std"],
        "ci": block.get("macro_f1_ci"),
    }


def family_b_rows(path: Path, names: dict[str, Any]) -> list[dict[str, Any]]:
    """Une ligne par encodeur de la famille B (C11)."""
    content = read_json(path)
    if content is None:
        return []
    rows = []
    for model_key, block in content["models"].items():
        scores = nested_scores(block)
        rows.append(model_row(model_key, scores, names))
    return rows


def esc50_rows(results_dir: Path, names: dict[str, Any]) -> list[dict[str, Any]]:
    """Événements sonores : référence SVM, famille A, puis famille B (P3, 5 tours)."""
    rows = []
    # Étape 1 : la référence classique et la famille A, scores écrits à plat.
    svm = read_json(results_dir / ESC50_SVM_FILE)
    if svm is not None:
        rows.append(model_row("mfcc_svm", flat_scores(svm), names))
    for model_key, file_name in ESC50_FAMILY_A_FILES.items():
        content = read_json(results_dir / file_name)
        if content is not None:
            rows.append(model_row(model_key, flat_scores(content), names))
    # Étape 2 : les encodeurs de la famille B.
    rows.extend(family_b_rows(results_dir / ESC50_FAMILY_B_FILE, names))
    return rows


def emotion_rows(results_dir: Path, names: dict[str, Any]) -> list[dict[str, Any]]:
    """Émotions : famille A puis famille B, test indépendant du locuteur (P1, 3 graines)."""
    rows = []
    for model_key, file_name in EMOTION_FAMILY_A_FILES.items():
        content = read_json(results_dir / file_name)
        if content is not None:
            scores = nested_scores(content["summary"])
            scores["ci"] = content.get("macro_f1_ci")
            rows.append(model_row(model_key, scores, names))
    rows.extend(family_b_rows(results_dir / EMOTION_FAMILY_B_FILE, names))
    return rows


def label_of(model_key: str, names: dict[str, Any]) -> str:
    """Nom affiché d'un modèle, ou son identifiant s'il n'est pas dans la configuration."""
    identity = names.get(model_key)
    if identity is None:
        return model_key
    label: str = identity["label"]
    return label


def mcnemar_row(test: dict[str, Any], names: dict[str, Any], level: float) -> dict[str, Any]:
    """Un test de McNemar entre deux modèles, sur les mêmes extraits de test (P8)."""
    # La p-valeur corrigée de Holm (plusieurs tests à la fois) prime quand le fichier la donne.
    p_value_holm = test.get("p_value_holm")
    p_value_used = test["p_value"]
    if p_value_holm is not None:
        p_value_used = p_value_holm
    return {
        "model_a": label_of(test["model_a"], names),
        "model_b": label_of(test["model_b"], names),
        "f1_macro_a": test["macro_f1_a"],
        "f1_macro_b": test["macro_f1_b"],
        "only_a_right": test["only_a_right"],
        "only_b_right": test["only_b_right"],
        "p_value": test["p_value"],
        "p_value_holm": p_value_holm,
        "significant": p_value_used < level,
    }


def mcnemar_rows(
    paths: list[Path], key: str, names: dict[str, Any], level: float
) -> list[dict[str, Any]]:
    """Tous les tests de McNemar rangés sous `key` dans ces fichiers, dans leur ordre."""
    rows = []
    for path in paths:
        content = read_json(path)
        if content is None:
            continue
        for test in content.get(key, []):
            rows.append(mcnemar_row(test, names, level))
    return rows


def classification_tables(results_dir: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Les deux tâches de classification, chacune avec ses modèles et ses tests."""
    names = config["models"]
    level = config["significance_level"]
    # Les tests entre familles sont rangés sous « comparisons », ceux entre encodeurs sous
    # « mcnemar » (fichiers C11).
    esc50_tests = mcnemar_rows([results_dir / ESC50_TESTS_FILE], "comparisons", names, level)
    esc50_tests += mcnemar_rows([results_dir / ESC50_FAMILY_B_FILE], "mcnemar", names, level)
    emotion_tests = mcnemar_rows([results_dir / EMOTION_TESTS_FILE], "comparisons", names, level)
    emotion_tests += mcnemar_rows([results_dir / EMOTION_FAMILY_B_FILE], "mcnemar", names, level)
    sound_event = {
        "task": "sound_event",
        "protocol": ESC50_PROTOCOL,
        "models": esc50_rows(results_dir, names),
        "tests": esc50_tests,
    }
    emotion = {
        "task": "emotion",
        "protocol": EMOTION_PROTOCOL,
        "models": emotion_rows(results_dir, names),
        "tests": emotion_tests,
    }
    return [sound_event, emotion]


def transcription_rows(results_dir: Path) -> list[dict[str, Any]]:
    """WER et CER de chaque modèle Whisper sur chaque corpus, avec leur intervalle (C17)."""
    content = read_json(results_dir / TRANSCRIPTION_FILE)
    if content is None:
        return []
    cpu_models = content["latency_cpu"]["models"]
    rows = []
    for model_key, by_corpus in content["gpu_float16"].items():
        for corpus_key, corpus_label in TRANSCRIPTION_CORPORA.items():
            scores = by_corpus[corpus_key]
            rows.append(
                {
                    "model": f"Whisper {model_key}",
                    "corpus": corpus_label,
                    "wer": scores["wer"]["value"],
                    "wer_ci": [scores["wer"]["low"], scores["wer"]["high"]],
                    "cer": scores["cer"]["value"],
                    "rtf_cpu": cpu_models[model_key]["rtf"],
                }
            )
    return rows


def latency_rows(results_dir: Path) -> list[dict[str, Any]]:
    """Taille, latence et RTF sur CPU des modèles de production, fenêtres de 2 s et 5 s (E6)."""
    content = read_json(results_dir / LATENCY_FILE)
    if content is None:
        return []
    realtime_models = list(content["realtime_choice"].values())
    rows = []
    for model_id, measures in content["models"].items():
        rows.append(
            {
                "model": model_id,
                "task": measures["task"],
                "f1_macro": measures["f1_macro"],
                "parameters": measures["total_parameters"],
                "p95_2s": measures["2s"]["p95_s"],
                "rtf_p95_2s": measures["2s"]["rtf_p95"],
                "p95_5s": measures["5s"]["p95_s"],
                "realtime": model_id in realtime_models,
            }
        )
    return rows


def comparison_tables(results_dir: Path) -> dict[str, Any]:
    """Tous les tableaux de la page Comparer (contrat de GET /api/v1/comparisons)."""
    config = load_yaml(COMPARISONS_CONFIG_PATH)
    return {
        "classification": classification_tables(results_dir, config),
        "transcription": transcription_rows(results_dir),
        "latency": latency_rows(results_dir),
    }
