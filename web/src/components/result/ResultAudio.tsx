import type { Analysis } from '../../api/client.ts'
import SpectrogramView from '../analyze/SpectrogramView.tsx'

// Écoute de l'audio conservé par le serveur, puis son spectrogramme log-Mel (EF-03, EF-04).
// Les deux viennent de l'API : le front ne calcule rien sur le signal (R5).
export default function ResultAudio({ analysis }: { analysis: Analysis }) {
  return (
    <section className="space-y-3 rounded-card border border-rule bg-card p-5">
      <h2 className="text-base font-semibold">Écoute</h2>
      {analysis.audio_url !== null && (
        <audio src={analysis.audio_url} controls preload="metadata" className="w-full" />
      )}
      <h2 className="text-base font-semibold">Spectrogramme</h2>
      <SpectrogramView analysis={analysis} />
    </section>
  )
}
