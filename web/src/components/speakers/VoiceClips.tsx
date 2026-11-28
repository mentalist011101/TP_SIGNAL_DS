import { useRef, type ChangeEvent } from 'react'
import { ACCEPTED_FORMATS, useMicrophone } from '../analyze/microphone.ts'
import { RecordingIndicator } from '../analyze/AudioPicker.tsx'
import { MicIcon, UploadIcon } from '../icons.tsx'
import WaveRibbon from '../WaveRibbon.tsx'
import { MIN_SPEECH_SECONDS, formatSpeech } from './speakerFormat.ts'
import { totalDuration, type VoiceClip } from './voiceClip.ts'

// Extraits de voix de l'étape 2 de la page Locuteurs (EF-11) : enregistrement au micro (le ruban
// suit la voix) ou fichiers, avec la durée de chacun et une barre vers les 10 s demandées.

const BUTTON_CLASSES =
  'inline-flex items-center gap-2 rounded-btn border border-rule-strong bg-card px-4 py-2 text-sm font-medium text-ink transition-colors duration-200 ease-out-soft hover:bg-paper-alt disabled:opacity-50'
const RECORDING_BUTTON_CLASSES =
  'inline-flex items-center gap-2 rounded-btn bg-accent px-4 py-2 text-sm font-semibold text-on-accent transition-colors duration-200 ease-out-soft hover:bg-accent-deep'

// Durée d'un fichier audio, lue dans ses métadonnées par le navigateur ; null s'il ne la donne
// pas (certains WebM).
function readDuration(file: File): Promise<number | null> {
  return new Promise((resolve) => {
    const audio = new Audio()
    const url = URL.createObjectURL(file)
    audio.preload = 'metadata'
    audio.onloadedmetadata = () => {
      URL.revokeObjectURL(url)
      resolve(Number.isFinite(audio.duration) ? audio.duration : null)
    }
    audio.onerror = () => {
      URL.revokeObjectURL(url)
      resolve(null)
    }
    audio.src = url
  })
}

// Nom d'un enregistrement du micro : « micro_2.webm », avec l'extension du navigateur.
function microphoneClip(file: File, position: number, durationS: number): VoiceClip {
  const extension = file.name.split('.').pop() ?? 'webm'
  const name = `micro_${position}.${extension}`
  const renamed = new File([file], name, { type: file.type })
  return { file: renamed, label: `Micro, extrait ${position}`, durationS }
}

// Boutons d'ajout : micro (démarre puis arrête) et fichiers (plusieurs à la fois).
export function ClipButtons({ onAdd }: { onAdd: (clips: VoiceClip[]) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const recordCount = useRef(0)
  const startedAt = useRef(0)
  const microphone = useMicrophone((file) => {
    recordCount.current += 1
    // Durée mesurée pendant l'enregistrement : le WebM du navigateur ne la donne pas toujours.
    const durationS = (performance.now() - startedAt.current) / 1000
    onAdd([microphoneClip(file, recordCount.current, durationS)])
  })

  function toggleMicrophone() {
    if (!microphone.isRecording) {
      startedAt.current = performance.now()
    }
    microphone.toggle()
  }

  async function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files
    if (files === null) {
      return
    }
    const chosen = Array.from(files)
    // Vider le champ permet de rajouter le même fichier juste après.
    event.target.value = ''
    const clips: VoiceClip[] = []
    for (const file of chosen) {
      const durationS = await readDuration(file)
      clips.push({ file, label: file.name, durationS })
    }
    onAdd(clips)
  }

  let microphoneClasses = BUTTON_CLASSES
  let microphoneText = 'Enregistrer au micro'
  if (microphone.isRecording) {
    microphoneClasses = RECORDING_BUTTON_CLASSES
    microphoneText = 'Arrêter et garder'
  }
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-3">
        <button type="button" className={microphoneClasses} onClick={toggleMicrophone}>
          <MicIcon />
          {microphoneText}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_FORMATS}
          multiple
          hidden
          onChange={(event) => void handleFiles(event)}
        />
        {!microphone.isRecording && (
          <button
            type="button"
            className={BUTTON_CLASSES}
            onClick={() => inputRef.current?.click()}
          >
            <UploadIcon />
            Ajouter des fichiers
          </button>
        )}
      </div>
      {microphone.isRecording && (
        <div className="space-y-2 rounded-xl border border-rule bg-paper p-3 text-center">
          <RecordingIndicator elapsedS={microphone.elapsedS} />
          <WaveRibbon className="h-20" readLevel={microphone.readLevel} />
        </div>
      )}
      {microphone.errorMessage !== null && (
        <p className="text-sm text-danger">{microphone.errorMessage}</p>
      )}
    </div>
  )
}

// Barre vers les 10 s : durée des extraits (la parole réelle, comptée par le serveur, est un
// peu plus courte que l'audio, à cause des silences).
export function DurationMeter({ clips }: { clips: VoiceClip[] }) {
  const total = totalDuration(clips)
  const ratio = Math.min(total / MIN_SPEECH_SECONDS, 1)
  let message = `${formatSpeech(total)} d’audio sur au moins ${MIN_SPEECH_SECONDS} s de parole.`
  if (total >= MIN_SPEECH_SECONDS) {
    message = `${formatSpeech(total)} d’audio : assez, si la parole est continue.`
  }
  return (
    <div className="space-y-1.5">
      <span className="block h-2 rounded-btn bg-paper-alt" aria-hidden="true">
        <span
          className="block h-full rounded-btn bg-brand transition-[width] duration-500 ease-out-soft"
          style={{ width: `${ratio * 100}%` }}
        />
      </span>
      <p className="text-xs text-ink-soft">{message}</p>
    </div>
  )
}

// Liste des extraits, avec leur durée et un bouton Retirer.
export function ClipList({
  clips,
  onRemove,
}: {
  clips: VoiceClip[]
  onRemove: (index: number) => void
}) {
  if (clips.length === 0) {
    return <p className="text-sm text-ink-soft">Aucun extrait pour l’instant.</p>
  }
  return (
    <ul className="divide-y divide-rule rounded-xl border border-rule">
      {clips.map((clip, index) => (
        <li
          key={`${clip.label}-${index}`}
          className="flex items-center justify-between gap-3 px-3 py-2"
        >
          <span className="min-w-0 truncate font-mono text-sm">{clip.label}</span>
          <span className="flex shrink-0 items-center gap-3">
            <span className="font-mono text-xs text-ink-faint">
              {clip.durationS === null ? '—' : formatSpeech(clip.durationS)}
            </span>
            <button
              type="button"
              className="text-sm text-accent-ink hover:underline"
              onClick={() => onRemove(index)}
            >
              Retirer
            </button>
          </span>
        </li>
      ))}
    </ul>
  )
}
