import { useEffect, useRef } from 'react'
import { readCssColor } from '../theme.ts'

// Ruban d'ondes décoratif (zone de dépôt d'Analyser) : des sinusoïdes qui glissent, plus
// amples au centre, comme une voix qui enfle puis retombe. Pure décoration (aria-hidden).

interface WaveLine {
  // Nombre de creux et de bosses sur la largeur.
  cycles: number
  // Vitesse de glissement, en tours par seconde.
  speed: number
  // Hauteur maximale, en part de la demi-hauteur du canvas.
  amplitude: number
  phase: number
  // Vrai pour la ligne en couleur de marque ; les autres sont discrètes.
  isBrand: boolean
}

const LINES: WaveLine[] = [
  { cycles: 3.2, speed: 0.16, amplitude: 0.85, phase: 0, isBrand: true },
  { cycles: 4.1, speed: -0.11, amplitude: 0.6, phase: 1.3, isBrand: false },
  { cycles: 2.4, speed: 0.08, amplitude: 0.7, phase: 2.6, isBrand: false },
  { cycles: 5.3, speed: 0.21, amplitude: 0.4, phase: 4.0, isBrand: false },
  { cycles: 3.7, speed: -0.18, amplitude: 0.5, phase: 5.1, isBrand: false },
]

// Écart entre deux points d'une courbe, en pixels.
const STEP_PX = 4
const LINE_WIDTH_PX = 1.5
const FAINT_OPACITY = 0.45

// Enveloppe en cloche : 0 aux bords, 1 au centre. Les ondes naissent et meurent sur les côtés.
function envelope(ratio: number): number {
  const distance = ratio - 0.5
  return Math.exp(-(distance * distance) / 0.045)
}

// Dessine une ligne à l'instant t, point par point, de gauche à droite.
function drawLine(context: CanvasRenderingContext2D, line: WaveLine, timeS: number): void {
  const width = context.canvas.width
  const middle = context.canvas.height / 2
  context.beginPath()
  for (let x = 0; x <= width; x += STEP_PX) {
    const ratio = x / width
    const angle = (ratio * line.cycles + timeS * line.speed) * 2 * Math.PI + line.phase
    const y = middle + Math.sin(angle) * line.amplitude * middle * envelope(ratio)
    if (x === 0) {
      context.moveTo(x, y)
    } else {
      context.lineTo(x, y)
    }
  }
  context.stroke()
}

// Une image : on efface, puis on trace chaque ligne avec les couleurs du thème en cours.
function drawFrame(context: CanvasRenderingContext2D, timeS: number): void {
  context.clearRect(0, 0, context.canvas.width, context.canvas.height)
  context.lineWidth = LINE_WIDTH_PX * window.devicePixelRatio
  const brandColor = readCssColor('--color-brand')
  const faintColor = readCssColor('--color-ink-faint')
  for (const line of LINES) {
    context.strokeStyle = faintColor
    context.globalAlpha = FAINT_OPACITY
    if (line.isBrand) {
      context.strokeStyle = brandColor
      context.globalAlpha = 1
    }
    drawLine(context, line, timeS)
  }
  context.globalAlpha = 1
}

// Le canvas suit la taille affichée (et la densité de l'écran), pour rester net.
function fitToDisplay(canvas: HTMLCanvasElement): void {
  const width = Math.round(canvas.clientWidth * window.devicePixelRatio)
  const height = Math.round(canvas.clientHeight * window.devicePixelRatio)
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width
    canvas.height = height
  }
}

// className règle la hauteur (h-40 par défaut).
export default function WaveRibbon({ className = 'h-40' }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (canvas === null) {
      return
    }
    const context = canvas.getContext('2d')
    if (context === null) {
      return
    }
    const startMs = performance.now()
    const render = () => {
      fitToDisplay(canvas)
      const timeS = (performance.now() - startMs) / 1000
      drawFrame(context, timeS)
    }

    // Moins d'animations demandé : une seule image, immobile.
    render()
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return
    }
    const animation = { frameId: 0 }
    const loop = () => {
      render()
      animation.frameId = window.requestAnimationFrame(loop)
    }
    animation.frameId = window.requestAnimationFrame(loop)
    return () => {
      window.cancelAnimationFrame(animation.frameId)
    }
  }, [])

  return <canvas ref={canvasRef} className={`block w-full ${className}`} aria-hidden="true" />
}
