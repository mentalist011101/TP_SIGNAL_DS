"""C25 : outils de l'évaluation hors domaine sur CaFE (H2, P7, E1), sans torch.

Un acteur joue des dizaines d'extraits : les extraits d'un même acteur ne sont pas
indépendants. Les intervalles de confiance se font donc en tirant des ACTEURS avec remise (et
non des extraits), puis en prenant tous les extraits des acteurs tirés.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, Field
from sklearn.metrics import f1_score

from echolens.config import CONFIG_DIR, load_yaml
from echolens.training.evaluation import EvaluationConfig, IntArray, macro_f1

OOD_CONFIG_PATH = CONFIG_DIR / "ood.yaml"
Metric = Callable[[IntArray, IntArray], float]


class ModelSpec(BaseModel):
    """Un modèle évalué : identifiant et famille (A : log-Mel, B : encodeur gelé)."""

    id: str
    family: str


class H2Pair(BaseModel):
    """Les deux modèles de H2 : l'écart est F1(first) − F1(second)."""

    first: str
    second: str


class OodConfig(BaseModel):
    """Contenu de configs/ood.yaml."""

    reference_seed: int
    models: list[ModelSpec] = Field(min_length=1)
    in_domain_tolerance: float = Field(gt=0)
    h2: H2Pair
    cafe_expected_clips: int = Field(gt=0)
    cafe_expected_actors: int = Field(gt=0)
    intensity_names: dict[str, str]
    neutral_class: str


def load_ood_config(path: Path = OOD_CONFIG_PATH) -> OodConfig:
    """Lit configs/ood.yaml."""
    return OodConfig(**load_yaml(path))


def actor_positions(actors: list[str]) -> dict[str, IntArray]:
    """Positions des extraits de chaque acteur : {acteur: tableau de positions}."""
    positions: dict[str, list[int]] = {}
    for position, actor in enumerate(actors):
        positions.setdefault(actor, []).append(position)
    result: dict[str, IntArray] = {}
    for actor in sorted(positions):
        result[actor] = np.array(positions[actor], dtype=np.int_)
    return result


def draw_actor_samples(actors: list[str], config: EvaluationConfig) -> list[IntArray]:
    """Tirages bootstrap : pour chaque tirage, les positions des extraits des acteurs tirés.

    On tire autant d'acteurs que l'on en a, avec remise. Les MÊMES tirages servent à tous les
    modèles : la comparaison de deux modèles est alors appariée (mêmes acteurs, mêmes extraits).
    """
    by_actor = actor_positions(actors)
    names = sorted(by_actor)
    rng = np.random.default_rng(config.seed)
    samples: list[IntArray] = []
    for _ in range(config.n_bootstrap):
        drawn = rng.integers(0, len(names), size=len(names))
        pieces = [by_actor[names[index]] for index in drawn]
        samples.append(np.concatenate(pieces))
    return samples


def percentile_interval(values: npt.NDArray[np.float64], confidence: float) -> tuple[float, float]:
    """Bornes qui encadrent `confidence` des valeurs : 2,5 % coupés de chaque côté pour 95 %."""
    tail = (1.0 - confidence) / 2.0
    low, high = np.quantile(values, [tail, 1.0 - tail])
    return float(low), float(high)


def metric_by_sample(
    y_true: IntArray, y_pred: IntArray, samples: list[IntArray], metric: Metric = macro_f1
) -> npt.NDArray[np.float64]:
    """La métrique recalculée sur chaque tirage bootstrap."""
    values = np.empty(len(samples), dtype=np.float64)
    for draw, positions in enumerate(samples):
        values[draw] = metric(y_true[positions], y_pred[positions])
    return values


def actor_bootstrap_ci(
    y_true: IntArray,
    y_pred: IntArray,
    samples: list[IntArray],
    config: EvaluationConfig,
    metric: Metric = macro_f1,
) -> tuple[float, float]:
    """Intervalle de confiance d'une métrique, par bootstrap sur les acteurs."""
    values = metric_by_sample(y_true, y_pred, samples, metric)
    return percentile_interval(values, config.confidence)


def paired_difference(
    y_true: IntArray,
    pred_first: IntArray,
    pred_second: IntArray,
    samples: list[IntArray],
    config: EvaluationConfig,
    metric: Metric = macro_f1,
) -> tuple[float, float, float]:
    """Écart de métrique first − second et son intervalle, bootstrap apparié sur les acteurs.

    À chaque tirage, les deux modèles sont notés sur les mêmes extraits ; on garde l'écart de
    ce tirage. Renvoie (écart observé, borne basse, borne haute).
    """
    observed = metric(y_true, pred_first) - metric(y_true, pred_second)
    first_values = metric_by_sample(y_true, pred_first, samples, metric)
    second_values = metric_by_sample(y_true, pred_second, samples, metric)
    low, high = percentile_interval(first_values - second_values, config.confidence)
    return float(observed), low, high


def h2_verdict(low: float, high: float) -> str:
    """Verdict de H2 : confirmée si l'intervalle est entièrement positif, infirmée s'il est
    entièrement négatif, non tranchée sinon (il contient 0)."""
    if low > 0.0:
        return "confirmée"
    if high < 0.0:
        return "infirmée"
    return "non tranchée"


def intensity_scores(
    y_true: IntArray, y_pred: IntArray, intensities: list[str], neutral_target: int
) -> dict[str, float]:
    """F1 macro par intensité (faible, forte), sur les émotions jouées aux deux intensités.

    Dans CaFE, le neutre est joué sans intensité : ses extraits sont écartés et la moyenne porte
    sur les 5 autres classes, les mêmes pour les deux groupes. Sinon « faible » compterait
    6 classes et « forte » 5, et les deux F1 ne seraient pas comparables.
    """
    # Étape 1 : on écarte les extraits neutres.
    emotional = y_true != neutral_target
    kept_true = y_true[emotional]
    kept_pred = y_pred[emotional]
    kept_groups = np.asarray(intensities)[emotional]

    # Étape 2 : les classes de la moyenne, imposées (labels) pour qu'une prédiction « neutre »
    # compte comme une erreur sans ajouter de classe à la moyenne.
    labels = sorted(set(kept_true.tolist()))
    scores: dict[str, float] = {}
    for name in sorted(set(kept_groups.tolist())):
        mask = kept_groups == name
        score = f1_score(
            kept_true[mask], kept_pred[mask], labels=labels, average="macro", zero_division=0.0
        )
        scores[name] = float(score)
    return scores


def f1_drop(in_domain_f1: float, ood_f1: float) -> float:
    """Chute de F1 macro entre le test en domaine et CaFE (positive = le modèle perd).

    Les deux F1 doivent venir du même réseau (mêmes poids), mesuré sur les deux jeux.
    """
    return in_domain_f1 - ood_f1


def check_in_domain(measured_f1: float, published_f1: float, tolerance: float) -> bool:
    """Vrai si le F1 macro retrouvé est à `tolerance` près de la valeur publiée."""
    return bool(abs(measured_f1 - published_f1) <= tolerance)
