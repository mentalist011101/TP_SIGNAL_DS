import type { Analysis, AnalysisStatusValue } from '../../api/client.ts'

// Libellés français des statuts renvoyés par l'API.
const STATUS_LABELS: Record<AnalysisStatusValue, string> = {
  pending: 'En attente',
  processing: 'En cours',
  done: 'Terminée',
  failed: 'Échec',
}

const PANEL_CLASSES =
  'space-y-1 rounded-md border border-slate-200 bg-white p-4 text-sm dark:border-slate-800 dark:bg-slate-900'

interface AnalysisStatusProps {
  analysis: Analysis | undefined
  isSubmitting: boolean
  errorMessage: string | null
}

// Durée en secondes, au format français (virgule décimale) ; inconnue tant que ce n'est pas fini.
function formatDuration(durationSeconds: number | null): string {
  if (durationSeconds === null) {
    return 'connue à la fin du traitement'
  }
  const formatted = durationSeconds.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
  return `${formatted} s`
}

// Détail d'une analyse : fichier, statut, durée, puis résultat ou raison de l'échec.
function AnalysisDetails({ analysis }: { analysis: Analysis }) {
  const statusLabel = STATUS_LABELS[analysis.status]
  const duration = formatDuration(analysis.duration_s)
  return (
    <div className={PANEL_CLASSES}>
      <p>Fichier : {analysis.original_filename}</p>
      <p>Statut : {statusLabel}</p>
      <p>Durée : {duration}</p>
      {analysis.status === 'failed' && (
        <p className="text-red-600">Raison : {analysis.error_message}</p>
      )}
      {analysis.status === 'done' && (
        <p className="text-slate-500">Résultats disponibles quand les modèles seront branchés.</p>
      )}
    </div>
  )
}

// Suivi de l'analyse : envoi en cours, erreur de l'API, ou détail de l'analyse.
export default function AnalysisStatus(props: AnalysisStatusProps) {
  if (props.isSubmitting) {
    return <p className="text-sm text-slate-500">Envoi du fichier au serveur…</p>
  }
  if (props.errorMessage !== null) {
    return <p className="text-sm text-red-600">{props.errorMessage}</p>
  }
  if (props.analysis === undefined) {
    return null
  }
  return <AnalysisDetails analysis={props.analysis} />
}
