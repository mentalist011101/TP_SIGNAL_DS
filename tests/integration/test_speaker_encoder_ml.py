"""Vrai modèle de voix du registre (ECAPA-TDNN, C15) : forme et stabilité des vecteurs.

Marqueur ml : télécharge le modèle depuis Hugging Face (environ 80 Mo), à sa révision figée.
"""

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("speechbrain")

from echolens.config import CONFIG_DIR
from echolens.core.models.registry import ModelRegistry, Profile, Task
from echolens.services.speaker_encoder import SpeakerEncoder

pytestmark = pytest.mark.ml

SAMPLE_RATE = 16_000
VECTOR_SIZE = 192


def test_ecapa_gives_the_same_192_values_for_the_same_signal(tmp_path: Path) -> None:
    registry = ModelRegistry.from_yaml(CONFIG_DIR / "registry.yaml")
    entry = registry.model_for(Task.SPEAKER, Profile.REALTIME)
    assert entry is not None
    generator = np.random.default_rng(0)
    signal = (0.1 * generator.standard_normal(3 * SAMPLE_RATE)).astype(np.float32)
    encoder = SpeakerEncoder(tmp_path)

    first, second = encoder.embed(entry, [signal, signal])

    assert first.shape == (VECTOR_SIZE,)
    np.testing.assert_allclose(first, second, rtol=1e-5)
