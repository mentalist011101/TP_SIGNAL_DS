// Un extrait de voix de la page Locuteurs : son fichier, un nom lisible et sa durée (null tant
// qu'elle est inconnue).
export interface VoiceClip {
  file: File
  label: string
  durationS: number | null
}

// Durée totale des extraits dont la durée est connue.
export function totalDuration(clips: VoiceClip[]): number {
  let total = 0
  for (const clip of clips) {
    if (clip.durationS !== null) {
      total += clip.durationS
    }
  }
  return total
}
