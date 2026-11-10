import type { Analysis, AnalysisStatusValue } from '../../api/client.ts'

// Libellés français des statuts renvoyés par l'API.
const STATUS_LABELS: Record<AnalysisStatusValue, string> = {
  pending: 'En attente',
  processing: 'En cours',
  done: 'Terminée',
  failed: 'Échec',
}

const PANEL_CLASSES = 'space-y-1 rounded-card border border-rule bg-card p-4 text-sm shadow-card'

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

// Détail d'une analyse : fichier, statut, durée, puis résultat ou raison de l'échec.
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
      {analysis.status === 'done' && (
        <p className="text-ink-faint">Résultats disponibles quand les modèles seront branchés.</p>
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
