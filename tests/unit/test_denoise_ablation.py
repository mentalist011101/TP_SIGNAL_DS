import numpy as np
import pytest

from echolens.training.denoise_ablation import (
    choose_strength,
    fit_noise_length,
    load_ablation_config,
    measured_snr_db,
    mix_at_snr,
    pick_noise_clip,
    rms,
    rms_dbfs,
)

SAMPLE_RATE = 16_000


def sine(level_rms: float, seconds: float = 1.0) -> np.ndarray:
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    wave = np.sin(2 * np.pi * 440 * t)
    # Le RMS d'une sinusoïde d'amplitude 1 vaut 1 / racine(2) : on ramène au niveau voulu.
    return (wave * level_rms * np.sqrt(2.0)).astype(np.float32)


def test_mix_at_snr_gives_exact_snr():
    signal = sine(0.1)
    rng = np.random.default_rng(0)
    noise = rng.normal(0.0, 0.3, signal.size).astype(np.float32)
    for snr in [20.0, 10.0, 0.0]:
        mixed = mix_at_snr(signal, noise, snr)
        assert measured_snr_db(signal, mixed) == pytest.approx(snr, abs=1e-3)


def test_zero_db_means_equal_levels():
    # À 0 dB, le bruit ajouté a exactement le même RMS que le signal (calcul à la main).
    signal = sine(0.2)
    noise = np.random.default_rng(1).normal(0.0, 1.0, signal.size).astype(np.float32)
    mixed = mix_at_snr(signal, noise, 0.0)
    added = mixed - signal
    assert rms(added) == pytest.approx(rms(signal), rel=1e-3)


def test_mix_refuses_different_lengths_and_silent_noise():
    signal = sine(0.1)
    with pytest.raises(ValueError):
        mix_at_snr(signal, signal[:-1], 10.0)
    with pytest.raises(ValueError):
        mix_at_snr(signal, np.zeros_like(signal), 10.0)


def test_fit_noise_length_loops_short_noise():
    noise = np.arange(10, dtype=np.float32)
    fitted = fit_noise_length(noise, length=25, start=8)
    assert fitted.size == 25
    assert fitted[:4].tolist() == [8.0, 9.0, 0.0, 1.0]


def test_pick_noise_clip_skips_quiet_clips_and_fails_when_all_quiet():
    quiet = np.full(1000, 1e-5, dtype=np.float32)
    loud = np.full(1000, 0.1, dtype=np.float32)
    rng = np.random.default_rng(0)
    picked = pick_noise_clip([quiet, loud], min_dbfs=-50.0, max_tries=50, rng=rng)
    assert rms_dbfs(picked) > -50.0
    with pytest.raises(RuntimeError):
        pick_noise_clip([quiet], min_dbfs=-50.0, max_tries=5, rng=rng)


def test_choose_strength_best_mean_wins():
    scores = {"none": 0.60, "0.5": 0.65, "0.8": 0.70, "1.0": 0.62}
    chosen, _ = choose_strength(scores, tie_decimals=3)
    assert chosen == "0.8"


def test_choose_strength_tie_picks_weakest_strength():
    scores = {"none": 0.6502, "0.5": 0.6504, "0.8": 0.6503, "1.0": 0.40}
    chosen, rounded = choose_strength(scores, tie_decimals=3)
    assert rounded["none"] == rounded["0.5"] == rounded["0.8"] == 0.65
    assert chosen == "none"


def test_choose_strength_tie_between_numbers_picks_smaller():
    scores = {"none": 0.50, "0.5": 0.70, "0.8": 0.70, "1.0": 0.70}
    chosen, _ = choose_strength(scores, tie_decimals=3)
    assert chosen == "0.5"


def test_ablation_config_matches_spec():
    config = load_ablation_config()
    assert config.strengths == [None, 0.5, 0.8, 1.0]
    assert config.snr_db == [None, 20, 10, 0]
