import { useState } from 'react'
import type { ClassProbability, TaskResult } from '../../api/client.ts'
import { formatPercent } from './format.ts'
import ProbabilityChart from './ProbabilityChart.tsx'

const CARD_CLASSES = 'space-y-3 rounded-card border border-rule bg-card p-5 shadow-card'
const TOGGLE_CLASSES = 'text-sm font-semibold text-accent-ink hover:underline'

// Identifiant du faux prédicteur de C13 : ses probabilités ne veulent rien dire.
const DEMO_MODEL_ID = 'demo'

interface TaskResultCardProps {
  title: string
  result: TaskResult
  // Nombre de classes affichées d'abord (5 pour les 50 événements) ; null = toutes.
  initialCount: number | null
}

// « Modèle : demo 0 · probabilités non calibrées » : traçabilité du résultat (ENF-06).
function modelLine(result: TaskResult): string {
  const name = `${result.model_id} ${result.model_version}`
  if (result.calibrated === true) {
    return `Modèle : ${name} · probabilités calibrées`
  }
  return `Modèle : ${name} · probabilités non calibrées`
}

// Les premières classes seulement, ou toutes si on a cliqué sur « Voir tout ».
function visibleProbabilities(
  probabilities: ClassProbability[],
  initialCount: number | null,
  showAll: boolean,
): ClassProbability[] {
  if (initialCount === null || showAll) {
    return probabilities
  }
  return probabilities.slice(0, initialCount)
}

// Résultat calculé : classe la plus probable, barres, bouton « Voir tout » et modèle utilisé.
function DoneResult({ result, initialCount }: { result: TaskResult; initialCount: number | null }) {
  const [showAll, setShowAll] = useState(false)
  const total = result.probabilities.length
  // Garde-fou : l'API promet au moins une classe en done, mais une liste vide ne doit pas
  // faire planter la page.
  if (total === 0) {
    return <p className="text-ink-faint">Aucune probabilité renvoyée pour cette tâche.</p>
  }
  const shown = visibleProbabilities(result.probabilities, initialCount, showAll)
  const topProbability = result.probabilities[0].probability
  const canExpand = shown.length < total
  return (
    <>
      <p className="text-lg">
        <span className="font-semibold">{result.label_fr}</span>{' '}
        <span className="font-mono text-ink-soft">{formatPercent(topProbability)}</span>
      </p>
      <ProbabilityChart probabilities={shown} />
      {canExpand && (
        <button type="button" className={TOGGLE_CLASSES} onClick={() => setShowAll(true)}>
          Voir les {total} classes
        </button>
      )}
      <p className="text-xs text-ink-faint">{modelLine(result)}</p>
      {result.model_id === DEMO_MODEL_ID && <DemoWarning />}
    </>
  )
}

// Avertissement honnête : tant que les vrais modèles ne sont pas branchés, le serveur utilise
// un faux prédicteur, dont les chiffres ne mesurent rien.
function DemoWarning() {
  return (
    <p className="rounded-card bg-paper-alt p-2 text-xs text-ink-soft">
      Résultat de démonstration : le vrai modèle n’est pas encore branché, ces probabilités ne
      veulent rien dire.
    </p>
  )
}

// Carte d'une tâche (émotion, événement, transcription, locuteur). Si la tâche n'a pas de
// résultat (no_speech, unavailable), le message du serveur s'affiche en gris : ce n'est pas
// une erreur, donc pas de couleur danger.
export default function TaskResultCard({ title, result, initialCount }: TaskResultCardProps) {
  return (
    <div className={CARD_CLASSES}>
      <h2 className="font-display text-lg font-bold">{title}</h2>
      {result.status === 'done' && <DoneResult result={result} initialCount={initialCount} />}
      {result.status !== 'done' && <p className="text-ink-faint">{result.message}</p>}
    </div>
  )
}
