import type { CSSProperties, ReactNode } from 'react'
import { EmotionIcon, SpeakersIcon, TranscriptIcon, WaveIcon } from '../icons.tsx'
import Reveal from './Reveal.tsx'

// Grille des outils : une carte par outil, chacune avec un visuel animé. Les visuels sont des
// illustrations, pas des résultats ; toutes les animations s'arrêtent quand le système demande
// moins d'animations (motion-safe).

// --- Événements sonores : une frise qui défile, avec les événements posés sur l'onde ---

interface StripEvent {
  label: string
  time: string
  // Position dans une moitié de la frise, en % de cette moitié.
  leftPercent: number
}

const STRIP_EVENTS: StripEvent[] = [
  { label: 'Coups à la porte', time: '0:04', leftPercent: 4 },
  { label: 'Pas', time: '0:12', leftPercent: 21 },
  { label: 'Sirène', time: '0:19', leftPercent: 37 },
  { label: 'Pluie', time: '0:26', leftPercent: 54 },
  { label: 'Chien', time: '0:33', leftPercent: 70 },
  { label: 'Rires', time: '0:41', leftPercent: 86 },
]

// Les étiquettes alternent entre deux hauteurs, pour ne jamais se chevaucher.
const CHIP_TOPS_PX = [10, 46]
const STRIP_BAR_COUNT = 72

// Hauteurs des barres de l'onde, en % : une suite régulière mais irrégulière à l'œil.
function stripHeights(): number[] {
  const heights: number[] = []
  for (let index = 0; index < STRIP_BAR_COUNT; index++) {
    const value = Math.abs(Math.sin(index * 1.7) * Math.cos(index * 0.37))
    heights.push(18 + Math.round(value * 70))
  }
  return heights
}

const STRIP_HEIGHTS = stripHeights()

function chipStyle(event: StripEvent, index: number): CSSProperties {
  const top = CHIP_TOPS_PX[index % CHIP_TOPS_PX.length]
  return { left: `${event.leftPercent}%`, top: `${top}px` }
}

// Une moitié de la frise : l'onde en bas, les événements au-dessus, reliés par un trait.
function StripHalf() {
  return (
    <div className="relative h-full w-1/2 shrink-0">
      <div className="absolute inset-x-0 bottom-3 flex h-14 items-end gap-[3px] px-1">
        {STRIP_HEIGHTS.map((height, index) => (
          <span
            key={index}
            className="flex-1 rounded-t-sm bg-ink-faint/50"
            style={{ height: `${height}%` }}
          />
        ))}
      </div>
      {STRIP_EVENTS.map((event, index) => (
        <span key={event.label} className="absolute" style={chipStyle(event, index)}>
          <span className="flex items-center gap-2 rounded-btn border border-rule-strong bg-card px-3 py-1 text-sm whitespace-nowrap">
            {event.label}
            <span className="font-mono text-[11px] text-ink-faint">{event.time}</span>
          </span>
        </span>
      ))}
    </div>
  )
}

// La frise complète : deux moitiés identiques qui glissent vers la gauche, en boucle ; la tête
// de lecture reste au milieu.
function EventsStrip() {
  return (
    <div className="relative h-44 overflow-hidden rounded-xl border border-rule bg-paper">
      {/* Sur téléphone, chaque moitié vaut deux largeurs d'écran : les étiquettes ne se
          chevauchent pas. */}
      <div className="flex h-full w-[400%] motion-safe:animate-scroll-x sm:w-[200%]">
        <StripHalf />
        <StripHalf />
      </div>
      <span className="absolute top-0 bottom-0 left-1/2 w-0.5 bg-brand" />
      <span className="label-mono absolute bottom-1 left-1/2 ml-2 text-[10px] text-brand">
        maintenant
      </span>
    </div>
  )
}

// --- Émotions : chaque émotion apparaît à son tour, avec son émoji qui grandit ---

interface Emotion {
  label: string
  emoji: string
}

const EMOTIONS: Emotion[] = [
  { label: 'Neutre', emoji: '😐' },
  { label: 'Joie', emoji: '😄' },
  { label: 'Tristesse', emoji: '😢' },
  { label: 'Colère', emoji: '😠' },
  { label: 'Peur', emoji: '😨' },
  { label: 'Dégoût', emoji: '🤢' },
]

// Cycle de 9 s de l'animation emotion-cycle (index.css) : 1,5 s par émotion.
const EMOTION_STEP_MS = 1500

function emotionStyle(index: number): CSSProperties {
  return { animationDelay: `${index * EMOTION_STEP_MS}ms` }
}

function EmotionStage() {
  return (
    <div className="space-y-4">
      <div className="relative h-36 overflow-hidden rounded-xl border border-rule bg-paper">
        {EMOTIONS.map((emotion, index) => (
          <span
            key={emotion.label}
            className="absolute inset-0 flex flex-col items-center justify-center gap-1 motion-safe:animate-emotion-cycle motion-safe:opacity-0 motion-reduce:hidden"
            style={emotionStyle(index)}
          >
            <span className="text-6xl leading-none">{emotion.emoji}</span>
            <span className="font-display text-2xl">{emotion.label}</span>
          </span>
        ))}
        {/* Sans animation : la première émotion, immobile. */}
        <span className="absolute inset-0 hidden flex-col items-center justify-center gap-1 motion-reduce:flex">
          <span className="text-6xl leading-none">{EMOTIONS[0].emoji}</span>
          <span className="font-display text-2xl">{EMOTIONS[0].label}</span>
        </span>
      </div>
      <ul className="flex flex-wrap gap-1.5">
        {EMOTIONS.map((emotion) => (
          <li key={emotion.label} className="rounded-btn bg-paper-alt px-2.5 py-1 text-xs">
            {emotion.emoji} {emotion.label}
          </li>
        ))}
      </ul>
    </div>
  )
}

// --- Transcription : deux phrases horodatées, la seconde s'écrit ---

const TRANSCRIPT_LINES = [
  { time: '0:00', text: 'Bonjour, merci d’être là.' },
  { time: '0:03', text: 'Je ne suis pas d’accord.' },
]

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

// --- Locuteurs : une piste par voix, révélée au passage de la tête de lecture ---

interface SpeakerTurn {
  startPercent: number
  widthPercent: number
}

interface SpeakerLane {
  name: string
  isUnknown: boolean
  turns: SpeakerTurn[]
}

const SPEAKER_LANES: SpeakerLane[] = [
  {
    name: 'Awa',
    isUnknown: false,
    turns: [
      { startPercent: 2, widthPercent: 22 },
      { startPercent: 52, widthPercent: 14 },
    ],
  },
  {
    name: 'Moussa',
    isUnknown: false,
    turns: [
      { startPercent: 26, widthPercent: 18 },
      { startPercent: 80, widthPercent: 17 },
    ],
  },
  {
    name: 'Inconnu',
    isUnknown: true,
    turns: [{ startPercent: 67, widthPercent: 11 }],
  },
]

function turnStyle(turn: SpeakerTurn): CSSProperties {
  return { left: `${turn.startPercent}%`, width: `${turn.widthPercent}%` }
}

function Lane({ lane }: { lane: SpeakerLane }) {
  let color = 'bg-ink'
  if (lane.isUnknown) {
    color = 'bg-ink-faint/60'
  }
  return (
    <div className="grid grid-cols-[4.5rem_minmax(0,1fr)] items-center gap-3">
      <span className="truncate text-xs text-ink-soft">{lane.name}</span>
      <span className="relative h-5 rounded-md bg-paper-alt">
        {lane.turns.map((turn) => (
          <span
            key={turn.startPercent}
            className={`absolute top-0 bottom-0 rounded-md ${color}`}
            style={turnStyle(turn)}
          />
        ))}
      </span>
    </div>
  )
}

function SpeakerLanes() {
  return (
    <div className="space-y-3 rounded-xl border border-rule bg-paper p-4">
      <div className="relative space-y-2">
        {SPEAKER_LANES.map((lane) => (
          <Lane key={lane.name} lane={lane} />
        ))}
        {/* Partie pas encore lue : cachée, de la tête de lecture jusqu'au bout. Même cycle de
            8 s que la tête : les tours apparaissent quand la lecture les atteint. */}
        <span className="absolute inset-y-0 right-0 left-[5.25rem]">
          <span className="absolute inset-y-0 right-0 bg-paper motion-safe:animate-uncover motion-reduce:hidden" />
          <span className="absolute top-0 bottom-0 w-0.5 bg-brand motion-safe:animate-playhead motion-reduce:hidden" />
        </span>
      </div>
      <p className="text-xs text-ink-soft">
        Une voix trop loin de toutes celles enregistrées reste « Inconnu ».
      </p>
    </div>
  )
}

// --- Carte d'un outil ---

const CARD_CLASSES = 'flex h-full flex-col gap-5 rounded-card border border-rule bg-card p-6 sm:p-7'

interface ToolCardProps {
  icon: ReactNode
  title: string
  text: string
  children: ReactNode
}

function ToolCard({ icon, title, text, children }: ToolCardProps) {
  return (
    <article className={CARD_CLASSES}>
      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-paper-alt text-ink-soft">
        {icon}
      </span>
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
        <Reveal className="min-w-0 lg:col-span-2">
          <ToolCard
            icon={<WaveIcon className="h-5 w-5" />}
            title="Événements sonores"
            text="Porte, pas, sirène, pluie : 50 sons du quotidien repérés fenêtre par fenêtre, avec leur moment."
          >
            <EventsStrip />
          </ToolCard>
        </Reveal>
        <Reveal className="min-w-0" delayMs={100}>
          <ToolCard
            icon={<EmotionIcon className="h-5 w-5" />}
            title="Émotions"
            text="Six émotions estimées sur les passages de parole, segment par segment."
          >
            <EmotionStage />
          </ToolCard>
        </Reveal>
        <Reveal className="min-w-0">
          <ToolCard
            icon={<TranscriptIcon className="h-5 w-5" />}
            title="Transcription"
            text="Le texte de ce qui est dit, horodaté, pensé pour le français et ses accents."
          >
            <TypingTranscript />
          </ToolCard>
        </Reveal>
        <Reveal className="min-w-0 lg:col-span-2" delayMs={100}>
          <ToolCard
            icon={<SpeakersIcon className="h-5 w-5" />}
            title="Locuteurs"
            text="Qui parle, et quand : chaque morceau de parole reçoit le nom d’une voix enregistrée avec son accord."
          >
            <SpeakerLanes />
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
