import type { ChangeEvent, ReactNode } from 'react'

// Case de consentement compacte (S6, ENF-10) : la phrase à cocher, puis le texte complet dans un
// bloc dépliable. Sert aux deux consentements de la page Locuteurs.

interface ConsentBoxProps {
  checked: boolean
  disabled: boolean
  onChange: (checked: boolean) => void
  // Phrase à côté de la case.
  label: ReactNode
  // Texte complet, déplié à la demande.
  children: ReactNode
}

export default function ConsentBox({
  checked,
  disabled,
  onChange,
  label,
  children,
}: ConsentBoxProps) {
  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    onChange(event.target.checked)
  }

  return (
    <div className="space-y-2 rounded-xl border border-rule bg-paper p-4 has-checked:border-rule-strong">
      <label className="flex items-start gap-3 text-sm">
        <input
          type="checkbox"
          className="mt-0.5 h-4 w-4 shrink-0 accent-accent"
          checked={checked}
          disabled={disabled}
          onChange={handleChange}
        />
        <span>{label}</span>
      </label>
      <details className="group pl-7">
        <summary className="cursor-pointer list-none text-sm font-semibold text-accent-ink hover:underline">
          <span className="group-open:hidden">Lire le texte</span>
          <span className="hidden group-open:inline">Masquer le texte</span>
        </summary>
        <div className="mt-2 space-y-2 text-sm text-ink-soft">{children}</div>
      </details>
    </div>
  )
}
