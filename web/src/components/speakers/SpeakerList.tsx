import { useState } from 'react'
import { describeApiError, useDeleteSpeaker, useSpeakers, type Speaker } from '../../api/client.ts'
import { countLabel, formatDay, formatSpeech } from './speakerFormat.ts'

// Voix enregistrées (EF-11) : nom, date, parole utilisée, modèle, et suppression en deux
// temps (la voix et ses extraits sont effacés pour de bon).

const BUTTON_CLASSES =
  'rounded-btn border border-rule-strong bg-card px-3 py-1 text-sm text-ink transition-colors duration-200 ease-out-soft hover:bg-paper-alt disabled:opacity-50'
const MESSAGE_CLASSES =
  'rounded-card border border-dashed border-rule-strong bg-card p-6 text-center text-ink-soft'

// Premier clic : demande confirmation ; second clic : supprime.
function DeleteSpeaker({ speaker }: { speaker: Speaker }) {
  const [isConfirming, setIsConfirming] = useState(false)
  const deletion = useDeleteSpeaker()
  if (!isConfirming) {
    return (
      <button type="button" className={BUTTON_CLASSES} onClick={() => setIsConfirming(true)}>
        Supprimer
      </button>
    )
  }
  return (
    <div className="space-y-1">
      <p className="text-sm">Supprimer la voix de {speaker.name} et ses extraits ?</p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className={`${BUTTON_CLASSES} font-semibold`}
          disabled={deletion.isPending}
          onClick={() => deletion.mutate(speaker.id)}
        >
          Oui, supprimer
        </button>
        <button
          type="button"
          className={BUTTON_CLASSES}
          disabled={deletion.isPending}
          onClick={() => setIsConfirming(false)}
        >
          Annuler
        </button>
      </div>
      {deletion.error !== null && (
        <p className="text-sm text-danger">{describeApiError(deletion.error)}</p>
      )}
    </div>
  )
}

// Une voix : son nom, puis ce qui la compose et le modèle qui l'a calculée.
function SpeakerItem({ speaker }: { speaker: Speaker }) {
  const pieces = countLabel(speaker.segment_count, 'morceau', 'morceaux')
  const clips = countLabel(speaker.audio_count, 'extrait', 'extraits')
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 rounded-card border border-rule bg-card p-4">
      <div className="space-y-1">
        <p className="font-semibold">{speaker.name}</p>
        <p className="text-sm text-ink-soft">
          {formatSpeech(speaker.speech_s)} de parole · {pieces} · {clips} ·{' '}
          {formatDay(speaker.created_at)}
        </p>
        <p className="text-xs text-ink-soft">
          Modèle <span className="font-mono">{speaker.model_id}</span> · consentement{' '}
          <span className="font-mono">{speaker.consent_version}</span>
          {speaker.cloning_allowed && ' · clonage accepté'}
        </p>
      </div>
      <DeleteSpeaker speaker={speaker} />
    </li>
  )
}

export default function SpeakerList() {
  const speakers = useSpeakers()
  let content = <p className="text-sm text-ink-soft">Chargement des voix…</p>
  if (speakers.error !== null) {
    content = <p className="text-sm text-danger">{describeApiError(speakers.error)}</p>
  }
  if (speakers.data !== undefined && speakers.data.length === 0) {
    content = (
      <p className={MESSAGE_CLASSES}>
        Aucune voix enregistrée : dans une analyse, tous les locuteurs seront « Inconnu ».
      </p>
    )
  }
  if (speakers.data !== undefined && speakers.data.length > 0) {
    content = (
      <ul className="space-y-3">
        {speakers.data.map((speaker) => (
          <SpeakerItem key={speaker.id} speaker={speaker} />
        ))}
      </ul>
    )
  }
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">Voix enregistrées</h2>
      {content}
    </section>
  )
}
