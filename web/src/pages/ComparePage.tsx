import { useState, type ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { describeApiError, useCreateComparison, type ComparedTask } from '../api/client.ts'
import AudioPicker, { RecordingIndicator } from '../components/analyze/AudioPicker.tsx'
import { useMicrophone } from '../components/analyze/microphone.ts'
import DuelPicker from '../components/compare/DuelPicker.tsx'
import WaveRibbon from '../components/WaveRibbon.tsx'

// Page Comparer (EF-15), pensée comme un tournoi plutôt qu'une analyse : 1. un son, 2. les
// duels (chaque modèle du registre d'une tâche contre les autres), 3. le lancement. Dès que la
// comparaison est acceptée, sa page s'ouvre et suit le calcul.

const DEFAULT_TASKS: ComparedTask[] = ['emotion', 'sound_event']

const BUTTON_CLASSES =
  'rounded-btn bg-accent px-7 py-3 font-semibold text-on-accent transition-colors duration-200 ease-out-soft hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-50'

// Coche ou décoche une tâche : renvoie une nouvelle liste, sans modifier l'ancienne.
function toggleTask(tasks: ComparedTask[], task: ComparedTask): ComparedTask[] {
  if (tasks.includes(task)) {
    return tasks.filter((item) => item !== task)
  }
  return [...tasks, task]
}

// Une étape numérotée : le numéro dans un rond, le titre, puis son contenu.
function Step({ number, title, children }: { number: number; title: string; children: ReactNode }) {
  return (
    <section className="grid grid-cols-[2.75rem_minmax(0,1fr)] items-center gap-4">
      <span className="flex h-11 w-11 items-center justify-center rounded-full border border-rule-strong font-display text-xl">
        {number}
      </span>
      <h2 className="text-xl font-semibold">{title}</h2>
      <div className="col-span-2 min-w-0 md:col-span-1 md:col-start-2">{children}</div>
    </section>
  )
}

// Étape 1 : le son, en bandeau compact (fichier, ou micro avec son ruban).
function SoundStep({ file, onFile }: { file: File | null; onFile: (file: File) => void }) {
  const microphone = useMicrophone(onFile)
  return (
    <div className="space-y-3 rounded-card border border-rule bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0">
          <p className="label-mono text-ink-faint">Son à comparer</p>
          {file === null && <p className="text-ink-soft">Aucun son choisi pour l’instant.</p>}
          {file !== null && <p className="font-mono break-all">{file.name}</p>}
        </div>
        <AudioPicker onAudioSelected={onFile} microphone={microphone} />
      </div>
      {microphone.isRecording && (
        <div className="space-y-2 text-center">
          <RecordingIndicator elapsedS={microphone.elapsedS} />
          <WaveRibbon className="h-20" readLevel={microphone.readLevel} />
        </div>
      )}
    </div>
  )
}

// « 2 duels · 4 modèles » : ce qui va tourner, avant de lancer.
function launchSummary(tasks: ComparedTask[]): string {
  if (tasks.length === 0) {
    return 'Choisissez au moins un duel.'
  }
  let duels = `${tasks.length} duels`
  if (tasks.length === 1) {
    duels = '1 duel'
  }
  return `${duels} : chaque modèle de ces tâches tourne sur le même son, avec son temps de calcul.`
}

export default function ComparePage() {
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [tasks, setTasks] = useState<ComparedTask[]>(DEFAULT_TASKS)
  const creation = useCreateComparison()
  const isReady = audioFile !== null && tasks.length > 0

  function handleCompare() {
    if (audioFile !== null) {
      creation.mutate({ file: audioFile, tasks })
    }
  }

  // Comparaison acceptée : sa page suit le calcul puis montre les modèles côte à côte.
  if (creation.data !== undefined) {
    return <Navigate to={`/comparer/${creation.data.id}`} />
  }
  let buttonText = 'Lancer les duels'
  if (creation.isPending) {
    buttonText = 'Envoi…'
  }
  return (
    <section className="space-y-10">
      <div className="space-y-2">
        <h1 className="text-5xl leading-tight">Comparer les modèles</h1>
        <p className="max-w-3xl text-ink-soft">
          Un même son, plusieurs modèles face à face : résultat principal, premières classes et
          temps de calcul, côte à côte. La comparaison est gardée dans l’Historique.
        </p>
      </div>
      <Step number={1} title="Le son">
        <SoundStep file={audioFile} onFile={setAudioFile} />
      </Step>
      <Step number={2} title="Les duels">
        <DuelPicker tasks={tasks} onToggle={(task) => setTasks(toggleTask(tasks, task))} />
      </Step>
      <Step number={3} title="Le verdict">
        <div className="flex flex-wrap items-center gap-4">
          <button
            type="button"
            className={BUTTON_CLASSES}
            disabled={!isReady || creation.isPending}
            onClick={handleCompare}
          >
            {buttonText}
          </button>
          <p className="text-sm text-ink-soft">
            {audioFile === null ? 'Choisissez d’abord un son.' : launchSummary(tasks)}
          </p>
        </div>
        {creation.error !== null && (
          <p className="text-sm text-danger">{describeApiError(creation.error)}</p>
        )}
      </Step>
    </section>
  )
}
