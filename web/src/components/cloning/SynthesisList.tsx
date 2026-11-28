import { useState } from 'react'
import {
  describeApiError,
  useDeleteSynthesis,
  useSyntheses,
  type Synthesis,
} from '../../api/client.ts'
import { formatComputeTime } from '../compare/compareFormat.ts'
import { formatSeconds } from '../result/timeline.ts'

// Extraits synthétiques gardés (EF-18) : chacun dit qu'il est une voix synthétique, quelle voix
// il imite et quel texte elle dit ; on peut le réécouter, le télécharger ou le supprimer. Les
// extraits préparés avant une démo se rejouent sans recharger XTTS.

const BUTTON_CLASSES =
  'rounded-btn border border-rule-strong bg-card px-3 py-1 text-sm text-ink transition-colors duration-200 ease-out-soft hover:bg-paper-alt disabled:opacity-50'
const MESSAGE_CLASSES =
  'rounded-card border border-dashed border-rule-strong bg-card p-6 text-center text-ink-soft'
const SYNTHETIC_BADGE_CLASSES =
  'label-mono rounded-btn border border-accent px-2 py-0.5 font-semibold text-accent-ink'

// « 27 nov. 2026, 14:05 » : date et heure de la synthèse.
function formatDate(isoDate: string): string {
  const date = new Date(isoDate)
  return date.toLocaleString('fr-FR', { dateStyle: 'medium', timeStyle: 'short' })
}

// Lecteur et lien de téléchargement, ou l'état du calcul.
function SynthesisAudio({ synthesis }: { synthesis: Synthesis }) {
  if (synthesis.status === 'failed') {
    return <p className="text-sm text-danger">{synthesis.error_message}</p>
  }
  if (synthesis.audio_url === null) {
    return (
      <p className="text-sm text-ink-soft" aria-live="polite">
        Synthèse en cours… Le premier clonage charge XTTS-v2, ce qui peut prendre une minute.
      </p>
    )
  }
  return (
    <div className="flex flex-wrap items-center gap-3">
      <audio controls src={synthesis.audio_url} className="w-full max-w-md" />
      <a
        href={synthesis.audio_url}
        download={synthesis.download_name}
        className="text-sm font-semibold text-accent-ink hover:underline"
      >
        Télécharger
      </a>
    </div>
  )
}

// « 4,2 s · 12,80 s de calcul · xtts-v2 » sous le texte.
function SynthesisDetails({ synthesis }: { synthesis: Synthesis }) {
  const parts = [formatDate(synthesis.created_at)]
  if (synthesis.duration_s !== null) {
    parts.push(formatSeconds(synthesis.duration_s))
  }
  if (synthesis.compute_s !== null) {
    parts.push(`${formatComputeTime(synthesis.compute_s)} de calcul`)
  }
  parts.push(synthesis.model_id)
  return <p className="font-mono text-xs text-ink-soft">{parts.join(' · ')}</p>
}

// Suppression en deux temps.
function DeleteSynthesis({ synthesis }: { synthesis: Synthesis }) {
  const [isConfirming, setIsConfirming] = useState(false)
  const deletion = useDeleteSynthesis()
  if (!isConfirming) {
    return (
      <button type="button" className={BUTTON_CLASSES} onClick={() => setIsConfirming(true)}>
        Supprimer
      </button>
    )
  }
  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        type="button"
        className={`${BUTTON_CLASSES} font-semibold`}
        disabled={deletion.isPending}
        onClick={() => deletion.mutate(synthesis.id)}
      >
        Oui, supprimer
      </button>
      <button type="button" className={BUTTON_CLASSES} onClick={() => setIsConfirming(false)}>
        Annuler
      </button>
    </div>
  )
}

function SynthesisItem({ synthesis }: { synthesis: Synthesis }) {
  return (
    <li className="space-y-3 rounded-card border border-rule bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex flex-wrap items-center gap-2">
          <span className={SYNTHETIC_BADGE_CLASSES}>Voix synthétique</span>
          <span className="font-semibold">imite {synthesis.speaker_name}</span>
        </p>
        <DeleteSynthesis synthesis={synthesis} />
      </div>
      <p className="text-sm">« {synthesis.text} »</p>
      <SynthesisDetails synthesis={synthesis} />
      <SynthesisAudio synthesis={synthesis} />
    </li>
  )
}

export default function SynthesisList() {
  const syntheses = useSyntheses()
  let content = <p className="text-sm text-ink-soft">Chargement des extraits…</p>
  if (syntheses.error !== null) {
    content = <p className="text-sm text-danger">{describeApiError(syntheses.error)}</p>
  }
  if (syntheses.data !== undefined && syntheses.data.length === 0) {
    content = <p className={MESSAGE_CLASSES}>Aucun extrait synthétique pour l’instant.</p>
  }
  if (syntheses.data !== undefined && syntheses.data.length > 0) {
    content = (
      <ul className="space-y-3">
        {syntheses.data.map((synthesis) => (
          <SynthesisItem key={synthesis.id} synthesis={synthesis} />
        ))}
      </ul>
    )
  }
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">Extraits synthétiques</h2>
      {content}
    </section>
  )
}
