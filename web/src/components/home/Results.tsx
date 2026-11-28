import type { CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { useModels } from '../../api/client.ts'
import { formatF1, HOME_MODELS, HOME_REFERENCE } from './examples.ts'
import Reveal from './Reveal.tsx'
import { useInView } from './useInView.ts'

// Section « résultats » : le F1 macro de test de la référence et des deux familles, en barres
// horizontales sur une même échelle de 0 à 1 (un diagramme par tâche). Une seule série par
// diagramme : une seule couleur, chaque barre porte son nom et sa valeur, pas de légende. Les
// chiffres viennent du registre figé avec les exemples ; la référence vient de C5 (PR #11).

interface ScoreBar {
  label: string
  detail: string
  score: number
  // Fiche du modèle (EF-16) ; null pour la référence, qui n'est pas au registre.
  modelId: string | null
}

const FAMILY_NAMES: Record<string, string> = {
  A: 'Famille A',
  B: 'Famille B',
}

// Graduations de l'axe : le F1 va de 0 à 1.
const TICKS = [0, 0.25, 0.5, 0.75, 1]

// Ce que les barres lisent d'un modèle : le catalogue en direct (GET /api/v1/models) ou, en
// attendant sa réponse, le registre figé avec les exemples.
interface ScoredModel {
  id: string
  task: string
  family: string
  f1_macro: number | null
}

function familyModel(models: ScoredModel[], task: string, family: string): ScoredModel | null {
  for (const model of models) {
    if (model.task === task && model.family === family) {
      return model
    }
  }
  return null
}

// Barres d'une tâche : la référence (s'il y en a une), puis les familles A et B au registre.
function taskBars(models: ScoredModel[], task: string, withReference: boolean): ScoreBar[] {
  const bars: ScoreBar[] = []
  if (withReference) {
    bars.push({
      label: 'Référence',
      detail: HOME_REFERENCE.name,
      score: HOME_REFERENCE.f1_macro,
      modelId: null,
    })
  }
  for (const family of ['A', 'B']) {
    const model = familyModel(models, task, family)
    if (model !== null && model.f1_macro !== null) {
      bars.push({
        label: FAMILY_NAMES[family],
        detail: model.id,
        score: model.f1_macro,
        modelId: model.id,
      })
    }
  }
  return bars
}

function tickStyle(tick: number): CSSProperties {
  return { left: `${tick * 100}%` }
}

// Barre : la longueur est le F1 ; elle pousse depuis l'axe, l'une après l'autre.
function barStyle(score: number, index: number): CSSProperties {
  return { width: `${score * 100}%`, animationDelay: `${200 + index * 150}ms` }
}

// Valeur écrite juste après le bout de la barre.
function valueStyle(score: number): CSSProperties {
  return { left: `${score * 100}%` }
}

// « 0,25 » : graduation au format français.
function tickLabel(tick: number): string {
  return tick.toLocaleString('fr-FR')
}

// Nom de la barre ; lien vers la fiche du modèle quand il est au registre.
function BarName({ bar }: { bar: ScoreBar }) {
  const name = (
    <>
      <span className="font-semibold">{bar.label}</span>
      <span className="block truncate font-mono text-[11px] text-ink-faint">{bar.detail}</span>
    </>
  )
  if (bar.modelId === null) {
    return <span className="min-w-0">{name}</span>
  }
  return (
    <Link to={`/modeles/${bar.modelId}`} className="min-w-0 hover:underline">
      {name}
    </Link>
  )
}

// Une ligne du diagramme : nom à gauche, barre sur la piste, valeur au bout de la barre.
function BarRow({ bar, index, isInView }: { bar: ScoreBar; index: number; isInView: boolean }) {
  const value = formatF1(bar.score)
  // Avant d'être vue, la barre est repliée sur l'axe ; elle pousse quand le diagramme apparaît.
  let growth = 'scale-x-0 motion-reduce:scale-x-100'
  if (isInView) {
    growth = 'motion-safe:animate-bar-grow'
  }
  return (
    <li
      className="grid grid-cols-[minmax(0,8.5rem)_minmax(0,1fr)] items-center gap-3 sm:grid-cols-[minmax(0,11rem)_minmax(0,1fr)]"
      title={`${bar.label} · ${bar.detail} : F1 de test ${value}`}
    >
      <BarName bar={bar} />
      {/* Piste de 0 à 1 : la barre et sa valeur y sont posées en absolu, pour que la longueur
          de la barre soit exactement le F1, sans que l'étiquette la raccourcisse. */}
      <span className="relative block h-7">
        <span
          className={`absolute top-1/2 left-0 block h-3.5 origin-left -translate-y-1/2 rounded-r-[4px] bg-ink ${growth}`}
          style={barStyle(bar.score, index)}
        />
        <span
          className="absolute top-1/2 ml-2 -translate-y-1/2 font-mono text-sm"
          style={valueStyle(bar.score)}
        >
          {value}
        </span>
      </span>
    </li>
  )
}

// L'axe sous les barres : graduations de 0 à 1, alignées sur la piste.
function Axis() {
  return (
    <div className="grid grid-cols-[minmax(0,8.5rem)_minmax(0,1fr)] gap-3 sm:grid-cols-[minmax(0,11rem)_minmax(0,1fr)]">
      <span />
      <span className="relative h-4 font-mono text-[11px] text-ink-faint">
        {TICKS.map((tick) => (
          <span key={tick} className="absolute -translate-x-1/2" style={tickStyle(tick)}>
            {tickLabel(tick)}
          </span>
        ))}
      </span>
    </div>
  )
}

// Lignes verticales de la grille, derrière les barres : discrètes.
function Grid() {
  return (
    <div
      className="pointer-events-none absolute inset-0 grid grid-cols-[minmax(0,8.5rem)_minmax(0,1fr)] gap-3 sm:grid-cols-[minmax(0,11rem)_minmax(0,1fr)]"
      aria-hidden="true"
    >
      <span />
      <span className="relative">
        {TICKS.map((tick) => (
          <span
            key={tick}
            className="absolute top-0 bottom-0 w-px bg-rule"
            style={tickStyle(tick)}
          />
        ))}
      </span>
    </div>
  )
}

interface ChartProps {
  title: string
  protocol: string
  bars: ScoreBar[]
}

function ScoreChart({ title, protocol, bars }: ChartProps) {
  const { ref, isInView } = useInView<HTMLElement>()
  return (
    <figure ref={ref} className="m-0 space-y-5 rounded-card border border-rule bg-card p-5 sm:p-6">
      <figcaption className="space-y-1">
        <h3 className="text-lg font-semibold">{title}</h3>
        <p className="text-sm text-ink-soft">{protocol}</p>
      </figcaption>
      <div className="space-y-2">
        <div className="relative">
          <Grid />
          <ol className="relative space-y-3">
            {bars.map((bar, index) => (
              <BarRow key={bar.label} bar={bar} index={index} isInView={isInView} />
            ))}
          </ol>
        </div>
        <Axis />
      </div>
    </figure>
  )
}

export default function Results() {
  const catalog = useModels()
  const models: ScoredModel[] = catalog.data ?? HOME_MODELS
  return (
    <section id="resultats" className="mx-auto max-w-6xl space-y-12 px-6 py-24">
      <Reveal className="max-w-3xl space-y-4">
        <p className="label-mono text-ink-faint">Résultats</p>
        <h2 className="font-display text-5xl leading-tight">
          Des scores <em className="text-ink-soft">mesurés sans fuite</em>.
        </h2>
        <p className="text-lg leading-relaxed text-ink-soft">
          F1 macro de test : la moyenne du F1 de chaque classe, pour ne pas favoriser les classes
          fréquentes. 1 = parfait. Cliquez sur un modèle pour sa fiche complète.
        </p>
      </Reveal>
      <Reveal className="grid items-start gap-4 md:grid-cols-2">
        <ScoreChart
          title="Événements sonores"
          protocol="ESC-50, 50 classes : moyenne des 5 folds officiels, jamais remélangés (P3)."
          bars={taskBars(models, 'sound_event', true)}
        />
        <ScoreChart
          title="Émotions"
          protocol="CREMA-D et RAVDESS, 6 classes : acteurs du test jamais vus à l’entraînement (P1), 3 graines."
          bars={taskBars(models, 'emotion', false)}
        />
      </Reveal>
    </section>
  )
}
