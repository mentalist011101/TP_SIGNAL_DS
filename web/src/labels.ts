import type { AnalysisProfile, AnalysisStatusValue, AnalysisTask } from './api/client.ts'

// Libellés français des valeurs renvoyées par l'API, partagés par toutes les pages.

export const STATUS_LABELS: Record<AnalysisStatusValue, string> = {
  pending: 'En attente',
  processing: 'En cours',
  done: 'Terminée',
  failed: 'Échec',
}

export const TASK_LABELS: Record<AnalysisTask, string> = {
  emotion: 'Émotion',
  sound_event: 'Événement sonore',
  transcription: 'Transcription',
  speaker: 'Locuteur',
}

export const PROFILE_LABELS: Record<AnalysisProfile, string> = {
  quality: 'Qualité',
  realtime: 'Temps réel',
}
