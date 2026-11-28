// Processeur AudioWorklet de la page Direct (C23, D8). Il tourne dans le fil audio du
// navigateur, dans un contexte déjà à 16 kHz : le navigateur a rééchantillonné le micro. Il ne
// fait que convertir le format (aucune feature, R5) : il regroupe les échantillons par morceaux
// de 100 ms, les passe de Float32 dans [-1, 1] à Int16, puis les envoie à la page.

// Durée d'un morceau envoyé au serveur : 100 ms.
const CHUNK_SECONDS = 0.1
// Plus grande valeur d'un Int16.
const INT16_MAX = 32767

class PcmCaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    // sampleRate est la fréquence du contexte audio, ici 16 000 Hz.
    this.chunkSamples = Math.round(sampleRate * CHUNK_SECONDS)
    this.pending = new Float32Array(this.chunkSamples)
    this.filled = 0
  }

  // Appelé par le navigateur pour chaque bloc de 128 échantillons du micro.
  process(inputs) {
    const channel = inputs[0][0]
    if (channel === undefined) {
      return true
    }
    for (const sample of channel) {
      this.pending[this.filled] = sample
      this.filled += 1
      if (this.filled === this.chunkSamples) {
        this.sendChunk()
      }
    }
    return true
  }

  // Float32 → Int16 (valeurs écrêtées à [-1, 1]), puis envoi à la page sans copie.
  sendChunk() {
    const pcm = new Int16Array(this.chunkSamples)
    for (let index = 0; index < this.chunkSamples; index += 1) {
      const clamped = Math.max(-1, Math.min(1, this.pending[index]))
      pcm[index] = Math.round(clamped * INT16_MAX)
    }
    this.port.postMessage(pcm.buffer, [pcm.buffer])
    this.filled = 0
  }
}

registerProcessor('pcm-capture', PcmCaptureProcessor)
