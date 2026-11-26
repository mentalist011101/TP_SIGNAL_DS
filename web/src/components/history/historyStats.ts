import type { AnalysisSummary } from '../../api/client.ts'

// Chiffres clés de l'historique. Ce ne sont que des comptes et des sommes sur la liste
// renvoyée par l'API : aucun calcul sur le signal (R5).
export interface HistoryStats {
  analysisCount: number
  doneCount: number
  failedCount: number
  analysedSeconds: number
  lastWeekCount: number
}

const MS_PER_DAY = 24 * 60 * 60 * 1000
const WEEK_DAYS = 7

// Nombre d'analyses qui ont un statut donné.
function countWithStatus(analyses: AnalysisSummary[], status: AnalysisSummary['status']): number {
  let count = 0
  for (const analysis of analyses) {
    if (analysis.status === status) {
      count += 1
    }
  }
  return count
}

// Durée totale des audios dont l'analyse est terminée, en secondes.
function totalAnalysedSeconds(analyses: AnalysisSummary[]): number {
  let total = 0
  for (const analysis of analyses) {
    if (analysis.status === 'done' && analysis.duration_s !== null) {
      total += analysis.duration_s
    }
  }
  return total
}

// Nombre d'analyses créées pendant les 7 derniers jours.
function countLastWeek(analyses: AnalysisSummary[], now: Date): number {
  const weekStart = now.getTime() - WEEK_DAYS * MS_PER_DAY
  let count = 0
  for (const analysis of analyses) {
    const createdAt = new Date(analysis.created_at).getTime()
    if (createdAt >= weekStart) {
      count += 1
    }
  }
  return count
}

// Tous les chiffres clés de l'historique chargé.
export function computeHistoryStats(analyses: AnalysisSummary[], now: Date): HistoryStats {
  return {
    analysisCount: analyses.length,
    doneCount: countWithStatus(analyses, 'done'),
    failedCount: countWithStatus(analyses, 'failed'),
    analysedSeconds: totalAnalysedSeconds(analyses),
    lastWeekCount: countLastWeek(analyses, now),
  }
}
