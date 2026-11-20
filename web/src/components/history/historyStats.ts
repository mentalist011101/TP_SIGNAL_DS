import type { Analysis, AnalysisTask } from '../../api/client.ts'

// Compteurs de l'historique, pour les chiffres clés et les badges. Ce ne sont que des
// comptes et des sommes sur la liste renvoyée par l'API : aucun calcul sur le signal (R5).
export interface HistoryStats {
  analysisCount: number
  doneCount: number
  failedCount: number
  analysedSeconds: number
  tasksTried: number
  recordingCount: number
  streakDays: number
}

const MS_PER_DAY = 24 * 60 * 60 * 1000

// Nom donné par la page Analyser aux enregistrements du micro (AudioPicker).
const RECORDING_PREFIX = 'enregistrement'

// Nombre d'analyses qui ont un statut donné.
function countWithStatus(analyses: Analysis[], status: Analysis['status']): number {
  let count = 0
  for (const analysis of analyses) {
    if (analysis.status === status) {
      count += 1
    }
  }
  return count
}

// Durée totale des audios dont l'analyse est terminée, en secondes.
function totalAnalysedSeconds(analyses: Analysis[]): number {
  let total = 0
  for (const analysis of analyses) {
    if (analysis.status === 'done' && analysis.duration_s !== null) {
      total += analysis.duration_s
    }
  }
  return total
}

// Nombre de tâches différentes demandées au moins une fois (4 au plus).
function countTasksTried(analyses: Analysis[]): number {
  const tried = new Set<AnalysisTask>()
  for (const analysis of analyses) {
    for (const task of analysis.tasks) {
      tried.add(task)
    }
  }
  return tried.size
}

// Nombre d'analyses faites sur un enregistrement du micro.
function countRecordings(analyses: Analysis[]): number {
  let count = 0
  for (const analysis of analyses) {
    if (analysis.original_filename.startsWith(RECORDING_PREFIX)) {
      count += 1
    }
  }
  return count
}

// « 2026-11-20 » : le jour local d'une date, pour comparer des jours et non des heures.
function dayKey(date: Date): string {
  return date.toLocaleDateString('fr-CA')
}

// Jours d'affilée avec au moins une analyse, en remontant depuis aujourd'hui. Une série qui
// s'est arrêtée hier compte encore : la journée d'aujourd'hui n'est pas finie.
function countStreakDays(analyses: Analysis[], now: Date): number {
  const activeDays = new Set<string>()
  for (const analysis of analyses) {
    activeDays.add(dayKey(new Date(analysis.created_at)))
  }
  let day = new Date(now)
  if (!activeDays.has(dayKey(day))) {
    day = new Date(day.getTime() - MS_PER_DAY)
  }
  let streak = 0
  while (activeDays.has(dayKey(day))) {
    streak += 1
    day = new Date(day.getTime() - MS_PER_DAY)
  }
  return streak
}

// Tous les compteurs de l'historique chargé.
export function computeHistoryStats(analyses: Analysis[], now: Date): HistoryStats {
  return {
    analysisCount: analyses.length,
    doneCount: countWithStatus(analyses, 'done'),
    failedCount: countWithStatus(analyses, 'failed'),
    analysedSeconds: totalAnalysedSeconds(analyses),
    tasksTried: countTasksTried(analyses),
    recordingCount: countRecordings(analyses),
    streakDays: countStreakDays(analyses, now),
  }
}
