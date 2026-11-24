import type { ModelInfo } from '../../api/client.ts'

// Mise en forme des valeurs du registre pour la page Modèles et la page Résultat.

// « 0,830 » : un F1 ou une accuracy de test, au millième, au format français ; tiret si
// non mesuré.
export function formatScore(score: number | null): string {
  if (score === null) {
    return '—'
  }
  return score.toLocaleString('fr-FR', { minimumFractionDigits: 3, maximumFractionDigits: 3 })
}

// « T = 1,461 » si le modèle est calibré, sinon « non calibré ».
export function formatCalibration(model: ModelInfo): string {
  if (model.temperature === null) {
    return 'non calibré'
  }
  const value = model.temperature.toLocaleString('fr-FR', { maximumFractionDigits: 3 })
  return `T = ${value}`
}

// Modèle du catalogue qui porte cet identifiant, ou null (faux prédicteur, modèle retiré).
export function findModel(models: ModelInfo[], modelId: string | null): ModelInfo | null {
  for (const model of models) {
    if (model.id === modelId) {
      return model
    }
  }
  return null
}
