import type { ComparedTask, Comparison, ModelRun } from '../../api/client.ts'
import { TASK_LABELS } from '../../labels.ts'
import { agreementText } from './compareFormat.ts'
import ModelRunCard from './ModelRunCard.tsx'

// Résultats d'une comparaison terminée (EF-15) : une section par tâche, les modèles côte à
// côte, et une phrase qui dit s'ils donnent le même résultat principal.

interface TaskSectionProps {
  task: ComparedTask
  runs: ModelRun[]
  durationS: number | null
}

function TaskSection({ task, runs, durationS }: TaskSectionProps) {
  const agreement = agreementText(runs)
  return (
    <section className="space-y-3">
      <div className="space-y-1">
        <h2 className="text-2xl">{TASK_LABELS[task]}</h2>
        {agreement !== null && <p className="text-sm text-ink-soft">{agreement}</p>}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        {runs.map((run) => (
          <ModelRunCard key={run.model_id} task={task} run={run} durationS={durationS} />
        ))}
      </div>
    </section>
  )
}

export default function ComparisonView({ comparison }: { comparison: Comparison }) {
  const results = comparison.results
  if (results === null) {
    return null
  }
  return (
    <div className="space-y-8">
      {comparison.tasks.map((task) => (
        <TaskSection
          key={task}
          task={task}
          runs={results[task] ?? []}
          durationS={comparison.duration_s}
        />
      ))}
    </div>
  )
}
