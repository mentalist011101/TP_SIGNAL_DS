import { API_BASE, type Analysis, type ModelInfo } from '../../api/client.ts'
import { findModel } from '../models/modelFormat.ts'

// Carte Grad-CAM (C14, E7, EF-13) : seulement pour les réseaux de la famille A (les CRNN du
// profil Temps réel), qui lisent le spectrogramme. Les têtes Whisper du profil Qualité n'en ont
// pas : on le dit plutôt que d'expliquer un autre modèle que celui du résultat.

export type GradCamTask = 'sound_event' | 'emotion'

const GRAD_CAM_TASKS: GradCamTask[] = ['sound_event', 'emotion']
const FAMILY_A = 'A'

// Tâches dont la carte existe : résultat calculé par un modèle de la famille A du catalogue.
export function gradCamTasks(analysis: Analysis, models: ModelInfo[]): GradCamTask[] {
  const available: GradCamTask[] = []
  if (analysis.results === null) {
    return available
  }
  for (const task of GRAD_CAM_TASKS) {
    const result = analysis.results[task]
    if (result === undefined || result.status !== 'done') {
      continue
    }
    const model = findModel(models, result.model_id)
    if (model !== null && model.family === FAMILY_A) {
      available.push(task)
    }
  }
  return available
}

// Vrai si l'analyse, faite en profil Qualité, a une émotion ou un événement calculé : la page
// explique alors pourquoi il n'y a pas de carte.
export function needsRealtimeNote(analysis: Analysis): boolean {
  if (analysis.profile !== 'quality' || analysis.results === null) {
    return false
  }
  for (const task of GRAD_CAM_TASKS) {
    const result = analysis.results[task]
    if (result !== undefined && result.status === 'done') {
      return true
    }
  }
  return false
}

// Adresse de l'image de la carte, de la taille du spectrogramme (calculée à la première demande).
export function gradCamUrl(analysisId: string, task: GradCamTask): string {
  return `${API_BASE}/analyses/${analysisId}/gradcam?task=${task}`
}
