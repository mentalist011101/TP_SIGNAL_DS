import type { TaskResultSummary } from '../../api/client.ts'
import type { WindowMessage } from '../../api/stream.ts'
import { TASK_LABELS } from '../../labels.ts'
import { formatProbability } from '../result/taskResult.ts'

// Résultats de la fenêtre la plus récente (2 dernières secondes) : émotion et événement, tels
// que le serveur les renvoie (R5 : rien n'est recalculé ici).

const TILE_CLASSES = 'space-y-1 bg-card px-6 py-5'

// « Colère 62 % », ou le message du serveur (« Aucune parole détectée »).
function ResultValue({ result }: { result: TaskResultSummary | undefined }) {
  if (result === undefined) {
    return <p className="text-ink-soft">—</p>
  }
  if (result.status !== 'done') {
    return <p className="text-ink-soft">{result.message}</p>
  }
  return (
    <p className="flex flex-wrap items-baseline gap-x-3">
      <span className="font-display text-4xl leading-tight">{result.label_fr}</span>
      {result.probability !== null && (
        <span className="font-mono text-ink-soft">{formatProbability(result.probability)}</span>
      )}
    </p>
  )
}

// Indicateur de parole : vert de la marque quand la VAD entend une voix.
function SpeechIndicator({ speech }: { speech: boolean | null }) {
  if (speech === null) {
    return null
  }
  let dotClasses = 'h-2.5 w-2.5 rounded-full bg-rule-strong'
  let text = 'Pas de parole'
  if (speech) {
    dotClasses = 'h-2.5 w-2.5 rounded-full bg-brand'
    text = 'Parole détectée'
  }
  return (
    <span className="inline-flex items-center gap-2 text-sm text-ink-soft">
      <span className={dotClasses} aria-hidden="true" />
      {text}
    </span>
  )
}

// « −42 dBFS » : niveau du son reçu par le serveur, pour voir si le micro capte.
function LevelIndicator({ levelDbfs }: { levelDbfs: number }) {
  const level = Math.round(levelDbfs).toLocaleString('fr-FR')
  return <span className="font-mono text-sm text-ink-soft">niveau reçu {level} dBFS</span>
}

// Le serveur ne reçoit que du silence : les résultats affichés ne veulent alors rien dire.
function SilentWarning() {
  return (
    <p className="text-sm text-danger">
      Le serveur ne reçoit que du silence : le micro choisi par le navigateur ne capte rien.
      Vérifiez le micro sélectionné (icône du micro dans la barre d’adresse) et qu’il n’est pas
      coupé dans le système, puis redémarrez.
    </p>
  )
}

export default function LiveResults({ latest }: { latest: WindowMessage | null }) {
  const emotion = latest?.results.emotion
  const soundEvent = latest?.results.sound_event
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold">Les 2 dernières secondes</h2>
        {latest !== null && (
          <div className="flex flex-wrap items-center gap-4">
            <LevelIndicator levelDbfs={latest.level_dbfs} />
            <SpeechIndicator speech={latest.speech} />
          </div>
        )}
      </div>
      {latest !== null && latest.silent && <SilentWarning />}
      <div className="grid gap-px overflow-hidden rounded-card border border-rule bg-rule sm:grid-cols-2">
        <div className={TILE_CLASSES}>
          <p className="label-mono text-ink-faint">{TASK_LABELS.emotion}</p>
          <ResultValue result={emotion} />
        </div>
        <div className={TILE_CLASSES}>
          <p className="label-mono text-ink-faint">{TASK_LABELS.sound_event}</p>
          <ResultValue result={soundEvent} />
        </div>
      </div>
    </div>
  )
}
