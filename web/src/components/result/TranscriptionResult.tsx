import type { SegmentResult, TaskResult } from '../../api/client.ts'
import { formatSeconds } from './timeline.ts'

// Transcription (EF-10) : un texte par segment de parole, tel que l'API le renvoie (aucun appel
// direct au modèle depuis le front). Pas de classe ni de probabilités pour cette tâche.

// Un segment : « 0,5 s – 3 s », puis ce qui y a été dit. Un segment où le modèle n'a rien
// entendu (texte vide) le dit, plutôt que d'afficher une ligne vide.
function TranscriptSegment({ segment }: { segment: SegmentResult }) {
  const start = formatSeconds(segment.start_s)
  const end = formatSeconds(segment.end_s)
  const text = segment.text ?? ''
  return (
    <li className="grid gap-x-4 gap-y-1 py-2 sm:grid-cols-[9rem_1fr]">
      <span className="font-mono text-xs whitespace-nowrap text-ink-soft">
        {start} – {end}
      </span>
      {text !== '' && <p className="text-sm">{text}</p>}
      {text === '' && <p className="text-sm text-ink-faint">Rien d’intelligible.</p>}
    </li>
  )
}

// « Modèle : echolens-transcription-whisper-small, version 1.0.0 » : la transcription n'a pas
// de probabilités, donc pas de ligne de calibration.
function TranscriptModelLine({ result }: { result: TaskResult }) {
  return (
    <p className="text-xs text-ink-soft">
      Modèle : <span className="font-mono">{result.model_id}</span>, version{' '}
      <span className="font-mono">{result.model_version}</span>
    </p>
  )
}

// Liste des segments dans l'ordre du temps, puis le modèle utilisé.
export default function TranscriptionResult({ result }: { result: TaskResult }) {
  return (
    <>
      <ol className="divide-y divide-rule">
        {result.segments.map((segment, index) => (
          <TranscriptSegment key={index} segment={segment} />
        ))}
      </ol>
      <TranscriptModelLine result={result} />
    </>
  )
}
