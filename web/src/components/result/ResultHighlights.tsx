import type { Analysis, AnalysisTask, TaskResult } from '../../api/client.ts'
import { TASK_LABELS } from '../../labels.ts'
import MainResultValue from './MainResultValue.tsx'

interface Highlight {
  task: AnalysisTask
  result: TaskResult
}

// Tâches terminées avec un résultat principal (done), dans l'ordre de la demande. La
// transcription n'a pas de classe principale : son texte est dans sa propre carte.
function doneResults(analysis: Analysis): Highlight[] {
  const highlights: Highlight[] = []
  if (analysis.results === null) {
    return highlights
  }
  for (const task of analysis.tasks) {
    const result = analysis.results[task]
    if (task === 'transcription') {
      continue
    }
    if (result !== undefined && result.status === 'done') {
      highlights.push({ task, result })
    }
  }
  return highlights
}

// « Émotion · emotion-cnn 0.1.0 » : la tâche, puis le modèle qui a produit son résultat.
function modelLine(highlight: Highlight): string {
  const taskLabel = TASK_LABELS[highlight.task]
  const result = highlight.result
  return `${taskLabel} · ${result.model_id} ${result.model_version}`
}

// Une case : la tâche, son résultat principal en grand et sa probabilité.
function HighlightTile({ task, result }: Highlight) {
  return (
    <div className="space-y-1 bg-card px-6 py-5">
      <p className="label-mono text-ink-faint">{TASK_LABELS[task]}</p>
      <MainResultValue task={task} result={result} leading="leading-tight" />
    </div>
  )
}

// Rangée des chiffres clés en haut du résultat : le résultat principal de chaque tâche, puis
// les modèles utilisés. Rien tant qu'aucune tâche n'a de résultat.
export default function ResultHighlights({ analysis }: { analysis: Analysis }) {
  const highlights = doneResults(analysis)
  if (highlights.length === 0) {
    return null
  }
  return (
    <div className="grid gap-px overflow-hidden rounded-card border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-3">
      {highlights.map((highlight) => (
        <HighlightTile key={highlight.task} task={highlight.task} result={highlight.result} />
      ))}
      <div className="space-y-1 bg-card px-6 py-5">
        <p className="label-mono text-ink-faint">Modèles</p>
        {highlights.map((highlight) => (
          <p key={highlight.task} className="font-mono text-sm">
            {modelLine(highlight)}
          </p>
        ))}
      </div>
    </div>
  )
}
