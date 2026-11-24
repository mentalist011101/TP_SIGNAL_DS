import type { ClassProbability, SpectrogramInfo } from '../../api/client.ts'
import examplesJson from './examples.json'

// Exemples réels de l'accueil, figés par scripts/export-example.mjs depuis l'API d'un serveur
// lancé avec les vrais modèles : spectrogramme (public/exemple/), probabilités de la tâche
// montrée, modèles du registre. Rien n'est calculé ici (R5).

export interface HomeExample {
  slug: string
  title: string
  task: 'emotion' | 'sound_event'
  source: string
  licence: string
  duration_s: number
  created_at: string
  spectrogram: SpectrogramInfo
  result: {
    status: string
    label_fr: string
    probabilities: ClassProbability[]
    model_id: string
    model_version: string
    calibrated: boolean
  }
}

export interface HomeModel {
  id: string
  task: string
  family: string
  f1_macro: number | null
  temperature: number | null
  huggingface_url: string | null
}

export interface HomeReference {
  name: string
  task: string
  f1_macro: number
  source: string
}

interface ExamplesData {
  generated_at: string
  examples: HomeExample[]
  models: HomeModel[]
  reference: HomeReference
}

// Le JSON est écrit par le script : sa forme est celle d'ExamplesData.
const data = examplesJson as ExamplesData

export const HOME_EXAMPLES = data.examples
export const HOME_MODELS = data.models
export const HOME_REFERENCE = data.reference

// « 21 nov. 2026 » : le jour où les exemples ont été analysés.
export function frozenDate(): string {
  const date = new Date(data.examples[0].created_at)
  return date.toLocaleDateString('fr-FR', { dateStyle: 'medium' })
}

// Modèle du registre qui porte cet identifiant, ou null.
export function findHomeModel(modelId: string): HomeModel | null {
  for (const model of data.models) {
    if (model.id === modelId) {
      return model
    }
  }
  return null
}

// « 0,830 » : un F1 au millième, au format français.
export function formatF1(score: number): string {
  return score.toLocaleString('fr-FR', { minimumFractionDigits: 3, maximumFractionDigits: 3 })
}
