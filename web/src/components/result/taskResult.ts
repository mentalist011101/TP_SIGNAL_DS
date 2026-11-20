// « 62 % », « 0,5 % » : format français, une décimale au plus.
export function formatProbability(probability: number): string {
  return probability.toLocaleString('fr-FR', { style: 'percent', maximumFractionDigits: 1 })
}
