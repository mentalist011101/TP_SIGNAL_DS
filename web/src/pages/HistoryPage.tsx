import { useState } from 'react'
import { Link } from 'react-router-dom'
import { describeApiError, useAnalysisHistory, type AnalysisSummary } from '../api/client.ts'
import ComparisonList from '../components/history/ComparisonList.tsx'
import HistoryFilters from '../components/history/HistoryFilters.tsx'
import HistoryList from '../components/history/HistoryList.tsx'
import HistoryOverview from '../components/history/HistoryOverview.tsx'
import { filterAnalyses, type HistoryFilterValues } from '../components/history/historyFilters.ts'
import { computeHistoryStats } from '../components/history/historyStats.ts'

// Filtres à l'ouverture de la page : tout afficher.
const DEFAULT_FILTERS: HistoryFilterValues = { status: 'all', date: 'all', query: '' }

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
      <Link to="/analyser" className="font-semibold text-accent-ink underline underline-offset-4">
        Analyser un premier audio
      </Link>
    </p>
  )
}

interface HistoryContentProps {
  analyses: AnalysisSummary[]
  filters: HistoryFilterValues
  onFiltersChange: (filters: HistoryFilterValues) => void
  loadedAt: number
}

// Chiffres clés, puis filtres et liste. Les périodes (aujourd'hui, 7 jours…) et la
// série de jours sont comptées depuis le chargement de la liste, pas depuis chaque affichage :
// le résultat reste le même tant que la liste ne change pas.
function HistoryContent({ analyses, filters, onFiltersChange, loadedAt }: HistoryContentProps) {
  const now = new Date(loadedAt)
  const stats = computeHistoryStats(analyses, now)
  const visible = filterAnalyses(analyses, filters, now)
  return (
    <>
      <HistoryOverview stats={stats} />
      <section className="space-y-3">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="text-base font-semibold">Analyses</h2>
          <p className="font-mono text-sm text-ink-soft">
            {visible.length} / {analyses.length}
          </p>
        </div>
        <HistoryFilters filters={filters} onFiltersChange={onFiltersChange} />
        {visible.length === 0 && <EmptyHistory hasAnalyses={analyses.length > 0} />}
        {visible.length > 0 && <HistoryList analyses={visible} />}
      </section>
    </>
  )
}

// Page Historique (C22, EF-08) : chiffres clés, puis les analyses passées, filtrables,
// à rouvrir ou à supprimer.
export default function HistoryPage() {
  const [filters, setFilters] = useState<HistoryFilterValues>(DEFAULT_FILTERS)
  const history = useAnalysisHistory()

  let content = <p className="text-sm text-ink-soft">Chargement de l’historique…</p>
  if (history.error !== null) {
    content = <p className="text-sm text-danger">{describeApiError(history.error)}</p>
  }
  if (history.data !== undefined) {
    content = (
      <HistoryContent
        analyses={history.data}
        filters={filters}
        onFiltersChange={setFilters}
        loadedAt={history.dataUpdatedAt}
      />
    )
  }

  return (
    <section className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-5xl leading-tight">Historique</h1>
        <p className="text-ink-soft">
          Vos 100 analyses les plus récentes : rouvrez un résultat, filtrez ou supprimez. Les
          comparaisons de modèles sont listées à la suite.
        </p>
      </div>
      {content}
      <ComparisonList />
    </section>
  )
}
