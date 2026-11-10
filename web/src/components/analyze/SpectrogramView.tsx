import { useState, type CSSProperties } from 'react'
import type { Analysis, FrequencyTick, SpectrogramInfo } from '../../api/client.ts'

const MESSAGE_CLASSES =
  'flex h-40 items-center justify-center rounded-md border border-dashed border-slate-300 text-sm text-slate-500 dark:border-slate-700'

// Étiquettes posées sur l'image : fond sombre pour rester lisibles sur toutes les couleurs.
const FREQUENCY_LABEL_CLASSES =
  'absolute left-1 rounded bg-black/60 px-1 text-[10px] leading-4 text-white'

// Pas des graduations de temps : 1 s jusqu'à 10 s, 10 s jusqu'à 60 s, 30 s au-delà.
const SHORT_AUDIO_MAX_S = 10
const MEDIUM_AUDIO_MAX_S = 60
const SHORT_AUDIO_STEP_S = 1
const MEDIUM_AUDIO_STEP_S = 10
const LONG_AUDIO_STEP_S = 30

interface TimeTick {
  seconds: number
  percent: number
}

interface SpectrogramViewProps {
  analysis: Analysis | undefined
}

// « 250 Hz », « 1 kHz », « 1,5 kHz » : au-delà de 1 000 Hz on passe en kHz.
function formatHz(hz: number): string {
  if (hz < 1000) {
    return `${hz} Hz`
  }
  const kiloHertz = hz / 1000
  const formatted = kiloHertz.toLocaleString('fr-FR', { maximumFractionDigits: 1 })
  return `${formatted} kHz`
}

// « −80 dB », « +40 dB » : signe toujours affiché, avec le vrai signe moins typographique.
function formatDb(db: number): string {
  const magnitude = Math.abs(db)
  if (db < 0) {
    return `−${magnitude} dB`
  }
  return `+${magnitude} dB`
}

// Écart entre deux graduations de temps, selon la durée de l'audio.
function timeTickStep(durationSeconds: number): number {
  if (durationSeconds <= SHORT_AUDIO_MAX_S) {
    return SHORT_AUDIO_STEP_S
  }
  if (durationSeconds <= MEDIUM_AUDIO_MAX_S) {
    return MEDIUM_AUDIO_STEP_S
  }
  return LONG_AUDIO_STEP_S
}

// Une graduation à chaque multiple du pas, placée à (t / durée) × 100 % de la largeur.
// L'image couvre toute la durée sur toute la largeur, comme la forme d'onde au-dessus.
function timeTicks(durationSeconds: number): TimeTick[] {
  const step = timeTickStep(durationSeconds)
  const ticks: TimeTick[] = []
  for (let seconds = 0; seconds <= durationSeconds; seconds += step) {
    const percent = (seconds / durationSeconds) * 100
    ticks.push({ seconds, percent })
  }
  return ticks
}

// Dégradé CSS de la légende, de la couleur de db_min (gauche) à celle de db_max (droite).
function legendGradient(stops: string[]): string {
  const colorList = stops.join(', ')
  return `linear-gradient(to right, ${colorList})`
}

// Étiquette de fréquence placée à position × 100 % depuis le BAS de l'image. Les valeurs
// viennent de l'API (échelle Mel) : aucun calcul Mel ici (R5).
function frequencyLabelStyle(tick: FrequencyTick): CSSProperties {
  const bottomPercent = tick.position * 100
  // Centrée verticalement sur sa graduation, sauf tout en haut où elle sortirait de l'image.
  let shift = '50%'
  if (tick.position >= 0.95) {
    shift = '100%'
  }
  return { bottom: `${bottomPercent}%`, transform: `translateY(${shift})` }
}

// Étiquette de temps centrée sur sa graduation, sauf aux deux bords où elle déborderait.
function timeLabelStyle(tick: TimeTick): CSSProperties {
  let shift = '-50%'
  if (tick.percent === 0) {
    shift = '0%'
  }
  if (tick.percent >= 95) {
    shift = '-100%'
  }
  return { left: `${tick.percent}%`, transform: `translateX(${shift})` }
}

// Image du serveur étirée à toute la largeur, avec l'axe des fréquences posé sur son bord gauche.
// Une analyse importée avant l'ajout du spectrogramme n'a pas d'image : le serveur répond 404.
function SpectrogramImage({ url, info }: { url: string; info: SpectrogramInfo }) {
  const [hasError, setHasError] = useState(false)
  if (hasError) {
    return <div className={MESSAGE_CLASSES}>Spectrogramme indisponible pour cette analyse</div>
  }
  return (
    <div className="relative h-40 w-full">
      <img
        src={url}
        alt="Spectrogramme log-Mel de l’audio analysé"
        className="h-40 w-full rounded-md"
        onError={() => setHasError(true)}
      />
      {info.frequency_ticks.map((tick) => (
        <span key={tick.hz} className={FREQUENCY_LABEL_CLASSES} style={frequencyLabelStyle(tick)}>
          {formatHz(tick.hz)}
        </span>
      ))}
    </div>
  )
}

// Axe du temps sous l'image, en secondes.
function TimeAxis({ durationSeconds }: { durationSeconds: number }) {
  const ticks = timeTicks(durationSeconds)
  return (
    <div className="relative h-4 w-full text-[10px] text-slate-500">
      {ticks.map((tick) => (
        <span key={tick.seconds} className="absolute top-0" style={timeLabelStyle(tick)}>
          {tick.seconds} s
        </span>
      ))}
    </div>
  )
}

// Légende des couleurs : dégradé de la palette, de db_min à gauche à db_max à droite.
function ColorLegend({ info }: { info: SpectrogramInfo }) {
  const gradientStyle = { backgroundImage: legendGradient(info.colormap_stops) }
  return (
    <div className="flex items-center gap-2 text-xs text-slate-500">
      <span>{formatDb(info.db_min)}</span>
      <div className="h-3 w-48 rounded" style={gradientStyle} />
      <span>{formatDb(info.db_max)}</span>
      <span>(énergie de chaque bande)</span>
    </div>
  )
}

interface SpectrogramFigureProps {
  url: string
  info: SpectrogramInfo
  durationSeconds: number
}

// Spectrogramme complet : image, axe des fréquences, axe du temps et légende.
function SpectrogramFigure({ url, info, durationSeconds }: SpectrogramFigureProps) {
  return (
    <div className="space-y-1">
      <SpectrogramImage url={url} info={info} />
      <TimeAxis durationSeconds={durationSeconds} />
      <ColorLegend info={info} />
    </div>
  )
}

// Spectrogramme log-Mel calculé par le serveur (EF-04, U6) : message d'attente tant que
// l'analyse n'est pas terminée, rien en cas d'échec (le statut en donne déjà la raison).
export default function SpectrogramView({ analysis }: SpectrogramViewProps) {
  if (analysis === undefined) {
    return <div className={MESSAGE_CLASSES}>Le spectrogramme apparaîtra après l’analyse</div>
  }
  if (analysis.status === 'failed') {
    return null
  }
  if (analysis.status !== 'done') {
    return <div className={MESSAGE_CLASSES}>Calcul du spectrogramme en cours…</div>
  }
  // En done, l'API remplit ces trois champs ; le test rassure TypeScript (types « | null »).
  const url = analysis.spectrogram_url
  const info = analysis.spectrogram
  const durationSeconds = analysis.duration_s
  if (url === null || info === null || durationSeconds === null) {
    return <div className={MESSAGE_CLASSES}>Spectrogramme indisponible pour cette analyse</div>
  }
  return <SpectrogramFigure url={url} info={info} durationSeconds={durationSeconds} />
}
