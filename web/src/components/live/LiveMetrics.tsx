import type { WindowMessage } from '../../api/stream.ts'
import { InfoIcon } from '../icons.tsx'

// Mesures du direct (EF-14, ENF-01, ENF-02) : temps de calcul d'une fenêtre (serveur), RTF,
// latence perçue (page) et fenêtres sautées. Le calcul doit rester sous H = 0,5 s au p95.

const SECONDS_TO_MS = 1000
const TILE_CLASSES = 'space-y-1 bg-card px-5 py-4'

interface LiveMetricsProps {
  latest: WindowMessage | null
  hopS: number
  latencyMs: number | null
  latencyP50Ms: number | null
  latencyP95Ms: number | null
}

// « 142 ms », ou un tiret tant qu'il n'y a pas de mesure.
function formatMs(value: number | null): string {
  if (value === null) {
    return '—'
  }
  return `${Math.round(value).toLocaleString('fr-FR')} ms`
}

// « 0,07 » : RTF avec deux décimales.
function formatRtf(value: number): string {
  return value.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function MetricTile({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className={TILE_CLASSES}>
      <p className="label-mono text-ink-faint">{label}</p>
      <p className="font-mono text-2xl">{value}</p>
      <p className="font-mono text-xs text-ink-soft">{detail}</p>
    </div>
  )
}

// Avertissement si le p95 du calcul dépasse H : des fenêtres sont alors sautées (ENF-01).
function BudgetWarning({ latest, hopS }: { latest: WindowMessage; hopS: number }) {
  const budgetMs = hopS * SECONDS_TO_MS
  if (latest.compute_p95_ms <= budgetMs) {
    return null
  }
  return (
    <p className="flex items-center gap-2 text-sm text-ink-soft">
      <InfoIcon className="h-4 w-4 shrink-0" />
      Le calcul dépasse {formatMs(budgetMs)} au p95 : des fenêtres sont sautées pour rester à jour.
    </p>
  )
}

export default function LiveMetrics(props: LiveMetricsProps) {
  const latest = props.latest
  if (latest === null) {
    return null
  }
  const computeDetail = `médiane ${formatMs(latest.compute_p50_ms)} · p95 ${formatMs(latest.compute_p95_ms)}`
  const latencyDetail = `médiane ${formatMs(props.latencyP50Ms)} · p95 ${formatMs(props.latencyP95Ms)}`
  const windowsDetail = `${latest.skipped_count} sautée(s)`
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-px overflow-hidden rounded-card border border-rule bg-rule lg:grid-cols-4">
        <MetricTile label="Calcul" value={formatMs(latest.compute_ms)} detail={computeDetail} />
        <MetricTile label="RTF" value={formatRtf(latest.rtf)} detail="calcul ÷ 2 s analysées" />
        <MetricTile
          label="Latence perçue"
          value={formatMs(props.latencyMs)}
          detail={latencyDetail}
        />
        <MetricTile label="Fenêtres" value={String(latest.window_count)} detail={windowsDetail} />
      </div>
      <BudgetWarning latest={latest} hopS={props.hopS} />
    </div>
  )
}
