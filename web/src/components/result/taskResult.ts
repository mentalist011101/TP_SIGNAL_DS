import type { Analysis, ClassProbability, TaskResult } from '../../api/client.ts'

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

// Règle de présentation (relecture du 21 novembre 2026, reportée dans les maquettes) : quand
// les deux classes les plus probables ont moins de 0,10 d'écart, le modèle n'a pas vraiment
// choisi. On l'écrit (« Hésite entre X et Y ») plutôt que d'annoncer un seul gagnant. Ce n'est
// pas un calcul sur le signal (R5) : on compare deux probabilités renvoyées par l'API.
const HESITATION_GAP = 0.1

// Les deux premiers choix d'un modèle qui hésite.
export interface Hesitation {
  first: ClassProbability
  second: ClassProbability
}

// Les deux premiers choix si leur écart est sous HESITATION_GAP, sinon null. La liste arrive
// triée de la plus probable à la moins probable (contrat de la PR #26).
export function findHesitation(result: TaskResult): Hesitation | null {
  if (result.probabilities.length < 2) {
    return null
  }
  const first = result.probabilities[0]
  const second = result.probabilities[1]
  const gap = first.probability - second.probability
  if (gap >= HESITATION_GAP) {
    return null
  }
  return { first, second }
}
