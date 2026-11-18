"""Encodeurs de la famille B sur de minuscules modèles à poids aléatoires (extra [ml]).

On ne vérifie que les formes : les vrais poids sont téléchargés sur Kaggle, pas en test.
"""

import shutil
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")

from echolens.core.data.manifest import ManifestRow  # noqa: E402
from echolens.training.embeddings import EncoderConfig  # noqa: E402
from echolens.training.encoders import (  # noqa: E402
    LoadedEncoder,
    embed_manifest,
    embed_ssl,
    embed_whisper,
    make_metadata,
)

pytestmark = pytest.mark.ml

SAMPLE_RATE = 16_000
FAKE_REVISION = "0" * 40
# Tailles minuscules : 2 couches cachées de dimension 16, donc 3 sorties (entrée comprise).
HIDDEN_SIZE = 16
LAYER_COUNT = 2


def sine(duration_s: float) -> np.ndarray:
    t = np.arange(int(duration_s * SAMPLE_RATE)) / SAMPLE_RATE
    return (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)


def tiny_ssl_encoder() -> LoadedEncoder:
    config = transformers.Wav2Vec2Config(
        hidden_size=HIDDEN_SIZE,
        num_hidden_layers=LAYER_COUNT,
        num_attention_heads=2,
        intermediate_size=32,
        conv_dim=(8, 8, 8, 8, 8, 8, 8),
        num_conv_pos_embeddings=16,
        num_conv_pos_embedding_groups=2,
    )
    model = transformers.Wav2Vec2Model(config)
    model.eval()
    feature_extractor = transformers.Wav2Vec2FeatureExtractor(
        feature_size=1, sampling_rate=SAMPLE_RATE, do_normalize=True, return_attention_mask=False
    )
    encoder_config = EncoderConfig(
        id="tiny-ssl", checkpoint="tiny", revision=FAKE_REVISION, kind="ssl"
    )
    return LoadedEncoder(
        config=encoder_config,
        feature_extractor=feature_extractor,
        model=model,
        device=torch.device("cpu"),
        sample_rate=SAMPLE_RATE,
    )


def tiny_whisper_encoder() -> LoadedEncoder:
    # max_source_positions = 1 500 : l'encodeur exige 3 000 trames log-Mel, soit 30 s.
    config = transformers.WhisperConfig(
        d_model=HIDDEN_SIZE,
        encoder_layers=LAYER_COUNT,
        encoder_attention_heads=2,
        encoder_ffn_dim=32,
        decoder_layers=1,
        decoder_attention_heads=2,
        decoder_ffn_dim=32,
        num_mel_bins=80,
        max_source_positions=1500,
    )
    model = transformers.WhisperModel(config).get_encoder()
    model.eval()
    feature_extractor = transformers.WhisperFeatureExtractor(feature_size=80)
    encoder_config = EncoderConfig(
        id="tiny-whisper",
        checkpoint="tiny",
        revision=FAKE_REVISION,
        kind="whisper",
        samples_per_output_frame=320,
        max_output_frames=1500,
    )
    return LoadedEncoder(
        config=encoder_config,
        feature_extractor=feature_extractor,
        model=model,
        device=torch.device("cpu"),
        sample_rate=SAMPLE_RATE,
    )


def test_ssl_gives_one_mean_per_layer() -> None:
    means = embed_ssl(sine(1.0), tiny_ssl_encoder())
    assert means.shape == (LAYER_COUNT + 1, HIDDEN_SIZE)
    assert means.dtype == np.float32
    assert np.all(np.isfinite(means))


def test_whisper_gives_useful_and_padded_means() -> None:
    result = embed_whisper(sine(1.0), tiny_whisper_encoder())
    assert result.useful_mean.shape == (LAYER_COUNT + 1, HIDDEN_SIZE)
    assert result.padded_mean.shape == (LAYER_COUNT + 1, HIDDEN_SIZE)
    # 1 s = 50 trames utiles sur 1 500.
    assert result.useful_share == pytest.approx(50 / 1500)
    # Les deux moyennes ne portent pas sur les mêmes trames : elles diffèrent.
    assert not np.allclose(result.useful_mean, result.padded_mean)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="load_audio a besoin de ffmpeg")
def test_manifest_embeddings_keep_manifest_order(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "esc50"
    dataset_dir.mkdir()
    rows: list[ManifestRow] = []
    for name, duration_s in [("a.wav", 1.0), ("b.wav", 2.0)]:
        sf.write(dataset_dir / name, sine(duration_s), SAMPLE_RATE)
        rows.append(ManifestRow(dataset="esc50", path=name, duration_s=duration_s))
    encoder = tiny_whisper_encoder()
    result = embed_manifest(rows, tmp_path, encoder)
    assert result.embeddings.shape == (2, LAYER_COUNT + 1, HIDDEN_SIZE)
    assert result.padded is not None
    assert result.padded.shape == (2, LAYER_COUNT + 1, HIDDEN_SIZE)
    # Parts utiles : 50 et 100 trames sur 1 500, en moyenne 75 / 1 500.
    assert result.mean_useful_frame_share == pytest.approx(75 / 1500)
    metadata = make_metadata(encoder, "esc50", result, padded=True)
    assert metadata.clip_count == 2
    assert metadata.layer_count == LAYER_COUNT + 1
    assert metadata.do_normalize is False
