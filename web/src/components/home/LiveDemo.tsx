import { useEffect, useState, type CSSProperties } from 'react'
import {
  DEMO_MOODS,
  MOOD_DURATION_MS,
  dominantEmotion,
  type DemoEmotion,
  type DemoMood,
} from './demoMoods.ts'
import SpectrogramAnimation from './SpectrogramAnimation.tsx'

const CHIP_CLASSES = 'label-mono rounded-btn border px-2.5 py-1'

// Numéro de l'humeur affichée : il avance toutes les 2,8 s, puis revient à la première.
// Si le système demande moins d'animations, on reste sur la première.
function useMoodCycle(): number {
  const [moodIndex, setMoodIndex] = useState(0)
  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduceMotion) {
      return
    }
    const timer = window.setInterval(() => {
      setMoodIndex((index) => (index + 1) % DEMO_MOODS.length)
    }, MOOD_DURATION_MS)
    return () => {
      window.clearInterval(timer)
    }
  }, [])
  return moodIndex
}

// Longueur de la barre : le pourcentage de la largeur. La transition CSS la fait glisser.
function barStyle(percent: number): CSSProperties {
  return { width: `${percent}%` }
}

// Une émotion : libellé, barre, pourcentage. La plus forte est en encre, les autres en gris.
function EmotionRow({ emotion, isDominant }: { emotion: DemoEmotion; isDominant: boolean }) {
  let barColor = 'bg-ink-faint'
  if (isDominant) {
    barColor = 'bg-ink'
  }
  return (
    <li className="grid grid-cols-[5rem_minmax(0,1fr)_2.75rem] items-center gap-3 text-sm">
      <span>{emotion.label}</span>
      <span className="h-1.5 rounded-btn bg-paper-alt">
        <span
          className={`block h-full rounded-btn ${barColor} transition-[width] duration-700 ease-out-soft`}
          style={barStyle(emotion.percent)}
        />
      </span>
      <span className="text-right font-mono text-ink-soft">{emotion.percent} %</span>
    </li>
  )
}

// Carte des émotions : l'émotion dominante en grand, puis les six barres.
function EmotionMeter({ mood }: { mood: DemoMood }) {
  const dominant = dominantEmotion(mood)
  return (
    <div className="space-y-4 rounded-card border border-rule bg-card p-5">
      <div>
        <p className="label-mono text-ink-faint">Émotion</p>
        <p className="flex items-baseline gap-3">
          <span className="font-display text-4xl">{dominant.label}</span>
          <span className="font-mono text-ink-soft">{dominant.percent} %</span>
        </p>
      </div>
      <ul className="space-y-2">
        {mood.emotions.map((emotion) => (
          <EmotionRow
            key={emotion.label}
            emotion={emotion}
            isDominant={emotion.label === dominant.label}
          />
        ))}
      </ul>
    </div>
  )
}

// Aperçu animé de la page d'accueil : un spectrogramme qui défile et, à côté, les émotions
// qui évoluent avec lui. C'est une illustration, et la carte le dit.
export default function LiveDemo() {
  const moodIndex = useMoodCycle()
  const mood = DEMO_MOODS[moodIndex]
  return (
    <figure className="m-0 rounded-[22px] border border-rule-strong bg-card p-3">
      <div className="overflow-hidden rounded-card border border-rule bg-paper">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-rule px-5 py-3">
          <span className="flex items-center gap-2 text-sm">
            <span className="h-2 w-2 rounded-full bg-brand motion-safe:animate-pulse" />
            Analyse en direct
          </span>
          <span className={`${CHIP_CLASSES} border-dashed border-rule-strong text-ink-faint`}>
            Illustration
          </span>
        </div>
        <div className="flex flex-wrap gap-5 p-5" aria-hidden="true">
          <div className="min-w-0 flex-[999_1_28rem] space-y-2">
            <SpectrogramAnimation mood={mood} />
            <p className="flex justify-between font-mono text-xs text-ink-faint">
              <span>fréquence ↑</span>
              <span>temps →</span>
            </p>
          </div>
          <div className="min-w-0 flex-[1_1_18rem]">
            <EmotionMeter mood={mood} />
          </div>
        </div>
      </div>
      <figcaption className="sr-only">
        Illustration animée : un spectrogramme défile et les probabilités des six émotions changent
        au fil de l’audio.
      </figcaption>
    </figure>
  )
}
