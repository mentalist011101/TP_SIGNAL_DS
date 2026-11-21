import type { CSSProperties } from 'react'
import type { ClassProbability } from '../../api/client.ts'
import { formatProbability } from './taskResult.ts'

// Une ligne : libellé, barre, pourcentage. La largeur des deux colonnes de texte est fixe pour que
// toutes les barres commencent et finissent au même endroit.
const ROW_CLASSES =
  'grid grid-cols-[minmax(0,10rem)_minmax(0,1fr)_3.5rem] items-center gap-3 text-sm'

// Longueur de la barre : la probabilité en pourcentage de la largeur disponible.
function barStyle(probability: number): CSSProperties {
  const percent = probability * 100
  return { width: `${percent}%` }
}

// Une classe et sa probabilité. La barre n'est qu'une aide visuelle : le pourcentage est
// toujours écrit en texte, et c'est lui que lisent les lecteurs d'écran.
function ProbabilityRow({ item, isTop }: { item: ClassProbability; isTop: boolean }) {
  const percentText = formatProbability(item.probability)
  let barColor = 'bg-ink-faint'
  if (isTop) {
    barColor = 'bg-ink'
  }
  return (
    <li className={ROW_CLASSES}>
      <span className="break-words">{item.label_fr}</span>
      <span className="h-2.5 rounded-btn bg-paper-alt" aria-hidden="true">
        <span
          className={`block h-full rounded-btn ${barColor}`}
          style={barStyle(item.probability)}
        />
      </span>
      <span className="text-right font-mono text-ink-soft">{percentText}</span>
    </li>
  )
}

// Probabilités en barres horizontales, dans l'ordre reçu de l'API (la plus probable d'abord,
// d'où sa barre en encre ; les autres en gris).
export default function ProbabilityBars({ probabilities }: { probabilities: ClassProbability[] }) {
  return (
    <ul className="space-y-1.5">
      {probabilities.map((item, index) => (
        <ProbabilityRow key={item.label} item={item} isTop={index === 0} />
      ))}
    </ul>
  )
}
