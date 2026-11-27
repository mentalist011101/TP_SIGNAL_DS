import type { ChangeEvent } from 'react'

// Seconde case, facultative : accord pour que la voix soit aussi clonée (C35, EF-18, ENF-10).
// Cloner est un usage plus fort que reconnaître : il a son propre texte, version clonage-v1
// (CLONING_CONSENT_VERSION, speakerFormat.ts, et configs/inference.yaml).

interface CloningConsentProps {
  accepted: boolean
  disabled: boolean
  onAcceptedChange: (accepted: boolean) => void
}

export default function CloningConsent({
  accepted,
  disabled,
  onAcceptedChange,
}: CloningConsentProps) {
  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onAcceptedChange(event.target.checked)
  }

  return (
    <div className="space-y-3">
      <div className="space-y-2 rounded-xl border border-rule bg-paper p-4 text-sm text-ink-soft">
        <p>
          Facultatif. Si vous acceptez aussi le clonage, la page Cloner pourra faire dire un texte à
          cette voix avec le modèle XTTS-v2, à partir des extraits envoyés ici. Chaque extrait
          produit commence par un bip et est marqué « voix synthétique » ; il est gardé avec son
          texte et sa date.
        </p>
        <p>
          Supprimer la voix supprime aussi tous ses extraits synthétiques. Sans cette case, la voix
          sert seulement à reconnaître la personne.
        </p>
      </div>
      <label className="flex items-start gap-3 text-sm">
        <input
          type="checkbox"
          className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
          checked={accepted}
          disabled={disabled}
          onChange={handleChange}
        />
        La personne enregistrée accepte aussi que sa voix soit clonée.
      </label>
    </div>
  )
}
