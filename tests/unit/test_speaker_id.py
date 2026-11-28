"""Identification du locuteur par cosinus (EF-11, C15) et morceaux de parole, sans torch."""

import json

import numpy as np
import pytest

from echolens.config import REPO_ROOT
from echolens.core.audio.segment import Segment
from echolens.core.inference import load_inference_config, speaker_windows
from echolens.core.speaker_id import best_match, speaking_shares, unit_vector, voice_print

C15_RESULTS = REPO_ROOT / "training" / "results" / "c15_speaker_openslr57.json"


def test_unit_vector_has_norm_one() -> None:
    vector = unit_vector(np.array([3.0, 4.0]))

    assert vector.tolist() == pytest.approx([0.6, 0.8])


def test_zero_vector_is_refused() -> None:
    with pytest.raises(ValueError, match="nul"):
        unit_vector(np.zeros(3))


def test_voice_print_gives_each_piece_the_same_weight() -> None:
    # Le second vecteur est 10 fois plus long : sans normalisation, il emporterait la moyenne.
    voice = voice_print([np.array([1.0, 0.0]), np.array([0.0, 10.0])])

    assert voice.tolist() == pytest.approx([np.sqrt(0.5), np.sqrt(0.5)])


def test_best_voice_is_chosen_when_above_the_threshold() -> None:
    voices = [unit_vector(np.array([1.0, 0.0])), unit_vector(np.array([0.0, 1.0]))]

    match = best_match(np.array([0.1, 2.0]), voices, threshold=0.5)

    assert match.index == 1
    assert match.score == pytest.approx(2.0 / np.sqrt(4.01))


def test_voice_under_the_threshold_is_unknown_but_keeps_its_score() -> None:
    voices = [unit_vector(np.array([1.0, 0.0]))]

    match = best_match(np.array([1.0, 1.0]), voices, threshold=0.8)

    assert match.index is None
    assert match.score == pytest.approx(np.sqrt(0.5))


def test_speaking_shares_sum_to_one_in_order_of_appearance() -> None:
    shares = speaking_shares(["awa", "unknown", "awa"], [2.0, 1.0, 1.0])

    assert list(shares) == ["awa", "unknown"]
    assert shares["awa"] == pytest.approx(0.75)
    assert shares["unknown"] == pytest.approx(0.25)


def test_speaker_windows_cut_long_turns_and_drop_short_pieces() -> None:
    settings = load_inference_config().speaker
    speech = [Segment(start_s=0.0, end_s=0.6), Segment(start_s=1.0, end_s=9.0)]

    windows = speaker_windows(speech, settings)

    # 0,6 s : trop court ; 8 s : deux morceaux de 4 s (5 s au plus).
    bounds = [(window.start_s, window.end_s) for window in windows]
    assert bounds == [(1.0, 5.0), (5.0, 9.0)]


def test_speaker_threshold_is_the_c15_one() -> None:
    # Une seule vérité : le seuil de l'application est celui mesuré en C15 (P11).
    results = json.loads(C15_RESULTS.read_text(encoding="utf-8"))
    measured = results["encoders"]["ecapa-voxceleb"]["threshold"]

    assert load_inference_config().speaker.threshold == pytest.approx(measured, abs=5e-5)
