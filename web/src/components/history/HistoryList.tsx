import { Link } from 'react-router-dom'
import type { AnalysisSummary, AnalysisTask } from '../../api/client.ts'
import { TASK_LABELS } from '../../labels.ts'
import { formatProbability, hasDemoResult } from '../result/taskResult.ts'
import StatusBadge from '../StatusBadge.tsx'
import DeleteControl from './DeleteControl.tsx'

const ITEM_CLASSES =
  'flex flex-wrap items-center justify-between gap-x-6 gap-y-3 px-4 py-3 transition-colors duration-200 ease-out-soft hover:bg-paper-alt'
const LINK_CLASSES = 'font-semibold text-accent-ink underline-offset-2 hover:underline'

// « 18 nov. 2026, 21:27 » : date et heure locales du navigateur (l'API envoie de l'UTC).
function formatDate(isoDate: string): string {
  const date = new Date(isoDate)
  return date.toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
}

// « 3,2 s », ou un tiret tant que la durée n'est pas connue.
function formatDuration(durationSeconds: number | null): string {
  if (durationSeconds === null) {
    return '—'
  }
  const formatted = durationSeconds.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
  return `${formatted} s`
}

// « Peur 30,5 % » : premier choix d'une tâche terminée, tel que résumé par l'API ;
// null tant qu'il n'y en a pas (analyse en cours, no_speech, unavailable).
function taskSummary(analysis: AnalysisSummary, task: AnalysisTask): string | null {
  if (analysis.results === null) {
    return null
  }
  const result = analysis.results[task]
  if (result === undefined || result.status !== 'done') {
    return null
  }
  if (result.probability === null) {
    return result.label_fr
  }
  const percent = formatProbability(result.probability)
  return `${result.label_fr} ${percent}`
}

// Étiquette d'une tâche demandée, avec son résultat principal s'il existe.
function TaskChip({ analysis, task }: { analysis: AnalysisSummary; task: AnalysisTask }) {
  const summary = taskSummary(analysis, task)
  return (
    <span className="inline-flex items-center gap-2 rounded-btn bg-paper-alt px-2 py-1 text-xs">
      <span className="font-semibold">{TASK_LABELS[task]}</span>
      {summary !== null && <span className="font-mono text-ink-soft">{summary}</span>}
    </span>
  )
}

// Une ligne par analyse, à la manière d'une liste de tickets : statut, nom (qui ouvre le
// résultat) et tâches à gauche ; date, durée et suppression à droite. Sur téléphone, la ligne
// passe sur plusieurs rangées au lieu de déborder.
function HistoryItem({ analysis }: { analysis: AnalysisSummary }) {
  const resultPath = `/analyses/${analysis.id}`
  const isDemo = hasDemoResult(analysis)
  return (
    <li className={ITEM_CLASSES}>
      <div className="min-w-0 flex-1 basis-72 space-y-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <StatusBadge status={analysis.status} />
          <Link to={resultPath} className={`${LINK_CLASSES} font-mono break-all`}>
            {analysis.original_filename}
          </Link>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {analysis.tasks.map((task) => (
            <TaskChip key={task} analysis={analysis} task={task} />
          ))}
          {isDemo && <span className="text-xs text-ink-faint">probabilités de démonstration</span>}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="font-mono text-xs whitespace-nowrap text-ink-soft">
          {formatDate(analysis.created_at)} · {formatDuration(analysis.duration_s)}
        </span>
        <DeleteControl analysisId={analysis.id} filename={analysis.original_filename} />
      </div>
    </li>
  )
}

// Liste de l'historique : un seul cadre, des lignes séparées par des filets fins.
export default function HistoryList({ analyses }: { analyses: AnalysisSummary[] }) {
  return (
    <ul className="divide-y divide-rule overflow-hidden rounded-card border border-rule bg-card">
      {analyses.map((analysis) => (
        <HistoryItem key={analysis.id} analysis={analysis} />
      ))}
    </ul>
  )
}
