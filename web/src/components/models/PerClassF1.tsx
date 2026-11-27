import { useState } from 'react'
import type { ClassF1, ClassProbability } from '../../api/client.ts'
import ProbabilityBars from '../result/ProbabilityBars.tsx'

// F1 de test de chaque classe (EF-16), du mieux au moins bien reconnu. Avec 50 classes
// (ESC-50), on montre d'abord les 5 meilleures et les 5 moins bonnes, le reste sur demande.

const SHORT_LIST_COUNT = 5
const TOGGLE_CLASSES = 'text-sm font-semibold text-accent-ink hover:underline'

// Les barres attendent une probabilité entre 0 et 1 : le F1 en est une aussi.
function asBars(rows: ClassF1[]): ClassProbability[] {
  return rows.map((row) => ({ label: row.label, label_fr: row.label_fr, probability: row.f1 }))
}

function ShortList({ rows }: { rows: ClassF1[] }) {
  const best = rows.slice(0, SHORT_LIST_COUNT)
  const worst = rows.slice(rows.length - SHORT_LIST_COUNT)
  return (
    <div className="grid gap-6 md:grid-cols-2">
      <div className="space-y-2">
        <p className="label-mono text-ink-faint">Les mieux reconnues</p>
        <ProbabilityBars probabilities={asBars(best)} />
      </div>
      <div className="space-y-2">
        <p className="label-mono text-ink-faint">Les moins bien reconnues</p>
        <ProbabilityBars probabilities={asBars(worst)} />
      </div>
    </div>
  )
}

export default function PerClassF1({ rows }: { rows: ClassF1[] }) {
  const [showAll, setShowAll] = useState(false)
  const isLong = rows.length > 2 * SHORT_LIST_COUNT
  if (!isLong) {
    return <ProbabilityBars probabilities={asBars(rows)} />
  }
  let toggleText = `Voir les ${rows.length} classes`
  if (showAll) {
    toggleText = 'Revenir aux extrêmes'
  }
  return (
    <div className="space-y-3">
      {showAll ? <ProbabilityBars probabilities={asBars(rows)} /> : <ShortList rows={rows} />}
      <button
        type="button"
        className={TOGGLE_CLASSES}
        aria-expanded={showAll}
        onClick={() => setShowAll(!showAll)}
      >
        {toggleText}
      </button>
    </div>
  )
}
