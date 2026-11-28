import { useState, type FormEvent, type ReactNode } from 'react'
import { describeApiError, useEnrollSpeaker, type Speaker } from '../../api/client.ts'
import CloningConsent from './CloningConsent.tsx'
import { MIN_SPEECH_SECONDS, formatSpeech } from './speakerFormat.ts'
import { ClipButtons, ClipList, DurationMeter } from './VoiceClips.tsx'
import { totalDuration, type VoiceClip } from './voiceClip.ts'
import VoiceConsent from './VoiceConsent.tsx'

// Enregistrement d'une voix (EF-11), en trois étapes courtes plutôt qu'un long formulaire :
// 1. qui (le nom), 2. sa voix (micro ou fichiers, au moins 10 s de parole), 3. son accord
// (consentements, puis l'envoi). Le serveur garde les morceaux de parole de 1 à 5 s ; la voix
// est la moyenne de leurs vecteurs (C15).

const FIELD_CLASSES =
  'w-full rounded-btn border border-rule-strong bg-card px-4 py-2 text-base text-ink'
const PRIMARY_CLASSES =
  'rounded-btn bg-accent px-5 py-2.5 font-semibold text-on-accent transition-colors duration-200 ease-out-soft hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-50'
const SECONDARY_CLASSES =
  'rounded-btn px-4 py-2.5 text-sm font-semibold text-ink-soft transition-colors duration-200 ease-out-soft hover:text-ink'

// Texte proposé à la lecture : environ 20 s lu à voix haute, de quoi dépasser les 10 s de
// parole demandées même après les pauses.
const READING_TEXT =
  'Bonjour, j’enregistre ma voix pour qu’EchoLens puisse la reconnaître. Le soleil se lève sur Yaoundé, les taxis klaxonnent et le marché s’anime déjà. Je compte jusqu’à dix : un, deux, trois, quatre, cinq, six, sept, huit, neuf, dix.'

const STEPS = ['Qui ?', 'Sa voix', 'Son accord']

type StepNumber = 1 | 2 | 3

// Indicateur des étapes : une pastille par étape ; on peut revenir à une étape déjà franchie.
function StepIndicator({
  current,
  onGoTo,
}: {
  current: StepNumber
  onGoTo: (step: StepNumber) => void
}) {
  return (
    <ol className="flex items-center gap-2">
      {STEPS.map((title, index) => {
        const step = (index + 1) as StepNumber
        let classes = 'border-rule text-ink-faint'
        if (step === current) {
          classes = 'border-accent bg-accent text-on-accent'
        } else if (step < current) {
          classes = 'border-rule-strong text-ink hover:bg-paper-alt'
        }
        return (
          <li key={title} className="flex min-w-0 flex-1 items-center gap-2">
            <button
              type="button"
              disabled={step > current}
              onClick={() => onGoTo(step)}
              className={`flex w-full items-center gap-2 rounded-btn border px-3 py-1.5 text-sm transition-colors duration-200 ease-out-soft ${classes}`}
              aria-current={step === current ? 'step' : undefined}
            >
              <span className="font-mono text-xs">{step}</span>
              <span className="truncate font-semibold">{title}</span>
            </button>
          </li>
        )
      })}
    </ol>
  )
}

// Pied d'une étape : retour à gauche, suite à droite.
function StepFooter({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule pt-4">
      {children}
    </div>
  )
}

// Message après l'envoi : l'erreur du serveur, ou la voix qui vient d'être enregistrée.
function SubmitMessage({ error, saved }: { error: Error | null; saved: Speaker | null }) {
  if (error !== null) {
    return <p className="text-sm text-danger">{describeApiError(error)}</p>
  }
  if (saved === null) {
    return null
  }
  return (
    <p className="rounded-xl border border-brand px-4 py-3 text-sm" aria-live="polite">
      Voix de <span className="font-semibold">{saved.name}</span> enregistrée :{' '}
      {formatSpeech(saved.speech_s)} de parole.
    </p>
  )
}

export default function EnrollForm() {
  const [step, setStep] = useState<StepNumber>(1)
  const [name, setName] = useState('')
  const [clips, setClips] = useState<VoiceClip[]>([])
  const [accepted, setAccepted] = useState(false)
  const [cloningAccepted, setCloningAccepted] = useState(false)
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
    const request = { name, consent: accepted, cloningConsent: cloningAccepted, files }
    enrollment.mutate(request, {
      onSuccess: () => {
        setName('')
        setClips([])
        setAccepted(false)
        setCloningAccepted(false)
        setStep(1)
      },
    })
  }

  const hasName = name.trim() !== ''
  const hasClips = clips.length > 0
  let submitText = 'Enregistrer la voix'
  if (enrollment.isPending) {
    submitText = 'Calcul de la voix…'
  }
  return (
    <form className="space-y-6 rounded-card border border-rule bg-card p-5" onSubmit={handleSubmit}>
      <div className="space-y-4">
        <h2 className="text-base font-semibold">Nouvelle voix</h2>
        <StepIndicator current={step} onGoTo={setStep} />
      </div>

      {step === 1 && (
        <div className="space-y-5">
          <label className="block space-y-2">
            <span className="block text-sm text-ink-soft">
              Le nom affiché dans les analyses quand cette voix est reconnue.
            </span>
            <input
              className={FIELD_CLASSES}
              value={name}
              maxLength={80}
              placeholder="Par exemple : Awa"
              onChange={(event) => setName(event.target.value)}
            />
          </label>
          <StepFooter>
            <span />
            <button
              type="button"
              className={PRIMARY_CLASSES}
              disabled={!hasName}
              onClick={() => setStep(2)}
            >
              Suivant
            </button>
          </StepFooter>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-5">
          <p className="text-sm text-ink-soft">
            Au moins {MIN_SPEECH_SECONDS} s de parole, en un ou plusieurs extraits. Au micro, lisez
            par exemple :
          </p>
          <blockquote className="rounded-xl bg-paper p-4 text-sm leading-relaxed italic">
            {READING_TEXT}
          </blockquote>
          <ClipButtons onAdd={addClips} />
          <ClipList clips={clips} onRemove={removeClip} />
          {hasClips && <DurationMeter clips={clips} />}
          <StepFooter>
            <button type="button" className={SECONDARY_CLASSES} onClick={() => setStep(1)}>
              Retour
            </button>
            <button
              type="button"
              className={PRIMARY_CLASSES}
              disabled={!hasClips}
              onClick={() => setStep(3)}
            >
              Suivant
            </button>
          </StepFooter>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-4">
          <p className="text-sm text-ink-soft">
            Voix de <span className="font-semibold text-ink">{name.trim()}</span> : {clips.length}{' '}
            extrait{clips.length > 1 ? 's' : ''}, {formatSpeech(totalDuration(clips))} d’audio.
          </p>
          <VoiceConsent
            accepted={accepted}
            disabled={enrollment.isPending}
            onAcceptedChange={setAccepted}
          />
          <CloningConsent
            accepted={cloningAccepted}
            disabled={enrollment.isPending}
            onAcceptedChange={setCloningAccepted}
          />
          <StepFooter>
            <button type="button" className={SECONDARY_CLASSES} onClick={() => setStep(2)}>
              Retour
            </button>
            <button
              type="submit"
              className={PRIMARY_CLASSES}
              disabled={!accepted || enrollment.isPending}
            >
              {submitText}
            </button>
          </StepFooter>
        </div>
      )}

      <SubmitMessage error={enrollment.error} saved={enrollment.data ?? null} />
    </form>
  )
}
