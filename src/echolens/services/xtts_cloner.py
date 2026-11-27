"""Clonage réel avec XTTS-v2 (Coqui, paquet coqui-tts, extra [tts]) : EF-18, C35.

XTTS-v2 demande environ 2,5 Go de mémoire. Il n'est donc chargé qu'au premier clonage, puis
libéré après idle_unload_s secondes sans usage (configs/inference.yaml) : le reste de
l'application garde sa mémoire. Les imports de torch, huggingface_hub et coqui-tts sont faits au
chargement,
pour que le serveur démarre sans l'extra [tts].

Chaîne : extraits d'enregistrement du locuteur → « latents de conditionnement » (ce que XTTS
retient de la voix) → texte dit avec cette voix, en français, à 24 kHz.

Licence : Coqui Public Model License, usage non commercial. Le modèle ne se charge que si
voice_cloning_license_accepted est vrai (configs/app.yaml ou variable d'environnement).
"""

from __future__ import annotations

import gc
import os
import threading
from pathlib import Path
from typing import Any

import numpy as np

from echolens.core.inference import VoiceCloningSettings
from echolens.core.models.registry import ModelEntry
from echolens.services.voice_cloning import CloningUnavailableError, SpeechAudio

HF_PREFIX = "hf://"
LICENSE_MESSAGE = (
    "Clonage désactivé : XTTS-v2 est sous Coqui Public Model License (usage non commercial). "
    "Pour l'activer, la personne qui lance le serveur accepte la licence avec "
    "ECHOLENS_VOICE_CLONING_LICENSE_ACCEPTED=true."
)
MEMORY_MESSAGE = (
    "Mémoire insuffisante pour charger XTTS-v2 (environ 2,5 Go libres nécessaires) : fermez "
    "des applications, puis relancez le clonage."
)
MISSING_EXTRA_MESSAGE = "Clonage indisponible : installez l'extra tts (uv sync --extra tts)."


class XttsCloner:
    """XTTS-v2 chargé à la demande, libéré après un temps sans usage."""

    def __init__(
        self, entry: ModelEntry, settings: VoiceCloningSettings, license_accepted: bool
    ) -> None:
        self.entry = entry
        self.model_id = entry.id
        self.model_version = entry.version
        self.settings = settings
        self.license_accepted = license_accepted
        self._model: Any = None
        self._sample_rate = 0
        # Un seul clonage à la fois : deux chargements en parallèle doubleraient la mémoire.
        self._lock = threading.Lock()
        self._unload_timer: threading.Timer | None = None

    def check_available(self) -> None:
        """Lève CloningUnavailableError si la licence CPML n'a pas été acceptée."""
        if not self.license_accepted:
            raise CloningUnavailableError(LICENSE_MESSAGE)

    def synthesize(self, text: str, references: list[Path]) -> SpeechAudio:
        """Le texte dit avec la voix des extraits de référence, à 24 kHz."""
        self.check_available()
        with self._lock:
            model = self._loaded_model()
            samples = self._speak(model, text, references)
            self._schedule_unload()
        return SpeechAudio(samples=samples, sample_rate=self._sample_rate)

    def _speak(self, model: Any, text: str, references: list[Path]) -> Any:
        import torch

        # Étape 1 : ce que XTTS retient de la voix, à partir des extraits d'enregistrement.
        reference_paths = [str(path) for path in references]
        with torch.no_grad():
            latent, embedding = model.get_conditioning_latents(audio_path=reference_paths)
            # Étape 2 : le texte dit avec cette voix, dans la langue imposée.
            output = model.inference(
                text,
                self.settings.language,
                latent,
                embedding,
                temperature=self.settings.temperature,
            )
        return np.asarray(output["wav"], dtype=np.float32)

    def _loaded_model(self) -> Any:
        if self._model is None:
            self._model, self._sample_rate = _load_xtts(self.entry)
        return self._model

    def _schedule_unload(self) -> None:
        # Chaque clonage repousse la libération : le modèle reste chargé pendant une démo.
        if self._unload_timer is not None:
            self._unload_timer.cancel()
        timer = threading.Timer(self.settings.idle_unload_s, self._unload)
        # daemon : le minuteur n'empêche pas le serveur de s'arrêter.
        timer.daemon = True
        timer.start()
        self._unload_timer = timer

    def _unload(self) -> None:
        with self._lock:
            self._model = None
            gc.collect()


def _load_xtts(entry: ModelEntry) -> tuple[Any, int]:
    # Étape 1 : le dépôt à sa révision figée (cache Hugging Face).
    if not entry.weights.startswith(HF_PREFIX) or not entry.revision:
        raise CloningUnavailableError(f"{entry.id} : dépôt et révision attendus dans le registre.")
    from huggingface_hub import snapshot_download

    repo_id = entry.weights.removeprefix(HF_PREFIX)
    folder = Path(snapshot_download(repo_id=repo_id, revision=entry.revision))
    # Étape 2 : coqui-tts demande que la licence soit acceptée ; elle l'est (voir synthesize).
    os.environ["COQUI_TOS_AGREED"] = "1"
    try:
        from TTS.tts.configs.xtts_config import XttsConfig
        from TTS.tts.models.xtts import Xtts
    except ImportError as error:
        raise CloningUnavailableError(MISSING_EXTRA_MESSAGE) from error
    config = XttsConfig()
    config.load_json(str(folder / "config.json"))
    # Étape 3 : le réseau, puis ses poids, en mode eval ; « not enough memory » de torch devient
    # un message clair.
    try:
        model = Xtts.init_from_config(config)
        model.load_checkpoint(config, checkpoint_dir=str(folder), eval=True)
    except (MemoryError, RuntimeError) as error:
        if isinstance(error, MemoryError) or "memory" in str(error):
            raise CloningUnavailableError(MEMORY_MESSAGE) from error
        raise
    sample_rate = int(config.audio.output_sample_rate)
    return model, sample_rate
