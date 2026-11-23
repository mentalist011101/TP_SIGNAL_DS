import type { CSSProperties } from 'react'
import { formatF1, HOME_MODELS, HOME_REFERENCE, type HomeModel } from './examples.ts'
import Reveal from './Reveal.tsx'

interface ScoreLine {
  label: string
  detail: string
  score: number | null
}

// Libellé d'une famille, pour la ligne de score.
const FAMILY_NAMES: Record<string, string> = {
  A: 'Famille A',
  B: 'Famille B',
}

// Modèle d'une famille pour une tâche, pris dans le registre figé ; null s'il n'y en a pas.
function familyModel(task: string, family: string): HomeModel | null {
  for (const model of HOME_MODELS) {
    if (model.task === task && model.family === family) {
      return model
    }
  }
  return null
}

// Ligne d'une famille : son modèle et son F1, ou « pas encore au registre ».
function familyLine(task: string, family: string): ScoreLine {
  const model = familyModel(task, family)
  if (model === null) {
    return { label: FAMILY_NAMES[family], detail: 'pas encore au registre', score: null }
  }
  return { label: FAMILY_NAMES[family], detail: model.id, score: model.f1_macro }
}

// Lignes des événements sonores : la référence, puis les familles A et B.
function soundEventLines(): ScoreLine[] {
  const reference: ScoreLine = {
    label: 'Référence',
    detail: HOME_REFERENCE.name,
    score: HOME_REFERENCE.f1_macro,
  }
  return [reference, familyLine('sound_event', 'A'), familyLine('sound_event', 'B')]
}

// Lignes des émotions : les familles A et B.
function emotionLines(): ScoreLine[] {
  return [familyLine('emotion', 'A'), familyLine('emotion', 'B')]
}

// Longueur de la barre : le F1 (0 à 1) en pourcentage de la largeur.
function barStyle(score: number): CSSProperties {
  return { width: `${score * 100}%` }
}

// Une ligne : nom, détail, valeur écrite et barre sur l'échelle 0 à 1.
function ScoreRow({ line }: { line: ScoreLine }) {
  return (
    <li className="space-y-1.5">
      <p className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span>
          <span className="font-semibold">{line.label}</span>{' '}
          <span className="font-mono text-xs text-ink-soft">{line.detail}</span>
        </span>
        <span className="font-mono">{line.score === null ? '—' : formatF1(line.score)}</span>
      </p>
      {line.score !== null && (
        <span className="block h-2 rounded-btn bg-paper-alt" aria-hidden="true">
          <span className="block h-full rounded-btn bg-ink" style={barStyle(line.score)} />
        </span>
      )}
    </li>
  )
}

// Carte d'une tâche : son jeu de test et ses lignes de score.
function TaskScores({
  title,
  protocol,
  lines,
}: {
  title: string
  protocol: string
  lines: ScoreLine[]
}) {
  return (
    <article className="space-y-5 rounded-card border border-rule bg-card p-6">
      <div className="space-y-1">
        <h3 className="text-lg font-semibold">{title}</h3>
        <p className="text-sm text-ink-soft">{protocol}</p>
      </div>
      <ul className="space-y-4">
        {lines.map((line) => (
          <ScoreRow key={line.label} line={line} />
        ))}
      </ul>
    </article>
  )
}

// Section « résultats » : F1 macro de test de la référence et des deux familles, lus dans le
// registre au moment où les exemples ont été figés (la référence vient de C5, PR #11).
export default function Results() {
  return (
    <section id="resultats" className="mx-auto max-w-6xl space-y-12 px-6 py-24">
      <Reveal className="max-w-3xl space-y-4">
        <p className="label-mono text-ink-faint">Résultats</p>
        <h2 className="font-display text-5xl leading-tight">
          Des scores <em className="text-ink-soft">mesurés sans fuite</em>.
        </h2>
        <p className="text-lg leading-relaxed text-ink-soft">
          F1 macro de test : la moyenne du F1 de chaque classe, pour ne pas favoriser les classes
          fréquentes. 1 = parfait.
        </p>
      </Reveal>
      <Reveal className="grid items-start gap-4 md:grid-cols-2">
        <TaskScores
          title="Événements sonores"
          protocol="ESC-50, 50 classes : moyenne des 5 folds officiels, jamais remélangés (P3)."
          lines={soundEventLines()}
        />
        <TaskScores
          title="Émotions"
          protocol="CREMA-D et RAVDESS, 6 classes : acteurs du test jamais vus à l’entraînement (P1), 3 graines."
          lines={emotionLines()}
        />
      </Reveal>
    </section>
  )
}
