import { useEffect, useRef } from 'react'
import { MAGMA_STOPS } from '../../theme.ts'
import type { DemoMood } from './demoMoods.ts'

// Illustration seulement : ce spectrogramme est fabriqué par des sinus, il ne vient d'aucun
// audio. Les vrais spectrogrammes sont calculés par le serveur (U6, R5).

// Taille du dessin en pixels ; le CSS l'étire à la largeur de la carte.
const CANVAS_WIDTH = 720
const CANVAS_HEIGHT = 240

// Défilement : 2 pixels par image, soit environ 6 secondes visibles à 60 images par seconde.
const PIXELS_PER_FRAME = 2
const FRAME_DURATION_S = 1 / 60
const FRAMES_PER_SCREEN = CANVAS_WIDTH / PIXELS_PER_FRAME

// Trois bandes de fréquence, comme les formants d'une voix : hauteur de repos (pixels depuis
// le bas), vitesse et décalage de leur va-et-vient, force. Leurs vitesses diffèrent : quand
// l'une monte, une autre descend.
const FORMANTS = [
  { base: 52, speed: 1.3, phase: 0, strength: 1 },
  { base: 118, speed: 0.9, phase: 2.1, strength: 0.75 },
  { base: 178, speed: 1.7, phase: 4.2, strength: 0.5 },
]
const FORMANT_WIDTH_PX = 16

// Bruit de fond : un silence reste presque noir, avec un léger grain aléatoire.
const NOISE_FLOOR = 0.02
const NOISE_GRAIN = 0.05

type Rgb = [number, number, number]

// Couleur magma d'une intensité entre 0 et 1 : mélange des deux couleurs voisines.
function magmaColor(intensity: number): Rgb {
  const clamped = Math.min(Math.max(intensity, 0), 1)
  const position = clamped * (MAGMA_STOPS.length - 1)
  const lowerIndex = Math.floor(position)
  const upperIndex = Math.min(lowerIndex + 1, MAGMA_STOPS.length - 1)
  const ratio = position - lowerIndex
  const lower = MAGMA_STOPS[lowerIndex]
  const upper = MAGMA_STOPS[upperIndex]
  const red = lower[0] + (upper[0] - lower[0]) * ratio
  const green = lower[1] + (upper[1] - lower[1]) * ratio
  const blue = lower[2] + (upper[2] - lower[2]) * ratio
  return [red, green, blue]
}

// Volume de la voix à l'instant t : des syllabes qui s'allument, puis de courts silences. Deux
// rythmes mêlés, pour que les syllabes n'aient pas toutes la même longueur.
function syllableVolume(timeS: number, mood: DemoMood): number {
  const fastWave = Math.sin(timeS * mood.syllableRate * Math.PI)
  const slowWave = Math.sin(timeS * mood.syllableRate * 0.37 * Math.PI + 1)
  const mixed = 0.7 * fastWave + 0.3 * slowWave
  const positivePart = Math.max(mixed, 0)
  return positivePart
}

// Énergie des trois bandes à une hauteur donnée : chaque bande est une bosse en cloche dont le
// centre monte et descend avec le temps.
function formantEnergy(heightPx: number, timeS: number, mood: DemoMood): number {
  let energy = 0
  for (const formant of FORMANTS) {
    const swing = mood.formantSwing * Math.sin(timeS * formant.speed + formant.phase)
    const center = formant.base + swing
    const distance = heightPx - center
    const bump = Math.exp(-(distance * distance) / (2 * FORMANT_WIDTH_PX * FORMANT_WIDTH_PX))
    energy += formant.strength * bump
  }
  return energy
}

// Intensité d'un point (0 à 1) : bandes rayées par les harmoniques, graves un peu renforcés.
function intensityAt(heightPx: number, timeS: number, mood: DemoMood): number {
  const bands = formantEnergy(heightPx, timeS, mood)
  const harmonicPhase = (heightPx / mood.harmonicSpacing) * 2 * Math.PI
  const harmonics = 0.6 + 0.4 * Math.cos(harmonicPhase)
  const lowBoost = 0.35 * Math.exp(-heightPx / 90)
  const voice = (bands * harmonics + lowBoost) * syllableVolume(timeS, mood)
  const grain = NOISE_GRAIN * Math.random()
  return NOISE_FLOOR + grain + voice
}

// Remplit la colonne neuve (PIXELS_PER_FRAME de large), du haut vers le bas de l'image.
function fillColumn(column: ImageData, timeS: number, mood: DemoMood): void {
  for (let row = 0; row < CANVAS_HEIGHT; row++) {
    const heightPx = CANVAS_HEIGHT - 1 - row
    const color = magmaColor(intensityAt(heightPx, timeS, mood))
    for (let x = 0; x < PIXELS_PER_FRAME; x++) {
      const offset = (row * PIXELS_PER_FRAME + x) * 4
      column.data[offset] = color[0]
      column.data[offset + 1] = color[1]
      column.data[offset + 2] = color[2]
      column.data[offset + 3] = 255
    }
  }
}

// Une image de l'animation : tout glisse à gauche, puis la colonne neuve arrive à droite.
function drawFrame(
  context: CanvasRenderingContext2D,
  column: ImageData,
  timeS: number,
  mood: DemoMood,
): void {
  context.drawImage(context.canvas, -PIXELS_PER_FRAME, 0)
  fillColumn(column, timeS, mood)
  context.putImageData(column, CANVAS_WIDTH - PIXELS_PER_FRAME, 0)
}

// Vrai si le système demande moins d'animations : on montre alors une image fixe.
function prefersReducedMotion(): boolean {
  const query = window.matchMedia('(prefers-reduced-motion: reduce)')
  return query.matches
}

// Spectrogramme qui défile. L'humeur passe par une ref : en changer ne relance pas
// l'animation, seules les colonnes suivantes prennent la nouvelle allure.
export default function SpectrogramAnimation({ mood }: { mood: DemoMood }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const moodRef = useRef(mood)

  useEffect(() => {
    moodRef.current = mood
  }, [mood])

  useEffect(() => {
    const canvas = canvasRef.current
    if (canvas === null) {
      return
    }
    const context = canvas.getContext('2d')
    if (context === null) {
      return
    }
    const column = context.createImageData(PIXELS_PER_FRAME, CANVAS_HEIGHT)
    let timeS = 0

    const step = () => {
      timeS += FRAME_DURATION_S
      drawFrame(context, column, timeS, moodRef.current)
    }

    // Étape 1 : un écran complet tout de suite, pour ne jamais montrer un cadre vide.
    for (let frame = 0; frame < FRAMES_PER_SCREEN; frame++) {
      step()
    }
    if (prefersReducedMotion()) {
      return
    }

    // Étape 2 : une colonne neuve à chaque image de l'écran.
    // L'identifiant de la prochaine image est rangé dans un objet : la boucle le met à jour,
    // le nettoyage le lit pour arrêter l'animation quand la page change.
    const animation = { frameId: 0 }
    const loop = () => {
      step()
      animation.frameId = window.requestAnimationFrame(loop)
    }
    animation.frameId = window.requestAnimationFrame(loop)
    return () => {
      window.cancelAnimationFrame(animation.frameId)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      width={CANVAS_WIDTH}
      height={CANVAS_HEIGHT}
      className="h-60 w-full rounded-xl lg:h-72"
      aria-hidden="true"
    />
  )
}
