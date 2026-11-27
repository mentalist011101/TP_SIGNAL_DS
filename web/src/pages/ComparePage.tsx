import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { describeApiError, useCreateComparison, type ComparedTask } from '../api/client.ts'
import AudioPanel from '../components/analyze/AudioPanel.tsx'
import { COMPARED_TASKS } from '../components/compare/compareFormat.ts'

// Page Comparer (EF-15) : un audio et des tâches ; chaque modèle du registre de ces tâches
// tourne sur le même fichier. Dès que la comparaison est acceptée, sa page s'ouvre et suit
// le calcul.

const DEFAULT_TASKS: ComparedTask[] = ['emotion', 'sound_event']

const BUTTON_CLASSES =
  'w-full rounded-btn bg-accent px-5 py-2.5 font-semibold text-on-accent transition-colors duration-200 ease-out-soft hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-50'
const SETTINGS_CLASSES = 'space-y-5 rounded-card border border-rule bg-card p-5 lg:sticky lg:top-10'
const LAYOUT_CLASSES = 'grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_21rem]'
const TILE_CLASSES =
  'flex cursor-pointer items-center gap-3 rounded-2xl border border-rule bg-card p-3 transition-colors duration-200 ease-out-soft hover:bg-paper-alt has-checked:border-accent has-checked:bg-paper-alt'

// Coche ou décoche une tâche : renvoie une nouvelle liste, sans modifier l'ancienne.
function toggleTask(tasks: ComparedTask[], task: ComparedTask): ComparedTask[] {
  if (tasks.includes(task)) {
    return tasks.filter((item) => item !== task)
  }
  return [...tasks, task]
}

interface TaskPickerProps {
  tasks: ComparedTask[]
  onTasksChange: (tasks: ComparedTask[]) => void
}

// Une tuile par tâche comparable, avec les modèles qui s'affronteront.
function TaskPicker({ tasks, onTasksChange }: TaskPickerProps) {
  return (
    <fieldset className="space-y-2">
      <legend className="label-mono mb-2 text-ink-faint">Tâches à comparer</legend>
      {COMPARED_TASKS.map((option) => (
        <label key={option.value} className={TILE_CLASSES}>
          <span className="min-w-0 flex-1">
            <span className="block text-sm font-semibold">{option.label}</span>
            <span className="block text-xs text-ink-soft">{option.detail}</span>
          </span>
          <input
            type="checkbox"
            className="h-4 w-4 accent-accent"
            checked={tasks.includes(option.value)}
            onChange={() => onTasksChange(toggleTask(tasks, option.value))}
          />
        </label>
      ))}
    </fieldset>
  )
}

// Ce qui manque pour lancer la comparaison ; null quand tout est prêt.
function compareHint(hasFile: boolean, hasTasks: boolean): string | null {
  if (!hasFile) {
    return 'Importez un fichier ou enregistrez-vous au micro pour commencer.'
  }
  if (!hasTasks) {
    return 'Cochez au moins une tâche.'
  }
  return null
}

export default function ComparePage() {
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [tasks, setTasks] = useState<ComparedTask[]>(DEFAULT_TASKS)
  const creation = useCreateComparison()
  const hint = compareHint(audioFile !== null, tasks.length > 0)

  function handleCompare() {
    if (audioFile !== null) {
      creation.mutate({ file: audioFile, tasks })
    }
  }

  // Comparaison acceptée : sa page suit le calcul puis montre les modèles côte à côte.
  if (creation.data !== undefined) {
    return <Navigate to={`/comparer/${creation.data.id}`} />
  }
  let buttonText = 'Comparer les modèles'
  if (creation.isPending) {
    buttonText = 'Envoi…'
  }
  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-5xl leading-tight">Comparer les modèles</h1>
        <p className="max-w-3xl text-ink-soft">
          Un même fichier passé dans chaque modèle du registre : résultat principal, premières
          classes et temps de calcul, côte à côte. La comparaison est gardée dans l’Historique.
        </p>
      </div>
      <div className={LAYOUT_CLASSES}>
        <AudioPanel file={audioFile} onAudioSelected={setAudioFile} />
        <aside className={SETTINGS_CLASSES} aria-label="Réglages de la comparaison">
          <TaskPicker tasks={tasks} onTasksChange={setTasks} />
          <div className="space-y-2 border-t border-rule pt-5">
            <button
              type="button"
              className={BUTTON_CLASSES}
              disabled={hint !== null || creation.isPending}
              onClick={handleCompare}
            >
              {buttonText}
            </button>
            {hint !== null && <p className="text-sm text-ink-soft">{hint}</p>}
            {creation.error !== null && (
              <p className="text-sm text-danger">{describeApiError(creation.error)}</p>
            )}
          </div>
        </aside>
      </div>
    </section>
  )
}
