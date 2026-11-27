"""Image PNG du spectrogramme log-Mel affichée dans l'interface (EF-04, U6).

Ce module ne fait que de la présentation : le log-Mel est calculé par
echolens.core.features.log_mel_spectrogram, le même code que l'entrée des modèles (R5).

On importe matplotlib.image et jamais matplotlib.pyplot : pyplot sert à ouvrir des fenêtres
et garde un état global (la « figure courante ») qui n'est pas fait pour plusieurs threads.
Le serveur n'a pas d'écran et calcule les analyses dans un pool de threads (S2).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.colors
import matplotlib.image
import numpy as np

from echolens.core.features import FeatureConfig, FloatArray


def save_spectrogram_png(log_mel: FloatArray, path: Path, config: FeatureConfig) -> None:
    """Enregistre le log-Mel (n_mels, n_frames) en PNG, un pixel par trame et par bande Mel.

    L'image fait n_frames pixels de large (une trame toutes les 10 ms) et n_mels pixels de
    haut. Les couleurs suivent une échelle fixe en dB absolus (display_db_min à
    display_db_max) : deux images sont comparables, et un audio faible paraît sombre (U6).
    """
    # vmin et vmax : échelle de couleurs fixe, lue dans features.yaml. Sous vmin, la couleur
    # la plus sombre ; au-dessus de vmax, la plus claire.
    # origin="lower" : la ligne 0 du tableau (bande Mel la plus grave) va en bas de l'image,
    # comme sur l'axe des fréquences d'un graphique.
    matplotlib.image.imsave(
        path,
        log_mel,
        vmin=config.display_db_min,
        vmax=config.display_db_max,
        cmap=config.display_colormap,
        origin="lower",
        format="png",
    )


# Carte Grad-CAM : blanc plus ou moins opaque posé sur le spectrogramme. L'opacité monte
# avec la carte, jusqu'à ce plafond, pour que les couleurs du spectrogramme restent visibles.
GRAD_CAM_MAX_OPACITY = 0.8


def save_grad_cam_png(grad_map: FloatArray, path: Path) -> None:
    """Enregistre la carte Grad-CAM (bandes, trames), entre 0 et 1, en PNG transparent.

    Même taille et même orientation que l'image du spectrogramme (graves en bas) : posée
    dessus, chaque pixel de la carte tombe sur la case qu'il explique (EF-13).
    """
    # Étape 1 : une image blanche (rouge, vert et bleu à 1).
    band_count, frame_count = grad_map.shape
    rgba = np.ones((band_count, frame_count, 4), dtype=np.float32)
    # Étape 2 : l'opacité suit la carte : transparent là où rien ne soutient la classe.
    clipped = np.clip(grad_map, 0.0, 1.0)
    rgba[:, :, 3] = clipped * GRAD_CAM_MAX_OPACITY
    matplotlib.image.imsave(path, rgba, origin="lower", format="png")


def colormap_stops(config: FeatureConfig, count: int) -> list[str]:
    """Couleurs « #rrggbb » régulièrement réparties sur la palette, de la plus sombre à la plus
    claire : la légende de l'image, de display_db_min à display_db_max (U6).

    Le front s'en sert pour un dégradé CSS : il n'a pas à connaître la palette matplotlib.
    """
    colormap = matplotlib.colormaps[config.display_colormap]
    stops = []
    for index in range(count):
        # Position sur la palette : 0 (display_db_min) … 1 (display_db_max).
        position = index / (count - 1)
        rgba = colormap(position)
        stops.append(matplotlib.colors.to_hex(rgba))
    return stops
