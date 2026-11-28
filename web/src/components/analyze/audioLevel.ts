// Niveau sonore du micro, pour l'affichage seulement (ruban qui réagit à la voix pendant un
// enregistrement, pages Analyser et Direct). Le navigateur le mesure avec un AnalyserNode : ce
// n'est pas une feature des modèles (R5), aucun résultat n'en dépend.

// Niveau en dB pleine échelle ramené entre 0 et 1 : -60 dBFS (silence) → 0, -10 dBFS (voix forte
// près du micro) → 1.
const SILENT_DBFS = -60
const LOUD_DBFS = -10
// Lissage d'une image à l'autre : le ruban suit la voix sans trembler.
const SMOOTHING = 0.75
// Nombre d'échantillons lus à chaque image.
const WINDOW_SIZE = 1024

export interface LevelMeter {
  // Niveau lissé, entre 0 et 1, lu à chaque image du ruban.
  read: () => number
}

// Branche un analyseur sur la source du micro et renvoie de quoi lire son niveau.
export function createLevelMeter(context: AudioContext, source: AudioNode): LevelMeter {
  const analyser = context.createAnalyser()
  analyser.fftSize = WINDOW_SIZE
  source.connect(analyser)
  const samples = new Float32Array(WINDOW_SIZE)
  const smoothed = { value: 0 }

  function read(): number {
    analyser.getFloatTimeDomainData(samples)
    // Étape 1 : valeur efficace (RMS) des derniers échantillons.
    let sumOfSquares = 0
    for (const sample of samples) {
      sumOfSquares += sample * sample
    }
    const rms = Math.sqrt(sumOfSquares / samples.length)
    // Étape 2 : en dB pleine échelle, puis entre 0 et 1.
    const dbfs = 20 * Math.log10(Math.max(rms, 1e-6))
    const ratio = (dbfs - SILENT_DBFS) / (LOUD_DBFS - SILENT_DBFS)
    const level = Math.min(Math.max(ratio, 0), 1)
    // Étape 3 : lissage, pour un mouvement fluide.
    smoothed.value = SMOOTHING * smoothed.value + (1 - SMOOTHING) * level
    return smoothed.value
  }

  return { read }
}
