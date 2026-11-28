"""C17a : évaluation de la transcription (EF-10, E1, P10, P12), sans modèle.

Ce module ne fait que compter : les transcriptions viennent du notebook c17_transcription
(faster-whisper, module transcription_models). Pour chaque phrase, référence et transcription
sont normalisées de la même façon (P12), puis jiwer compte les erreurs de mots et de
caractères (substitutions + suppressions + insertions).

- WER et CER du corpus = total des erreurs / total des mots (ou caractères) de référence : une
  phrase longue pèse plus qu'une phrase courte.
- Intervalle à 95 % par bootstrap PAR LOCUTEUR : on tire des locuteurs avec remise, puis on
  garde toutes leurs phrases. Les phrases d'un même locuteur ne sont pas indépendantes (même
  voix, même micro) ; tirer des phrases donnerait un intervalle trop étroit.
- Écart entre deux systèmes (small − base, int8 − float16) : bootstrap apparié, les mêmes
  locuteurs tirés pour les deux systèmes. Si l'intervalle contient 0, l'écart n'est pas
  significatif.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import jiwer
import numpy as np
from pydantic import BaseModel, Field

from echolens.config import CONFIG_DIR, load_yaml
from echolens.core.data.manifest import ManifestRow
from echolens.core.text_normalization import normalize_for_wer

TRANSCRIPTION_CONFIG_PATH = CONFIG_DIR / "transcription.yaml"


class TranscriptionModel(BaseModel):
    """Un modèle faster-whisper du Hub, à une révision figée."""

    id: str
    repo_id: str
    revision: str = Field(min_length=40, max_length=40)


class CorpusSelection(BaseModel):
    """Un sous-corpus d'OpenSLR 57 : par découpage officiel, sous-corpus et dossier (P10)."""

    id: str
    official_split: str | None = None
    subset: str | None = None
    # Dossier qui doit figurer dans le chemin du fichier (ex. « read » pour yaounde/read).
    folder: str | None = None


class TranscriptionEvalConfig(BaseModel):
    """Contenu de configs/transcription.yaml."""

    models: list[TranscriptionModel] = Field(min_length=1)
    language: str
    beam_size: int = Field(gt=0)
    temperature: list[float] = Field(min_length=1)
    vad_filter: bool
    condition_on_previous_text: bool
    cpu_threads: int = Field(gt=0)
    corpora: list[CorpusSelection] = Field(min_length=1)
    seed: int
    bootstrap_draws: int = Field(gt=0)
    confidence_level: float = Field(gt=0, lt=1)
    cpu_check_sentences: int = Field(gt=0)
    worst_sentence_count: int = Field(gt=0)
    suspect_min_wer: float = Field(gt=0)
    latency_audio_s: float = Field(gt=0)
    latency_runs: int = Field(gt=0)


@dataclass(frozen=True)
class SentenceScore:
    """Erreurs d'une phrase, après normalisation P12 de la référence et de la transcription."""

    path: str
    speaker: str
    reference: str
    hypothesis: str
    word_errors: int
    word_count: int
    char_errors: int
    char_count: int


@dataclass(frozen=True)
class Interval:
    """Valeur mesurée sur tout le corpus et son intervalle de confiance (bootstrap)."""

    value: float
    low: float
    high: float


@dataclass(frozen=True)
class ErrorTotals:
    """Somme des erreurs et des longueurs de référence d'un groupe de phrases."""

    word_errors: int
    word_count: int
    char_errors: int
    char_count: int


def load_transcription_eval_config(
    path: Path = TRANSCRIPTION_CONFIG_PATH,
) -> TranscriptionEvalConfig:
    """Lit configs/transcription.yaml."""
    return TranscriptionEvalConfig(**load_yaml(path))


def corpus_rows(rows: list[ManifestRow], selection: CorpusSelection) -> list[ManifestRow]:
    """Lignes du manifeste d'OpenSLR 57 qui appartiennent au sous-corpus demandé (P10)."""
    selected: list[ManifestRow] = []
    for row in rows:
        if selection.official_split is not None and row.official_split != selection.official_split:
            continue
        if selection.subset is not None and row.subset != selection.subset:
            continue
        if selection.folder is not None and not _in_folder(row.path, selection.folder):
            continue
        selected.append(row)
    return selected


def sample_rows(rows: list[ManifestRow], size: int, seed: int) -> list[ManifestRow]:
    """Tirage sans remise de size lignes, reproductible, dans l'ordre du manifeste."""
    generator = np.random.default_rng(seed)
    chosen = generator.choice(len(rows), size=size, replace=False)
    chosen_sorted = sorted(int(index) for index in chosen)
    return [rows[index] for index in chosen_sorted]


def score_sentence(path: str, speaker: str, reference: str, hypothesis: str) -> SentenceScore:
    """Normalise les deux textes (P12), puis compte les erreurs de mots et de caractères."""
    clean_reference = normalize_for_wer(reference)
    clean_hypothesis = normalize_for_wer(hypothesis)
    # Mots : alignement de Levenshtein entre les deux suites de mots (jiwer).
    words = jiwer.process_words(clean_reference, clean_hypothesis)
    word_errors = words.substitutions + words.deletions + words.insertions
    word_count = words.hits + words.substitutions + words.deletions
    # Caractères : même calcul, lettre par lettre (espaces compris).
    chars = jiwer.process_characters(clean_reference, clean_hypothesis)
    char_errors = chars.substitutions + chars.deletions + chars.insertions
    char_count = chars.hits + chars.substitutions + chars.deletions
    return SentenceScore(
        path=path,
        speaker=speaker,
        reference=clean_reference,
        hypothesis=clean_hypothesis,
        word_errors=word_errors,
        word_count=word_count,
        char_errors=char_errors,
        char_count=char_count,
    )


def error_rates(scores: list[SentenceScore]) -> tuple[float, float]:
    """WER et CER de tout le corpus : total des erreurs / total des mots (caractères)."""
    totals = _sum_scores(scores)
    return _rates(totals)


def bootstrap_intervals(
    scores: list[SentenceScore], draws: int, seed: int, level: float
) -> tuple[Interval, Interval]:
    """WER et CER avec leur intervalle à level, par bootstrap par locuteur."""
    wer, cer = error_rates(scores)
    totals_per_speaker = _totals_per_speaker(scores)
    wer_values: list[float] = []
    cer_values: list[float] = []
    for drawn_speakers in _draw_speakers(sorted(totals_per_speaker), draws, seed):
        drawn_totals = _sum_speaker_totals(totals_per_speaker, drawn_speakers)
        drawn_wer, drawn_cer = _rates(drawn_totals)
        wer_values.append(drawn_wer)
        cer_values.append(drawn_cer)
    wer_low, wer_high = _percentile_bounds(wer_values, level)
    cer_low, cer_high = _percentile_bounds(cer_values, level)
    return Interval(wer, wer_low, wer_high), Interval(cer, cer_low, cer_high)


def paired_wer_difference(
    first: list[SentenceScore], second: list[SentenceScore], draws: int, seed: int, level: float
) -> Interval:
    """Écart de WER second − first sur les mêmes phrases, intervalle par bootstrap apparié.

    Les mêmes locuteurs sont tirés pour les deux systèmes : l'écart ne dépend que des
    différences de transcription, pas du hasard du tirage. Négatif : second fait mieux.
    """
    _check_same_sentences(first, second)
    first_wer, _ = error_rates(first)
    second_wer, _ = error_rates(second)
    first_per_speaker = _totals_per_speaker(first)
    second_per_speaker = _totals_per_speaker(second)
    differences: list[float] = []
    for drawn_speakers in _draw_speakers(sorted(first_per_speaker), draws, seed):
        drawn_first, _ = _rates(_sum_speaker_totals(first_per_speaker, drawn_speakers))
        drawn_second, _ = _rates(_sum_speaker_totals(second_per_speaker, drawn_speakers))
        differences.append(drawn_second - drawn_first)
    low, high = _percentile_bounds(differences, level)
    return Interval(second_wer - first_wer, low, high)


def interval_contains_zero(interval: Interval) -> bool:
    """Vrai si l'intervalle contient 0 : l'écart n'est pas significatif."""
    return interval.low <= 0.0 <= interval.high


def worst_sentences(scores: list[SentenceScore], count: int) -> list[SentenceScore]:
    """Les count phrases au plus grand nombre d'erreurs de mots (à égalité, par chemin)."""
    ordered = sorted(scores, key=_worst_first)
    return ordered[:count]


def suspect_sentences(
    first: list[SentenceScore], second: list[SentenceScore], min_wer: float
) -> list[tuple[SentenceScore, SentenceScore]]:
    """Phrases où les deux systèmes ont un WER de phrase ≥ min_wer : référence à vérifier.

    Deux modèles différents qui se trompent autant sur la même phrase pointent plutôt vers la
    référence (texte qui ne correspond pas à l'audio) que vers la reconnaissance.
    """
    _check_same_sentences(first, second)
    suspects: list[tuple[SentenceScore, SentenceScore]] = []
    for first_score, second_score in zip(first, second, strict=True):
        first_failed = _sentence_wer_at_least(first_score, min_wer)
        second_failed = _sentence_wer_at_least(second_score, min_wer)
        if first_failed and second_failed:
            suspects.append((first_score, second_score))
    return suspects


def country_of_speaker(speaker: str) -> str:
    """Pays d'un locuteur du test officiel d'OpenSLR 57 : « cameroon_m_006 » → « cameroon »."""
    fields = speaker.split("_")
    if len(fields) != 3:
        raise ValueError(f"Locuteur sans pays (attendu pays_genre_numéro) : {speaker}")
    return fields[0]


def scores_by_country(scores: list[SentenceScore]) -> dict[str, list[SentenceScore]]:
    """Range les phrases notées par pays du locuteur (test officiel d'OpenSLR 57 seulement)."""
    grouped: dict[str, list[SentenceScore]] = {}
    for score in scores:
        country = country_of_speaker(score.speaker)
        grouped.setdefault(country, []).append(score)
    return grouped


def _in_folder(path: str, folder: str) -> bool:
    # Le chemin du manifeste s'écrit avec des « / » (ex. speech/train/yaounde/read/…).
    parts = PurePosixPath(path).parts
    return folder in parts


def _sentence_wer_at_least(score: SentenceScore, min_wer: float) -> bool:
    # Comparaison sans division : une référence vide (0 mot) ne fait pas planter le calcul.
    return score.word_errors >= min_wer * score.word_count


def _worst_first(score: SentenceScore) -> tuple[int, str]:
    return (-score.word_errors, score.path)


def _rates(totals: ErrorTotals) -> tuple[float, float]:
    wer = totals.word_errors / totals.word_count
    cer = totals.char_errors / totals.char_count
    return wer, cer


def _sum_scores(scores: list[SentenceScore]) -> ErrorTotals:
    word_errors = 0
    word_count = 0
    char_errors = 0
    char_count = 0
    for score in scores:
        word_errors += score.word_errors
        word_count += score.word_count
        char_errors += score.char_errors
        char_count += score.char_count
    return ErrorTotals(word_errors, word_count, char_errors, char_count)


def _totals_per_speaker(scores: list[SentenceScore]) -> dict[str, ErrorTotals]:
    scores_per_speaker: dict[str, list[SentenceScore]] = {}
    for score in scores:
        scores_per_speaker.setdefault(score.speaker, []).append(score)
    totals: dict[str, ErrorTotals] = {}
    for speaker, speaker_scores in scores_per_speaker.items():
        totals[speaker] = _sum_scores(speaker_scores)
    return totals


def _draw_speakers(speakers: list[str], draws: int, seed: int) -> list[list[str]]:
    # Chaque tirage prend autant de locuteurs qu'il y en a, avec remise : certains reviennent
    # plusieurs fois, d'autres sont absents.
    generator = np.random.default_rng(seed)
    samples: list[list[str]] = []
    for _ in range(draws):
        indexes = generator.integers(0, len(speakers), size=len(speakers))
        samples.append([speakers[int(index)] for index in indexes])
    return samples


def _sum_speaker_totals(
    totals_per_speaker: dict[str, ErrorTotals], speakers: list[str]
) -> ErrorTotals:
    word_errors = 0
    word_count = 0
    char_errors = 0
    char_count = 0
    for speaker in speakers:
        totals = totals_per_speaker[speaker]
        word_errors += totals.word_errors
        word_count += totals.word_count
        char_errors += totals.char_errors
        char_count += totals.char_count
    return ErrorTotals(word_errors, word_count, char_errors, char_count)


def _percentile_bounds(values: list[float], level: float) -> tuple[float, float]:
    # Intervalle par percentiles : 2,5 % et 97,5 % des valeurs tirées pour level = 0,95.
    tail = (1.0 - level) / 2.0
    low = float(np.percentile(values, 100.0 * tail))
    high = float(np.percentile(values, 100.0 * (1.0 - tail)))
    return low, high


def _check_same_sentences(first: list[SentenceScore], second: list[SentenceScore]) -> None:
    first_paths = [score.path for score in first]
    second_paths = [score.path for score in second]
    if first_paths != second_paths:
        raise ValueError("Comparaison appariée impossible : les phrases ne sont pas les mêmes")
