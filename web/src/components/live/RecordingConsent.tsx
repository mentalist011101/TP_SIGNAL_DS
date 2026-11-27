import type { ChangeEvent } from 'react'

// Choix d'enregistrer la session dans l'Historique, avec le consentement écrit (ENF-10). Le
// texte a une version (CONSENT_VERSION, api/stream.ts) : le modifier oblige à changer la
// version, ici et dans configs/inference.yaml.

const CHECKBOX_CLASSES = 'mt-0.5 h-4 w-4 shrink-0 accent-accent'

interface RecordingConsentProps {
  record: boolean
  accepted: boolean
  disabled: boolean
  onRecordChange: (record: boolean) => void
  onAcceptedChange: (accepted: boolean) => void
}

// Texte du consentement, version direct-v1.
function ConsentText() {
  return (
    <div className="space-y-2 rounded-xl border border-rule bg-paper p-4 text-sm text-ink-soft">
      <p>
        Si vous acceptez, le son capté par votre micro pendant cette session est enregistré dans la
        base de données d’EchoLens, puis analysé comme un fichier importé : émotion, événements
        sonores et transcription. L’enregistrement dure au plus 5 minutes.
      </p>
      <p>
        Il apparaît dans l’Historique, d’où vous pouvez le supprimer à tout moment ; sa suppression
        efface aussi ce consentement. Sans votre accord, rien n’est enregistré.
      </p>
    </div>
  )
}

export default function RecordingConsent(props: RecordingConsentProps) {
  function handleRecordChange(event: ChangeEvent<HTMLInputElement>) {
    props.onRecordChange(event.target.checked)
  }

  function handleAcceptedChange(event: ChangeEvent<HTMLInputElement>) {
    props.onAcceptedChange(event.target.checked)
  }

  return (
    <div className="space-y-3">
      <label className="flex items-start gap-3 text-sm font-semibold">
        <input
          type="checkbox"
          className={CHECKBOX_CLASSES}
          checked={props.record}
          disabled={props.disabled}
          onChange={handleRecordChange}
        />
        Enregistrer cette session dans l’Historique
      </label>
      {props.record && (
        <div className="space-y-3 pl-7">
          <ConsentText />
          <label className="flex items-start gap-3 text-sm">
            <input
              type="checkbox"
              className={CHECKBOX_CLASSES}
              checked={props.accepted}
              disabled={props.disabled}
              onChange={handleAcceptedChange}
            />
            J’ai lu ce texte et j’accepte que ma voix soit enregistrée.
          </label>
        </div>
      )}
    </div>
  )
}
