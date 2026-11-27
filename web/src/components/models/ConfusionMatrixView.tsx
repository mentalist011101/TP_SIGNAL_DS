import type { CSSProperties } from 'react'
import type { ConfusionMatrix } from '../../api/client.ts'
import { formatProbability } from '../result/taskResult.ts'

// Matrice de confusion (EF-16) en carte de chaleur : une ligne par vraie classe, une colonne par
// classe prédite ; la case (i, j) est la part des extraits de la classe i prédits j. Plus la
// case est foncée, plus la part est grande ; le pourcentage est toujours écrit, la couleur ne
// porte jamais seule l'information. La diagonale, ce qui est bien reconnu, est encadrée.

// Opacité du fond : la part elle-même, avec un plancher pour qu'une petite erreur reste visible.
const MIN_VISIBLE_OPACITY = 0.06

function cellStyle(value: number): CSSProperties {
  if (value === 0) {
    return { opacity: 0 }
  }
  return { opacity: Math.max(value, MIN_VISIBLE_OPACITY) }
}

// Texte lisible sur une case foncée : encre claire au-dessus de la moitié.
function textClass(value: number): string {
  if (value >= 0.5) {
    return 'text-paper'
  }
  return 'text-ink'
}

interface CellProps {
  value: number
  isDiagonal: boolean
  rowLabel: string
  columnLabel: string
}

function MatrixCell({ value, isDiagonal, rowLabel, columnLabel }: CellProps) {
  const percent = formatProbability(value)
  let border = 'border-rule'
  if (isDiagonal) {
    border = 'border-ink'
  }
  return (
    <td
      className={`relative h-10 min-w-14 border ${border} p-0 text-center font-mono text-xs`}
      title={`Vraie classe ${rowLabel}, prédite ${columnLabel} : ${percent}`}
    >
      <span className="absolute inset-0 bg-ink" style={cellStyle(value)} aria-hidden="true" />
      <span className={`relative ${textClass(value)}`}>{percent}</span>
    </td>
  )
}

export default function ConfusionMatrixView({ confusion }: { confusion: ConfusionMatrix }) {
  return (
    <div className="overflow-x-auto">
      <table className="border-collapse text-sm">
        <caption className="mb-2 text-left text-xs text-ink-soft">
          Lignes : vraie classe. Colonnes : classe prédite. Chaque ligne somme à 100 %.
        </caption>
        <thead>
          <tr>
            <th className="p-1" />
            {confusion.labels.map((label) => (
              <th
                key={label}
                scope="col"
                className="max-w-24 p-1 text-left align-bottom text-xs font-medium text-ink-soft"
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {confusion.matrix.map((row, rowIndex) => (
            <tr key={confusion.labels[rowIndex]}>
              <th scope="row" className="pr-3 text-right text-xs font-medium whitespace-nowrap">
                {confusion.labels[rowIndex]}
              </th>
              {row.map((value, columnIndex) => (
                <MatrixCell
                  key={confusion.labels[columnIndex]}
                  value={value}
                  isDiagonal={rowIndex === columnIndex}
                  rowLabel={confusion.labels[rowIndex]}
                  columnLabel={confusion.labels[columnIndex]}
                />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
