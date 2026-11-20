import { API_BASE, isAnalysisRunning, type Analysis } from '../../api/client.ts'
import { PROFILE_LABELS, STATUS_LABELS } from '../../labels.ts'

// Bouton secondaire de la charte (même style que Supprimer dans l'historique).
const DOWNLOAD_CLASSES =
  'inline-block rounded-btn border border-rule-strong bg-card px-3 py-1.5 text-sm font-semibold text-ink shadow-hard-sm transition-colors duration-200 ease-out-soft hover:bg-paper-alt'

// « 20 nov. 2026, 11:15 » : date et heure locales du navigateur (l'API envoie de l'UTC).
function formatDate(isoDate: string): string {
  const date = new Date(isoDate)
  return date.toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
}

// « 8 s », « 41,2 s » ; inconnue tant que le serveur n'a pas décodé l'audio.
function formatDuration(durationSeconds: number | null): string {
  if (durationSeconds === null) {
    return 'durée inconnue'
  }
  const formatted = durationSeconds.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
  return `${formatted} s`
}

// Statut en texte ; en rouge seulement pour un échec (danger = erreurs).
function StatusText({ analysis }: { analysis: Analysis }) {
  const label = STATUS_LABELS[analysis.status]
  if (analysis.status === 'failed') {
    return <span className="font-semibold text-danger">{label}</span>
  }
  if (isAnalysisRunning(analysis)) {
    return <span className="font-semibold">{label}… (actualisation chaque seconde)</span>
  }
  return <span className="font-semibold">{label}</span>
}

// Le lien pointe sur GET /api/v1/analyses/{id} : le fichier téléchargé est la réponse de
// l'API telle quelle, sans rien recalculer ni retirer.
function DownloadJsonLink({ analysisId }: { analysisId: string }) {
  const url = `${API_BASE}/analyses/${analysisId}`
  const filename = `echolens-analyse-${analysisId}.json`
  return (
    <a href={url} download={filename} className={DOWNLOAD_CLASSES}>
      Télécharger le résultat (JSON)
    </a>
  )
}

// En-tête de la page Résultat : fichier, date, durée, profil, statut, puis l'export (EF-09),
// proposé seulement une fois l'analyse terminée.
export default function ResultHeader({ analysis }: { analysis: Analysis }) {
  const profileLabel = PROFILE_LABELS[analysis.profile]
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 space-y-1">
        <p className="label-mono text-ink-faint">Résultat de l’analyse</p>
        <h1 className="font-mono text-2xl font-medium break-all">{analysis.original_filename}</h1>
        <p className="text-sm text-ink-soft">
          <span className="font-mono">{formatDate(analysis.created_at)}</span> ·{' '}
          <span className="font-mono">{formatDuration(analysis.duration_s)}</span> · profil{' '}
          {profileLabel} · <StatusText analysis={analysis} />
        </p>
      </div>
      {analysis.status === 'done' && <DownloadJsonLink analysisId={analysis.id} />}
    </div>
  )
}
