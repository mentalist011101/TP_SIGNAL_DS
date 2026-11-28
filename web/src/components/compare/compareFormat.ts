import type { ComparedTask, ModelRun } from '../../api/client.ts'

// Mise en forme de la comparaison de modèles (EF-15). Rien n'est recalculé sur le signal
// (R5) : on compare des libellés et on divise deux durées renvoyées par l'API.

// Ordre et libellés des tâches comparables, comme sur la page Analyser.
export const COMPARED_TASKS: { value: ComparedTask; label: string; detail: string }[] = [
  { value: 'emotion', label: 'Émotions', detail: 'Tête Whisper contre CRNN' },
  { value: 'sound_event', label: 'Événements sonores', detail: 'Tête Whisper contre CRNN' },
  { value: 'transcription', label: 'Transcription', detail: 'Whisper small contre base' },
]

// « 1,24 s » : un temps de calcul, deux décimales.
export function formatComputeTime(seconds: number): string {
  const formatted = seconds.toLocaleString('fr-FR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  return `${formatted} s`
}

// Facteur temps réel (RTF) : temps de calcul / durée de l'audio. Sous 1, le modèle va plus
// vite que le son. null si la durée est inconnue.
export function realTimeFactor(computeS: number, durationS: number | null): string | null {
  if (durationS === null || durationS <= 0) {
    return null
  }
  const factor = computeS / durationS
  return factor.toLocaleString('fr-FR', { maximumFractionDigits: 3 })
}

// Verdict sur le résultat principal des modèles d'une tâche, ou null s'il n'y a pas au moins
// deux résultats calculés à comparer (transcription : pas de classe principale).
export function agreementText(runs: ModelRun[]): string | null {
  const labels: string[] = []
  for (const run of runs) {
    if (run.result.status === 'done' && run.result.label_fr !== null) {
      labels.push(run.result.label_fr)
    }
  }
  if (labels.length < 2) {
    return null
  }
  const distinct = new Set(labels)
  if (distinct.size === 1) {
    return `Les ${labels.length} modèles donnent le même résultat principal : ${labels[0]}.`
  }
  return `Désaccord sur le résultat principal : ${labels.join(' / ')}.`
}
