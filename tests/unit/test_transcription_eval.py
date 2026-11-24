"""Évaluation de la transcription (C17a) avec de petites listes écrites à la main, sans modèle."""

import pytest

from echolens.core.data.manifest import ManifestRow
from echolens.training.transcription_eval import (
    CorpusSelection,
    Interval,
    SentenceScore,
    bootstrap_intervals,
    corpus_rows,
    error_rates,
    interval_contains_zero,
    load_transcription_eval_config,
    paired_wer_difference,
    sample_rows,
    score_sentence,
    worst_sentences,
)

DRAWS = 1000
SEED = 42
LEVEL = 0.95


def make_score(path: str, speaker: str, word_errors: int, word_count: int) -> SentenceScore:
    # Les caractères suivent les mots (5 caractères par mot), pour garder des CER simples.
    return SentenceScore(
        path=path,
        speaker=speaker,
        reference="",
        hypothesis="",
        word_errors=word_errors,
        word_count=word_count,
        char_errors=5 * word_errors,
        char_count=5 * word_count,
    )


def make_row(path: str, official_split: str, subset: str) -> ManifestRow:
    return ManifestRow(
        dataset="openslr57",
        path=path,
        speaker="001",
        duration_s=3.0,
        official_split=official_split,
        subset=subset,
        transcript="bonjour",
    )


def test_one_substitution_and_one_insertion_on_three_words() -> None:
    score = score_sentence("a.wav", "001", "le chat dort", "le chien dort bien")
    assert score.word_errors == 2
    assert score.word_count == 3
    assert score.char_count == len("le chat dort")


def test_p12_normalization_is_applied_to_both_sides() -> None:
    score = score_sentence("a.wav", "001", "C' est à 7 h 30.", "c’est à sept heures trente")
    assert score.word_errors == 0
    assert score.char_errors == 0
    assert score.reference == "c'est à sept heures trente"


def test_empty_transcription_counts_every_reference_word_as_deleted() -> None:
    score = score_sentence("a.wav", "001", "il fait beau", "")
    assert score.word_errors == 3
    assert score.word_count == 3


def test_corpus_wer_is_total_errors_over_total_words() -> None:
    # 2 erreurs sur 3 mots, puis 0 sur 2 : WER du corpus 2 / 5 = 0,4, et non la moyenne des
    # deux phrases (0,33).
    scores = [make_score("a", "001", 2, 3), make_score("b", "002", 0, 2)]
    wer, cer = error_rates(scores)
    assert wer == pytest.approx(0.4)
    assert cer == pytest.approx(0.4)


def test_bootstrap_draws_speakers_not_sentences() -> None:
    # Locuteur A : tout juste (2 phrases) ; locuteur B : tout faux. Un tirage de 2 locuteurs
    # donne 0, 0,5 ou 1 : l'intervalle à 95 % va de 0 à 1.
    scores = [
        make_score("a1", "A", 0, 4),
        make_score("a2", "A", 0, 4),
        make_score("b1", "B", 8, 8),
    ]
    wer, cer = bootstrap_intervals(scores, DRAWS, SEED, LEVEL)
    assert wer.value == pytest.approx(0.5)
    assert wer.low == pytest.approx(0.0)
    assert wer.high == pytest.approx(1.0)
    assert cer.value == pytest.approx(0.5)


def test_bootstrap_interval_is_a_point_when_every_speaker_has_the_same_wer() -> None:
    scores = [make_score("a", "A", 1, 4), make_score("b", "B", 2, 8), make_score("c", "C", 3, 12)]
    wer, _ = bootstrap_intervals(scores, DRAWS, SEED, LEVEL)
    assert wer.low == pytest.approx(0.25)
    assert wer.high == pytest.approx(0.25)


def test_bootstrap_is_reproducible_with_the_seed() -> None:
    scores = [make_score("a", "A", 1, 4), make_score("b", "B", 3, 4), make_score("c", "C", 0, 4)]
    first = bootstrap_intervals(scores, DRAWS, SEED, LEVEL)
    second = bootstrap_intervals(scores, DRAWS, SEED, LEVEL)
    assert first == second


def test_paired_difference_of_a_system_better_for_every_speaker() -> None:
    # Le second système fait une erreur de moins sur chaque phrase de 4 mots : −0,25 partout.
    first = [make_score("a", "A", 2, 4), make_score("b", "B", 2, 4)]
    second = [make_score("a", "A", 1, 4), make_score("b", "B", 1, 4)]
    difference = paired_wer_difference(first, second, DRAWS, SEED, LEVEL)
    assert difference.value == pytest.approx(-0.25)
    assert difference.low == pytest.approx(-0.25)
    assert difference.high == pytest.approx(-0.25)
    assert not interval_contains_zero(difference)


def test_paired_difference_of_identical_systems_is_zero() -> None:
    scores = [make_score("a", "A", 2, 4), make_score("b", "B", 1, 4)]
    difference = paired_wer_difference(scores, scores, DRAWS, SEED, LEVEL)
    assert difference == Interval(0.0, 0.0, 0.0)
    assert interval_contains_zero(difference)


def test_paired_difference_needs_the_same_sentences() -> None:
    first = [make_score("a", "A", 1, 4)]
    second = [make_score("b", "A", 1, 4)]
    with pytest.raises(ValueError, match="pas les mêmes"):
        paired_wer_difference(first, second, DRAWS, SEED, LEVEL)


def test_worst_sentences_have_the_most_word_errors() -> None:
    scores = [
        make_score("a", "A", 1, 4),
        make_score("b", "A", 5, 6),
        make_score("c", "B", 3, 4),
        make_score("d", "B", 5, 9),
    ]
    worst = worst_sentences(scores, 3)
    assert [score.path for score in worst] == ["b", "d", "c"]


def test_corpus_rows_by_official_split_or_subset() -> None:
    rows = [
        make_row("t1.wav", "test", "ca16"),
        make_row("y1.wav", "train", "yaounde"),
        make_row("n1.wav", "dev", "niger"),
    ]
    test_rows = corpus_rows(rows, CorpusSelection(id="test", official_split="test"))
    yaounde_rows = corpus_rows(rows, CorpusSelection(id="yaounde", subset="yaounde"))
    assert [row.path for row in test_rows] == ["t1.wav"]
    assert [row.path for row in yaounde_rows] == ["y1.wav"]


def test_sample_is_reproducible_and_without_duplicates() -> None:
    rows = [make_row(f"{index}.wav", "test", "ca16") for index in range(50)]
    first = sample_rows(rows, 10, SEED)
    second = sample_rows(rows, 10, SEED)
    paths = [row.path for row in first]
    assert paths == [row.path for row in second]
    assert len(set(paths)) == 10


def test_configuration_pins_both_models() -> None:
    config = load_transcription_eval_config()
    model_ids = [model.id for model in config.models]
    assert model_ids == ["base", "small"]
    assert config.language == "fr"
    assert config.vad_filter is False
    assert config.condition_on_previous_text is False
    assert config.bootstrap_draws == 1000
    assert config.cpu_check_sentences == 100
