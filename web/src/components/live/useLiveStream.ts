import { useEffect, useRef, useState } from 'react'
import {
  CONSENT_VERSION,
  streamUrl,
  type ReadyMessage,
  type SavedMessage,
  type ServerMessage,
  type WindowMessage,
} from '../../api/stream.ts'
import { CaptureError, startCapture, type AudioCapture } from './audioCapture.ts'
import { createLatencyTracker, percentile, recordSent, recordWindow } from './liveLatency.ts'

// Une session du flux micro (C23, EF-14) : WebSocket, micro, résultats et mesures. Le protocole
// est décrit dans docs/api-flux-micro.md.

export type LiveStatus = 'idle' | 'connecting' | 'live' | 'stopping' | 'finished' | 'error'

export interface LiveState {
  status: LiveStatus
  ready: ReadyMessage | null
  lastWindow: WindowMessage | null
  // Latence perçue (ENF-02), mesurée par la page, en ms.
  latencyMs: number | null
  latencyP50Ms: number | null
  latencyP95Ms: number | null
  saved: SavedMessage | null
  error: string | null
}

const INITIAL_STATE: LiveState = {
  status: 'idle',
  ready: null,
  lastWindow: null,
  latencyMs: null,
  latencyP50Ms: null,
  latencyP95Ms: null,
  saved: null,
  error: null,
}

const MEDIAN_PERCENT = 50
const TAIL_PERCENT = 95

// Message « start » : avec le consentement seulement si l'enregistrement est demandé (ENF-10).
function startMessage(record: boolean): string {
  if (!record) {
    return JSON.stringify({ type: 'start', record: false })
  }
  const consent = { accepted: true, version: CONSENT_VERSION }
  return JSON.stringify({ type: 'start', record: true, consent })
}

export function useLiveStream() {
  const [state, setState] = useState<LiveState>(INITIAL_STATE)
  const socketRef = useRef<WebSocket | null>(null)
  const captureRef = useRef<AudioCapture | null>(null)
  const trackerRef = useRef(createLatencyTracker())
  // Statut lu par les gestionnaires du WebSocket, qui ne voient pas l'état React à jour.
  const statusRef = useRef<LiveStatus>('idle')

  function setStatus(status: LiveStatus): void {
    statusRef.current = status
    setState((previous) => ({ ...previous, status }))
  }

  function stopCapture(): void {
    captureRef.current?.stop()
    captureRef.current = null
  }

  function fail(message: string): void {
    stopCapture()
    socketRef.current?.close()
    statusRef.current = 'error'
    setState((previous) => ({ ...previous, status: 'error', error: message }))
  }

  // Chaque morceau de 100 ms part au serveur ; son heure d'envoi sert à la latence perçue.
  function sendChunk(chunk: ArrayBuffer): void {
    const socket = socketRef.current
    if (socket === null || socket.readyState !== WebSocket.OPEN) {
      return
    }
    socket.send(chunk)
    recordSent(trackerRef.current, chunk.byteLength, performance.now())
  }

  // Le serveur est prêt : on ouvre le micro, puis on passe en direct.
  async function handleReady(ready: ReadyMessage): Promise<void> {
    setState((previous) => ({ ...previous, ready }))
    try {
      captureRef.current = await startCapture(sendChunk)
      setStatus('live')
    } catch (error) {
      let message = 'Micro indisponible.'
      if (error instanceof CaptureError) {
        message = error.message
      }
      fail(message)
    }
  }

  function handleWindow(message: WindowMessage): void {
    const tracker = trackerRef.current
    const latencyMs = recordWindow(tracker, message.end_s, performance.now())
    const latencyP50Ms = percentile(tracker.latenciesMs, MEDIAN_PERCENT)
    const latencyP95Ms = percentile(tracker.latenciesMs, TAIL_PERCENT)
    setState((previous) => ({
      ...previous,
      lastWindow: message,
      latencyMs,
      latencyP50Ms,
      latencyP95Ms,
    }))
  }

  function handleMessage(event: MessageEvent<string>): void {
    const message = JSON.parse(event.data) as ServerMessage
    if (message.type === 'ready') {
      void handleReady(message)
    } else if (message.type === 'window') {
      handleWindow(message)
    } else if (message.type === 'saved') {
      setState((previous) => ({ ...previous, saved: message }))
    } else {
      fail(message.message)
    }
  }

  // Fermeture par le serveur : normale après « stop », anormale en plein direct.
  function handleClose(): void {
    stopCapture()
    if (statusRef.current === 'stopping') {
      setStatus('finished')
    } else if (statusRef.current === 'connecting' || statusRef.current === 'live') {
      fail('Connexion au serveur perdue : vérifiez que l’application est lancée, puis réessayez.')
    }
  }

  function start(record: boolean): void {
    trackerRef.current = createLatencyTracker()
    setState(INITIAL_STATE)
    setStatus('connecting')
    const socket = new WebSocket(streamUrl())
    socket.binaryType = 'arraybuffer'
    socket.onopen = () => socket.send(startMessage(record))
    socket.onmessage = handleMessage
    socket.onclose = handleClose
    socketRef.current = socket
  }

  // Arrêt demandé : micro coupé, puis « stop » ; le serveur répond (« saved » si la session
  // est enregistrée) puis ferme la connexion.
  function stop(): void {
    stopCapture()
    setStatus('stopping')
    const socket = socketRef.current
    if (socket !== null && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'stop' }))
    }
  }

  // Quitter la page coupe le micro et la connexion.
  useEffect(() => {
    return () => {
      captureRef.current?.stop()
      socketRef.current?.close()
    }
  }, [])

  return { state, start, stop }
}
