"""C24 : la VAD prend-elle du bruit pour de la parole ? Mesure des options de D5.

Options comparées, de la plus simple à la plus lourde :
1. webrtcvad seul, agressivité 0 à 3 ;
2. webrtcvad plus un contrôle d'énergie : une trame n'est gardée que si la bande 300–3 400 Hz
   contient au moins une part donnée de sa puissance ;
3. Silero VAD (réseau de neurones, torch), à plusieurs seuils, avec ou sans l'hystérésis de
   Silero (un segment commence à p ≥ seuil et continue tant que p ≥ seuil − 0,15).

Les décisions brutes de chaque extrait (trames webrtcvad, parts d'énergie, probabilités
Silero) sont calculées une fois, puis chaque option les combine et passe par le même
nettoyage des segments que l'application (flags_to_segments, D5).

Mesures : sur ESC-50 sans les classes vocales, part des extraits avec au moins 0,5 s de
« parole » (faux positifs) ; sur 200 extraits de CREMA-D, part des extraits dont au moins
50 % de la durée est « parole » (parole retrouvée).
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from echolens.config import CONFIG_DIR, load_yaml
from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.core.audio.preprocess_config import VadConfig
from echolens.core.audio.segment import FloatArray, flags_to_segments, speech_flags
from echolens.core.data.manifest import ManifestRow
from echolens.core.features import FeatureConfig, band_power_share

VAD_BENCHMARK_CONFIG_PATH = CONFIG_DIR / "vad_benchmark.yaml"
WEBRTCVAD_LEVELS = [0, 1, 2, 3]
Method = Literal["webrtcvad", "webrtcvad_band", "silero"]
# Ordre de simplicité : la première famille qui tient les deux critères l'emporte.
METHOD_ORDER: list[Method] = ["webrtcvad", "webrtcvad_band", "silero"]


class VadBenchmarkConfig(BaseModel):
    """Contenu de configs/vad_benchmark.yaml."""

    excluded_esc50_classes: list[str]
    false_speech_min_s: float = Field(gt=0)
    cremad_sample_size: int = Field(gt=0)
    seed: int
    speech_share_min: float = Field(gt=0, le=1)
    band_low_hz: float = Field(ge=0)
    band_high_hz: float = Field(gt=0)
    band_share_thresholds: list[float] = Field(min_length=1)
    silero_thresholds: list[float] = Field(min_length=1)
    silero_hysteresis_gap: float = Field(gt=0, lt=1)
    silero_min_end_threshold: float = Field(gt=0, lt=1)
    max_false_positive_rate: float = Field(ge=0, le=1)
    min_speech_recall: float = Field(ge=0, le=1)


@dataclass(frozen=True)
class ClipDecisions:
    """Décisions brutes d'un extrait, calculées une seule fois."""

    label: str
    duration_s: float
    # webrtcvad_flags[a] : une décision par trame de 30 ms, avec l'agressivité a.
    webrtcvad_flags: list[list[bool]]
    webrtcvad_frame_s: float
    # Part de la puissance dans la bande 300–3 400 Hz, une valeur par trame de 30 ms.
    band_shares: list[float]
    silero_probabilities: list[float]
    silero_frame_s: float


@dataclass(frozen=True)
class VadOption:
    """Une option mesurée. Les champs inutiles à la méthode valent None."""

    name: str
    method: Method
    aggressiveness: int | None = None
    band_threshold: float | None = None
    silero_threshold: float | None = None
    # Seuil de fin de l'hystérésis de Silero ; None : un seul seuil, sans hystérésis.
    silero_end_threshold: float | None = None


@dataclass(frozen=True)
class OptionScore:
    """Résultat d'une option sur les deux jeux."""

    option: VadOption
    false_positive_rate: float
    speech_recall: float
    passes: bool


def load_vad_benchmark_config(path: Path = VAD_BENCHMARK_CONFIG_PATH) -> VadBenchmarkConfig:
    """Lit configs/vad_benchmark.yaml."""
    return VadBenchmarkConfig(**load_yaml(path))


def non_vocal_esc50_rows(rows: list[ManifestRow], excluded: list[str]) -> list[ManifestRow]:
    """Extraits d'ESC-50 dont la classe n'est pas une des classes vocales exclues."""
    kept: list[ManifestRow] = []
    for row in rows:
        if row.label not in excluded:
            kept.append(row)
    return kept


def sample_rows(rows: list[ManifestRow], size: int, seed: int) -> list[ManifestRow]:
    """Tirage sans remise de size lignes, reproductible, dans l'ordre du manifeste."""
    generator = np.random.default_rng(seed)
    chosen = generator.choice(len(rows), size=size, replace=False)
    chosen_sorted = sorted(int(index) for index in chosen)
    return [rows[index] for index in chosen_sorted]


def clip_decisions(
    signal: FloatArray,
    label: str,
    vad_config: VadConfig,
    benchmark_config: VadBenchmarkConfig,
    silero_probabilities: list[float],
    silero_frame_s: float,
) -> ClipDecisions:
    """Calcule les décisions brutes d'un extrait (les probabilités Silero sont fournies)."""
    # Étape 1 : webrtcvad à chaque niveau d'agressivité, mêmes trames que l'application.
    flags_per_level: list[list[bool]] = []
    for level in WEBRTCVAD_LEVELS:
        level_config = vad_config.model_copy(update={"aggressiveness": level})
        flags_per_level.append(speech_flags(signal, level_config))
    # Étape 2 : part d'énergie dans la bande, sur des trames alignées sur celles de webrtcvad.
    shares = vad_frame_band_shares(signal, vad_config, benchmark_config)
    duration_s = len(signal) / TARGET_SAMPLE_RATE
    return ClipDecisions(
        label=label,
        duration_s=duration_s,
        webrtcvad_flags=flags_per_level,
        webrtcvad_frame_s=vad_config.frame_ms / 1000,
        band_shares=shares,
        silero_probabilities=silero_probabilities,
        silero_frame_s=silero_frame_s,
    )


def vad_frame_band_shares(
    signal: FloatArray, vad_config: VadConfig, benchmark_config: VadBenchmarkConfig
) -> list[float]:
    """Part de la puissance dans la bande, une valeur par trame de la VAD (C24)."""
    # Une trame STFT = une trame de la VAD : fenêtre et pas de frame_ms, sans centrage.
    frame_length = TARGET_SAMPLE_RATE * vad_config.frame_ms // 1000
    if len(signal) < frame_length:
        return []
    feature_config = FeatureConfig(
        sample_rate=TARGET_SAMPLE_RATE, n_fft=frame_length, hop_length=frame_length, center=False
    )
    shares = band_power_share(
        signal, feature_config, benchmark_config.band_low_hz, benchmark_config.band_high_hz
    )
    return [float(share) for share in shares]


def benchmark_options(config: VadBenchmarkConfig) -> list[VadOption]:
    """Toutes les options mesurées, dans l'ordre de simplicité."""
    options: list[VadOption] = []
    for level in WEBRTCVAD_LEVELS:
        options.append(VadOption(f"webrtcvad {level}", "webrtcvad", aggressiveness=level))
    for level in WEBRTCVAD_LEVELS:
        for threshold in config.band_share_thresholds:
            name = f"webrtcvad {level} + bande ≥ {threshold:.2f}"
            option = VadOption(
                name, "webrtcvad_band", aggressiveness=level, band_threshold=threshold
            )
            options.append(option)
    for threshold in config.silero_thresholds:
        name = f"Silero ≥ {threshold:.2f}"
        options.append(VadOption(name, "silero", silero_threshold=threshold))
    for threshold in config.silero_thresholds:
        end_threshold = silero_end_threshold(threshold, config)
        name = f"Silero ≥ {threshold:.2f}, fin < {end_threshold:.2f}"
        option = VadOption(
            name, "silero", silero_threshold=threshold, silero_end_threshold=end_threshold
        )
        options.append(option)
    return options


def silero_end_threshold(threshold: float, config: VadBenchmarkConfig) -> float:
    """Seuil de fin de l'hystérésis, comme get_speech_timestamps de Silero : seuil − 0,15,
    sans descendre sous 0,01."""
    end_threshold = threshold - config.silero_hysteresis_gap
    return max(end_threshold, config.silero_min_end_threshold)


def hysteresis_flags(probabilities: list[float], start: float, end: float) -> list[bool]:
    """Parole dès que p ≥ start, et jusqu'à ce que p < end : un creux bref au milieu d'un mot
    ne coupe pas le segment, mais un son faible ne peut pas en commencer un."""
    flags: list[bool] = []
    speaking = False
    for probability in probabilities:
        if not speaking and probability >= start:
            speaking = True
        elif speaking and probability < end:
            speaking = False
        flags.append(speaking)
    return flags


def option_flags(
    decisions: ClipDecisions, option: VadOption, config: VadBenchmarkConfig
) -> tuple[list[bool], float]:
    """Décisions par trame d'une option, et durée d'une trame en secondes."""
    if option.method == "silero":
        return _silero_flags(decisions, option), decisions.silero_frame_s
    if option.aggressiveness is None:
        raise ValueError(f"Option sans agressivité : {option.name}")
    level_flags = decisions.webrtcvad_flags[option.aggressiveness]
    if option.method == "webrtcvad":
        return level_flags, decisions.webrtcvad_frame_s
    if option.band_threshold is None:
        raise ValueError(f"Option sans seuil d'énergie : {option.name}")
    band_flags = _flags_above(decisions.band_shares, option.band_threshold)
    # Une trame est « parole » si webrtcvad le dit ET si la bande porte assez d'énergie.
    combined = [vad and band for vad, band in zip(level_flags, band_flags, strict=True)]
    return combined, decisions.webrtcvad_frame_s


def speech_seconds(
    decisions: ClipDecisions, option: VadOption, vad_config: VadConfig, config: VadBenchmarkConfig
) -> float:
    """Durée totale de « parole » d'un extrait après le nettoyage des segments de D5."""
    flags, frame_s = option_flags(decisions, option, config)
    segments = flags_to_segments(flags, frame_s, vad_config, decisions.duration_s)
    total_s = 0.0
    for segment in segments:
        total_s += segment.duration_s
    return total_s


def speech_shares(
    clips: list[ClipDecisions],
    option: VadOption,
    vad_config: VadConfig,
    config: VadBenchmarkConfig,
) -> list[float]:
    """Part de la durée de chaque extrait détectée comme « parole »."""
    shares: list[float] = []
    for clip in clips:
        seconds = speech_seconds(clip, option, vad_config, config)
        shares.append(seconds / clip.duration_s)
    return shares


def false_positive_rate(
    clips: list[ClipDecisions],
    option: VadOption,
    vad_config: VadConfig,
    config: VadBenchmarkConfig,
) -> float:
    """Part des extraits non vocaux avec au moins false_speech_min_s de « parole »."""
    flagged = false_positive_labels(clips, option, vad_config, config)
    return len(flagged) / len(clips)


def false_positive_labels(
    clips: list[ClipDecisions],
    option: VadOption,
    vad_config: VadConfig,
    config: VadBenchmarkConfig,
) -> list[str]:
    """Classe de chaque extrait non vocal compté comme faux positif."""
    labels: list[str] = []
    for clip in clips:
        seconds = speech_seconds(clip, option, vad_config, config)
        if seconds >= config.false_speech_min_s:
            labels.append(clip.label)
    return labels


def speech_recall(
    clips: list[ClipDecisions],
    option: VadOption,
    vad_config: VadConfig,
    config: VadBenchmarkConfig,
) -> float:
    """Part des extraits de parole dont au moins speech_share_min de la durée est « parole »."""
    found = 0
    for share in speech_shares(clips, option, vad_config, config):
        if share >= config.speech_share_min:
            found += 1
    return found / len(clips)


def score_options(
    noise_clips: list[ClipDecisions],
    speech_clips: list[ClipDecisions],
    vad_config: VadConfig,
    config: VadBenchmarkConfig,
) -> list[OptionScore]:
    """Faux positifs et parole retrouvée de chaque option, et respect des deux critères."""
    scores: list[OptionScore] = []
    for option in benchmark_options(config):
        fp_rate = false_positive_rate(noise_clips, option, vad_config, config)
        recall = speech_recall(speech_clips, option, vad_config, config)
        fp_ok = fp_rate <= config.max_false_positive_rate
        recall_ok = recall >= config.min_speech_recall
        scores.append(OptionScore(option, fp_rate, recall, fp_ok and recall_ok))
    return scores


def select_option(scores: list[OptionScore]) -> OptionScore | None:
    """Option retenue : la famille la plus simple qui a une option valide (METHOD_ORDER).

    Dans cette famille, la plus forte parole retrouvée, puis les moins de faux positifs.
    None si aucune option ne tient les deux critères.
    """
    for method in METHOD_ORDER:
        candidates = [score for score in scores if score.passes and score.option.method == method]
        if not candidates:
            continue
        best = candidates[0]
        for candidate in candidates[1:]:
            if _is_better(candidate, best):
                best = candidate
        return best
    return None


def most_frequent_labels(labels: list[str], count: int) -> list[tuple[str, int]]:
    """Les count classes les plus fréquentes, avec leur nombre d'extraits."""
    return Counter(labels).most_common(count)


def save_clip_decisions(clips: list[ClipDecisions], path: Path) -> None:
    """Enregistre les décisions brutes en JSON, pour recombiner les options sans recalcul."""
    records = [asdict(clip) for clip in clips]
    path.write_text(json.dumps(records), encoding="utf-8")


def load_clip_decisions(path: Path) -> list[ClipDecisions]:
    """Relit les décisions brutes enregistrées par save_clip_decisions."""
    records = json.loads(path.read_text(encoding="utf-8"))
    return [ClipDecisions(**record) for record in records]


def _is_better(candidate: OptionScore, best: OptionScore) -> bool:
    if candidate.speech_recall != best.speech_recall:
        return candidate.speech_recall > best.speech_recall
    return candidate.false_positive_rate < best.false_positive_rate


def _silero_flags(decisions: ClipDecisions, option: VadOption) -> list[bool]:
    if option.silero_threshold is None:
        raise ValueError(f"Option sans seuil Silero : {option.name}")
    probabilities = decisions.silero_probabilities
    if option.silero_end_threshold is None:
        return _flags_above(probabilities, option.silero_threshold)
    return hysteresis_flags(probabilities, option.silero_threshold, option.silero_end_threshold)


def _flags_above(values: list[float], threshold: float) -> list[bool]:
    return [value >= threshold for value in values]
