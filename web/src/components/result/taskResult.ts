import type { Analysis, TaskResult } from '../../api/client.ts'

// Identifiant du faux prédicteur dans le contrat de l'API (C13).
const DEMO_MODEL_ID = 'demo'

// Plus petite probabilité affichée en chiffres (0,1 %) : en dessous, l'arrondi donnerait
// « 0 % », ce qui laisserait croire que la classe est impossible. Règle de Nicole (C21).
const SMALLEST_SHOWN_PROBABILITY = 0.001

// « 62 % », « 0,5 % », « < 0,1 % » : format français, une décimale au plus.
export function formatProbability(probability: number): string {
  if (probability < SMALLEST_SHOWN_PROBABILITY) {
    return '< 0,1 %'
  }
  return probability.toLocaleString('fr-FR', { style: 'percent', maximumFractionDigits: 1 })
}

// Probabilité du résultat principal, lue dans la liste renvoyée par l'API (rien n'est recalculé).
export function mainProbability(result: TaskResult): number | null {
  for (const item of result.probabilities) {
    if (item.label === result.label) {
      return item.probability
    }
  }
  return null
}

// Vrai si ce résultat affiche des probabilités du faux prédicteur : seulement en done, car
// no_speech et unavailable n'affichent aucun chiffre.
export function isDemoResult(result: TaskResult): boolean {
  if (result.status !== 'done') {
    return false
  }
  return result.model_id === DEMO_MODEL_ID
}

// Vrai si au moins une tâche de l'analyse affiche des probabilités de démonstration.
export function hasDemoResult(analysis: Analysis): boolean {
  if (analysis.results === null) {
    return false
  }
  for (const task of analysis.tasks) {
    const result = analysis.results[task]
    if (result !== undefined && isDemoResult(result)) {
      return true
    }
  }
  return false
}
