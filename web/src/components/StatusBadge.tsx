import type { AnalysisStatusValue } from '../api/client.ts'
import { STATUS_LABELS } from '../labels.ts'

const BADGE_CLASSES =
  'inline-flex items-center gap-1.5 rounded-btn border px-2 py-0.5 text-xs font-semibold whitespace-nowrap'

// Couleur du point : rouge seulement pour un échec (danger = erreurs) ; il pulse tant que
// l'analyse tourne.
const DOT_CLASSES: Record<AnalysisStatusValue, string> = {
  pending: 'bg-ink-soft motion-safe:animate-pulse',
  processing: 'bg-ink-soft motion-safe:animate-pulse',
  done: 'bg-ink',
  failed: 'bg-danger',
}

// Pastille de statut d'une analyse : un point et le libellé en français.
export default function StatusBadge({ status }: { status: AnalysisStatusValue }) {
  const label = STATUS_LABELS[status]
  let colorClasses = 'border-rule-strong text-ink'
  if (status === 'failed') {
    colorClasses = 'border-danger text-danger'
  }
  return (
    <span className={`${BADGE_CLASSES} ${colorClasses}`}>
      <span className={`h-2 w-2 rounded-full ${DOT_CLASSES[status]}`} aria-hidden="true" />
      {label}
    </span>
  )
}
