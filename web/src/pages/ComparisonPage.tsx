import { Link, useParams } from 'react-router-dom'
import { describeApiError, useComparison, type Comparison } from '../api/client.ts'
import ComparisonView from '../components/compare/ComparisonView.tsx'
import { formatSeconds } from '../components/result/timeline.ts'
import { TASK_LABELS } from '../labels.ts'

// Page d'une comparaison (EF-15) : suit le calcul, puis montre chaque modèle côte à côte, avec
// l'audio pour réécouter. Ouverte depuis la page Comparer ou depuis l'Historique.

// En-tête : nom du fichier, durée, tâches comparées, et le lecteur une fois l'audio prêt.
function ComparisonHeader({ comparison }: { comparison: Comparison }) {
  const tasks = comparison.tasks.map((task) => TASK_LABELS[task]).join(', ')
  return (
    <div className="space-y-3">
      <p className="font-mono text-xs text-ink-faint">
        <Link to="/historique" className="hover:underline">
          Historique
        </Link>{' '}
        / Comparaison
      </p>
      <h1 className="text-4xl leading-tight break-all">{comparison.original_filename}</h1>
      <p className="text-sm text-ink-soft">
        {tasks}
        {comparison.duration_s !== null && ` · ${formatSeconds(comparison.duration_s)}`}
      </p>
      {comparison.audio_url !== null && (
        <audio controls src={comparison.audio_url} className="w-full max-w-xl" />
      )}
    </div>
  )
}

// Corps selon le statut : calcul en cours, échec avec sa raison, ou les résultats.
function ComparisonBody({ comparison }: { comparison: Comparison }) {
  if (comparison.status === 'failed') {
    return <p className="text-sm text-danger">{comparison.error_message}</p>
  }
  if (comparison.status !== 'done') {
    return (
      <p className="text-sm text-ink-soft" aria-live="polite">
        Chaque modèle tourne à son tour sur le fichier… La transcription peut prendre plus d’une
        minute.
      </p>
    )
  }
  return <ComparisonView comparison={comparison} />
}

export default function ComparisonPage() {
  const { comparisonId } = useParams()
  const query = useComparison(comparisonId ?? null)
  if (query.error !== null) {
    return <p className="text-sm text-danger">{describeApiError(query.error)}</p>
  }
  if (query.data === undefined) {
    return <p className="text-sm text-ink-soft">Chargement de la comparaison…</p>
  }
  return (
    <section className="space-y-8">
      <ComparisonHeader comparison={query.data} />
      <ComparisonBody comparison={query.data} />
    </section>
  )
}
