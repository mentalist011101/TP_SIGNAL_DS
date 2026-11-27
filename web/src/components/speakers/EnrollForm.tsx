import { useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { describeApiError, useEnrollSpeaker, type Speaker } from '../../api/client.ts'
import { ACCEPTED_FORMATS, useMicrophone } from '../analyze/microphone.ts'
import { MicIcon, UploadIcon } from '../icons.tsx'
import { MIN_SPEECH_SECONDS, formatSpeech } from './speakerFormat.ts'
import VoiceConsent from './VoiceConsent.tsx'

// Enregistrement d'une voix (EF-11) : un nom, des extraits (micro ou fichiers), le
// consentement. Le serveur garde les morceaux de parole de 1 à 5 s et en demande au moins
// 10 s au total ; la voix est la moyenne de leurs vecteurs (C15).

const FIELD_CLASSES =
  'w-full rounded-btn border border-rule-strong bg-card px-3 py-1.5 text-sm text-ink'
const BUTTON_CLASSES =
  'inline-flex items-center gap-2 rounded-btn border border-rule-strong bg-card px-4 py-2 text-sm font-medium text-ink transition-colors duration-200 ease-out-soft hover:bg-paper-alt disabled:opacity-50'
const SUBMIT_CLASSES =
  'w-full rounded-btn bg-accent px-5 py-2.5 font-semibold text-on-accent transition-colors duration-200 ease-out-soft hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-50'
const SMALL_BUTTON_CLASSES = 'text-sm text-accent-ink hover:underline'

// Texte proposé à la lecture : environ 20 s lu à voix haute, de quoi dépasser les 10 s de
// parole demandées même après les pauses.
const READING_TEXT =
  'Bonjour, je m’appelle comme indiqué ci-dessus. J’enregistre ma voix pour qu’EchoLens puisse la reconnaître. Le soleil se lève sur Yaoundé, les taxis klaxonnent et le marché s’anime déjà. Je compte jusqu’à dix : un, deux, trois, quatre, cinq, six, sept, huit, neuf, dix.'

// Un extrait de voix : son fichier et un nom lisible dans la liste.
interface VoiceClip {
  file: File
  label: string
}

// Nom d'un enregistrement du micro : « micro_2.webm », avec l'extension du navigateur.
function microphoneClip(file: File, position: number): VoiceClip {
  const extension = file.name.split('.').pop() ?? 'webm'
  const name = `micro_${position}.${extension}`
  const renamed = new File([file], name, { type: file.type })
  return { file: renamed, label: `Micro, extrait ${position}` }
}

// Liste des extraits choisis, chacun avec son bouton Retirer.
function ClipList({ clips, onRemove }: { clips: VoiceClip[]; onRemove: (index: number) => void }) {
  if (clips.length === 0) {
    return <p className="text-sm text-ink-soft">Aucun extrait pour l’instant.</p>
  }
  return (
    <ul className="space-y-1">
      {clips.map((clip, index) => (
        <li key={`${clip.label}-${index}`} className="flex items-center justify-between gap-3">
          <span className="truncate font-mono text-sm">{clip.label}</span>
          <button type="button" className={SMALL_BUTTON_CLASSES} onClick={() => onRemove(index)}>
            Retirer
          </button>
        </li>
      ))}
    </ul>
  )
}

// Boutons d'ajout d'extraits : micro (démarre puis arrête) et fichiers (plusieurs à la fois).
function ClipButtons({ onAdd }: { onAdd: (clips: VoiceClip[]) => void }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const recordCount = useRef(0)
  const microphone = useMicrophone((file) => {
    recordCount.current += 1
    onAdd([microphoneClip(file, recordCount.current)])
  })

  function handleFiles(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files
    if (files === null) {
      return
    }
    const clips: VoiceClip[] = []
    for (const file of Array.from(files)) {
      clips.push({ file, label: file.name })
    }
    onAdd(clips)
    // Vider le champ permet de rajouter le même fichier juste après.
    event.target.value = ''
  }

  let microphoneText = 'Enregistrer au micro'
  if (microphone.isRecording) {
    microphoneText = 'Arrêter l’enregistrement'
  }
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-3">
        <button type="button" className={BUTTON_CLASSES} onClick={microphone.toggle}>
          <MicIcon />
          {microphoneText}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_FORMATS}
          multiple
          hidden
          onChange={handleFiles}
        />
        <button type="button" className={BUTTON_CLASSES} onClick={() => inputRef.current?.click()}>
          <UploadIcon />
          Ajouter des fichiers
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

// Message sous le bouton : l'erreur du serveur, ou la voix qui vient d'être enregistrée.
function SubmitMessage({ error, saved }: { error: Error | null; saved: Speaker | null }) {
  if (error !== null) {
    return <p className="text-sm text-danger">{describeApiError(error)}</p>
  }
  if (saved === null) {
    return null
  }
  return (
    <p className="text-sm text-ink-soft" aria-live="polite">
      Voix de {saved.name} enregistrée : {formatSpeech(saved.speech_s)} de parole.
    </p>
  )
}

export default function EnrollForm() {
  const [name, setName] = useState('')
  const [clips, setClips] = useState<VoiceClip[]>([])
  const [accepted, setAccepted] = useState(false)
  const enrollment = useEnrollSpeaker()

  function addClips(added: VoiceClip[]) {
    setClips((current) => [...current, ...added])
  }

  function removeClip(index: number) {
    setClips((current) => current.filter((_, position) => position !== index))
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const files = clips.map((clip) => clip.file)
    const request = { name, consent: accepted, files }
    enrollment.mutate(request, {
      onSuccess: () => {
        setName('')
        setClips([])
        setAccepted(false)
      },
    })
  }

  const isMissingSomething = name.trim() === '' || clips.length === 0 || !accepted
  const isDisabled = isMissingSomething || enrollment.isPending
  let submitText = 'Enregistrer la voix'
  if (enrollment.isPending) {
    submitText = 'Calcul de la voix…'
  }
  return (
    <form className="space-y-5 rounded-card border border-rule bg-card p-5" onSubmit={handleSubmit}>
      <h2 className="text-base font-semibold">Nouvelle voix</h2>
      <label className="block space-y-1">
        <span className="label-mono text-ink-faint">Nom affiché</span>
        <input
          className={FIELD_CLASSES}
          value={name}
          maxLength={80}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <div className="space-y-2">
        <p className="label-mono text-ink-faint">Extraits de voix</p>
        <p className="text-sm text-ink-soft">
          Au moins {MIN_SPEECH_SECONDS} s de parole au total, extraits réunis. Au micro, lisez par
          exemple :
        </p>
        <blockquote className="border-l-2 border-rule-strong pl-3 text-sm italic">
          {READING_TEXT}
        </blockquote>
        <ClipButtons onAdd={addClips} />
        <ClipList clips={clips} onRemove={removeClip} />
      </div>
      <VoiceConsent
        accepted={accepted}
        disabled={enrollment.isPending}
        onAcceptedChange={setAccepted}
      />
      <div className="space-y-2">
        <button type="submit" className={SUBMIT_CLASSES} disabled={isDisabled}>
          {submitText}
        </button>
        <SubmitMessage error={enrollment.error} saved={enrollment.data ?? null} />
      </div>
    </form>
  )
}
