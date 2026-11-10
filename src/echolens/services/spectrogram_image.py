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
