import { useModels, type ComparedTask, type ModelRun } from '../../api/client.ts'
import { FAMILY_LABELS, PROFILE_LABELS } from '../../labels.ts'
import { findModel } from '../models/modelFormat.ts'
import MainResultValue from '../result/MainResultValue.tsx'
import ProbabilityBars from '../result/ProbabilityBars.tsx'
import { formatComputeTime, realTimeFactor } from './compareFormat.ts'

// Carte d'un modèle dans la comparaison (EF-15) : identité (famille, profils), temps de calcul,
// puis son résultat principal et ses premières classes, ou son texte pour la transcription.

// Classes montrées par carte : assez pour voir où les modèles divergent.
const TOP_CLASS_COUNT = 5

const CARD_CLASSES = 'space-y-4 rounded-card border border-rule bg-card p-5'
const BADGE_CLASSES = 'label-mono rounded-btn border border-rule-strong px-2 py-0.5 text-ink-soft'

interface ModelRunCardProps {
  task: ComparedTask
  run: ModelRun
  durationS: number | null
}

// Famille du modèle, lue dans le catalogue (GET /models) ; rien pour le faux prédicteur.
function FamilyBadge({ modelId }: { modelId: string }) {
  const models = useModels()
  const model = findModel(models.data ?? [], modelId)
  if (model === null) {
    return null
  }
  return <span className={BADGE_CLASSES}>{FAMILY_LABELS[model.family]}</span>
}

// « 1,24 s de calcul · RTF 0,08 » sous le nom du modèle.
function ComputeLine({ run, durationS }: { run: ModelRun; durationS: number | null }) {
  const factor = realTimeFactor(run.compute_s, durationS)
  const profiles = run.profiles.map((profile) => PROFILE_LABELS[profile]).join(', ')
  return (
    <p className="font-mono text-xs text-ink-soft">
      {formatComputeTime(run.compute_s)} de calcul
      {factor !== null && ` · RTF ${factor}`} · profil {profiles}
    </p>
  )
}

// Le résultat lui-même : message si rien n'est calculé, texte pour la transcription, sinon
// résultat principal et premières classes.
function RunResult({ task, run }: { task: ComparedTask; run: ModelRun }) {
  const result = run.result
  if (result.status !== 'done') {
    return <p className="text-sm text-ink-soft">{result.message}</p>
  }
  if (task === 'transcription') {
    return <p className="text-sm">{result.text}</p>
  }
  const topClasses = result.probabilities.slice(0, TOP_CLASS_COUNT)
  return (
    <>
      <MainResultValue result={result} leading="leading-none" />
      <ProbabilityBars probabilities={topClasses} />
    </>
  )
}

export default function ModelRunCard({ task, run, durationS }: ModelRunCardProps) {
  return (
    <article className={CARD_CLASSES}>
      <div className="space-y-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-mono text-sm font-semibold">{run.model_id}</h3>
          <FamilyBadge modelId={run.model_id} />
        </div>
        <ComputeLine run={run} durationS={durationS} />
      </div>
      <RunResult task={task} run={run} />
    </article>
  )
}
