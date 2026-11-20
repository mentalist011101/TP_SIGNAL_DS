import type { Analysis, AnalysisTask, TaskResult } from '../../api/client.ts'
import TaskResultCard from './TaskResultCard.tsx'

// Résultat d'une tâche, ou null tant que l'analyse tourne (l'API renvoie alors results: null).
function findResult(analysis: Analysis, task: AnalysisTask): TaskResult | null {
  if (analysis.results === null) {
    return null
  }
  const result = analysis.results[task]
  return result ?? null
}

// Une carte par tâche demandée, dans l'ordre de la demande ; les autres n'apparaissent pas.
// Deux colonnes sur grand écran, une seule sur téléphone.
export default function TaskResultList({ analysis }: { analysis: Analysis }) {
  return (
    <div className="grid items-start gap-4 md:grid-cols-2">
      {analysis.tasks.map((task) => (
        <TaskResultCard key={task} task={task} result={findResult(analysis, task)} />
      ))}
    </div>
  )
}
