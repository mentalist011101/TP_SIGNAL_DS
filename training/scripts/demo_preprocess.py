"""C2 : figure pour l'oral, débruitage (D4) et segmentation de la parole (D5).

Produit report/figures/c2_debruitage_segmentation.png en trois parties :
1. la forme d'onde, avec les segments de parole détectés en bandes colorées ;
2. le log-Mel avant débruitage ;
3. le log-Mel après débruitage, forcé à p = 0,8 pour la figure (désactivé par défaut, D4).

Les deux log-Mel utilisent l'échelle de couleurs fixe de configs/features.yaml : une même
couleur veut dire la même énergie, avant et après.

L'audio n'est jamais commité : seule la figure l'est.

Usage, depuis la racine du dépôt :
    uv run python training/scripts/demo_preprocess.py <chemin_audio>
"""

from __future__ import annotations

import sys

import matplotlib

# Backend sans fenêtre : le script ne fait qu'écrire un PNG.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.axes import Axes
from matplotlib.image import AxesImage

from echolens.config import CONFIG_DIR, REPO_ROOT
from echolens.core.audio import (
    Segment,
    denoise,
    detect_speech,
    load_audio,
    load_preprocess_config,
    preprocess,
)
from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.core.features import FeatureConfig, FloatArray, log_mel_spectrogram, mel_axis_position

OUTPUT_PATH = REPO_ROOT / "report" / "figures" / "c2_debruitage_segmentation.png"
# Force du débruitage pour la figure : la valeur provisoire de D4.
FIGURE_PROP_DECREASE = 0.8


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage : python training/scripts/demo_preprocess.py <chemin_audio>")
        sys.exit(1)
    feature_config = FeatureConfig.from_yaml(CONFIG_DIR / "features.yaml")
    preprocess_config = load_preprocess_config()
    # Étape 1 : même entrée que l'application, mono 16 kHz (D1, D2) puis niveau normalisé (D3).
    signal = preprocess(load_audio(sys.argv[1]))
    # Étape 2 : zones de parole, sur le signal non débruité (réglage par défaut, D4).
    segments = detect_speech(signal, preprocess_config.vad)
    # Étape 3 : débruitage forcé pour la figure, avec la force provisoire de D4.
    denoise_config = preprocess_config.denoise.model_copy(
        update={"enabled": True, "prop_decrease": FIGURE_PROP_DECREASE}
    )
    denoised = denoise(signal, denoise_config)
    # Étape 4 : les deux log-Mel, calculés par le module unique des features (R5).
    before = log_mel_spectrogram(signal, feature_config)
    after = log_mel_spectrogram(denoised, feature_config)
    draw_figure(signal, segments, before, after, feature_config)
    print(f"Figure écrite dans {OUTPUT_PATH} ({len(segments)} segments de parole)")


def draw_figure(
    signal: FloatArray,
    segments: list[Segment],
    before: FloatArray,
    after: FloatArray,
    config: FeatureConfig,
) -> None:
    # Mise en page « constrained » : la forme d'onde garde la même largeur que les log-Mel,
    # malgré la barre de couleurs, pour que les temps restent alignés à l'œil.
    figure, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True, layout="constrained")
    draw_waveform(axes[0], signal, segments)
    image = draw_log_mel(axes[1], before, signal, config, "Log-Mel avant débruitage")
    draw_log_mel(axes[2], after, signal, config, "Log-Mel après débruitage (force 0,8)")
    axes[2].set_xlabel("Temps (s)")
    figure.colorbar(image, ax=[axes[1], axes[2]], label="dB (échelle fixe)")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_PATH, dpi=150)
    plt.close(figure)


def draw_waveform(axis: Axes, signal: FloatArray, segments: list[Segment]) -> None:
    times = np.arange(len(signal)) / TARGET_SAMPLE_RATE
    axis.plot(times, signal, color="#444444", linewidth=0.5)
    # Une bande colorée par segment de parole détecté.
    for segment in segments:
        axis.axvspan(segment.start_s, segment.end_s, color="#4a7a3a", alpha=0.3)
    axis.set_title(f"Forme d'onde et segments de parole (webrtcvad, {len(segments)} segments)")
    axis.set_ylabel("Amplitude")


def draw_log_mel(
    axis: Axes, log_mel: FloatArray, signal: FloatArray, config: FeatureConfig, title: str
) -> AxesImage:
    duration_s = len(signal) / TARGET_SAMPLE_RATE
    # Échelle fixe (U6) : vmin et vmax ne dépendent jamais de l'extrait.
    image = axis.imshow(
        log_mel,
        origin="lower",
        aspect="auto",
        extent=(0.0, duration_s, 0.0, 1.0),
        cmap=config.display_colormap,
        vmin=config.display_db_min,
        vmax=config.display_db_max,
    )
    # Graduations en Hz, placées sur l'axe Mel (R2), comme dans l'application.
    tick_positions: list[float] = []
    tick_labels: list[str] = []
    for frequency_hz in config.display_frequency_ticks_hz:
        tick_positions.append(mel_axis_position(frequency_hz, config))
        tick_labels.append(f"{frequency_hz:g}")
    axis.set_yticks(tick_positions, tick_labels)
    axis.set_ylabel("Fréquence (Hz)")
    axis.set_title(title)
    return image


if __name__ == "__main__":
    main()
