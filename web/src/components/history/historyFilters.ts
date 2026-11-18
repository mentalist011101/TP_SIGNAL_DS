import { isAnalysisRunning, type Analysis } from '../../api/client.ts'

// Filtre par statut : « en cours » regroupe pending et processing, que l'utilisateur ne
// distingue pas.
export type StatusFilter = 'all' | 'done' | 'running' | 'failed'

// Filtre par date de création, compté depuis maintenant.
export type DateFilter = 'all' | 'today' | 'week' | 'month'

export interface HistoryFilterValues {
  status: StatusFilter
  date: DateFilter
}

const MS_PER_DAY = 24 * 60 * 60 * 1000
const WEEK_DAYS = 7
const MONTH_DAYS = 30

// Vrai si le statut de l'analyse correspond au filtre choisi.
function matchesStatus(analysis: Analysis, filter: StatusFilter): boolean {
  if (filter === 'all') {
    return true
  }
  if (filter === 'running') {
    return isAnalysisRunning(analysis)
  }
  return analysis.status === filter
}

// Début de la période du filtre : minuit aujourd'hui, ou il y a 7 ou 30 jours.
function periodStart(filter: DateFilter, now: Date): Date {
  if (filter === 'today') {
    const midnight = new Date(now)
    midnight.setHours(0, 0, 0, 0)
    return midnight
  }
  let days = MONTH_DAYS
  if (filter === 'week') {
    days = WEEK_DAYS
  }
  const startTime = now.getTime() - days * MS_PER_DAY
  return new Date(startTime)
}

// Vrai si l'analyse a été créée dans la période choisie.
function matchesDate(analysis: Analysis, filter: DateFilter, now: Date): boolean {
  if (filter === 'all') {
    return true
  }
  const createdAt = new Date(analysis.created_at)
  const start = periodStart(filter, now)
  return createdAt >= start
}

// Garde les analyses qui passent les deux filtres, dans l'ordre reçu (les plus récentes d'abord).
export function filterAnalyses(
  analyses: Analysis[],
  filters: HistoryFilterValues,
  now: Date,
): Analysis[] {
  const kept: Analysis[] = []
  for (const analysis of analyses) {
    const statusOk = matchesStatus(analysis, filters.status)
    const dateOk = matchesDate(analysis, filters.date, now)
    if (statusOk && dateOk) {
      kept.push(analysis)
    }
  }
  return kept
}
