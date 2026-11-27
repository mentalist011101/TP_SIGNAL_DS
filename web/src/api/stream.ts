import type { TaskResultSummary } from './client.ts'

// Protocole du WebSocket /ws/stream (C23, D8), décrit dans docs/api-flux-micro.md. Un
// WebSocket n'est pas dans l'OpenAPI : ces types sont écrits à la main d'après ce document.

// Fréquence d'échantillonnage du flux (D8) : le navigateur convertit le micro en 16 kHz.
export const STREAM_SAMPLE_RATE = 16000

// Version du texte de consentement affiché par la page Direct. Elle doit être celle de
// configs/inference.yaml (stream.consent_version) : sinon le serveur refuse l'enregistrement.
export const CONSENT_VERSION = 'direct-v1'

export interface ReadyMessage {
  type: 'ready'
  window_s: number
  hop_s: number
  sample_rate: number
  tasks: string[]
  record: boolean
}

// Résultats d'une fenêtre de 2 s, envoyés toutes les 0,5 s de son reçu.
export interface WindowMessage {
  type: 'window'
  end_s: number
  skipped: number
  results: { emotion?: TaskResultSummary; sound_event?: TaskResultSummary }
  // La VAD a trouvé de la parole ; null si l'émotion n'est pas demandée.
  speech: boolean | null
  compute_ms: number
  rtf: number
  compute_p50_ms: number
  compute_p95_ms: number
  window_count: number
  skipped_count: number
}

export interface SavedMessage {
  type: 'saved'
  analysis_id: string
  truncated: boolean
}

export interface ErrorMessage {
  type: 'error'
  message: string
}

export type ServerMessage = ReadyMessage | WindowMessage | SavedMessage | ErrorMessage

// Adresse du WebSocket sur le même serveur que la page (ws:// en http, wss:// en https).
export function streamUrl(): string {
  let scheme = 'ws'
  if (window.location.protocol === 'https:') {
    scheme = 'wss'
  }
  return `${scheme}://${window.location.host}/ws/stream`
}
