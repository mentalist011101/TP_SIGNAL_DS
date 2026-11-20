import type { AnalysisResults, AnalysisTask } from '../../api/client.ts'
import TaskResultCard from './TaskResultCard.tsx'

interface TaskDisplay {
  task: AnalysisTask
  title: string
  // Classes affichées d'abord : toutes pour les 6 émotions, 5 pour les 50 événements.
  initialCount: number | null
}

// Ordre et titres des cartes, comme sur la maquette (docs/maquettes/analyser-et-resultat.md).
const TASK_DISPLAYS: TaskDisplay[] = [
  { task: 'emotion', title: 'Émotion', initialCount: null },
  { task: 'sound_event', title: 'Événement sonore', initialCount: 5 },
  { task: 'transcription', title: 'Transcription', initialCount: null },
  { task: 'speaker', title: 'Locuteur', initialCount: null },
]

// Une carte par tâche demandée : l'API n'envoie que celles-là, les autres sont absentes.
export default function ResultsGrid({ results }: { results: AnalysisResults }) {
  const cards = []
  for (const display of TASK_DISPLAYS) {
    const result = results[display.task]
    if (result === undefined) {
      continue
    }
    cards.push(
      <TaskResultCard
        key={display.task}
        title={display.title}
        result={result}
        initialCount={display.initialCount}
      />,
    )
  }
  return <div className="grid items-start gap-6 lg:grid-cols-2">{cards}</div>
}
