import { useState } from 'react'
import { Link } from 'react-router-dom'
import { describeApiError, useAnalysisHistory, type Analysis } from '../api/client.ts'
import HistoryFilters from '../components/history/HistoryFilters.tsx'
import HistoryTable from '../components/history/HistoryTable.tsx'
import { filterAnalyses, type HistoryFilterValues } from '../components/history/historyFilters.ts'

// Filtres à l'ouverture de la page : tout afficher.
const DEFAULT_FILTERS: HistoryFilterValues = { status: 'all', date: 'all' }

const MESSAGE_CLASSES =
  'rounded-card border border-dashed border-rule-strong bg-card p-6 text-center text-ink-soft'

// Liste vide : aucune analyse du tout, ou aucune qui passe les filtres.
function EmptyHistory({ hasAnalyses }: { hasAnalyses: boolean }) {
  if (hasAnalyses) {
    return <p className={MESSAGE_CLASSES}>Aucune analyse ne correspond à ces filtres.</p>
  }
  return (
    <p className={MESSAGE_CLASSES}>
      Aucune analyse pour l’instant.{' '}
      <Link to="/" className="font-semibold text-accent-ink hover:underline">
        Analyser un premier audio
      </Link>
    </p>
  )
}

interface HistoryListProps {
  analyses: Analysis[]
  filters: HistoryFilterValues
  loadedAt: number
}

// Applique les filtres, puis affiche le tableau ou le message de liste vide. Les périodes
// (aujourd'hui, 7 jours…) sont comptées depuis le chargement de la liste, pas depuis chaque
// affichage : le résultat reste le même tant que la liste ne change pas.
function HistoryList({ analyses, filters, loadedAt }: HistoryListProps) {
  const now = new Date(loadedAt)
  const visible = filterAnalyses(analyses, filters, now)
  if (visible.length === 0) {
    return <EmptyHistory hasAnalyses={analyses.length > 0} />
  }
  return (
    <div className="space-y-2">
      <p className="text-sm text-ink-soft">
        {visible.length} analyse(s) sur {analyses.length}
      </p>
      <HistoryTable analyses={visible} />
    </div>
  )
}

// Page Historique (C22, EF-08) : analyses passées, filtrables, à rouvrir ou à supprimer.
export default function HistoryPage() {
  const [filters, setFilters] = useState<HistoryFilterValues>(DEFAULT_FILTERS)
  const history = useAnalysisHistory()

  let content = <p className="text-sm text-ink-soft">Chargement de l’historique…</p>
  if (history.error !== null) {
    content = <p className="text-sm text-danger">{describeApiError(history.error)}</p>
  }
  if (history.data !== undefined) {
    content = (
      <HistoryList analyses={history.data} filters={filters} loadedAt={history.dataUpdatedAt} />
    )
  }

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="font-display text-3xl font-extrabold tracking-tight">Historique</h1>
        <p className="text-ink-soft">
          Les 100 analyses les plus récentes. Rouvrez-en une pour revoir son résultat.
        </p>
      </div>
      <HistoryFilters filters={filters} onFiltersChange={setFilters} />
      {content}
    </section>
  )
}
