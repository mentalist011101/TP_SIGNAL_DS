import type { CSSProperties } from 'react'
import type { AnalysisTask, ModelInfo } from '../../api/client.ts'
import { FAMILY_LABELS, TASK_LABELS } from '../../labels.ts'
import { formatScore } from './modelFormat.ts'

// Tâches comparées : celles qui ont des modèles entraînés par l'équipe.
const COMPARED_TASKS: AnalysisTask[] = ['emotion', 'sound_event']

// Familles comparées par le protocole : A (réseaux entraînés sur le log-Mel) et B (encodeur
// pré-entraîné gelé et tête entraînée).
const COMPARED_FAMILIES: ('A' | 'B')[] = ['A', 'B']

// Modèles d'une tâche et d'une famille, dans l'ordre du registre.
function modelsOf(models: ModelInfo[], task: AnalysisTask, family: 'A' | 'B'): ModelInfo[] {
  const found: ModelInfo[] = []
  for (const model of models) {
    if (model.task === task && model.family === family) {
      found.push(model)
    }
  }
  return found
}

// Longueur de la barre : le F1 (entre 0 et 1) en pourcentage de la largeur.
function scoreBarStyle(score: number): CSSProperties {
  return { width: `${score * 100}%` }
}

// Une ligne : le modèle, sa barre de F1 et la valeur écrite.
function ScoreRow({ model }: { model: ModelInfo }) {
  return (
    <li className="space-y-1">
      <p className="flex justify-between gap-3 text-sm">
        <span className="font-mono break-all">{model.id}</span>
        <span className="font-mono text-ink-soft">{formatScore(model.f1_macro)}</span>
      </p>
      {model.f1_macro !== null && (
        <span className="block h-2 rounded-btn bg-paper-alt" aria-hidden="true">
          <span className="block h-full rounded-btn bg-ink" style={scoreBarStyle(model.f1_macro)} />
        </span>
      )}
    </li>
  )
}

// Une famille dans une tâche : ses modèles, ou un message s'il n'y en a aucun au registre.
function FamilyBlock({ models, family }: { models: ModelInfo[]; family: 'A' | 'B' }) {
  return (
    <div className="space-y-2">
      <p className="label-mono text-ink-faint">{FAMILY_LABELS[family]}</p>
      {models.length === 0 && (
        <p className="text-sm text-ink-soft">Aucun modèle de cette famille au registre.</p>
      )}
      <ul className="space-y-3">
        {models.map((model) => (
          <ScoreRow key={model.id} model={model} />
        ))}
      </ul>
    </div>
  )
}

// Carte d'une tâche : la famille A au-dessus de la famille B, F1 macro de test sur la même
// échelle (0 à 1), pour les comparer d'un coup d'œil.
function TaskComparison({ models, task }: { models: ModelInfo[]; task: AnalysisTask }) {
  return (
    <article className="space-y-5 rounded-card border border-rule bg-card p-5">
      <h3 className="text-base font-semibold">{TASK_LABELS[task]}</h3>
      {COMPARED_FAMILIES.map((family) => (
        <FamilyBlock key={family} family={family} models={modelsOf(models, task, family)} />
      ))}
    </article>
  )
}

// Comparaison A contre B, tâche par tâche (EF-16), à partir des F1 de test du registre.
export default function FamilyComparison({ models }: { models: ModelInfo[] }) {
  return (
    <div className="grid items-start gap-4 md:grid-cols-2">
      {COMPARED_TASKS.map((task) => (
        <TaskComparison key={task} task={task} models={models} />
      ))}
    </div>
  )
}
