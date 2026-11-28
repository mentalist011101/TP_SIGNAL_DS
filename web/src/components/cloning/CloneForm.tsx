import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { describeApiError, useCreateSynthesis, useSpeakers } from '../../api/client.ts'

// Demande de clonage (EF-18) : une voix qui a accepté le clonage, puis le texte à lui faire
// dire. Seules les voix avec la seconde case cochée sont proposées (ENF-10) ; le serveur le
// vérifie de nouveau.

// Longueur maximale du texte : configs/inference.yaml (voice_cloning.max_text_chars).
const MAX_TEXT_CHARS = 300

const FIELD_CLASSES =
  'w-full rounded-btn border border-rule-strong bg-card px-3 py-1.5 text-sm text-ink'
const SUBMIT_CLASSES =
  'w-full rounded-btn bg-accent px-5 py-2.5 font-semibold text-on-accent transition-colors duration-200 ease-out-soft hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-50'

export default function CloneForm() {
  const speakers = useSpeakers()
  const creation = useCreateSynthesis()
  const [speakerId, setSpeakerId] = useState('')
  const [text, setText] = useState('')

  const consenting = (speakers.data ?? []).filter((speaker) => speaker.cloning_allowed)
  if (speakers.data !== undefined && consenting.length === 0) {
    return (
      <p className="rounded-card border border-dashed border-rule-strong bg-card p-6 text-ink-soft">
        Aucune voix n’a accepté le clonage. Enregistrez-en une sur la page{' '}
        <Link to="/locuteurs" className="font-semibold text-accent-ink underline">
          Locuteurs
        </Link>
        , en cochant aussi la case du clonage.
      </p>
    )
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    creation.mutate({ speaker_id: speakerId, text })
  }

  const isDisabled = speakerId === '' || text.trim() === '' || creation.isPending
  return (
    <form className="space-y-5 rounded-card border border-rule bg-card p-5" onSubmit={handleSubmit}>
      <h2 className="text-base font-semibold">Nouvel extrait</h2>
      <label className="block space-y-1">
        <span className="label-mono text-ink-faint">Voix à cloner</span>
        <select
          className={FIELD_CLASSES}
          value={speakerId}
          onChange={(event) => setSpeakerId(event.target.value)}
        >
          <option value="">Choisir une voix consentante…</option>
          {consenting.map((speaker) => (
            <option key={speaker.id} value={speaker.id}>
              {speaker.name}
            </option>
          ))}
        </select>
      </label>
      <label className="block space-y-1">
        <span className="label-mono text-ink-faint">Texte à faire dire (français)</span>
        <textarea
          className={`${FIELD_CLASSES} min-h-28`}
          value={text}
          maxLength={MAX_TEXT_CHARS}
          onChange={(event) => setText(event.target.value)}
        />
        <span className="block text-right font-mono text-xs text-ink-soft">
          {text.length} / {MAX_TEXT_CHARS}
        </span>
      </label>
      <div className="space-y-2">
        <button type="submit" className={SUBMIT_CLASSES} disabled={isDisabled}>
          Générer la voix synthétique
        </button>
        {creation.error !== null && (
          <p className="text-sm text-danger">{describeApiError(creation.error)}</p>
        )}
      </div>
    </form>
  )
}
