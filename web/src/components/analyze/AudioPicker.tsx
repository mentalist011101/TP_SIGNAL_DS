import { useRef, type ChangeEvent } from 'react'
import { MicIcon, UploadIcon } from '../icons.tsx'
import { ACCEPTED_FORMATS, useMicrophone, type AudioHandler } from './microphone.ts'

const BUTTON_CLASSES =
  'inline-flex items-center gap-2 rounded-btn border border-rule-strong bg-card px-4 py-2 text-sm font-medium text-ink transition-colors duration-200 ease-out-soft hover:bg-paper-alt'

interface AudioPickerProps {
  onAudioSelected: AudioHandler
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
      <div className="flex flex-wrap justify-center gap-3">
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_FORMATS}
          hidden
          onChange={handleFileChange}
        />
        <button type="button" className={BUTTON_CLASSES} onClick={() => inputRef.current?.click()}>
          <UploadIcon />
          Importer un fichier
        </button>
        <button type="button" className={BUTTON_CLASSES} onClick={microphone.toggle}>
          <MicIcon />
          {microphone.isRecording ? 'Arrêter l’enregistrement' : 'Enregistrer au micro'}
        </button>
      </div>
      {microphone.isRecording && (
        <p className="font-mono text-sm text-ink-soft">● Enregistrement en cours…</p>
      )}
      {microphone.errorMessage !== null && (
        <p className="text-sm text-danger">{microphone.errorMessage}</p>
      )}
    </div>
  )
}
