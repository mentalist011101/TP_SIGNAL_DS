import { useEffect, useRef, type DragEvent } from 'react'
import AudioPicker from './AudioPicker.tsx'
import WaveformCanvas from './WaveformCanvas.tsx'

const CARD_CLASSES = 'rounded-card border border-rule bg-card p-5 shadow-card'

const DROP_ZONE_CLASSES =
  'flex min-h-80 flex-col items-center justify-center gap-5 rounded-card border border-dashed border-rule-strong bg-paper-alt/50 p-8 text-center'

// Hauteurs des barres de l'icône (en unités du dessin de 45 × 32).
const ICON_BAR_HEIGHTS = [8, 18, 28, 14, 24, 10, 20, 6]

type AudioHandler = (file: File) => void

// Clé qui change à chaque nouveau fichier (un enregistrement a toujours une date différente).
function fileKey(file: File): string {
  return `${file.name}-${file.lastModified}`
}

// Petite forme d'onde décorative, dans la couleur du texte discret.
function WaveIcon() {
  const bars = ICON_BAR_HEIGHTS.map((height, index) => {
    const x = index * 6
    const y = (32 - height) / 2
    return <rect key={x} x={x} y={y} width="3" height={height} rx="1.5" />
  })
  return (
    <svg
      viewBox="0 0 45 32"
      className="h-10 w-14 text-ink-faint"
      fill="currentColor"
      aria-hidden="true"
    >
      {bars}
    </svg>
  )
}

// Zone d'accueil : on y dépose un fichier, ou on passe par les deux boutons. Les limites sont
// rappelées pour éviter un refus prévisible du serveur (maquette, proposition 1).
function EmptyAudio({ onAudioSelected }: { onAudioSelected: AudioHandler }) {
  // Sans preventDefault, le navigateur ouvrirait le fichier au lieu de le donner à la page.
  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    const files = event.dataTransfer.files
    if (files.length === 0) {
      return
    }
    onAudioSelected(files[0])
  }

  return (
    <div className={DROP_ZONE_CLASSES} onDragOver={handleDragOver} onDrop={handleDrop}>
      <WaveIcon />
      <div className="space-y-1">
        <p className="font-display text-xl font-bold">Déposez un fichier audio ici</p>
        <p className="text-sm text-ink-soft">ou choisissez une source :</p>
      </div>
      <AudioPicker onAudioSelected={onAudioSelected} />
      <p className="font-mono text-xs text-ink-soft">
        wav, mp3, flac, ogg, webm, m4a · 5 min et 100 Mo maximum
      </p>
    </div>
  )
}

// Lecteur audio : l'URL locale (blob:) est créée pour le fichier, puis libérée quand il change.
function AudioPlayer({ file }: { file: File }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  useEffect(() => {
    const audio = audioRef.current
    if (audio === null) {
      return
    }
    const objectUrl = URL.createObjectURL(file)
    audio.src = objectUrl
    return () => {
      URL.revokeObjectURL(objectUrl)
    }
  }, [file])
  return <audio ref={audioRef} controls className="w-full" />
}

interface AudioPreviewProps {
  file: File
  onAudioSelected: AudioHandler
}

// Audio choisi : son nom, de quoi en changer, puis le lecteur et la forme d'onde.
function AudioPreview({ file, onAudioSelected }: AudioPreviewProps) {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="label-mono text-ink-faint">Audio choisi</p>
          <p className="font-mono text-lg break-all">{file.name}</p>
        </div>
        <AudioPicker onAudioSelected={onAudioSelected} />
      </div>
      <AudioPlayer file={file} />
      <WaveformCanvas file={file} />
    </div>
  )
}

interface AudioPanelProps {
  file: File | null
  onAudioSelected: AudioHandler
}

// Carte principale de la page Analyser : zone d'accueil, puis aperçu de l'audio choisi.
export default function AudioPanel({ file, onAudioSelected }: AudioPanelProps) {
  if (file === null) {
    return (
      <div className={CARD_CLASSES}>
        <EmptyAudio onAudioSelected={onAudioSelected} />
      </div>
    )
  }
  // Une clé par fichier : un nouvel audio repart d'un aperçu vierge.
  return (
    <div className={CARD_CLASSES}>
      <AudioPreview key={fileKey(file)} file={file} onAudioSelected={onAudioSelected} />
    </div>
  )
}
