import { useRef, type ChangeEvent } from 'react'
import { MicIcon, UploadIcon } from '../icons.tsx'
import { ACCEPTED_FORMATS, formatClock, type AudioHandler, type Microphone } from './microphone.ts'

const BUTTON_CLASSES =
  'inline-flex items-center gap-2 rounded-btn border border-rule-strong bg-card px-4 py-2 text-sm font-medium text-ink transition-colors duration-200 ease-out-soft hover:bg-paper-alt'
// Bouton du micro pendant l'enregistrement : plein, pour qu'on voie où arrêter.
const RECORDING_BUTTON_CLASSES =
  'inline-flex items-center gap-2 rounded-btn bg-accent px-4 py-2 text-sm font-semibold text-on-accent transition-colors duration-200 ease-out-soft hover:bg-accent-deep'

interface AudioPickerProps {
  onAudioSelected: AudioHandler
  // Micro du parent (useMicrophone) : le parent anime le ruban avec son niveau.
  microphone: Microphone
}

// « ● Enregistrement · 0:07 » : le micro écoute, comme pendant un message vocal.
export function RecordingIndicator({ elapsedS }: { elapsedS: number }) {
  return (
    <p className="inline-flex items-center gap-2 text-sm font-semibold" aria-live="polite">
      <span className="relative flex h-2.5 w-2.5" aria-hidden="true">
        <span className="absolute inset-0 rounded-full bg-brand motion-safe:animate-ping" />
        <span className="relative h-2.5 w-2.5 rounded-full bg-brand" />
      </span>
      Enregistrement
      <span className="font-mono font-normal text-ink-soft">{formatClock(elapsedS)}</span>
    </p>
  )
}

// Choix de l'audio : import d'un fichier (EF-01) ou enregistrement au micro (EF-02).
export default function AudioPicker({ onAudioSelected, microphone }: AudioPickerProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files
    if (files === null || files.length === 0) {
      return
    }
    onAudioSelected(files[0])
    // Vider le champ permet de réimporter le même fichier juste après.
    event.target.value = ''
  }

  let microphoneClasses = BUTTON_CLASSES
  let microphoneText = 'Enregistrer au micro'
  if (microphone.isRecording) {
    microphoneClasses = RECORDING_BUTTON_CLASSES
    microphoneText = 'Arrêter et utiliser'
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap justify-center gap-3">
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_FORMATS}
          hidden
          onChange={handleFileChange}
        />
        {!microphone.isRecording && (
          <button
            type="button"
            className={BUTTON_CLASSES}
            onClick={() => inputRef.current?.click()}
          >
            <UploadIcon />
            Importer un fichier
          </button>
        )}
        <button type="button" className={microphoneClasses} onClick={microphone.toggle}>
          <MicIcon />
          {microphoneText}
        </button>
      </div>
      {microphone.errorMessage !== null && (
        <p className="text-sm text-danger">{microphone.errorMessage}</p>
      )}
    </div>
  )
}
