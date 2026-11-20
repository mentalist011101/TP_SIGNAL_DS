// Plus petite probabilité affichée en chiffres (0,1 %) : en dessous, l'arrondi donnerait
// « 0 % », ce qui laisserait croire que la classe est impossible.
const SMALLEST_SHOWN_PROBABILITY = 0.001

// « 58 % », « 0,4 % », « < 0,1 % » : probabilité (entre 0 et 1) en pourcentage à la
// française, une décimale au plus.
export function formatPercent(probability: number): string {
  if (probability < SMALLEST_SHOWN_PROBABILITY) {
    return '< 0,1 %'
  }
  const percent = probability * 100
  const formatted = percent.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
  return `${formatted} %`
}
