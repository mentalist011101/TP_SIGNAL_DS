import type { CSSProperties } from 'react'
import type { Analysis, AnalysisTask, SegmentResult, TaskResult } from '../../api/client.ts'

// Segment choisi sur la frise : la tâche et sa place dans la liste `segments` de l'API.
export interface SelectedSegment {
  task: AnalysisTask
  index: number
}

// Place d'un instant sur la frise, en % de la durée de l'audio. Une fenêtre d'événement peut
// finir après l'audio (un audio court est complété par du silence, D5) : on s'arrête au bout.
export function percentOfDuration(timeS: number, durationS: number): number {
  const clamped = Math.min(timeS, durationS)
  return (clamped / durationS) * 100
}

// Position et largeur d'un segment sur la frise : seulement ses bornes, telles que l'API les
// renvoie (R5).
export function segmentStyle(segment: SegmentResult, durationS: number): CSSProperties {
  const left = percentOfDuration(segment.start_s, durationS)
  const right = percentOfDuration(segment.end_s, durationS)
  return { left: `${left}%`, width: `${right - left}%` }
}

// Résultat d'une tâche s'il est calculé (done) ; null sinon (absente, no_speech, unavailable).
export function doneResult(analysis: Analysis, task: AnalysisTask): TaskResult | null {
  if (analysis.results === null) {
    return null
  }
  const result = analysis.results[task]
  if (result === undefined || result.status !== 'done') {
    return null
  }
  return result
}

// Segment choisi, retrouvé dans la réponse de l'API ; null si rien n'est choisi.
export function findSegment(
  analysis: Analysis,
  selected: SelectedSegment | null,
): SegmentResult | null {
  if (selected === null) {
    return null
  }
  const result = doneResult(analysis, selected.task)
  if (result === null) {
    return null
  }
  return result.segments[selected.index] ?? null
}

// « 5,3 s » : un instant en secondes, au format français.
export function formatSeconds(timeS: number): string {
  const formatted = timeS.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
  return `${formatted} s`
}
