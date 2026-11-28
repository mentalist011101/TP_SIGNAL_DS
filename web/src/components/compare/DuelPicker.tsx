import { Fragment } from 'react'
import { useModels, type ComparedTask, type ModelInfo } from '../../api/client.ts'
import { FAMILY_LABELS } from '../../labels.ts'
import { formatScore } from '../models/modelFormat.ts'
import { COMPARED_TASKS } from './compareFormat.ts'

// Choix des « duels » de la page Comparer (EF-15) : une carte par tâche, avec les modèles du
// registre qui s'affronteront sur le même son. Cocher la carte ajoute la tâche à la comparaison.

const CARD_CLASSES =
  'flex h-full cursor-pointer flex-col gap-4 rounded-card border border-rule bg-card p-5 transition-[border-color,transform] duration-200 ease-out-soft hover:-translate-y-0.5 hover:border-rule-strong has-checked:border-accent has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-accent-ink'

// Modèles du registre pour une tâche, dans l'ordre du registre.
function taskModels(models: ModelInfo[], task: ComparedTask): ModelInfo[] {
  return models.filter((model) => model.task === task)
}

// Préfixes retirés pour le nom court : « echolens-emotion-whisper-base » devient
// « whisper-base ». L'identifiant complet reste dans l'infobulle.
const NAME_PREFIXES = ['echolens-', 'emotion-', 'sound-event-', 'transcription-']

function shortModelName(modelId: string): string {
  let name = modelId
  for (const prefix of NAME_PREFIXES) {
    if (name.startsWith(prefix)) {
      name = name.slice(prefix.length)
    }
  }
  return name
}

// Un adversaire : sa famille, son nom court et, s'il est mesuré, son F1 de test.
function Fighter({ model }: { model: ModelInfo }) {
  return (
    <div className="min-w-0 flex-1 space-y-1 rounded-xl bg-paper p-3" title={model.id}>
      <p className="label-mono text-ink-faint">{FAMILY_LABELS[model.family]}</p>
      <p className="truncate font-mono text-sm font-semibold">{shortModelName(model.id)}</p>
      {model.f1_macro !== null && (
        <p className="text-xs text-ink-soft">
          F1 de test <span className="font-mono">{formatScore(model.f1_macro)}</span>
        </p>
      )}
    </div>
  )
}

// Les adversaires côte à côte, séparés par « VS ».
function Fighters({ models }: { models: ModelInfo[] }) {
  if (models.length === 0) {
    return <p className="text-sm text-ink-soft">Chargement des modèles…</p>
  }
  return (
    <div className="flex items-stretch gap-2">
      {models.map((model, index) => (
        <Fragment key={model.id}>
          {index > 0 && (
            <span className="flex shrink-0 items-center font-display text-lg text-ink-faint italic">
              vs
            </span>
          )}
          <Fighter model={model} />
        </Fragment>
      ))}
    </div>
  )
}

interface DuelPickerProps {
  tasks: ComparedTask[]
  onToggle: (task: ComparedTask) => void
}

export default function DuelPicker({ tasks, onToggle }: DuelPickerProps) {
  const catalog = useModels()
  const models = catalog.data ?? []
  return (
    <fieldset className="grid gap-4 md:grid-cols-3">
      <legend className="sr-only">Duels à lancer</legend>
      {COMPARED_TASKS.map((option) => (
        <label key={option.value} className={CARD_CLASSES}>
          <span className="flex items-start justify-between gap-3">
            <span>
              <span className="block text-lg font-semibold">{option.label}</span>
              <span className="block text-sm text-ink-soft">{option.detail}</span>
            </span>
            <input
              type="checkbox"
              className="mt-1 h-4 w-4 shrink-0 accent-accent"
              checked={tasks.includes(option.value)}
              onChange={() => onToggle(option.value)}
            />
          </span>
          <Fighters models={taskModels(models, option.value)} />
        </label>
      ))}
    </fieldset>
  )
}
