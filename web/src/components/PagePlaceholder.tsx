interface PagePlaceholderProps {
  title: string
  description: string
  requirements: string[]
}

// Page provisoire : rappelle l'objectif et les exigences de la spécification à implémenter.
export default function PagePlaceholder({
  title,
  description,
  requirements,
}: PagePlaceholderProps) {
  return (
    <section className="space-y-4">
      <h1 className="font-display text-3xl font-extrabold tracking-tight">{title}</h1>
      <p className="max-w-2xl text-ink-soft">{description}</p>
      <p className="text-sm text-ink-faint">
        Exigences couvertes : {requirements.join(', ')} · page à implémenter
      </p>
    </section>
  )
}
