import type { AnalysisTask, TaskResult } from '../../api/client.ts'
import { findHesitation, formatProbability, mainProbability } from './taskResult.ts'

interface MainResultValueProps {
  task: AnalysisTask
  result: TaskResult
  // Interligne du titre : serré dans une carte, un peu plus large dans les chiffres clés.
  leading: 'leading-none' | 'leading-tight'
}

// Résultat principal d'une tâche, en grand : la classe la plus probable et sa probabilité,
// ou « Hésite entre X et Y » avec les deux probabilités quand elles sont trop proches
// (findHesitation). Sert à la carte de la tâche et aux chiffres clés. Locuteur : des parts du
// temps de parole, pas des probabilités, donc jamais d'hésitation.
export default function MainResultValue({ task, result, leading }: MainResultValueProps) {
  let hesitation = findHesitation(result)
  if (task === 'speaker') {
    hesitation = null
  }
  if (hesitation !== null) {
    const firstPercent = formatProbability(hesitation.first.probability)
    const secondPercent = formatProbability(hesitation.second.probability)
    return (
      <p className="flex flex-wrap items-baseline gap-x-3">
        <span className={`font-display text-4xl ${leading}`}>
          Hésite entre {hesitation.first.label_fr} et {hesitation.second.label_fr}
        </span>
        <span className="font-mono text-ink-soft">
          {firstPercent} · {secondPercent}
        </span>
      </p>
    )
  }
  const probability = mainProbability(result)
  return (
    <p className="flex flex-wrap items-baseline gap-x-3">
      <span className={`font-display text-4xl ${leading}`}>{result.label_fr}</span>
      {probability !== null && (
        <span className="font-mono text-ink-soft">{formatProbability(probability)}</span>
      )}
    </p>
  )
}
