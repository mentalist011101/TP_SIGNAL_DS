import ConsentBox from './ConsentBox.tsx'

// Consentement à l'enregistrement d'une voix (S6), texte de la version locuteurs-v1
// (SPEAKER_CONSENT_VERSION, speakerFormat.ts). Sans la case cochée, le bouton reste grisé et le
// serveur refuse de toute façon.

interface VoiceConsentProps {
  accepted: boolean
  disabled: boolean
  onAcceptedChange: (accepted: boolean) => void
}

export default function VoiceConsent({ accepted, disabled, onAcceptedChange }: VoiceConsentProps) {
  return (
    <ConsentBox
      checked={accepted}
      disabled={disabled}
      onChange={onAcceptedChange}
      label={
        <>
          <span className="font-semibold">Obligatoire.</span> J’ai lu ce texte, la personne
          enregistrée est d’accord et j’accepte que sa voix soit gardée.
        </>
      }
    >
      <p>
        Si vous acceptez, EchoLens garde dans sa base de données une empreinte de cette voix (192
        nombres calculés par le modèle ECAPA) et les extraits envoyés, pour reconnaître cette
        personne dans les analyses suivantes.
      </p>
      <p>
        La voix apparaît dans la liste ci-contre, d’où vous pouvez la supprimer à tout moment : sa
        suppression efface l’empreinte et les extraits. Sans votre accord, rien n’est enregistré.
      </p>
    </ConsentBox>
  )
}
