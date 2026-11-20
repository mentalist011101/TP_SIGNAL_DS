import type { TaskResult } from '../../api/client.ts'

// « 62 % », « 0,5 % » : format français, une décimale au plus.
export function formatProbability(probability: number): string {
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
