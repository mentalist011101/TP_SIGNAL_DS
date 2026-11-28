// Compte affiché en haut à droite de l'application. Indicatif seulement : il n'y a pas encore de
// connexion. Il montre la place que prendra le compte quand la page de connexion existera ; ce
// compte de démonstration n'ouvre et ne protège rien.

const DEMO_ACCOUNT = {
  name: 'Luciano Fokouo',
  initials: 'LF',
}

interface AccountChipProps {
  // Version courte (téléphone) : l'avatar seul.
  compact?: boolean
}

export default function AccountChip({ compact = false }: AccountChipProps) {
  const avatar = (
    <span
      className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold text-on-accent"
      aria-hidden="true"
    >
      {DEMO_ACCOUNT.initials}
    </span>
  )
  const label = `${DEMO_ACCOUNT.name}, compte de démonstration : la connexion arrive bientôt`
  if (compact) {
    return (
      <span title={label} aria-label={label}>
        {avatar}
      </span>
    )
  }
  return (
    <span
      className="flex items-center gap-3 rounded-btn border border-rule bg-card py-1 pr-4 pl-1"
      title={label}
    >
      {avatar}
      <span className="leading-tight">
        <span className="block text-sm font-semibold">{DEMO_ACCOUNT.name}</span>
        <span className="block text-[11px] text-ink-faint">Compte de démonstration</span>
      </span>
    </span>
  )
}
