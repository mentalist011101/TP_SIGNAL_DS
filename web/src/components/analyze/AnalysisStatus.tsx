import type { Analysis } from '../../api/client.ts'
import { STATUS_LABELS } from '../../labels.ts'

// Zone en retrait (paper-alt) : le panneau est posé dans la colonne des réglages, pas une carte de
// plus.
const PANEL_CLASSES = 'space-y-1 rounded-card bg-paper-alt p-3 text-sm'

interface AnalysisStatusProps {
  analysis: Analysis | undefined
  isSubmitting: boolean
  errorMessage: string | null
}

// Durée en secondes, au format français (virgule décimale) : le nombre en mono, l'unité dans la
// police du texte (en mono, l'espace et le « s » paraissaient détachés). Inconnue tant que ce
// n'est pas fini.
function DurationValue({ durationSeconds }: { durationSeconds: number | null }) {
  if (durationSeconds === null) {
    return <span>connue à la fin du traitement</span>
  }
  const formatted = durationSeconds.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
  return (
    <span>
      <span className="font-mono">{formatted}</span> s
    </span>
  )
}

// Détail d'une analyse : fichier, statut, durée, puis la raison d'un échec. Une analyse
// terminée n'est jamais affichée ici : la page Analyser ouvre alors la page Résultat.
function AnalysisDetails({ analysis }: { analysis: Analysis }) {
  const statusLabel = STATUS_LABELS[analysis.status]
  return (
    <div className={PANEL_CLASSES}>
      <p>
        Fichier : <span className="font-mono">{analysis.original_filename}</span>
      </p>
      <p>Statut : {statusLabel}</p>
      <p>
        Durée : <DurationValue durationSeconds={analysis.duration_s} />
      </p>
      {analysis.status === 'failed' && (
        <p className="text-danger">Raison : {analysis.error_message}</p>
      )}
    </div>
  )
}

// Suivi de l'analyse : envoi en cours, erreur de l'API, ou détail de l'analyse.
export default function AnalysisStatus(props: AnalysisStatusProps) {
  if (props.isSubmitting) {
    return <p className="text-sm text-ink-soft">Envoi du fichier au serveur…</p>
  }
  if (props.errorMessage !== null) {
    return <p className="text-sm text-danger">{props.errorMessage}</p>
  }
  if (props.analysis === undefined) {
    return null
  }
  return <AnalysisDetails analysis={props.analysis} />
}
