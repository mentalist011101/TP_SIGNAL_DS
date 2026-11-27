import type { CSSProperties } from 'react'
import type { Analysis, SegmentResult } from '../../api/client.ts'
import { formatProbability } from './taskResult.ts'
import {
  doneResult,
  formatSeconds,
  percentOfDuration,
  segmentStyle,
  type SelectedSegment,
} from './timeline.ts'

// Frise temporelle (EF-12), sous le spectrogramme et sur le même axe du temps : la frise prend
// toute la largeur, comme l'image, et le nom de chaque rangée est écrit au-dessus d'elle.
// Tout vient des `segments` de l'API (R5) : le front ne fait que les placer.

// Remplissage d'une fenêtre d'événement : sa probabilité règle l'opacité, entre un plancher
// (sinon le bloc disparaît) et un plafond (au-delà, le texte posé dessus serait moins lisible).
const MIN_EVENT_OPACITY = 0.35
const MAX_FILL_OPACITY = 0.45

// Les fenêtres d'événements se chevauchent de moitié (5 s, pas de 2,5 s, D5) : elles
// alternent entre deux voies pour rester lisibles.
const EVENT_LANES = 2

// Hauteur d'une voie d'événements, en px.
const LANE_HEIGHT_PX = 32

const ROW_TITLE_CLASSES = 'label-mono text-ink-faint'
const BLOCK_CLASSES =
  'absolute top-0 bottom-0 overflow-hidden rounded-md border px-2 text-left text-xs whitespace-nowrap transition-colors duration-200 ease-out-soft'

interface TimelineProps {
  analysis: Analysis
  durationS: number
  currentTimeS: number
  selected: SelectedSegment | null
  onSelect: (segment: SelectedSegment, startS: number) => void
}

// Vrai si ce segment est celui qu'on a choisi.
function isSelected(
  selected: SelectedSegment | null,
  task: SelectedSegment['task'],
  index: number,
): boolean {
  if (selected === null) {
    return false
  }
  return selected.task === task && selected.index === index
}

// Bordure du bloc : accent s'il est choisi, filet sinon.
function blockBorder(isChosen: boolean): string {
  if (isChosen) {
    return 'border-accent ring-1 ring-accent'
  }
  return 'border-rule-strong hover:border-ink-soft'
}

// « Émotion Colère, de 5,3 s à 6,8 s, 97,5 % » : ce que lit un lecteur d'écran.
function segmentLabel(taskLabel: string, segment: SegmentResult): string {
  const start = formatSeconds(segment.start_s)
  const end = formatSeconds(segment.end_s)
  const probability = formatProbability(segment.probabilities[0].probability)
  return `${taskLabel} ${segment.label_fr}, de ${start} à ${end}, ${probability}`
}

// Rangée « Parole détectée » : là où la détection de parole (VAD, D5) a trouvé de la voix,
// c'est-à-dire les segments d'émotion.
function SpeechRow({ segments, durationS }: { segments: SegmentResult[]; durationS: number }) {
  return (
    <div className="space-y-1">
      <p className={ROW_TITLE_CLASSES}>Parole détectée</p>
      <div className="relative h-3 rounded-btn bg-paper-alt">
        {segments.map((segment, index) => (
          <span
            key={index}
            className="absolute top-0 bottom-0 rounded-btn bg-brand"
            style={segmentStyle(segment, durationS)}
          />
        ))}
      </div>
    </div>
  )
}

// Rangée « Émotion » : le libellé français de chaque segment ; un clic le choisit.
function EmotionRow(props: TimelineProps & { segments: SegmentResult[] }) {
  return (
    <div className="space-y-1">
      <p className={ROW_TITLE_CLASSES}>Émotion</p>
      <div className="relative h-8">
        {props.segments.map((segment, index) => {
          const isChosen = isSelected(props.selected, 'emotion', index)
          return (
            <button
              key={index}
              type="button"
              aria-pressed={isChosen}
              aria-label={segmentLabel('Émotion', segment)}
              title={segmentLabel('Émotion', segment)}
              className={`${BLOCK_CLASSES} bg-card ${blockBorder(isChosen)}`}
              style={segmentStyle(segment, props.durationS)}
              onClick={() => props.onSelect({ task: 'emotion', index }, segment.start_s)}
            >
              {segment.label_fr}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// Fond d'une fenêtre d'événement : d'autant plus opaque que le modèle est sûr de lui. Le
// pourcentage est aussi écrit dans le bloc : la couleur ne porte jamais seule l'information.
function eventFillStyle(segment: SegmentResult): CSSProperties {
  const probability = segment.probabilities[0].probability
  const strength = Math.max(probability, MIN_EVENT_OPACITY)
  const opacity = strength * MAX_FILL_OPACITY
  return { opacity }
}

// Place d'une fenêtre : sa voie (paire en haut, impaire en bas), puis ses bornes.
function laneStyle(segment: SegmentResult, index: number, durationS: number): CSSProperties {
  const lane = index % EVENT_LANES
  const top = lane * (LANE_HEIGHT_PX + 4)
  return { ...segmentStyle(segment, durationS), top: `${top}px`, height: `${LANE_HEIGHT_PX}px` }
}

// Rangée « Événement » : le premier choix de chaque fenêtre de 5 s, sur deux voies.
function EventRow(props: TimelineProps & { segments: SegmentResult[] }) {
  const rowHeight = EVENT_LANES * (LANE_HEIGHT_PX + 4)
  return (
    <div className="space-y-1">
      <p className={ROW_TITLE_CLASSES}>Événement (fenêtres de 5 s)</p>
      <div className="relative" style={{ height: `${rowHeight}px` }}>
        {props.segments.map((segment, index) => {
          const isChosen = isSelected(props.selected, 'sound_event', index)
          const percent = formatProbability(segment.probabilities[0].probability)
          return (
            <button
              key={index}
              type="button"
              aria-pressed={isChosen}
              aria-label={segmentLabel('Événement', segment)}
              title={segmentLabel('Événement', segment)}
              className={`${BLOCK_CLASSES} bottom-auto bg-card ${blockBorder(isChosen)}`}
              style={laneStyle(segment, index, props.durationS)}
              onClick={() => props.onSelect({ task: 'sound_event', index }, segment.start_s)}
            >
              <span
                className="absolute inset-0 bg-brand"
                style={eventFillStyle(segment)}
                aria-hidden="true"
              />
              <span className="relative">
                {segment.label_fr} <span className="font-mono text-ink-soft">{percent}</span>
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

// « Texte, de 0,5 s à 3 s : Bonjour à tous » : ce qu'affiche le survol et ce que lit un
// lecteur d'écran.
function textLabel(segment: SegmentResult): string {
  const start = formatSeconds(segment.start_s)
  const end = formatSeconds(segment.end_s)
  const text = segment.text ?? ''
  return `Texte, de ${start} à ${end} : ${text}`
}

// Rangée « Texte » (EF-10, EF-12) : un bloc par segment de transcription, à sa place dans le
// temps. Le bloc montre le début du texte ; le texte entier s'affiche au survol. Un clic
// place la lecture au début du segment.
function TextRow(props: TimelineProps & { segments: SegmentResult[] }) {
  return (
    <div className="space-y-1">
      <p className={ROW_TITLE_CLASSES}>Texte</p>
      <div className="relative h-8">
        {props.segments.map((segment, index) => {
          const isChosen = isSelected(props.selected, 'transcription', index)
          return (
            <button
              key={index}
              type="button"
              aria-pressed={isChosen}
              aria-label={textLabel(segment)}
              title={textLabel(segment)}
              className={`${BLOCK_CLASSES} truncate bg-paper-alt ${blockBorder(isChosen)}`}
              style={segmentStyle(segment, props.durationS)}
              onClick={() => props.onSelect({ task: 'transcription', index }, segment.start_s)}
            >
              {segment.text}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// Tête de lecture : un trait vertical à l'instant joué, sur toutes les rangées.
function Playhead({ currentTimeS, durationS }: { currentTimeS: number; durationS: number }) {
  const left = percentOfDuration(currentTimeS, durationS)
  const style: CSSProperties = { left: `${left}%` }
  return (
    <span
      className="pointer-events-none absolute top-0 bottom-0 w-0.5 bg-brand"
      style={style}
      aria-hidden="true"
    />
  )
}

// Rangée « Parole détectée » vide : l'émotion a été demandée, mais la VAD n'a rien trouvé.
function NoSpeechRow() {
  return (
    <div className="space-y-1">
      <p className={ROW_TITLE_CLASSES}>Parole détectée</p>
      <p className="text-sm text-ink-soft">Aucune parole détectée sur cet audio.</p>
    </div>
  )
}

// Vrai si l'émotion a été demandée et que l'API répond no_speech.
function hasNoSpeech(analysis: Analysis): boolean {
  if (analysis.results === null) {
    return false
  }
  const emotion = analysis.results.emotion
  return emotion !== undefined && emotion.status === 'no_speech'
}

// Frise complète : une rangée par information disponible, rien pour une tâche sans segments.
export default function Timeline(props: TimelineProps) {
  const emotion = doneResult(props.analysis, 'emotion')
  const soundEvent = doneResult(props.analysis, 'sound_event')
  const transcription = doneResult(props.analysis, 'transcription')
  const noSpeech = hasNoSpeech(props.analysis)
  if (emotion === null && soundEvent === null && transcription === null && !noSpeech) {
    return null
  }
  return (
    <div className="relative space-y-3">
      {noSpeech && <NoSpeechRow />}
      {emotion !== null && <SpeechRow segments={emotion.segments} durationS={props.durationS} />}
      {emotion !== null && <EmotionRow {...props} segments={emotion.segments} />}
      {soundEvent !== null && <EventRow {...props} segments={soundEvent.segments} />}
      {transcription !== null && <TextRow {...props} segments={transcription.segments} />}
      {/* Tête de lecture seulement une fois la lecture lancée ou un segment choisi. */}
      {props.currentTimeS > 0 && (
        <Playhead currentTimeS={props.currentTimeS} durationS={props.durationS} />
      )}
    </div>
  )
}
