import { API_BASE, type Analysis } from '../../api/client.ts'
import { PROFILE_LABELS } from '../../labels.ts'
import { DownloadIcon } from '../icons.tsx'
import StatusBadge from '../StatusBadge.tsx'

// Bouton secondaire de la charte (même style que Supprimer dans l'historique).
const DOWNLOAD_CLASSES =
  'inline-flex items-center gap-2 rounded-btn border border-rule-strong bg-card px-3 py-1.5 text-sm font-semibold text-ink transition-colors duration-200 ease-out-soft hover:bg-paper-alt'

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

// Formats proposés par GET /api/v1/analyses/{id}/export (EF-09, C26).
const EXPORT_FORMATS = [
  { format: 'json', label: 'JSON' },
  { format: 'csv', label: 'CSV' },
  { format: 'pdf', label: 'PDF' },
]

// Un lien par format. Le serveur construit le fichier et propose son nom
// (echolens_<nom>_<date>.<format>) : download sans valeur garde ce nom.
function ExportLinks({ analysisId }: { analysisId: string }) {
  const exportUrl = `${API_BASE}/analyses/${analysisId}/export`
  return (
    <div className="flex flex-wrap gap-2">
      {EXPORT_FORMATS.map((item) => (
        <a
          key={item.format}
          href={`${exportUrl}?format=${item.format}`}
          download
          className={DOWNLOAD_CLASSES}
        >
          <DownloadIcon />
          Télécharger {item.label}
        </a>
      ))}
    </div>
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
        <h1 className="font-mono text-3xl font-medium break-all">{analysis.original_filename}</h1>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-soft">
          <StatusBadge status={analysis.status} />
          <span className="font-mono">{formatDate(analysis.created_at)}</span>
          <span className="font-mono">{formatDuration(analysis.duration_s)}</span>
          <span>profil {profileLabel}</span>
        </div>
      </div>
      {analysis.status === 'done' && <ExportLinks analysisId={analysis.id} />}
    </div>
  )
}
