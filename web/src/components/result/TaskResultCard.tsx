import { useState } from 'react'
import {
  useModels,
  type AnalysisTask,
  type ClassProbability,
  type TaskResult,
} from '../../api/client.ts'
import { TASK_LABELS } from '../../labels.ts'
import { findModel, formatCalibration, formatScore } from '../models/modelFormat.ts'
import MainResultValue from './MainResultValue.tsx'
import ProbabilityBars from './ProbabilityBars.tsx'
import SpeakerResult from './SpeakerResult.tsx'
import { isDemoResult } from './taskResult.ts'
import TranscriptionResult from './TranscriptionResult.tsx'

// Événements sonores : on montre les 5 classes les plus probables sur 50, le reste sur demande.
const SOUND_EVENT_TOP_COUNT = 5

const CARD_CLASSES = 'space-y-4 rounded-card border border-rule bg-card p-5'

// La transcription prend toute la largeur : ses textes sont plus longs qu'un libellé de classe.
const WIDE_CARD_CLASSES = `${CARD_CLASSES} md:col-span-2`

const TOGGLE_CLASSES = 'text-sm font-semibold text-accent-ink hover:underline'

// Résultat principal en grand : libellé français et probabilité.
function MainResult({ task, result }: { task: AnalysisTask; result: TaskResult }) {
  return (
    <div>
      <p className="label-mono text-ink-soft">Résultat principal</p>
      <MainResultValue task={task} result={result} leading="leading-none" />
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

// Modèle qui a produit le résultat, pour la traçabilité : sa version, son F1 de test, sa
// calibration (ENF-06) et la page de ses poids, lus dans le catalogue (GET /api/v1/models).
function ModelLine({ result }: { result: TaskResult }) {
  const models = useModels()
  const catalog = models.data ?? []
  const model = findModel(catalog, result.model_id)
  if (model === null) {
    return <BasicModelLine result={result} />
  }
  return (
    <p className="text-xs text-ink-soft">
      Modèle : <span className="font-mono">{model.id}</span>, version{' '}
      <span className="font-mono">{result.model_version}</span> · F1 de test{' '}
      <span className="font-mono">{formatScore(model.f1_macro)}</span> ·{' '}
      <span className="font-mono whitespace-nowrap">{formatCalibration(model)}</span>
      {model.huggingface_url !== null && (
        <>
          {' · '}
          <a href={model.huggingface_url} className="text-accent-ink underline underline-offset-2">
            page Hugging Face
          </a>
        </>
      )}
    </p>
  )
}

// Ligne de secours quand le modèle n'est pas au catalogue (faux prédicteur, modèle retiré du
// registre, catalogue pas encore chargé) : ce que dit le résultat lui-même.
function BasicModelLine({ result }: { result: TaskResult }) {
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

// Contenu d'une tâche terminée : résultat principal, barres, puis le modèle utilisé.
function DoneResult({ task, result }: { task: AnalysisTask; result: TaskResult }) {
  return (
    <>
      <MainResult task={task} result={result} />
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
  if (task === 'transcription') {
    return <TranscriptionResult result={result} />
  }
  if (task === 'speaker') {
    return <SpeakerResult result={result} />
  }
  return <DoneResult task={task} result={result} />
}

interface TaskResultCardProps {
  task: AnalysisTask
  // null tant que l'analyse n'est pas terminée.
  result: TaskResult | null
}

// Carte d'une tâche demandée : son nom, puis son résultat. L'étiquette « Démo » dit quelles
// cartes viennent du faux prédicteur, en plus du bandeau posé au-dessus des cartes.
export default function TaskResultCard({ task, result }: TaskResultCardProps) {
  const title = TASK_LABELS[task]
  const isDemo = result !== null && isDemoResult(result)
  let cardClasses = CARD_CLASSES
  if (task === 'transcription') {
    cardClasses = WIDE_CARD_CLASSES
  }
  return (
    <article className={cardClasses}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold">{title}</h2>
        {isDemo && (
          <span className="label-mono rounded-btn border border-rule-strong px-2 py-0.5 text-ink-soft">
            Démo
          </span>
        )}
      </div>
      <TaskResultBody task={task} result={result} />
    </article>
  )
}
