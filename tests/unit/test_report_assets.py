from echolens.training.report_assets import (
    emotion_models,
    emotion_table_rows,
    fr,
    fr_interval,
    fr_percent,
    fr_pm,
    latency_rows,
    render_table,
    transcription_rows,
)


def family_a_result(f1: float) -> dict:
    test = {"f1_per_class": [f1] * 6, "macro_f1_by_gender": {"F": f1 + 0.05, "M": f1 - 0.05}}
    return {
        "summary": {"macro_f1": {"mean": f1, "std": 0.01}, "accuracy": {"mean": f1}},
        "seeds": [{"seed": 42, "test": test}],
    }


def test_french_number_formatting():
    assert fr(0.7693) == "0{,}769"
    assert fr(12.0, 0) == "12"
    assert fr_pm(0.75, 0.0123) == "$0{,}750 \\pm 0{,}012$"
    assert fr_interval(0.5, 0.6) == "$[0{,}500\\,;\\,0{,}600]$"
    assert fr_percent(0.2792) == "27{,}9\\,\\%"


def test_render_table_cites_sources_and_has_booktabs_rules():
    text = render_table(["a.json", "b.json"], "@{}lr@{}", ["Modèle", "F1"], [["cnn", "0{,}5"]])
    lines = text.splitlines()
    assert lines[1] == "% Source : training/results/a.json, training/results/b.json"
    assert "\\toprule" in lines and "\\midrule" in lines and "\\bottomrule" in lines
    assert "cnn & 0{,}5 \\\\" in lines


def test_emotion_models_skips_padded_variant_and_orders_families():
    comparisons = {
        "comparisons": [
            {
                "model_a": "cnn",
                "model_b": "crnn",
                "macro_f1_a_ci": [0.5, 0.6],
                "macro_f1_b_ci": [0.6, 0.7],
            }
        ]
    }
    head = {
        "macro_f1": {"mean": 0.75, "std": 0.01},
        "accuracy": {"mean": 0.74},
        "macro_f1_ci": [0.7, 0.8],
        "f1_per_class": [0.75] * 6,
        "macro_f1_by_gender": {"F": {"mean": 0.8}, "M": {"mean": 0.7}},
        "confusion": [[1.0]],
    }
    c11 = {"models": {"mhubert-147": head, "whisper-base-padded": head}}
    models = emotion_models(c11, family_a_result(0.62), family_a_result(0.67), comparisons)
    assert [model["id"] for model in models] == ["cnn", "crnn", "mhubert-147"]
    assert models[0]["ci"] == [0.5, 0.6]
    assert models[2]["by_gender"] == {"F": 0.8, "M": 0.7}
    rows = emotion_table_rows(models)
    assert rows[2][0] == "mhubert-147" and rows[2][1] == "B"


def test_transcription_and_latency_rows():
    score = {
        "wer": {"value": 0.2792, "low": 0.2354, "high": 0.3202},
        "cer": {"value": 0.13, "low": 0.1, "high": 0.15},
    }
    c17 = {"gpu_float16": {"base": {"test": score}}}
    row = transcription_rows(c17)[0]
    assert row[:3] == ["Whisper base", "test officiel", "27{,}9\\,\\%"]
    window = {"p50_s": 0.059, "p95_s": 0.347, "rtf_p95": 0.173}
    latency = {
        "models": {
            "echolens-emotion-crnn": {
                "f1_macro": 0.668,
                "weights_mb": 2.7554,
                "2s": window,
                "5s": window,
            }
        }
    }
    assert latency_rows(latency)[0] == [
        "emotion-crnn",
        "0{,}668",
        "2{,}76",
        "59",
        "347",
        "0{,}173",
        "0{,}173",
    ]
