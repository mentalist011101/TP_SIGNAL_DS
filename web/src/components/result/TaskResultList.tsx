import type { Analysis, AnalysisTask, TaskResult } from '../../api/client.ts'
import DemoNotice from './DemoNotice.tsx'
import TaskResultCard from './TaskResultCard.tsx'

// Identifiant du faux prédicteur dans le contrat de l'API (C13).
const DEMO_MODEL_ID = 'demo'

// Résultat d'une tâche, ou null tant que l'analyse tourne (l'API renvoie alors results: null).
function findResult(analysis: Analysis, task: AnalysisTask): TaskResult | null {
  if (analysis.results === null) {
    return null
  }
  const result = analysis.results[task]
  return result ?? null
}

// Vrai si au moins une tâche a été calculée par le faux prédicteur.
function hasDemoResult(analysis: Analysis): boolean {
  for (const task of analysis.tasks) {
    const result = findResult(analysis, task)
    if (result !== null && result.model_id === DEMO_MODEL_ID) {
      return true
    }
  }
  return false
}

// Une carte par tâche demandée, dans l'ordre de la demande ; les autres n'apparaissent pas.
// Deux colonnes sur grand écran, une seule sur téléphone.
export default function TaskResultList({ analysis }: { analysis: Analysis }) {
  const isDemo = hasDemoResult(analysis)
  return (
    <div className="space-y-4">
      {isDemo && <DemoNotice />}
      <div className="grid items-start gap-4 md:grid-cols-2">
        {analysis.tasks.map((task) => (
          <TaskResultCard key={task} task={task} result={findResult(analysis, task)} />
        ))}
      </div>
    </div>
  )
}
