import type { TranscriptionScore } from '../../api/client.ts'
import { formatRate, formatRtf } from './compareFormat.ts'

const HEADER_CLASSES = 'px-4 py-3 text-left text-xs font-medium text-ink-soft'
const CELL_CLASSES = 'px-4 py-3 align-top'
const NUMBER_CLASSES = `${CELL_CLASSES} font-mono whitespace-nowrap`

// « 23,5 % – 32 % » : intervalle de confiance du WER (bootstrap par locuteur).
function intervalText(interval: number[]): string {
  const low = formatRate(interval[0])
  const high = formatRate(interval[1])
  return `${low} – ${high}`
}

// Une ligne : un modèle Whisper sur un corpus.
function TranscriptionRow({ row }: { row: TranscriptionScore }) {
  return (
    <tr className="border-t border-rule">
      <td className={CELL_CLASSES}>{row.model}</td>
      <td className={CELL_CLASSES}>{row.corpus}</td>
      <td className={NUMBER_CLASSES}>{formatRate(row.wer)}</td>
      <td className={NUMBER_CLASSES}>{intervalText(row.wer_ci)}</td>
      <td className={NUMBER_CLASSES}>{formatRate(row.cer)}</td>
      <td className={NUMBER_CLASSES}>{formatRtf(row.rtf_cpu)}</td>
    </tr>
  )
}

// Transcription (C17) : taux d'erreur par mot et par caractère ; plus bas, c'est mieux.
export default function TranscriptionTable({ rows }: { rows: TranscriptionScore[] }) {
  return (
    <div className="overflow-x-auto rounded-card border border-rule bg-card">
      <table className="w-full min-w-[44rem] text-sm">
        <thead>
          <tr>
            <th className={HEADER_CLASSES}>Modèle</th>
            <th className={HEADER_CLASSES}>Corpus</th>
            <th className={HEADER_CLASSES}>WER</th>
            <th className={HEADER_CLASSES}>IC 95 % du WER</th>
            <th className={HEADER_CLASSES}>CER</th>
            <th className={HEADER_CLASSES}>RTF sur CPU</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <TranscriptionRow key={`${row.model}-${row.corpus}`} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
