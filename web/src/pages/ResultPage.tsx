import { Link, useParams } from 'react-router-dom'
import { ApiError, useAnalysis } from '../api/client.ts'
import AnalysisStatus from '../components/analyze/AnalysisStatus.tsx'
import SpectrogramView from '../components/analyze/SpectrogramView.tsx'

const LINK_CLASSES = 'text-sm font-semibold text-accent-ink hover:underline'

// Message d'erreur : celui de l'API (analyse introuvable…), ou serveur injoignable.
function describeError(error: Error | null): string | null {
  if (error === null) {
    return null
  }
  if (error instanceof ApiError) {
    return error.message
  }
  return 'Serveur injoignable : vérifiez que l’application est lancée, puis réessayez.'
}

// Page Résultat, version minimale (C22) : ouverte depuis l'historique, elle montre le statut et
// le spectrogramme d'une analyse. La tâche C21 y ajoutera les probabilités, la transcription et
// l'export JSON.
export default function ResultPage() {
  const params = useParams()
  const analysisId = params.analysisId ?? null
  const query = useAnalysis(analysisId)
  const errorMessage = describeError(query.error)

  return (
    <section className="space-y-6">
      <Link to="/historique" className={LINK_CLASSES}>
        ← Retour à l’historique
      </Link>
      <h1 className="font-display text-3xl font-extrabold tracking-tight">Résultat de l’analyse</h1>
      <AnalysisStatus analysis={query.data} isSubmitting={false} errorMessage={errorMessage} />
      <SpectrogramView analysis={query.data} />
    </section>
  )
}
