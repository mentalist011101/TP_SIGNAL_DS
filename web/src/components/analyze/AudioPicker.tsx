import { useEffect, useRef, useState, type ChangeEvent, type RefObject } from 'react'

// Formats acceptés par le serveur (EF-01).
const ACCEPTED_FORMATS = '.wav,.mp3,.flac,.ogg,.webm,.m4a'

const BUTTON_CLASSES =
  'rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:hover:bg-slate-800'

type AudioHandler = (file: File) => void

interface AudioPickerProps {
  onAudioSelected: AudioHandler
}

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

// Arrête l'enregistreur s'il tourne encore ; son onstop coupe alors le micro.
function stopIfRecording(recorderRef: RefObject<MediaRecorder | null>): void {
  const recorder = recorderRef.current
  if (recorder !== null && recorder.state === 'recording') {
    recorder.stop()
  }
}

// Si l'on quitte la page pendant un enregistrement, on l'arrête pour libérer le micro.
// On lit volontairement la ref au moment du départ : c'est l'enregistreur en cours qui compte,
// pas celui qui existait à l'ouverture de la page.
function useStopRecorderOnUnmount(recorderRef: RefObject<MediaRecorder | null>): void {
  useEffect(() => {
    return () => {
      stopIfRecording(recorderRef)
    }
  }, [recorderRef])
}

// État du micro : bouton unique qui démarre puis arrête l'enregistrement (EF-02).
function useMicrophone(onAudioSelected: AudioHandler) {
  const [isRecording, setIsRecording] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const recorderRef = useRef<MediaRecorder | null>(null)
  useStopRecorderOnUnmount(recorderRef)

  async function start() {
    const stream = await openMicrophone()
    if (stream === null) {
      setErrorMessage('Accès au micro refusé : autorisez-le dans votre navigateur.')
      return
    }
    const recorder = createRecorder(stream, onAudioSelected)
    recorder.start()
    recorderRef.current = recorder
    setErrorMessage(null)
    setIsRecording(true)
  }

  function toggle() {
    if (!isRecording) {
      void start()
      return
    }
    recorderRef.current?.stop()
    recorderRef.current = null
    setIsRecording(false)
  }

  return { isRecording, errorMessage, toggle }
}

// Choix de l'audio : import d'un fichier (EF-01) ou enregistrement au micro (EF-02).
export default function AudioPicker({ onAudioSelected }: AudioPickerProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const microphone = useMicrophone(onAudioSelected)

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files
    if (files === null || files.length === 0) {
      return
    }
    onAudioSelected(files[0])
    // Vider le champ permet de réimporter le même fichier juste après.
    event.target.value = ''
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-3">
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_FORMATS}
          hidden
          onChange={handleFileChange}
        />
        <button type="button" className={BUTTON_CLASSES} onClick={() => inputRef.current?.click()}>
          Importer un fichier
        </button>
        <button type="button" className={BUTTON_CLASSES} onClick={microphone.toggle}>
          {microphone.isRecording ? 'Arrêter l’enregistrement' : 'Enregistrer au micro'}
        </button>
      </div>
      {microphone.isRecording && <p className="text-sm text-red-600">● Enregistrement en cours…</p>}
      {microphone.errorMessage !== null && (
        <p className="text-sm text-red-600">{microphone.errorMessage}</p>
      )}
    </div>
  )
}
