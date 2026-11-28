import type { CSSProperties, ReactNode } from 'react'
import Reveal from './Reveal.tsx'

// Schéma de la chaîne de traitement, tel que le serveur la fait (décisions de
// docs/specification.md). Une impulsion parcourt la ligne en 9 s et chaque étape s'allume à son
// passage : on voit l'audio traverser la chaîne. Ligne horizontale sur grand écran, verticale
// sur téléphone. Les visuels des étapes sont des illustrations (aria-hidden).

// Durée d'un passage de l'impulsion, celle des animations travel-x et stage-glow (index.css).
const CYCLE_MS = 9000

interface PipelineStep {
  title: string
  text: string
  decision: string
  visual: ReactNode
}

// Hauteurs des barres de l'onde, en % : une voix qui enfle puis retombe.
const WAVE_HEIGHTS = [30, 55, 80, 45, 95, 60, 35, 70, 50, 25]

// Opacités des cases du mini-spectrogramme (4 bandes × 8 instants), basses fréquences en bas.
const SPECTROGRAM_CELLS = [
  [0.15, 0.25, 0.6, 0.3, 0.2, 0.5, 0.2, 0.1],
  [0.3, 0.5, 0.8, 0.5, 0.3, 0.7, 0.4, 0.2],
  [0.5, 0.7, 0.9, 0.7, 0.5, 0.8, 0.6, 0.3],
  [0.7, 0.9, 1, 0.9, 0.8, 0.95, 0.8, 0.5],
]

// Longueurs des barres du résultat, en %.
const RESULT_BARS = [82, 36, 14]

function Wave() {
  return (
    <span className="flex h-8 items-center gap-[3px]">
      {WAVE_HEIGHTS.map((height, index) => (
        <span
          key={index}
          className="w-[3px] rounded-btn bg-ink-soft"
          style={{ height: `${height}%` }}
        />
      ))}
    </span>
  )
}

function Decoded() {
  return (
    <span className="flex flex-col items-center gap-1 font-mono text-[11px] leading-none">
      <span className="rounded-btn bg-paper-alt px-2 py-1">16 kHz</span>
      <span className="rounded-btn bg-paper-alt px-2 py-1">mono</span>
    </span>
  )
}

function Windows() {
  return (
    <span className="relative flex h-8 w-24 items-center">
      <span className="absolute inset-x-0 h-2 rounded-btn bg-paper-alt" />
      <span className="absolute left-0 h-6 w-12 rounded-md border border-ink-soft" />
      <span className="absolute left-6 h-6 w-12 rounded-md border border-dashed border-ink-faint" />
      <span className="absolute left-12 h-6 w-12 rounded-md border border-ink-soft" />
    </span>
  )
}

function Spectrogram() {
  return (
    <span className="grid grid-cols-8 gap-[2px]">
      {SPECTROGRAM_CELLS.map((row, rowIndex) =>
        row.map((opacity, columnIndex) => (
          <span
            key={`${rowIndex}-${columnIndex}`}
            className="block h-2 w-2 rounded-[2px] bg-ink"
            style={{ opacity }}
          />
        )),
      )}
    </span>
  )
}

function Models() {
  return (
    <span className="flex flex-col items-center gap-1 font-mono text-[11px] leading-none">
      <span className="rounded-btn border border-rule-strong px-2 py-1">A · CRNN</span>
      <span className="rounded-btn border border-rule-strong px-2 py-1">B · Whisper</span>
    </span>
  )
}

function Result() {
  return (
    <span className="flex w-20 flex-col gap-1.5">
      {RESULT_BARS.map((width, index) => {
        let color = 'bg-ink-faint'
        if (index === 0) {
          color = 'bg-ink'
        }
        return (
          <span key={width} className="h-1.5 rounded-btn bg-paper-alt">
            <span className={`block h-full rounded-btn ${color}`} style={{ width: `${width}%` }} />
          </span>
        )
      })}
    </span>
  )
}

const STEPS: PipelineStep[] = [
  {
    title: 'Audio',
    text: 'Un fichier ou le micro, jusqu’à 5 minutes.',
    decision: 'D6',
    visual: <Wave />,
  },
  {
    title: 'Décodage',
    text: 'ffmpeg le ramène toujours en mono, 16 kHz.',
    decision: 'D1, D2',
    visual: <Decoded />,
  },
  {
    title: 'Découpage',
    text: 'Fenêtres de 5 s pour les sons, morceaux de parole (VAD) pour la voix.',
    decision: 'D5',
    visual: <Windows />,
  },
  {
    title: 'Représentation',
    text: 'Log-Mel, ou encodeur Whisper gelé, calculé par le serveur seulement.',
    decision: 'R2, R5',
    visual: <Spectrogram />,
  },
  {
    title: 'Modèles calibrés',
    text: 'Famille A ou B selon le profil, scores divisés par la température T.',
    decision: 'ENF-06',
    visual: <Models />,
  },
  {
    title: 'Résultat',
    text: 'Probabilités par segment pour la frise, puis le résultat global.',
    decision: 'EF-05, EF-12',
    visual: <Result />,
  },
]

// La ligne va du centre de la première étape au centre de la dernière : l'impulsion passe sur
// l'étape de rang i à i / (nombre d'étapes − 1) du cycle, et l'étape s'allume à ce moment.
function glowStyle(index: number): CSSProperties {
  const position = index / (STEPS.length - 1)
  return { animationDelay: `${Math.round(position * CYCLE_MS)}ms` }
}

// Une étape : son visuel dans une pastille qui s'allume, puis son nom et sa phrase.
function Stage({ step, index }: { step: PipelineStep; index: number }) {
  return (
    <li className="relative flex gap-4 lg:flex-col lg:items-center lg:gap-3 lg:text-center">
      <span
        className="relative z-10 flex h-20 w-28 shrink-0 items-center justify-center rounded-2xl border border-rule bg-card motion-safe:animate-stage-glow"
        style={glowStyle(index)}
        aria-hidden="true"
      >
        {step.visual}
      </span>
      <div className="min-w-0 space-y-1 pt-1 lg:pt-0">
        <p className="flex items-baseline gap-2 lg:justify-center">
          <span className="font-mono text-xs text-ink-faint">{index + 1}</span>
          <span className="font-semibold">{step.title}</span>
        </p>
        <p className="text-sm leading-relaxed text-ink-soft">{step.text}</p>
        <p className="font-mono text-[11px] text-ink-faint">{step.decision}</p>
      </div>
    </li>
  )
}

// L'impulsion : un point de la couleur de marque qui parcourt la ligne.
function Pulse({ vertical }: { vertical: boolean }) {
  let classes =
    'absolute top-1/2 -translate-x-1/2 -translate-y-1/2 motion-safe:animate-travel-x motion-reduce:hidden'
  if (vertical) {
    classes =
      'absolute left-1/2 -translate-x-1/2 -translate-y-1/2 motion-safe:animate-travel-y motion-reduce:hidden'
  }
  return (
    <span className={classes} aria-hidden="true">
      <span className="block h-3 w-3 rounded-full bg-brand shadow-[0_0_16px_4px] shadow-brand/60" />
    </span>
  )
}

// Section « chaîne de traitement » : le schéma animé, de l'onde au résultat.
export default function Pipeline() {
  return (
    <section id="fonctionnement" className="mx-auto max-w-6xl space-y-12 px-6 py-24">
      <Reveal className="max-w-3xl space-y-4">
        <p className="label-mono text-ink-faint">Chaîne de traitement</p>
        <h2 className="font-display text-5xl leading-tight sm:text-6xl">
          De l’onde au résultat, <em className="text-ink-soft">étape par étape</em>.
        </h2>
        <p className="text-lg leading-relaxed text-ink-soft">
          Chaque audio suit exactement le même chemin, qu’il vienne d’un fichier ou du micro.
        </p>
      </Reveal>
      <Reveal>
        <div className="relative rounded-[22px] border border-rule-strong bg-paper p-6 sm:p-8">
          {/* Ligne du flux : horizontale à hauteur des pastilles sur grand écran, verticale à
              gauche sur téléphone. L'impulsion la parcourt. */}
          <span
            className="absolute top-[4.5rem] right-[calc(100%/12+2rem)] left-[calc(100%/12+2rem)] hidden h-px bg-rule-strong lg:block"
            aria-hidden="true"
          >
            <Pulse vertical={false} />
          </span>
          <span
            className="absolute top-16 bottom-24 left-[calc(1.5rem+3.5rem)] w-px bg-rule-strong sm:top-[4.5rem] sm:left-[calc(2rem+3.5rem)] lg:hidden"
            aria-hidden="true"
          >
            <Pulse vertical={true} />
          </span>
          <ol className="relative grid gap-8 lg:grid-cols-6 lg:gap-4">
            {STEPS.map((step, index) => (
              <Stage key={step.title} step={step} index={index} />
            ))}
          </ol>
        </div>
      </Reveal>
    </section>
  )
}
