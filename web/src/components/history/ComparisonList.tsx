import { useState } from 'react'
import { Link } from 'react-router-dom'
import {
  describeApiError,
  useComparisons,
  useDeleteComparison,
  type ComparisonSummary,
} from '../../api/client.ts'
import { STATUS_LABELS, TASK_LABELS } from '../../labels.ts'
import { formatSeconds } from '../result/timeline.ts'

// Comparaisons de modèles passées (EF-15), sous les analyses de l'Historique : rouvrir ou
// supprimer (l'audio de la comparaison est effacé avec elle).

const BUTTON_CLASSES =
  'rounded-btn border border-rule-strong bg-card px-3 py-1 text-sm text-ink transition-colors duration-200 ease-out-soft hover:bg-paper-alt disabled:opacity-50'
const MESSAGE_CLASSES =
  'rounded-card border border-dashed border-rule-strong bg-card p-6 text-center text-ink-soft'

// « 27 nov. 2026, 14:05 » : date et heure de la comparaison.
function formatDate(isoDate: string): string {
  const date = new Date(isoDate)
  return date.toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
}

// Suppression en deux temps, comme pour une analyse.
function DeleteComparison({ comparison }: { comparison: ComparisonSummary }) {
  const [isConfirming, setIsConfirming] = useState(false)
  const deletion = useDeleteComparison()
  if (!isConfirming) {
    return (
      <button type="button" className={BUTTON_CLASSES} onClick={() => setIsConfirming(true)}>
        Supprimer
      </button>
    )
  }
  return (
    <div className="space-y-1">
      <p className="text-sm">Supprimer cette comparaison ?</p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={`${BUTTON_CLASSES} font-semibold`}
          disabled={deletion.isPending}
          onClick={() => deletion.mutate(comparison.id)}
        >
          Oui, supprimer
        </button>
        <button
          type="button"
          className={BUTTON_CLASSES}
          disabled={deletion.isPending}
          onClick={() => setIsConfirming(false)}
        >
          Annuler
        </button>
      </div>
      {deletion.error !== null && (
        <p className="text-sm text-danger">{describeApiError(deletion.error)}</p>
      )}
    </div>
  )
}

// Une ligne : fichier (lien vers la comparaison), tâches, durée, statut, date.
function ComparisonItem({ comparison }: { comparison: ComparisonSummary }) {
  const tasks = comparison.tasks.map((task) => TASK_LABELS[task]).join(', ')
  let duration = ''
  if (comparison.duration_s !== null) {
    duration = ` · ${formatSeconds(comparison.duration_s)}`
  }
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 rounded-card border border-rule bg-card p-4">
      <div className="min-w-0 space-y-1">
        <Link
          to={`/comparer/${comparison.id}`}
          className="font-semibold break-all text-accent-ink hover:underline"
        >
          {comparison.original_filename}
        </Link>
        <p className="text-sm text-ink-soft">
          {tasks}
          {duration} · {STATUS_LABELS[comparison.status]} · {formatDate(comparison.created_at)}
        </p>
      </div>
      <DeleteComparison comparison={comparison} />
    </li>
  )
}

export default function ComparisonList() {
  const comparisons = useComparisons()
  let content = <p className="text-sm text-ink-soft">Chargement des comparaisons…</p>
  if (comparisons.error !== null) {
    content = <p className="text-sm text-danger">{describeApiError(comparisons.error)}</p>
  }
  if (comparisons.data !== undefined && comparisons.data.length === 0) {
    content = (
      <p className={MESSAGE_CLASSES}>
        Aucune comparaison pour l’instant.{' '}
        <Link to="/comparer" className="font-semibold text-accent-ink underline underline-offset-4">
          Comparer les modèles sur un audio
        </Link>
      </p>
    )
  }
  if (comparisons.data !== undefined && comparisons.data.length > 0) {
    content = (
      <ul className="space-y-3">
        {comparisons.data.map((comparison) => (
          <ComparisonItem key={comparison.id} comparison={comparison} />
        ))}
      </ul>
    )
  }
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">Comparaisons de modèles</h2>
      {content}
    </section>
  )
}
