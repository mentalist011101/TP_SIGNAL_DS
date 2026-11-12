"""Débruitage par spectral gating stationnaire (décision D4)."""

from __future__ import annotations

import noisereduce
import numpy as np
import numpy.typing as npt

from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.core.audio.preprocess_config import DenoiseConfig

FloatArray = npt.NDArray[np.float32]


def denoise(signal: FloatArray, config: DenoiseConfig) -> FloatArray:
    """Atténue un bruit de fond stable par spectral gating (D4) ; renvoie du float32.

    Spectral gating stationnaire, en 7 étapes (noisereduce) :
    1. STFT du signal : une grille temps × fréquence ;
    2. passage de chaque case en dB ;
    3. pour chaque fréquence, moyenne et écart-type du bruit en dB, sur tout l'extrait
       (« stationnaire » : un seul profil de bruit) ;
    4. seuil par fréquence : moyenne + n_std_thresh_stationary × écart-type ;
    5. masque : une case au-dessus du seuil est du signal (1), sinon du bruit (0) ;
    6. lissage du masque en fréquence et en temps, pour éviter les « trous » qui sonnent
       comme des bulles (bruit musical) ;
    7. application du masque à la STFT, puis STFT inverse.

    Le SEUIL (étape 4) décide quelles cases sont du bruit. La FORCE (prop_decrease) décide
    de combien on les baisse : à 0,8, une case de bruit garde 20 % de son amplitude
    (−14 dB). À 1,0 on l'efface complètement, ce qui crée des artefacts et abîme la parole.

    Désactivé (enabled = false, valeur par défaut tant que l'ablation n'est pas faite) :
    renvoie une copie du signal, inchangé.
    """
    if not config.enabled:
        return signal.copy()
    cleaned = noisereduce.reduce_noise(
        y=signal,
        sr=TARGET_SAMPLE_RATE,
        stationary=config.stationary,
        prop_decrease=config.prop_decrease,
        n_std_thresh_stationary=config.n_std_thresh_stationary,
        n_fft=config.n_fft,
        freq_mask_smooth_hz=config.freq_mask_smooth_hz,
        time_mask_smooth_ms=config.time_mask_smooth_ms,
        n_jobs=1,
    )
    result: FloatArray = np.asarray(cleaned, dtype=np.float32)
    return result
