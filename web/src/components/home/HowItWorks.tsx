import { useEffect, useState, type CSSProperties, type ReactNode } from 'react'
import { DEMO_MOODS } from './demoMoods.ts'
import Reveal from './Reveal.tsx'
import SpectrogramAnimation from './SpectrogramAnimation.tsx'

interface Step {
  title: string
  text: string
}

// Le chemin d'un audio dans EchoLens, tel que le code le fait (D1, D2, R2, D5).
const STEPS: Step[] = [
  {
    title: 'Vous déposez un audio',
    text: 'Fichier ou micro. Le serveur le décode et le convertit en 16 kHz mono, toujours de la même façon.',
  },
  {
    title: 'Le serveur le transforme en image',
    text: 'Un spectrogramme log-Mel : le même calcul que celui qu’ont vu les modèles pendant leur entraînement.',
  },
  {
    title: 'Chaque modèle l’écoute',
    text: 'L’audio est découpé en fenêtres ; chaque modèle donne la probabilité de chacune de ses classes.',
  },
  {
    title: 'Vous lisez le résultat',
    text: 'Le résultat global, les probabilités de chaque classe, et le modèle qui les a produites.',
  },
]

// Durée d'une étape avant de passer à la suivante.
const STEP_DURATION_MS = 4000

// Hauteurs des barres de la forme d'onde (en %), et leur décalage dans l'animation.
const WAVE_BARS = [30, 55, 80, 45, 95, 60, 35, 70, 90, 50, 25, 65, 85, 40, 75, 55, 30, 60]

const PANEL_CLASSES =
  'flex h-72 items-center justify-center overflow-hidden rounded-card border border-rule bg-paper p-6'

// Numéro de l'étape affichée : il avance seul, mais un clic choisit une étape et repart de là.
function useStepCycle(): [number, (index: number) => void] {
  const [stepIndex, setStepIndex] = useState(0)
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return
    }
    const timer = window.setInterval(() => {
      setStepIndex((index) => (index + 1) % STEPS.length)
    }, STEP_DURATION_MS)
    return () => {
      window.clearInterval(timer)
    }
  }, [stepIndex])
  return [stepIndex, setStepIndex]
}

// Barre de la forme d'onde : sa hauteur, et un retard pour que les barres ne bougent pas
// ensemble.
function waveBarStyle(heightPercent: number, index: number): CSSProperties {
  return { height: `${heightPercent}%`, animationDelay: `${index * 70}ms` }
}

// Étape 1 : une forme d'onde dont les barres montent et descendent.
function WaveVisual() {
  return (
    <div className="flex h-40 w-full items-center gap-1.5 rounded-xl bg-night px-6">
      {WAVE_BARS.map((height, index) => (
        <span
          key={index}
          className="flex-1 origin-center rounded-full bg-accent-soft motion-safe:animate-equalizer"
          style={waveBarStyle(height, index)}
        />
      ))}
    </div>
  )
}

// Étape 3 : les modèles qui écoutent l'audio, chacun avec ses classes.
function ModelsVisual() {
  return (
    <ul className="grid w-full gap-3">
      <li className="flex items-center justify-between rounded-xl border border-rule bg-card px-4 py-3">
        <span className="font-semibold">Émotions</span>
        <span className="font-mono text-xs text-ink-soft">6 classes · segments de parole</span>
      </li>
      <li className="flex items-center justify-between rounded-xl border border-rule bg-card px-4 py-3">
        <span className="font-semibold">Événements sonores</span>
        <span className="font-mono text-xs text-ink-soft">50 classes · fenêtres de 5 s</span>
      </li>
      <li className="flex items-center justify-between rounded-xl border border-dashed border-rule-strong px-4 py-3 text-ink-soft">
        <span className="font-semibold">Transcription · Locuteurs</span>
        <span className="font-mono text-xs">bientôt</span>
      </li>
    </ul>
  )
}

// Étape 4 : le résultat tel que la page Résultat le montre.
function ResultVisual() {
  return (
    <div className="w-full space-y-4 rounded-xl border border-rule bg-card p-5">
      <p className="label-mono text-ink-faint">Événement sonore</p>
      <p className="flex items-baseline gap-3">
        <span className="font-display text-4xl">Coups à la porte</span>
        <span className="font-mono text-ink-soft">71 %</span>
      </p>
      <p className="font-mono text-xs text-ink-faint">modèle, version, calibration : affichés</p>
    </div>
  )
}

// Le visuel de l'étape choisie.
function StepVisual({ stepIndex }: { stepIndex: number }) {
  let visual: ReactNode = <WaveVisual />
  if (stepIndex === 1) {
    visual = <SpectrogramAnimation mood={DEMO_MOODS[0]} />
  }
  if (stepIndex === 2) {
    visual = <ModelsVisual />
  }
  if (stepIndex === 3) {
    visual = <ResultVisual />
  }
  return (
    <div className={PANEL_CLASSES} aria-hidden="true">
      {visual}
    </div>
  )
}

interface StepButtonProps {
  step: Step
  index: number
  isActive: boolean
  onSelect: () => void
}

// Une étape de la liste : numéro, titre, et le texte seulement pour l'étape choisie, dont le
// trait de gauche passe en encre.
function StepButton({ step, index, isActive, onSelect }: StepButtonProps) {
  let classes = 'border-rule text-ink-faint hover:text-ink-soft'
  if (isActive) {
    classes = 'border-ink text-ink'
  }
  return (
    <li>
      <button
        type="button"
        aria-pressed={isActive}
        onClick={onSelect}
        className={`w-full border-l-2 py-3 pl-5 text-left transition-colors duration-300 ease-out-soft ${classes}`}
      >
        <span className="font-mono text-xs">0{index + 1}</span>
        <span className="block text-lg font-semibold">{step.title}</span>
        {isActive && <span className="mt-1 block text-ink-soft">{step.text}</span>}
      </button>
    </li>
  )
}

// Section « Comment ça marche » : la liste des étapes à gauche, le visuel à droite.
export default function HowItWorks() {
  const [stepIndex, setStepIndex] = useStepCycle()
  return (
    <section id="fonctionnement" className="mx-auto max-w-6xl space-y-12 px-6 py-24">
      <Reveal className="max-w-3xl space-y-4">
        <p className="label-mono text-ink-faint">Comment ça marche</p>
        <h2 className="font-display text-5xl leading-tight sm:text-6xl">
          De l’onde au résultat, <em className="text-ink-soft">en quatre temps</em>.
        </h2>
      </Reveal>
      <Reveal className="grid items-center gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <ol className="space-y-1">
          {STEPS.map((step, index) => (
            <StepButton
              key={step.title}
              step={step}
              index={index}
              isActive={index === stepIndex}
              onSelect={() => setStepIndex(index)}
            />
          ))}
        </ol>
        <StepVisual stepIndex={stepIndex} />
      </Reveal>
    </section>
  )
}
