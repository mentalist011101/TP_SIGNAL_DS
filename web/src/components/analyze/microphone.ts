import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'
import { createLevelMeter, type LevelMeter } from './audioLevel.ts'

// Micro du navigateur (EF-02) : enregistrement avec MediaRecorder, puis un fichier au format
// du navigateur. Sert à la page Analyser et à la page Locuteurs (EF-11). Pendant
// l'enregistrement, le niveau du son capté (readLevel) et la durée écoulée (elapsedS) disent à
// l'utilisateur que le micro l'entend, comme un message vocal.

// Mise à jour du chronomètre, en millisecondes.
const CLOCK_STEP_MS = 250

// Micro en cours : son enregistreur, et de quoi mesurer son niveau.
interface ActiveMicrophone {
  recorder: MediaRecorder
  context: AudioContext
  meter: LevelMeter
}

// Cette interface est celle que reçoit AudioPicker (et la page Locuteurs).
export interface Microphone {
  isRecording: boolean
  errorMessage: string | null
  elapsedS: number
  toggle: () => void
  // Niveau entre 0 et 1 ; 0 hors enregistrement.
  readLevel: () => number
}

// Formats acceptés par le serveur (EF-01).
export const ACCEPTED_FORMATS = '.wav,.mp3,.flac,.ogg,.webm,.m4a'

export type AudioHandler = (file: File) => void

// Nom du fichier enregistré, avec l'extension qui correspond au format réel du navigateur :
// Chrome produit du WebM, Safari du MP4 (m4a), Firefox de l'Ogg. Le serveur lit l'extension.
function recordingFileName(mimeType: string): string {
  if (mimeType.includes('mp4')) {
    return 'enregistrement.m4a'
  }
  if (mimeType.includes('ogg')) {
    return 'enregistrement.ogg'
  }
  return 'enregistrement.webm'
}

// Coupe chaque piste du micro : le voyant d'enregistrement du navigateur s'éteint.
function stopTracks(stream: MediaStream): void {
  const tracks = stream.getTracks()
  for (const track of tracks) {
    track.stop()
  }
}

// Demande l'accès au micro ; null si l'utilisateur refuse ou s'il n'y a pas de micro.
async function openMicrophone(): Promise<MediaStream | null> {
  try {
    return await navigator.mediaDevices.getUserMedia({ audio: true })
  } catch {
    return null
  }
}

// Enregistreur qui accumule les morceaux d'audio puis, à l'arrêt, coupe le micro et
// transmet un fichier typé avec le format choisi par le navigateur (rec.mimeType).
function createRecorder(stream: MediaStream, onAudioSelected: AudioHandler): MediaRecorder {
  const recorder = new MediaRecorder(stream)
  const chunks: Blob[] = []
  recorder.ondataavailable = (event) => {
    chunks.push(event.data)
  }
  recorder.onstop = () => {
    stopTracks(stream)
    const fileName = recordingFileName(recorder.mimeType)
    const file = new File(chunks, fileName, { type: recorder.mimeType })
    onAudioSelected(file)
  }
  return recorder
}

// Arrête l'enregistreur s'il tourne encore (son onstop coupe alors le micro), puis ferme le
// contexte audio de la mesure du niveau.
function stopIfRecording(activeRef: RefObject<ActiveMicrophone | null>): void {
  const active = activeRef.current
  if (active === null) {
    return
  }
  if (active.recorder.state === 'recording') {
    active.recorder.stop()
  }
  void active.context.close()
}

// Si l'on quitte la page pendant un enregistrement, on l'arrête pour libérer le micro.
// On lit volontairement la ref au moment du départ : c'est l'enregistreur en cours qui compte,
// pas celui qui existait à l'ouverture de la page.
function useStopRecorderOnUnmount(activeRef: RefObject<ActiveMicrophone | null>): void {
  useEffect(() => {
    return () => {
      stopIfRecording(activeRef)
    }
  }, [activeRef])
}

// Chronomètre : secondes écoulées depuis le début de l'enregistrement, 0 sinon.
function useElapsedSeconds(isRecording: boolean): number {
  const [elapsedS, setElapsedS] = useState(0)
  useEffect(() => {
    if (!isRecording) {
      return
    }
    const startMs = performance.now()
    const timer = window.setInterval(() => {
      setElapsedS((performance.now() - startMs) / 1000)
    }, CLOCK_STEP_MS)
    return () => {
      window.clearInterval(timer)
      setElapsedS(0)
    }
  }, [isRecording])
  return elapsedS
}

// État du micro : bouton unique qui démarre puis arrête l’enregistrement (EF-02). Sert aussi
// à la page Locuteurs, pour enregistrer une voix (EF-11).
export function useMicrophone(onAudioSelected: AudioHandler): Microphone {
  const [isRecording, setIsRecording] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const activeRef = useRef<ActiveMicrophone | null>(null)
  useStopRecorderOnUnmount(activeRef)
  const elapsedS = useElapsedSeconds(isRecording)

  async function start() {
    const stream = await openMicrophone()
    if (stream === null) {
      setErrorMessage('Accès au micro refusé : autorisez-le dans votre navigateur.')
      return
    }
    // Étape 1 : l'enregistreur, qui produit le fichier à l'arrêt.
    const recorder = createRecorder(stream, onAudioSelected)
    // Étape 2 : la mesure du niveau, sur le même flux du micro.
    const context = new AudioContext()
    const source = context.createMediaStreamSource(stream)
    const meter = createLevelMeter(context, source)
    recorder.start()
    activeRef.current = { recorder, context, meter }
    setErrorMessage(null)
    setIsRecording(true)
  }

  function toggle() {
    if (!isRecording) {
      void start()
      return
    }
    stopIfRecording(activeRef)
    activeRef.current = null
    setIsRecording(false)
  }

  // Fonction stable : le ruban la garde d'une image à l'autre.
  const readLevel = useCallback((): number => {
    const active = activeRef.current
    if (active === null) {
      return 0
    }
    return active.meter.read()
  }, [])

  return { isRecording, errorMessage, elapsedS, toggle, readLevel }
}

// « 0:07 » : durée d'enregistrement, en minutes et secondes.
export function formatClock(seconds: number): string {
  const whole = Math.floor(seconds)
  const minutes = Math.floor(whole / 60)
  const rest = whole % 60
  const paddedRest = String(rest).padStart(2, '0')
  return `${minutes}:${paddedRest}`
}
