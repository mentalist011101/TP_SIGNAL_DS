import { useEffect, useRef, useState } from 'react'
import { readCssColor } from '../../theme.ts'

// Résolution interne du dessin, en pixels ; le canvas est ensuite étiré à la largeur de la page.
const CANVAS_WIDTH = 1000
const CANVAS_HEIGHT = 160

// Couleurs du dessin : le canvas ne connaît pas les classes Tailwind, on lit donc les jetons de
// la charte (fond night, tracé accent-soft) au moment de dessiner.
const BACKGROUND_TOKEN = '--color-night'
const WAVE_TOKEN = '--color-accent-soft'

// Hauteur minimale d'un trait, pour qu'un silence reste visible sous la forme d'une ligne.
const MIN_STROKE_HEIGHT = 1

interface SampleRange {
  min: number
  max: number
}

interface WaveformCanvasProps {
  file: File
}

// Décode le fichier et renvoie les échantillons du premier canal, entre -1 et 1.
// L'AudioContext est fermé même si le décodage échoue (finally).
async function decodeFirstChannel(file: File): Promise<Float32Array> {
  const audioContext = new AudioContext()
  try {
    const encodedBytes = await file.arrayBuffer()
    const decoded = await audioContext.decodeAudioData(encodedBytes)
    return decoded.getChannelData(0)
  } finally {
    await audioContext.close()
  }
}

// Plus petit et plus grand échantillon entre les indices start (inclus) et end (exclu).
function findMinMax(samples: Float32Array, start: number, end: number): SampleRange {
  let min = samples[start]
  let max = samples[start]
  for (let index = start; index < end; index++) {
    const value = samples[index]
    if (value < min) {
      min = value
    }
    if (value > max) {
      max = value
    }
  }
  return { min, max }
}

// Paquet d'échantillons représenté par la colonne de pixels x : la colonne x couvre
// la fraction [x / width, (x + 1) / width[ du signal.
function columnRange(samples: Float32Array, x: number, width: number): SampleRange {
  const start = Math.floor((x * samples.length) / width)
  let end = Math.floor(((x + 1) * samples.length) / width)
  // Moins d'échantillons que de pixels : on prend au moins un échantillon.
  if (end <= start) {
    end = start + 1
  }
  return findMinMax(samples, start, end)
}

// Position verticale d'un échantillon : +1 en haut du canvas, 0 au milieu, -1 en bas.
function sampleToY(value: number, height: number): number {
  const halfHeight = height / 2
  const offset = value * halfHeight
  return halfHeight - offset
}

// Trace, pour chaque colonne de pixels, un trait vertical du min au max de son paquet.
function drawWaveform(context: CanvasRenderingContext2D, samples: Float32Array): void {
  const width = context.canvas.width
  const height = context.canvas.height
  context.fillStyle = readCssColor(BACKGROUND_TOKEN)
  context.fillRect(0, 0, width, height)
  context.strokeStyle = readCssColor(WAVE_TOKEN)
  context.beginPath()
  for (let x = 0; x < width; x++) {
    const range = columnRange(samples, x, width)
    const top = sampleToY(range.max, height)
    const rawBottom = sampleToY(range.min, height)
    const bottom = Math.max(rawBottom, top + MIN_STROKE_HEIGHT)
    // + 0,5 : le trait est centré sur le pixel, sinon il bave sur deux colonnes.
    const column = x + 0.5
    context.moveTo(column, top)
    context.lineTo(column, bottom)
  }
  context.stroke()
}

// Décode puis dessine ; lève une erreur si le navigateur ne fournit pas de contexte 2D.
async function paintWaveform(file: File, canvas: HTMLCanvasElement): Promise<void> {
  const samples = await decodeFirstChannel(file)
  if (samples.length === 0) {
    throw new Error('Audio vide')
  }
  const context = canvas.getContext('2d')
  if (context === null) {
    throw new Error('Contexte 2D indisponible')
  }
  drawWaveform(context, samples)
}

// Forme d'onde de l'audio choisi : simple affichage des échantillons, ce n'est pas une
// feature (R5). La page remonte le composant (key) à chaque nouveau fichier.
export default function WaveformCanvas({ file }: WaveformCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    const canvas = canvasRef.current
    if (canvas === null) {
      return
    }
    paintWaveform(file, canvas).catch(() => {
      setHasError(true)
    })
  }, [file])

  if (hasError) {
    return (
      <p className="text-sm text-danger">Impossible de dessiner la forme d’onde de cet audio.</p>
    )
  }
  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_WIDTH}
      height={CANVAS_HEIGHT}
      className="h-40 w-full rounded-card"
    />
  )
}
