import type { CSSProperties, ReactNode } from 'react'
import { EmotionIcon, SpeakersIcon, TranscriptIcon, WaveIcon } from '../icons.tsx'
import Reveal from './Reveal.tsx'

// Grille des outils, à la manière des pages produit récentes : une carte par outil, chacune
// avec un petit visuel animé. Les visuels sont des illustrations, pas des résultats.

interface TimelineEvent {
  label: string
  time: string
  // Position sur la frise, en % de la largeur.
  leftPercent: number
  // Moment d'apparition dans le cycle de 8 s : quand la tête de lecture passe (8 s × position).
  delayMs: number
}

const TIMELINE_EVENTS: TimelineEvent[] = [
  { label: 'Coups à la porte', time: '0:04', leftPercent: 6, delayMs: 480 },
  { label: 'Bruits de pas', time: '0:12', leftPercent: 30, delayMs: 2400 },
  { label: 'Grincement de porte', time: '0:19', leftPercent: 52, delayMs: 4160 },
  { label: 'Rires', time: '0:31', leftPercent: 76, delayMs: 6080 },
]

const EMOTIONS = ['Neutre', 'Joie', 'Tristesse', 'Colère', 'Peur', 'Dégoût']

// Phrases courtes : la seconde s'écrit sur une seule ligne, même dans une carte étroite.
const TRANSCRIPT_LINES = [
  { time: '0:00', text: 'Bonjour, merci d’être là.' },
  { time: '0:03', text: 'Je ne suis pas d’accord.' },
]

// Tours de parole des deux locuteurs, en % de la durée.
const SPEAKER_TURNS = [
  { speaker: 'A', widthPercent: 28 },
  { speaker: 'B', widthPercent: 18 },
  { speaker: 'A', widthPercent: 12 },
  { speaker: 'B', widthPercent: 26 },
  { speaker: 'A', widthPercent: 16 },
]

const CARD_CLASSES = 'flex h-full flex-col gap-5 rounded-card border border-rule bg-card p-7'

interface ToolCardProps {
  icon: ReactNode
  title: string
  text: string
  isSoon: boolean
  children: ReactNode
}

// Carte d'un outil : icône, titre, phrase, puis son visuel en bas.
function ToolCard({ icon, title, text, isSoon, children }: ToolCardProps) {
  return (
    <article className={CARD_CLASSES}>
      <div className="flex items-center justify-between">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-paper-alt text-ink-soft">
          {icon}
        </span>
        {isSoon && <span className="label-mono text-ink-faint">Bientôt</span>}
      </div>
      <div className="space-y-2">
        <h3 className="text-xl font-semibold">{title}</h3>
        <p className="leading-relaxed text-ink-soft">{text}</p>
      </div>
      <div className="mt-auto" aria-hidden="true">
        {children}
      </div>
    </article>
  )
}

// Les étiquettes alternent entre deux rangées, pour ne pas se chevaucher.
const ROW_TOPS_PX = [14, 58]

function eventStyle(event: TimelineEvent, index: number): CSSProperties {
  const top = ROW_TOPS_PX[index % ROW_TOPS_PX.length]
  return { left: `${event.leftPercent}%`, top: `${top}px`, animationDelay: `${event.delayMs}ms` }
}

// Repère sur la ligne du temps, à la position de l'événement.
function tickStyle(event: TimelineEvent): CSSProperties {
  return { left: `${event.leftPercent}%`, animationDelay: `${event.delayMs}ms` }
}

// Frise des événements : une tête de lecture avance, les événements apparaissent à son passage.
function EventsTimeline() {
  return (
    <div className="relative h-40 overflow-hidden rounded-xl border border-rule bg-paper">
      <span className="absolute top-0 bottom-0 w-px bg-brand motion-safe:animate-playhead" />
      <span className="absolute right-0 bottom-9 left-0 h-px bg-rule-strong" />
      {TIMELINE_EVENTS.map((event, index) => (
        <span key={event.label}>
          <span
            className="absolute rounded-btn border border-rule-strong bg-card px-3 py-1.5 text-sm whitespace-nowrap motion-safe:animate-pop-cycle motion-safe:opacity-0"
            style={eventStyle(event, index)}
          >
            {event.label}
            <span className="ml-2 font-mono text-xs text-ink-faint">{event.time}</span>
          </span>
          <span
            className="absolute bottom-[33px] h-2 w-2 -translate-x-1/2 rounded-full bg-ink motion-safe:animate-pop-cycle motion-safe:opacity-0"
            style={tickStyle(event)}
          />
        </span>
      ))}
    </div>
  )
}

// Les six émotions reconnues, en étiquettes.
function EmotionChips() {
  return (
    <ul className="flex flex-wrap gap-2">
      {EMOTIONS.map((emotion) => (
        <li key={emotion} className="rounded-btn bg-paper-alt px-3 py-1.5 text-sm">
          {emotion}
        </li>
      ))}
    </ul>
  )
}

// Transcription : deux phrases horodatées ; la seconde s'écrit avec un curseur qui clignote.
function TypingTranscript() {
  return (
    <div className="space-y-2 rounded-xl border border-rule bg-paper p-4 font-mono text-sm">
      <p className="flex gap-3">
        <span className="text-ink-faint">{TRANSCRIPT_LINES[0].time}</span>
        <span>{TRANSCRIPT_LINES[0].text}</span>
      </p>
      <p className="flex gap-3">
        <span className="text-ink-faint">{TRANSCRIPT_LINES[1].time}</span>
        <span className="inline-block overflow-hidden whitespace-nowrap motion-safe:animate-typing">
          {TRANSCRIPT_LINES[1].text}
        </span>
        <span className="motion-safe:animate-caret">▍</span>
      </p>
    </div>
  )
}

function turnStyle(widthPercent: number): CSSProperties {
  return { width: `${widthPercent}%` }
}

// Locuteurs : les tours de parole de A et B sur une frise, avec la tête de lecture.
function SpeakerTurns() {
  return (
    <div className="space-y-2">
      <div className="relative flex h-10 gap-1 overflow-hidden rounded-xl">
        {SPEAKER_TURNS.map((turn, index) => {
          let colorClasses = 'bg-paper-alt text-ink-soft'
          if (turn.speaker === 'A') {
            colorClasses = 'bg-accent text-on-accent'
          }
          return (
            <span
              key={index}
              className={`flex items-center px-3 text-xs font-semibold ${colorClasses}`}
              style={turnStyle(turn.widthPercent)}
            >
              {turn.speaker}
            </span>
          )
        })}
        <span className="absolute top-0 bottom-0 w-0.5 bg-brand motion-safe:animate-playhead" />
      </div>
      <p className="flex gap-5 text-xs text-ink-soft">
        <span className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-sm bg-accent" />
          Locuteur A
        </span>
        <span className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-sm bg-paper-alt" />
          Locuteur B
        </span>
      </p>
    </div>
  )
}

// Section des outils : deux grandes cartes et deux petites, en grille.
export default function ToolsBento() {
  return (
    <section id="outils" className="mx-auto max-w-6xl space-y-12 px-6 py-24">
      <Reveal className="max-w-3xl space-y-4">
        <p className="label-mono text-ink-faint">Outils</p>
        <h2 className="font-display text-5xl leading-tight sm:text-6xl">
          Tout ce qu’un audio peut dire, <em className="text-ink-soft">au même endroit</em>.
        </h2>
      </Reveal>
      <div className="grid gap-4 lg:grid-cols-3">
        <Reveal className="lg:col-span-2">
          <ToolCard
            icon={<WaveIcon className="h-5 w-5" />}
            title="Événements sonores"
            text="Porte, pas, sirène, pluie : 50 sons du quotidien repérés fenêtre par fenêtre, avec leur moment."
            isSoon={false}
          >
            <EventsTimeline />
          </ToolCard>
        </Reveal>
        <Reveal delayMs={100}>
          <ToolCard
            icon={<EmotionIcon className="h-5 w-5" />}
            title="Émotions"
            text="Six émotions estimées sur les passages de parole, segment par segment."
            isSoon={false}
          >
            <EmotionChips />
          </ToolCard>
        </Reveal>
        <Reveal>
          <ToolCard
            icon={<TranscriptIcon className="h-5 w-5" />}
            title="Transcription"
            text="Le texte de ce qui est dit, horodaté, pensé pour le français et ses accents."
            isSoon={true}
          >
            <TypingTranscript />
          </ToolCard>
        </Reveal>
        <Reveal className="lg:col-span-2" delayMs={100}>
          <ToolCard
            icon={<SpeakersIcon className="h-5 w-5" />}
            title="Locuteurs"
            text="Qui parle, et quand : les tours de parole de chaque voix sur la durée de l’audio."
            isSoon={true}
          >
            <SpeakerTurns />
          </ToolCard>
        </Reveal>
      </div>
      <p className="text-sm text-ink-soft">
        Les visuels de ces cartes sont des illustrations ; les vrais résultats sont dans l’exemple
        en haut de la page.
      </p>
    </section>
  )
}
