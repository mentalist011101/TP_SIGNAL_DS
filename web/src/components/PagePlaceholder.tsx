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
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="max-w-2xl text-slate-600 dark:text-slate-300">{description}</p>
      <p className="text-sm text-slate-500">
        Exigences couvertes : {requirements.join(', ')} · page à implémenter
      </p>
    </section>
  )
}
