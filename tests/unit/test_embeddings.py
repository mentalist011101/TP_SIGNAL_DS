from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from echolens.training.embeddings import (
    EmbeddingMetadata,
    EncoderConfig,
    layer_means,
    load_embeddings,
    load_embeddings_config,
    mean_cosine_of_random_pairs,
    save_embeddings,
    whisper_useful_frames,
)

# Réglages de Whisper base (configs/embeddings.yaml) : 320 échantillons par trame de sortie,
# 1 500 trames pour 30 s.
SAMPLES_PER_FRAME = 320
MAX_FRAMES = 1500


def test_one_second_gives_50_useful_frames() -> None:
    assert whisper_useful_frames(16_000, SAMPLES_PER_FRAME, MAX_FRAMES) == 50


def test_thirty_seconds_give_1500_useful_frames() -> None:
    assert whisper_useful_frames(30 * 16_000, SAMPLES_PER_FRAME, MAX_FRAMES) == 1500


def test_one_sample_gives_one_useful_frame() -> None:
    assert whisper_useful_frames(1, SAMPLES_PER_FRAME, MAX_FRAMES) == 1


def test_more_than_thirty_seconds_is_refused() -> None:
    with pytest.raises(ValueError, match="trop long"):
        whisper_useful_frames(30 * 16_000 + 1, SAMPLES_PER_FRAME, MAX_FRAMES)


def synthetic_hidden_states() -> np.ndarray:
    # 2 couches, 4 trames, 3 dimensions. Couche 0, trame t : [1, 2, 3] + 2t ;
    # couche 1 : la couche 0 multipliée par 10.
    layer_0 = np.array([[1, 2, 3], [3, 4, 5], [5, 6, 7], [7, 8, 9]], dtype=np.float32)
    layer_1 = 10 * layer_0
    return np.stack([layer_0, layer_1])


def test_layer_means_over_all_frames() -> None:
    # Moyenne des 4 trames de la couche 0 : (1 + 3 + 5 + 7) / 4 = 4, puis 5 et 6.
    means = layer_means(synthetic_hidden_states())
    expected = np.array([[4, 5, 6], [40, 50, 60]], dtype=np.float32)
    assert means.dtype == np.float32
    np.testing.assert_allclose(means, expected)


def test_layer_means_over_the_first_frames_only() -> None:
    # Les 2 premières trames de la couche 0 : (1 + 3) / 2 = 2, puis 3 et 4.
    means = layer_means(synthetic_hidden_states(), frame_count=2)
    expected = np.array([[2, 3, 4], [20, 30, 40]], dtype=np.float32)
    np.testing.assert_allclose(means, expected)


def test_weighted_sum_commutes_with_time_mean() -> None:
    # moyenne_t(Σ_l w_l·h_l,t) = Σ_l w_l·moyenne_t(h_l,t) : c'est ce qui permet de ne
    # calculer les moyennes qu'une fois (Brique 4).
    hidden_states = synthetic_hidden_states()
    weights = np.array([0.3, 0.7], dtype=np.float32)
    weighted_frames = np.tensordot(weights, hidden_states, axes=1)
    sum_then_mean = weighted_frames.mean(axis=0)
    mean_then_sum = np.tensordot(weights, layer_means(hidden_states), axes=1)
    np.testing.assert_allclose(sum_then_mean, mean_then_sum, rtol=1e-6)


def test_real_config_has_three_frozen_encoders() -> None:
    config = load_embeddings_config()
    encoder_ids = [encoder.id for encoder in config.encoders]
    assert encoder_ids == ["wav2vec2-base", "mhubert-147", "whisper-base"]
    assert config.datasets == ["esc50", "cremad", "ravdess"]
    whisper = config.encoders[2]
    assert whisper.samples_per_output_frame == SAMPLES_PER_FRAME
    assert whisper.max_output_frames == MAX_FRAMES


def test_whisper_encoder_without_frame_settings_is_refused() -> None:
    with pytest.raises(ValidationError, match="obligatoires"):
        EncoderConfig(id="w", checkpoint="openai/whisper-base", revision="0" * 40, kind="whisper")


def make_metadata(clip_count: int) -> EmbeddingMetadata:
    return EmbeddingMetadata(
        encoder_id="wav2vec2-base",
        checkpoint="facebook/wav2vec2-base",
        revision="0" * 40,
        dataset="esc50",
        padded=False,
        torch_version="test",
        transformers_version="test",
        do_normalize=True,
        layer_count=2,
        dimension=3,
        clip_count=clip_count,
        gpu="cpu",
        compute_seconds=1.5,
        sample_rate=16_000,
    )


def test_embeddings_round_trip(tmp_path: Path) -> None:
    embeddings = np.stack([synthetic_hidden_states()[:, 0, :], synthetic_hidden_states()[:, 1, :]])
    index = [("esc50", "audio/a.wav"), ("esc50", "audio/b.wav")]
    save_embeddings(tmp_path, embeddings, index, make_metadata(clip_count=2))
    files = load_embeddings(tmp_path)
    np.testing.assert_array_equal(files.embeddings, embeddings)
    assert files.embeddings.dtype == np.float32
    assert files.index == index
    assert files.metadata == make_metadata(clip_count=2)


def test_embeddings_and_index_must_have_the_same_length(tmp_path: Path) -> None:
    embeddings = np.zeros((2, 2, 3), dtype=np.float32)
    with pytest.raises(ValueError, match="lignes d'index"):
        save_embeddings(tmp_path, embeddings, [("esc50", "a.wav")], make_metadata(clip_count=2))


def test_identical_vectors_have_cosine_one() -> None:
    vectors = np.ones((5, 4), dtype=np.float32)
    assert mean_cosine_of_random_pairs(vectors, pair_count=20, seed=42) == pytest.approx(1.0)


def test_orthogonal_vectors_have_cosine_zero() -> None:
    vectors = np.array([[1, 0], [0, 1]], dtype=np.float32)
    assert mean_cosine_of_random_pairs(vectors, pair_count=20, seed=42) == pytest.approx(0.0)
