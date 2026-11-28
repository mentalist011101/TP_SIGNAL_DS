import { Link } from 'react-router-dom'
import type { TaskResult } from '../../api/client.ts'
import ProbabilityBars from './ProbabilityBars.tsx'
import { formatProbability, mainProbability } from './taskResult.ts'

// Carte « Locuteur » (EF-11) : qui parle le plus, puis la part du temps de parole de chacun.
// Ces parts ne sont pas des probabilités : chaque morceau de parole a reçu un nom (ou
// « Inconnu ») par similarité cosinus avec les voix enregistrées (C15), puis l'API a compté
// le temps de parole de chacun.

// « Awa » en grand, puis « 75 % du temps de parole ».
function MainSpeaker({ result }: { result: TaskResult }) {
  const share = mainProbability(result)
  return (
    <div>
      <p className="label-mono text-ink-soft">Parle le plus</p>
      <p className="flex flex-wrap items-baseline gap-x-3">
        <span className="font-display text-4xl leading-none">{result.label_fr}</span>
        {share !== null && (
          <span className="font-mono text-ink-soft">
            {formatProbability(share)} du temps de parole
          </span>
        )}
      </p>
    </div>
  )
}

export default function SpeakerResult({ result }: { result: TaskResult }) {
  return (
    <>
      <MainSpeaker result={result} />
      <div className="space-y-2">
        <p className="label-mono text-ink-faint">Part du temps de parole</p>
        <ProbabilityBars probabilities={result.probabilities} />
      </div>
      <p className="text-xs text-ink-soft">
        Modèle : <span className="font-mono">{result.model_id}</span>, version{' '}
        <span className="font-mono">{result.model_version}</span> · « Inconnu » : aucune voix
        enregistrée n’atteint le seuil de C15 ·{' '}
        <Link to="/locuteurs" className="text-accent-ink underline underline-offset-2">
          voix enregistrées
        </Link>
      </p>
    </>
  )
}
