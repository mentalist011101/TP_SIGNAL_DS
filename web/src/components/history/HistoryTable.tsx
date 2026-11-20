import { Link } from 'react-router-dom'
import type { Analysis, AnalysisTask } from '../../api/client.ts'
import { STATUS_LABELS, TASK_LABELS } from '../../labels.ts'
import DeleteControl from './DeleteControl.tsx'

const HEADER_CELL_CLASSES = 'px-3 py-2 text-left font-medium text-ink-soft'
const CELL_CLASSES = 'px-3 py-3 align-top'
const LINK_CLASSES = 'font-semibold text-accent-ink underline-offset-2 hover:underline'

// « 18/11/2026 21:27 » : date et heure locales du navigateur (l'API envoie de l'UTC).
function formatDate(isoDate: string): string {
  const date = new Date(isoDate)
  return date.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
}

// « 3,2 s », ou un tiret tant que la durée n'est pas connue.
function formatDuration(durationSeconds: number | null): string {
  if (durationSeconds === null) {
    return '—'
  }
  const formatted = durationSeconds.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
  return `${formatted} s`
}

// « Émotion, Événement sonore » : tâches demandées, en français.
function formatTasks(tasks: AnalysisTask[]): string {
  const labels = tasks.map((task) => TASK_LABELS[task])
  return labels.join(', ')
}

// Une ligne : date, fichier, tâches, statut, durée, puis les actions Rouvrir et Supprimer.
function HistoryRow({ analysis }: { analysis: Analysis }) {
  const statusLabel = STATUS_LABELS[analysis.status]
  const statusClasses = analysis.status === 'failed' ? 'text-danger' : 'text-ink'
  return (
    <tr className="border-t border-rule">
      <td className={`${CELL_CLASSES} font-mono whitespace-nowrap`}>
        {formatDate(analysis.created_at)}
      </td>
      {/* Largeur minimale : un nom comme p04_tel_A_07_lecture.m4a tient sur une ligne. Le nom
          ouvre le résultat, car sur téléphone la colonne Actions est hors de l'écran. */}
      <td className={`${CELL_CLASSES} min-w-56 font-mono break-all`}>
        <Link to={`/analyses/${analysis.id}`} className={LINK_CLASSES}>
          {analysis.original_filename}
        </Link>
      </td>
      <td className={CELL_CLASSES}>{formatTasks(analysis.tasks)}</td>
      <td className={`${CELL_CLASSES} ${statusClasses}`}>{statusLabel}</td>
      <td className={`${CELL_CLASSES} font-mono whitespace-nowrap`}>
        {formatDuration(analysis.duration_s)}
      </td>
      <td className={CELL_CLASSES}>
        <div className="flex flex-wrap items-start gap-3">
          <Link to={`/analyses/${analysis.id}`} className={`${LINK_CLASSES} py-1`}>
            Rouvrir
          </Link>
          <DeleteControl analysisId={analysis.id} filename={analysis.original_filename} />
        </div>
      </td>
    </tr>
  )
}

// Tableau de l'historique ; défile horizontalement sur un écran étroit au lieu de déborder.
export default function HistoryTable({ analyses }: { analyses: Analysis[] }) {
  return (
    <div className="overflow-x-auto rounded-card border border-rule bg-card shadow-card">
      <table className="w-full text-sm">
        <thead>
          <tr>
            <th className={HEADER_CELL_CLASSES}>Date</th>
            <th className={HEADER_CELL_CLASSES}>Fichier</th>
            <th className={HEADER_CELL_CLASSES}>Tâches</th>
            <th className={HEADER_CELL_CLASSES}>Statut</th>
            <th className={HEADER_CELL_CLASSES}>Durée</th>
            <th className={HEADER_CELL_CLASSES}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {analyses.map((analysis) => (
            <HistoryRow key={analysis.id} analysis={analysis} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
