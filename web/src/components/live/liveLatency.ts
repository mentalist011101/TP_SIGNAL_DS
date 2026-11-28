import { STREAM_SAMPLE_RATE } from '../../api/stream.ts'

// Latence perçue du flux micro (ENF-02) : temps entre l'envoi du dernier morceau d'une fenêtre
// et l'arrivée de son résultat. Le serveur donne le temps de calcul ; seule la page peut
// mesurer ce délai de bout en bout. Ce ne sont que des horodatages : aucun calcul sur le son.

// Nombre de latences gardées pour la médiane et le p95 (environ 5 min à 2 résultats par seconde).
const LATENCY_HISTORY = 600

interface SentChunk {
  // Nombre d'échantillons envoyés depuis le début, ce morceau compris.
  endSample: number
  sentAtMs: number
}

export interface LatencyTracker {
  sent: SentChunk[]
  latenciesMs: number[]
  sampleCount: number
}

export function createLatencyTracker(): LatencyTracker {
  return { sent: [], latenciesMs: [], sampleCount: 0 }
}

// À l'envoi d'un morceau de PCM Int16 (2 octets par échantillon).
export function recordSent(tracker: LatencyTracker, chunkBytes: number, nowMs: number): void {
  tracker.sampleCount += chunkBytes / 2
  tracker.sent.push({ endSample: tracker.sampleCount, sentAtMs: nowMs })
}

// À l'arrivée d'une fenêtre qui finit à endS secondes : latence de cette fenêtre, ou null si
// son dernier morceau est inconnu. Les morceaux plus anciens sont oubliés.
export function recordWindow(tracker: LatencyTracker, endS: number, nowMs: number): number | null {
  const endSample = Math.round(endS * STREAM_SAMPLE_RATE)
  const index = tracker.sent.findIndex((chunk) => chunk.endSample >= endSample)
  if (index === -1) {
    return null
  }
  const latencyMs = nowMs - tracker.sent[index].sentAtMs
  tracker.sent = tracker.sent.slice(index)
  tracker.latenciesMs.push(latencyMs)
  if (tracker.latenciesMs.length > LATENCY_HISTORY) {
    tracker.latenciesMs.shift()
  }
  return latencyMs
}

// Centile par la méthode du rang le plus proche : la valeur sous laquelle tombent percent %
// des mesures. null tant qu'il n'y a aucune mesure.
export function percentile(values: number[], percent: number): number | null {
  if (values.length === 0) {
    return null
  }
  const sorted = [...values].sort((first, second) => first - second)
  const rank = Math.ceil((percent / 100) * sorted.length)
  const index = Math.max(rank - 1, 0)
  return sorted[index]
}
