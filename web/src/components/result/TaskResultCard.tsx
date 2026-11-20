import { useState } from 'react'
import type { AnalysisTask, ClassProbability, TaskResult } from '../../api/client.ts'
import { TASK_LABELS } from '../../labels.ts'
import DemoNotice from './DemoNotice.tsx'
import { formatProbability } from './formatProbability.ts'
import ProbabilityBars from './ProbabilityBars.tsx'

// Identifiant du faux prédicteur dans le contrat de l'API (C13).
const DEMO_MODEL_ID = 'demo'

// Événements sonores : on montre les 5 classes les plus probables sur 50, le reste sur demande.
const SOUND_EVENT_TOP_COUNT = 5

const CARD_CLASSES = 'space-y-4 rounded-card border border-rule bg-card p-5 shadow-card'

const TOGGLE_CLASSES = 'text-sm font-semibold text-accent-ink hover:underline'

// Probabilité du résultat principal, lue dans la liste renvoyée par l'API (rien n'est recalculé).
function mainProbability(result: TaskResult): number | null {
  for (const item of result.probabilities) {
    if (item.label === result.label) {
      return item.probability
    }
  }
  return null
}

// Résultat principal en grand : libellé français et probabilité.
function MainResult({ result }: { result: TaskResult }) {
  const probability = mainProbability(result)
  return (
    <div>
      <p className="label-mono text-ink-soft">Résultat principal</p>
      <p className="flex flex-wrap items-baseline gap-x-3">
        <span className="font-display text-2xl font-bold">{result.label_fr}</span>
        {probability !== null && (
          <span className="font-mono text-lg text-ink-soft">{formatProbability(probability)}</span>
        )}
      </p>
    </div>
  )
}

// 5 premières classes, puis les 50 sur demande (bouton qui bascule entre les deux).
function SoundEventBars({ probabilities }: { probabilities: ClassProbability[] }) {
  const [showAll, setShowAll] = useState(false)
  let visible = probabilities
  let toggleText = `Voir les ${probabilities.length} classes`
  if (showAll) {
    toggleText = `Afficher les ${SOUND_EVENT_TOP_COUNT} premières`
  } else {
    visible = probabilities.slice(0, SOUND_EVENT_TOP_COUNT)
  }
  return (
    <div className="space-y-3">
      <ProbabilityBars probabilities={visible} />
      <button
        type="button"
        className={TOGGLE_CLASSES}
        aria-expanded={showAll}
        onClick={() => setShowAll(!showAll)}
      >
        {toggleText}
      </button>
    </div>
  )
}

// Émotion : les 6 classes. Événement sonore : les 5 premières sur 50.
function TaskBars({ task, result }: { task: AnalysisTask; result: TaskResult }) {
  if (task === 'sound_event') {
    return <SoundEventBars probabilities={result.probabilities} />
  }
  return <ProbabilityBars probabilities={result.probabilities} />
}

// Modèle qui a produit le résultat, pour la traçabilité (ENF-06 : calibration).
function ModelLine({ result }: { result: TaskResult }) {
  let calibrationText = 'probabilités non calibrées'
  if (result.calibrated === true) {
    calibrationText = 'probabilités calibrées'
  }
  return (
    <p className="text-xs text-ink-soft">
      Modèle : <span className="font-mono">{result.model_id}</span>, version{' '}
      <span className="font-mono">{result.model_version}</span> · {calibrationText}
    </p>
  )
}

// Contenu d'une tâche terminée. Le bandeau de démonstration passe avant les chiffres.
function DoneResult({ task, result }: { task: AnalysisTask; result: TaskResult }) {
  const isDemo = result.model_id === DEMO_MODEL_ID
  return (
    <>
      {isDemo && <DemoNotice />}
      <MainResult result={result} />
      <TaskBars task={task} result={result} />
      <ModelLine result={result} />
    </>
  )
}

// Corps de la carte selon l'état. no_speech et unavailable ne sont pas des erreurs : le message
// de l'API s'affiche en gris, sans barres.
function TaskResultBody({ task, result }: TaskResultCardProps) {
  if (result === null) {
    return <p className="text-sm text-ink-soft">Résultat en cours de calcul…</p>
  }
  if (result.status !== 'done') {
    return <p className="text-sm text-ink-soft">{result.message}</p>
  }
  return <DoneResult task={task} result={result} />
}

interface TaskResultCardProps {
  task: AnalysisTask
  // null tant que l'analyse n'est pas terminée.
  result: TaskResult | null
}

// Carte d'une tâche demandée : son nom, puis son résultat.
export default function TaskResultCard({ task, result }: TaskResultCardProps) {
  const title = TASK_LABELS[task]
  return (
    <article className={CARD_CLASSES}>
      <h2 className="font-display text-lg font-bold">{title}</h2>
      <TaskResultBody task={task} result={result} />
    </article>
  )
}
