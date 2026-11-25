import type { LatencyRow } from '../../api/client.ts'
import { TASK_LABELS } from '../../labels.ts'
import { formatMilliseconds, formatParameters, formatRtf } from './compareFormat.ts'
import { formatScore } from '../models/modelFormat.ts'

const HEADER_CLASSES = 'px-4 py-3 text-left text-xs font-medium whitespace-nowrap text-ink-soft'
const CELL_CLASSES = 'px-4 py-3 align-top'
const NUMBER_CLASSES = `${CELL_CLASSES} font-mono whitespace-nowrap`

// Profil où le modèle est utilisé : temps réel (micro) ou qualité (fichiers).
function profileText(row: LatencyRow): string {
  if (row.realtime) {
    return 'Temps réel'
  }
  return 'Qualité'
}

// Une ligne par modèle de production.
function LatencyTableRow({ row }: { row: LatencyRow }) {
  return (
    <tr className="border-t border-rule">
      <td className={`${CELL_CLASSES} font-mono whitespace-nowrap`}>{row.model}</td>
      <td className={CELL_CLASSES}>{TASK_LABELS[row.task]}</td>
      <td className={CELL_CLASSES}>{profileText(row)}</td>
      <td className={NUMBER_CLASSES}>{formatScore(row.f1_macro)}</td>
      <td className={NUMBER_CLASSES}>{formatParameters(row.parameters)}</td>
      <td className={NUMBER_CLASSES}>{formatMilliseconds(row.p95_2s)}</td>
      <td className={NUMBER_CLASSES}>{formatRtf(row.rtf_p95_2s)}</td>
      <td className={NUMBER_CLASSES}>{formatMilliseconds(row.p95_5s)}</td>
    </tr>
  )
}

// Taille et vitesse sur CPU (E6) : le profil temps réel exige un RTF nettement inférieur à 1.
export default function LatencyTable({ rows }: { rows: LatencyRow[] }) {
  return (
    <div className="overflow-x-auto rounded-card border border-rule bg-card">
      <table className="w-full min-w-[60rem] text-sm">
        <thead>
          <tr>
            <th className={HEADER_CLASSES}>Modèle</th>
            <th className={HEADER_CLASSES}>Tâche</th>
            <th className={HEADER_CLASSES}>Profil</th>
            <th className={HEADER_CLASSES}>F1 test</th>
            <th className={HEADER_CLASSES}>Paramètres</th>
            <th className={HEADER_CLASSES}>Latence p95, 2 s</th>
            <th className={HEADER_CLASSES}>RTF p95, 2 s</th>
            <th className={HEADER_CLASSES}>Latence p95, 5 s</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <LatencyTableRow key={row.model} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
