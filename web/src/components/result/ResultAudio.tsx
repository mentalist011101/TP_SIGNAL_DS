import { useRef, useState } from 'react'
import type { Analysis } from '../../api/client.ts'
import SpectrogramView from '../analyze/SpectrogramView.tsx'
import SegmentDetails from './SegmentDetails.tsx'
import Timeline from './Timeline.tsx'
import type { SelectedSegment } from './timeline.ts'

// Écoute de l'audio conservé par le serveur, son spectrogramme log-Mel (EF-03, EF-04), puis la
// frise temporelle (EF-12) sur le même axe du temps. Tout vient de l'API : le front ne calcule
// rien sur le signal (R5).
export default function ResultAudio({ analysis }: { analysis: Analysis }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  const [currentTimeS, setCurrentTimeS] = useState(0)
  const [selected, setSelected] = useState<SelectedSegment | null>(null)

  // La tête de lecture de la frise suit l'audio.
  function handleTimeUpdate() {
    const audio = audioRef.current
    if (audio !== null) {
      setCurrentTimeS(audio.currentTime)
    }
  }

  // Un clic sur un segment : la lecture se place à son début, et ses probabilités s'affichent.
  function handleSelect(segment: SelectedSegment, startS: number) {
    const audio = audioRef.current
    if (audio !== null) {
      audio.currentTime = startS
    }
    setCurrentTimeS(startS)
    setSelected(segment)
  }

  const durationS = analysis.duration_s
  const hasTimeline = analysis.status === 'done' && durationS !== null
  return (
    <section className="space-y-3 rounded-card border border-rule bg-card p-5">
      <h2 className="text-base font-semibold">Écoute</h2>
      {analysis.audio_url !== null && (
        <audio
          ref={audioRef}
          src={analysis.audio_url}
          controls
          preload="metadata"
          className="w-full"
          onTimeUpdate={handleTimeUpdate}
        />
      )}
      <h2 className="text-base font-semibold">Spectrogramme et frise</h2>
      <SpectrogramView analysis={analysis} />
      {hasTimeline && (
        <div className="space-y-4 border-t border-rule pt-4">
          <Timeline
            analysis={analysis}
            durationS={durationS}
            currentTimeS={currentTimeS}
            selected={selected}
            onSelect={handleSelect}
          />
          <SegmentDetails analysis={analysis} selected={selected} />
        </div>
      )}
    </section>
  )
}
