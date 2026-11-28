import { useState } from 'react'
import { TASK_LABELS } from '../../labels.ts'
import { SpectrogramFigure } from '../analyze/SpectrogramView.tsx'
import ProbabilityBars from '../result/ProbabilityBars.tsx'
import { formatProbability } from '../result/taskResult.ts'
import { findHomeModel, formatF1, frozenDate, HOME_EXAMPLES, type HomeExample } from './examples.ts'

// Classes montrées : les 6 émotions, ou les 5 premiers événements sur 50 (comme la page Résultat).
const EVENT_TOP_COUNT = 5

const TAB_CLASSES =
  'rounded-btn px-4 py-1.5 text-sm transition-colors duration-200 ease-out-soft has-checked:bg-accent has-checked:font-semibold has-checked:text-on-accent'

// Probabilités affichées pour la tâche de l'exemple.
function shownProbabilities(example: HomeExample) {
  const probabilities = example.result.probabilities
  if (example.task === 'sound_event') {
    return probabilities.slice(0, EVENT_TOP_COUNT)
  }
  return probabilities
}

// « echolens-emotion-whisper-base 1.0.0 · F1 de test 0,754 · T = 1,109 » : le modèle qui a
// produit le résultat, avec son score et sa calibration lus dans le registre.
function ModelLine({ example }: { example: HomeExample }) {
  const model = findHomeModel(example.result.model_id)
  return (
    <p className="text-xs text-ink-soft">
      Modèle <span className="font-mono">{example.result.model_id}</span>{' '}
      <span className="font-mono">{example.result.model_version}</span>
      {model !== null && model.f1_macro !== null && (
        <>
          {' · F1 de test '}
          <span className="font-mono">{formatF1(model.f1_macro)}</span>
        </>
      )}
      {model !== null && model.temperature !== null && (
        <>
          {' · '}
          <span className="font-mono whitespace-nowrap">
            T = {model.temperature.toLocaleString('fr-FR')}
          </span>
        </>
      )}
    </p>
  )
}

// Résultat de l'exemple : la tâche, la classe la plus probable en grand, puis les barres.
function ExampleResult({ example }: { example: HomeExample }) {
  const top = example.result.probabilities[0]
  return (
    // Hauteur minimale : celle des 6 émotions. Les 5 événements y tiennent aussi, et la carte
    // garde la même taille quand on change d'exemple.
    <div className="flex h-full min-h-[22rem] flex-col gap-4 rounded-card border border-rule bg-card p-5">
      <div>
        <p className="label-mono text-ink-faint">{TASK_LABELS[example.task]}</p>
        <p className="flex flex-wrap items-baseline gap-x-3">
          <span className="font-display text-4xl">{example.result.label_fr}</span>
          <span className="font-mono text-ink-soft">{formatProbability(top.probability)}</span>
        </p>
      </div>
      <ProbabilityBars probabilities={shownProbabilities(example)} />
      <div className="mt-auto">
        <ModelLine example={example} />
      </div>
    </div>
  )
}

// Choix de l'exemple : deux segments (boutons radio).
function ExampleTabs({
  selected,
  onSelect,
}: {
  selected: string
  onSelect: (slug: string) => void
}) {
  return (
    <fieldset className="flex flex-wrap gap-1 rounded-btn border border-rule-strong bg-card p-1">
      <legend className="sr-only">Exemple</legend>
      {HOME_EXAMPLES.map((example) => (
        <label key={example.slug} className={`${TAB_CLASSES} cursor-pointer text-ink-soft`}>
          <input
            type="radio"
            name="home-example"
            className="sr-only"
            checked={selected === example.slug}
            onChange={() => onSelect(example.slug)}
          />
          {example.title}
        </label>
      ))}
    </fieldset>
  )
}

// L'exemple choisi, ou le premier.
function findExample(slug: string): HomeExample {
  for (const example of HOME_EXAMPLES) {
    if (example.slug === slug) {
      return example
    }
  }
  return HOME_EXAMPLES[0]
}

// Vrai exemple figé (relecture du 21 novembre) : deux extraits réels analysés par les vrais
// modèles, avec le spectrogramme du serveur, les probabilités et le modèle de chacun.
export default function RealExample() {
  const [slug, setSlug] = useState(HOME_EXAMPLES[0].slug)
  const example = findExample(slug)
  return (
    <figure className="m-0 space-y-4 rounded-[22px] border border-rule-strong bg-card p-3 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ExampleTabs selected={slug} onSelect={setSlug} />
        <span className="inline-flex items-center gap-2 rounded-btn border border-brand bg-paper px-3.5 py-1.5 text-sm">
          <span className="h-2 w-2 shrink-0 rounded-full bg-brand motion-safe:animate-pulse" />
          <span className="font-semibold">Vrai résultat, pas une maquette</span>
          <span className="hidden font-mono text-xs text-ink-soft sm:inline">
            · figé le {frozenDate()}
          </span>
        </span>
      </div>
      {/* Deux colonnes sur grand écran (spectrogramme plus large que le résultat), une seule
          sur téléphone : les barres de probabilités gardent ainsi une longueur lisible. */}
      <div className="grid items-stretch gap-5 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <div className="flex min-w-0 flex-col justify-center rounded-card border border-rule bg-paper p-4">
          <SpectrogramFigure
            url={`/exemple/${example.slug}.png`}
            info={example.spectrogram}
            durationSeconds={example.duration_s}
          />
        </div>
        <ExampleResult example={example} />
      </div>
      <figcaption className="min-h-8 text-xs text-ink-soft">
        {example.source} · licence {example.licence}. Analysé par les vrais modèles d’EchoLens, puis
        figé par un script depuis l’API.
      </figcaption>
    </figure>
  )
}
