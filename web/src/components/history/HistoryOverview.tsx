import type { HistoryStats } from './historyStats.ts'

// Grille à filets fins : le fond « rule » ne se voit que dans l'espace de 1 px entre les cases.
const GRID_CLASSES =
  'grid grid-cols-2 gap-px overflow-hidden rounded-card border border-rule bg-rule lg:grid-cols-4'
const TILE_CLASSES = 'space-y-1 bg-card px-6 py-5'

const SECONDS_PER_MINUTE = 60

interface KeyFigure {
  label: string
  value: string
  detail: string
}

// « 4 min 12 s », ou « 42 s » sous une minute.
function formatTotalDuration(totalSeconds: number): string {
  const roundedSeconds = Math.round(totalSeconds)
  const minutes = Math.floor(roundedSeconds / SECONDS_PER_MINUTE)
  const seconds = roundedSeconds % SECONDS_PER_MINUTE
  if (minutes === 0) {
    return `${seconds} s`
  }
  return `${minutes} min ${seconds} s`
}

// Part des analyses finies qui ont réussi ; un tiret tant qu'aucune n'est finie.
function formatSuccessRate(stats: HistoryStats): string {
  const finishedCount = stats.doneCount + stats.failedCount
  if (finishedCount === 0) {
    return '—'
  }
  const rate = stats.doneCount / finishedCount
  return rate.toLocaleString('fr-FR', { style: 'percent', maximumFractionDigits: 0 })
}

// Les quatre chiffres clés affichés en tuiles.
function buildKeyFigures(stats: HistoryStats): KeyFigure[] {
  return [
    {
      label: 'Analyses',
      value: String(stats.analysisCount),
      detail: `${stats.doneCount} terminée(s)`,
    },
    {
      label: 'Audio analysé',
      value: formatTotalDuration(stats.analysedSeconds),
      detail: 'durée des analyses terminées',
    },
    {
      label: 'Réussite',
      value: formatSuccessRate(stats),
      detail: `${stats.failedCount} échec(s)`,
    },
    {
      label: 'Sur 7 jours',
      value: String(stats.lastWeekCount),
      detail: 'analyse(s) lancée(s)',
    },
  ]
}

// Chiffres clés de l'historique, en haut de la page.
export default function HistoryOverview({ stats }: { stats: HistoryStats }) {
  const figures = buildKeyFigures(stats)
  return (
    <div className={GRID_CLASSES}>
      {figures.map((figure) => (
        <div key={figure.label} className={TILE_CLASSES}>
          <p className="label-mono text-ink-soft">{figure.label}</p>
          <p className="font-display text-4xl leading-tight">{figure.value}</p>
          <p className="text-xs text-ink-soft">{figure.detail}</p>
        </div>
      ))}
    </div>
  )
}
