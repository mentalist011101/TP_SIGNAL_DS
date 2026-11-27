"""C19 : outils de l'ablation du débruitage (D4) : bruit au SNR exact et règle de choix.

Calcul pur (numpy). Les modèles (Whisper, tête des émotions) sont appelés dans le notebook
c19_denoising_ablation, pas ici.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field

from echolens.config import CONFIG_DIR, load_yaml

FloatArray = npt.NDArray[np.float32]
ABLATION_CONFIG_PATH = CONFIG_DIR / "denoise_ablation.yaml"

# Plancher numérique pour éviter une division par zéro sur un signal nul.
_EPS = 1e-10


class AblationConfig(BaseModel):
    """Contenu de configs/denoise_ablation.yaml."""

    strengths: list[float | None] = Field(min_length=1)
    snr_db: list[float | None] = Field(min_length=1)
    noise_classes: list[str] = Field(min_length=1)
    noise_min_dbfs: float
    noise_max_tries: int = Field(gt=0)
    emotion_model_id: str
    whisper_model_id: str
    wer_sentences: int | None = Field(default=None, gt=0)
    tie_decimals: int = Field(ge=0)
    seed: int


def load_ablation_config(path: Path = ABLATION_CONFIG_PATH) -> AblationConfig:
    """Lit configs/denoise_ablation.yaml."""
    return AblationConfig(**load_yaml(path))


def rms(signal: FloatArray) -> float:
    """Niveau RMS (racine de la moyenne des carrés) du signal."""
    squares = np.square(signal, dtype=np.float64)
    return float(np.sqrt(np.mean(squares)))


def rms_dbfs(signal: FloatArray) -> float:
    """Niveau RMS en dBFS."""
    return 20.0 * float(np.log10(max(rms(signal), _EPS)))


def fit_noise_length(noise: FloatArray, length: int, start: int) -> FloatArray:
    """Bruit de exactement `length` échantillons : on lit à partir de `start`, en bouclant.

    Un bruit plus court que la parole (ESC-50 : 5 s) est répété jusqu'à la bonne longueur.
    """
    positions = (start + np.arange(length)) % len(noise)
    return noise[positions].astype(np.float32)


def mix_at_snr(signal: FloatArray, noise: FloatArray, snr_db: float) -> FloatArray:
    """Mélange `signal` et `noise` pour que le rapport signal/bruit vaille exactement snr_db.

    SNR = 20 × log10(RMS signal / RMS bruit). On multiplie le bruit par
    g = RMS signal / (RMS bruit × 10^(SNR / 20)), puis on additionne. `noise` doit avoir la
    même longueur que `signal`. Pas d'écrêtage ici : le prétraitement (D3) s'en charge.
    """
    if len(noise) != len(signal):
        raise ValueError("signal et bruit doivent avoir la même longueur")
    signal_level = rms(signal)
    noise_level = rms(noise)
    if noise_level < _EPS:
        raise ValueError("bruit nul : le SNR n'est pas défini")
    wanted_ratio = 10.0 ** (snr_db / 20.0)
    gain = signal_level / (noise_level * wanted_ratio)
    mixed = signal + gain * noise
    return mixed.astype(np.float32)


def measured_snr_db(signal: FloatArray, mixed: FloatArray) -> float:
    """SNR réellement obtenu : (mélange − signal) est le bruit ajouté. Sert aux contrôles."""
    added_noise = mixed - signal
    return 20.0 * float(np.log10(rms(signal) / rms(added_noise)))


def pick_noise_clip(
    candidates: list[FloatArray], min_dbfs: float, max_tries: int, rng: np.random.Generator
) -> FloatArray:
    """Tire un extrait de bruit parmi `candidates`, en écartant ceux qui sont trop faibles."""
    for _ in range(max_tries):
        index = int(rng.integers(0, len(candidates)))
        candidate = candidates[index]
        if rms_dbfs(candidate) >= min_dbfs:
            return candidate
    raise RuntimeError(f"Aucun bruit au-dessus de {min_dbfs} dBFS après {max_tries} essais")


def choose_strength(
    scores_by_strength: dict[str, float], tie_decimals: int
) -> tuple[str, dict[str, float]]:
    """Règle de D4 : meilleur score moyen ; à égalité, la plus faible force.

    `scores_by_strength` : {nom de la force: score moyen}, avec la clé « none » pour « sans
    débruitage » (force 0), les autres clés étant la force en texte (« 0.5 », « 0.8 », « 1.0 »).
    Les scores sont arrondis à `tie_decimals` décimales avant comparaison : deux scores
    identiques une fois arrondis sont « égaux ». Renvoie (force retenue, scores arrondis).
    """
    rounded: dict[str, float] = {}
    for name, score in scores_by_strength.items():
        rounded[name] = round(score, tie_decimals)
    best_score = max(rounded.values())
    tied_names = []
    for name, score in rounded.items():
        if score == best_score:
            tied_names.append(name)
    chosen = min(tied_names, key=strength_value)
    return chosen, rounded


def strength_value(name: str) -> float:
    """Force numérique d'un nom : « none » vaut 0 (aucun débruitage), sinon le nombre."""
    if name == "none":
        return 0.0
    return float(name)
