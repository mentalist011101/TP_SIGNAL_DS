import type { ChangeEvent } from 'react'

// Enregistrer la session dans l'Historique, avec le consentement écrit (ENF-10). Une seule case
// accepte tout ; le texte complet se déplie pour le lire. Le texte a une version
// (CONSENT_VERSION, api/stream.ts) : le modifier oblige à changer la version, ici et dans
// configs/inference.yaml.

const CHECKBOX_CLASSES = 'mt-0.5 h-4 w-4 shrink-0 accent-accent'

interface RecordingConsentProps {
  // Vrai si la session sera enregistrée : la case cochée vaut aussi consentement.
  accepted: boolean
  disabled: boolean
  onAcceptedChange: (accepted: boolean) => void
}

// Texte du consentement, version direct-v1.
function ConsentText() {
  return (
    <div className="space-y-2 text-sm text-ink-soft">
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

export default function RecordingConsent({
  accepted,
  disabled,
  onAcceptedChange,
}: RecordingConsentProps) {
  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onAcceptedChange(event.target.checked)
  }

  return (
    <div className="space-y-3 rounded-xl border border-rule bg-paper p-4">
      <label className="flex items-start gap-3 text-sm">
        <input
          type="checkbox"
          className={CHECKBOX_CLASSES}
          checked={accepted}
          disabled={disabled}
          onChange={handleChange}
        />
        <span>
          <span className="font-semibold">Enregistrer cette session dans l’Historique.</span> J’ai
          lu les conditions et j’accepte que ma voix soit enregistrée.
        </span>
      </label>
      <details className="group pl-7">
        <summary className="cursor-pointer list-none text-sm font-semibold text-accent-ink hover:underline">
          <span className="group-open:hidden">Lire les conditions</span>
          <span className="hidden group-open:inline">Masquer les conditions</span>
        </summary>
        <div className="mt-3">
          <ConsentText />
        </div>
      </details>
    </div>
  )
}
