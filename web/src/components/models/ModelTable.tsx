import type { ModelInfo } from '../../api/client.ts'
import { FAMILY_LABELS, PROFILE_LABELS, TASK_LABELS } from '../../labels.ts'
import { formatCalibration, formatScore } from './modelFormat.ts'

const HEADER_CLASSES = 'px-4 py-3 text-left text-xs font-medium text-ink-soft'
const CELL_CLASSES = 'px-4 py-3 align-top'
const NUMBER_CLASSES = `${CELL_CLASSES} font-mono whitespace-nowrap`

// Nom de la tâche ; voice_cloning n'a pas encore de libellé dans l'interface.
function taskLabel(model: ModelInfo): string {
  if (model.task === 'voice_cloning') {
    return 'Clonage de voix'
  }
  return TASK_LABELS[model.task]
}

// « Qualité, Temps réel » : les profils qui utilisent ce modèle (EF-07).
function profilesText(model: ModelInfo): string {
  const labels = model.profiles.map((profile) => PROFILE_LABELS[profile])
  return labels.join(', ')
}

// Identifiant du modèle, en lien vers sa page Hugging Face quand les poids y sont publiés.
function ModelName({ model }: { model: ModelInfo }) {
  if (model.huggingface_url === null) {
    return <span className="font-mono break-all">{model.id}</span>
  }
  return (
    <a
      href={model.huggingface_url}
      className="font-mono break-all text-accent-ink underline underline-offset-4"
    >
      {model.id}
    </a>
  )
}

// Une ligne par modèle du registre.
function ModelRow({ model }: { model: ModelInfo }) {
  return (
    <tr className="border-t border-rule">
      <td className={CELL_CLASSES}>
        <ModelName model={model} />
        <p className="mt-1 text-xs text-ink-soft">{model.description}</p>
      </td>
      <td className={CELL_CLASSES}>{taskLabel(model)}</td>
      <td className={`${CELL_CLASSES} whitespace-nowrap`}>{FAMILY_LABELS[model.family]}</td>
      <td className={CELL_CLASSES}>{profilesText(model)}</td>
      <td className={NUMBER_CLASSES}>{model.version}</td>
      <td className={NUMBER_CLASSES}>{formatScore(model.f1_macro)}</td>
      <td className={NUMBER_CLASSES}>{formatScore(model.accuracy)}</td>
      <td className={NUMBER_CLASSES}>{formatCalibration(model)}</td>
    </tr>
  )
}

// Tableau des modèles du registre ; il défile de côté sur un écran étroit.
export default function ModelTable({ models }: { models: ModelInfo[] }) {
  return (
    <div className="overflow-x-auto rounded-card border border-rule bg-card">
      <table className="w-full min-w-[56rem] text-sm">
        <thead>
          <tr>
            <th className={HEADER_CLASSES}>Modèle</th>
            <th className={HEADER_CLASSES}>Tâche</th>
            <th className={HEADER_CLASSES}>Famille</th>
            <th className={HEADER_CLASSES}>Profil</th>
            <th className={HEADER_CLASSES}>Version</th>
            <th className={HEADER_CLASSES}>F1 test</th>
            <th className={HEADER_CLASSES}>Accuracy</th>
            <th className={HEADER_CLASSES}>Calibration</th>
          </tr>
        </thead>
        <tbody>
          {models.map((model) => (
            <ModelRow key={model.id} model={model} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
