import type { Analysis } from '../../api/client.ts'
import { TASK_LABELS } from '../../labels.ts'
import ProbabilityBars from './ProbabilityBars.tsx'
import { findSegment, formatSeconds, type SelectedSegment } from './timeline.ts'

// Classes montrées pour une fenêtre d'événement : les 5 premières, comme sur la carte.
const EVENT_TOP_COUNT = 5

interface SegmentDetailsProps {
  analysis: Analysis
  selected: SelectedSegment | null
}

// Détail du segment choisi sur la frise : sa tâche, ses bornes, puis ses probabilités, telles
// que l'API les renvoie pour ce segment. Avant tout choix, une consigne.
export default function SegmentDetails({ analysis, selected }: SegmentDetailsProps) {
  const segment = findSegment(analysis, selected)
  if (selected === null || segment === null) {
    return (
      <p className="text-sm text-ink-soft">
        Cliquez sur un segment de la frise : la lecture part de son début et ses probabilités
        s’affichent ici.
      </p>
    )
  }
  let probabilities = segment.probabilities
  if (selected.task === 'sound_event') {
    probabilities = probabilities.slice(0, EVENT_TOP_COUNT)
  }
  const taskLabel = TASK_LABELS[selected.task]
  const start = formatSeconds(segment.start_s)
  const end = formatSeconds(segment.end_s)
  return (
    <div className="space-y-3 rounded-xl border border-rule bg-paper p-4" aria-live="polite">
      <p className="flex flex-wrap items-baseline gap-x-3">
        <span className="label-mono text-ink-faint">{taskLabel}</span>
        <span className="font-semibold">{segment.label_fr}</span>
        <span className="font-mono text-sm text-ink-soft">
          {start} – {end}
        </span>
      </p>
      <ProbabilityBars probabilities={probabilities} />
    </div>
  )
}
