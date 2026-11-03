from pathlib import Path

import pytest

from echolens.config import CONFIG_DIR, load_settings
from echolens.core.features import FeatureConfig
from echolens.core.models.registry import ModelRegistry, Profile, Task


def test_feature_config_matches_specification() -> None:
    config = FeatureConfig.from_yaml(CONFIG_DIR / "features.yaml")
    assert config.sample_rate == 16_000
    assert config.n_fft == 400  # 25 ms
    assert config.hop_length == 160  # 10 ms
    assert config.frequency_resolution_hz == pytest.approx(40.0)


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ECHOLENS_MAX_UPLOAD_MB", "7")
    assert load_settings().max_upload_mb == 7


def test_registry_loads_and_filters(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text(
        "models:\n"
        "  - {id: emo-cnn, task: emotion, family: A, profiles: [realtime]}\n"
        "  - {id: emo-mhubert, task: emotion, family: B, profiles: [quality]}\n",
        encoding="utf-8",
    )
    registry = ModelRegistry.from_yaml(path)
    assert registry.get("emo-cnn").family == "A"
    assert [m.id for m in registry.for_task(Task.EMOTION, Profile.QUALITY)] == ["emo-mhubert"]


def test_registry_rejects_duplicates(tmp_path: Path) -> None:
    path = tmp_path / "registry.yaml"
    path.write_text(
        "models:\n"
        "  - {id: dup, task: emotion, family: A, profiles: [realtime]}\n"
        "  - {id: dup, task: emotion, family: B, profiles: [quality]}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="double"):
        ModelRegistry.from_yaml(path)


def test_default_registry_is_valid() -> None:
    ModelRegistry.from_yaml(CONFIG_DIR / "registry.yaml")
