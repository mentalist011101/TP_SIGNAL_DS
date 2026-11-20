import { Link, useParams } from 'react-router-dom'
import {
  ApiError,
  describeApiError,
  isAnalysisRunning,
  useAnalysis,
  type Analysis,
} from '../api/client.ts'
import ResultAudio from '../components/result/ResultAudio.tsx'
import ResultHeader from '../components/result/ResultHeader.tsx'
import { AnalysisNotFound, FailedAnalysis } from '../components/result/ResultMessages.tsx'
import TaskResultList from '../components/result/TaskResultList.tsx'

const LINK_CLASSES = 'text-sm font-semibold text-accent-ink hover:underline'

// Code HTTP de l'API pour une analyse inconnue.
const NOT_FOUND_STATUS = 404

// Avant la première réponse : chargement, analyse introuvable, ou serveur injoignable.
function MissingAnalysis({ error }: { error: Error | null }) {
  if (error === null) {
    return <p className="text-sm text-ink-soft">Chargement de l’analyse…</p>
  }
  if (error instanceof ApiError && error.status === NOT_FOUND_STATUS) {
    return <AnalysisNotFound />
  }
  return <p className="text-sm text-danger">{describeApiError(error)}</p>
}

// Corps de la page : la raison d'un échec, ou l'audio puis une carte par tâche demandée.
function ResultBody({ analysis }: { analysis: Analysis }) {
  if (analysis.status === 'failed') {
    return <FailedAnalysis reason={analysis.error_message} />
  }
  return (
    <>
      {isAnalysisRunning(analysis) && (
        <p className="text-sm text-ink-soft">
          Vous pouvez quitter cette page : l’analyse continue et restera dans l’historique.
        </p>
      )}
      <ResultAudio analysis={analysis} />
      <TaskResultList analysis={analysis} />
    </>
  )
}

// Page Résultat (C21, EF-05 à EF-08), adresse /analyses/{id} : ouverte par la page Analyser
// à la fin d'une analyse, ou depuis l'historique. useAnalysis interroge l'API chaque seconde
// tant que l'analyse est en attente ou en cours, puis s'arrête.
export default function ResultPage() {
  const params = useParams()
  const analysisId = params.analysisId ?? null
  const query = useAnalysis(analysisId)
  const analysis = query.data

  let content = <MissingAnalysis error={query.error} />
  if (analysis !== undefined) {
    content = (
      <>
        <ResultHeader analysis={analysis} />
        {/* Une interrogation a échoué alors qu'on avait déjà l'analyse (F11) : on garde
            l'affichage, et la suivante réessaiera toute seule. */}
        {query.error !== null && (
          <p className="text-sm text-danger">
            Connexion au serveur perdue. Nouvelle tentative en cours…
          </p>
        )}
        <ResultBody analysis={analysis} />
      </>
    )
  }

  return (
    <section className="space-y-6">
      <nav className="flex flex-wrap gap-4">
        <Link to="/" className={LINK_CLASSES}>
          ← Nouvelle analyse
        </Link>
        <Link to="/historique" className={LINK_CLASSES}>
          Historique
        </Link>
      </nav>
      {content}
    </section>
  )
}
