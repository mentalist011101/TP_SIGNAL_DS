// Mise en forme des nombres de la page Comparer, au format français.

// Plus petite p-valeur écrite en chiffres : en dessous, on écrit « < 0,001 ».
const SMALLEST_SHOWN_P_VALUE = 0.001
const MS_PER_SECOND = 1000
const MILLION = 1_000_000

// « 0,827 » : un score au millième.
function thousandths(value: number): string {
  return value.toLocaleString('fr-FR', { minimumFractionDigits: 3, maximumFractionDigits: 3 })
}

// « 0,827 ± 0,014 » : moyenne et écart-type sur les tours ou les graines.
export function formatMeanStd(mean: number, std: number): string {
  const meanText = thousandths(mean)
  const stdText = thousandths(std)
  return `${meanText} ± ${stdText}`
}

// « 0,812 – 0,844 » : intervalle de confiance à 95 % ; tiret s'il n'a pas été calculé.
export function formatInterval(interval: number[] | null): string {
  if (interval === null) {
    return '—'
  }
  const low = thousandths(interval[0])
  const high = thousandths(interval[1])
  return `${low} – ${high}`
}

// « 0,330 » ou « < 0,001 » : une p-valeur.
export function formatPValue(pValue: number): string {
  if (pValue < SMALLEST_SHOWN_P_VALUE) {
    return '< 0,001'
  }
  return thousandths(pValue)
}

// « 27,9 % » : un taux d'erreur (WER, CER).
export function formatRate(rate: number): string {
  const percent = rate * 100
  const text = percent.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
  return `${text} %`
}

// « 347 ms » : une durée en secondes, écrite en millisecondes.
export function formatMilliseconds(seconds: number): string {
  const milliseconds = Math.round(seconds * MS_PER_SECOND)
  return `${milliseconds} ms`
}

// « 20,7 M » : un nombre de paramètres, en millions.
export function formatParameters(count: number): string {
  const millions = count / MILLION
  const text = millions.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
  return `${text} M`
}

// « 0,17 » : un RTF (temps de calcul ÷ durée de l'audio), au centième.
export function formatRtf(rtf: number): string {
  return rtf.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}
