import { Link, useParams } from 'react-router-dom'
import {
  ApiError,
  isAnalysisRunning,
  useAnalysis,
  type Analysis,
  type AnalysisProfile,
  type AnalysisStatusValue,
} from '../api/client.ts'
import SpectrogramView from '../components/analyze/SpectrogramView.tsx'
import ExportJsonButton from '../components/result/ExportJsonButton.tsx'
import ResultsGrid from '../components/result/ResultsGrid.tsx'

const LINK_CLASSES = 'text-sm font-semibold text-accent-ink hover:underline'
const CARD_CLASSES = 'space-y-3 rounded-card border border-rule bg-card p-5 shadow-card'
const NOT_FOUND_STATUS = 404

const STATUS_LABELS: Record<AnalysisStatusValue, string> = {
  pending: 'En attente',
  processing: 'En cours',
  done: 'Terminée',
  failed: 'Échec',
}

const PROFILE_LABELS: Record<AnalysisProfile, string> = {
  quality: 'profil Qualité',
  realtime: 'profil Temps réel',
}

// « 18/11/2026 21:34 · 4,2 s · profil Qualité · Terminée » : la fiche de l'analyse en une ligne.
function summaryLine(analysis: Analysis): string {
  const date = new Date(analysis.created_at)
  const formattedDate = date.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' })
  const parts = [formattedDate]
  if (analysis.duration_s !== null) {
    const seconds = analysis.duration_s.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
    parts.push(`${seconds} s`)
  }
  parts.push(PROFILE_LABELS[analysis.profile])
  parts.push(STATUS_LABELS[analysis.status])
  return parts.join(' · ')
}

// En-tête : nom du fichier, fiche de l'analyse et bouton d'export.
function ResultHeader({ analysis }: { analysis: Analysis }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div className="space-y-1">
        <h1 className="font-display text-3xl font-extrabold tracking-tight break-all">
          {analysis.original_filename}
        </h1>
        <p className="font-mono text-sm text-ink-soft">{summaryLine(analysis)}</p>
      </div>
      <ExportJsonButton analysis={analysis} />
    </div>
  )
}

// Audio d'origine (converti en 16 kHz par le serveur) et son spectrogramme.
function AudioCard({ analysis }: { analysis: Analysis }) {
  return (
    <div className={CARD_CLASSES}>
      <h2 className="font-display text-lg font-bold">Audio</h2>
      {analysis.audio_url !== null && (
        <audio controls src={analysis.audio_url} className="w-full" />
      )}
      <SpectrogramView analysis={analysis} />
    </div>
  )
}

// Analyse terminée : audio, puis une carte par tâche demandée.
function DoneContent({ analysis }: { analysis: Analysis }) {
  return (
    <>
      <AudioCard analysis={analysis} />
      {analysis.results === null && (
        <p className="text-ink-faint">Résultats disponibles quand les modèles seront branchés.</p>
      )}
      {analysis.results !== null && <ResultsGrid results={analysis.results} />}
    </>
  )
}

// Analyse en échec : la raison donnée par le serveur et les deux façons de repartir.
function FailedContent({ analysis }: { analysis: Analysis }) {
  return (
    <div className={CARD_CLASSES}>
      <p className="text-danger">L’analyse n’a pas pu aboutir : {analysis.error_message}</p>
      <div className="flex flex-wrap gap-4">
        <Link to="/" className={LINK_CLASSES}>
          Relancer une analyse
        </Link>
        <Link to="/historique" className={LINK_CLASSES}>
          Voir l’historique
        </Link>
      </div>
    </div>
  )
}

// Analyse en cours : la page se met à jour seule (useAnalysis interroge chaque seconde).
function RunningContent() {
  return (
    <div className={CARD_CLASSES}>
      <p>Analyse en cours… la page se met à jour toute seule.</p>
      <p className="text-sm text-ink-soft">
        Vous pouvez quitter cette page : l’analyse continue et restera dans l’historique.
      </p>
    </div>
  )
}

// Contenu sous l'en-tête, selon le statut de l'analyse.
function AnalysisContent({ analysis }: { analysis: Analysis }) {
  if (isAnalysisRunning(analysis)) {
    return <RunningContent />
  }
  if (analysis.status === 'failed') {
    return <FailedContent analysis={analysis} />
  }
  return <DoneContent analysis={analysis} />
}

// Erreur de chargement : analyse introuvable (404) ou serveur injoignable.
function LoadError({ error }: { error: Error }) {
  let message = 'Serveur injoignable : vérifiez que l’application est lancée, puis réessayez.'
  if (error instanceof ApiError) {
    message = error.message
  }
  if (error instanceof ApiError && error.status === NOT_FOUND_STATUS) {
    message = 'Cette analyse n’existe pas ou a été supprimée.'
  }
  return (
    <div className={CARD_CLASSES}>
      <p className="text-danger">{message}</p>
      <Link to="/historique" className={LINK_CLASSES}>
        Voir l’historique
      </Link>
    </div>
  )
}

// Page Résultat (C21) : fiche, audio et spectrogramme, probabilités par tâche (contrat C13),
// export JSON. Ouverte après une analyse ou depuis l'historique.
export default function ResultPage() {
  const params = useParams()
  const analysisId = params.analysisId ?? null
  const query = useAnalysis(analysisId)

  let content = <p className="text-sm text-ink-soft">Chargement de l’analyse…</p>
  if (query.error !== null) {
    content = <LoadError error={query.error} />
  }
  if (query.data !== undefined) {
    content = (
      <>
        <ResultHeader analysis={query.data} />
        <AnalysisContent analysis={query.data} />
      </>
    )
  }
  return (
    <section className="space-y-6">
      <Link to="/historique" className={LINK_CLASSES}>
        ← Retour à l’historique
      </Link>
      {content}
    </section>
  )
}
