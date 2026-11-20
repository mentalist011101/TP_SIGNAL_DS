interface PagePlaceholderProps {
  title: string
  description: string
  requirements: string[]
}

// Page provisoire : annonce la fonctionnalité et les exigences de la spécification qu'elle
// couvrira, pour qu'une page encore vide paraisse voulue et non cassée.
export default function PagePlaceholder({
  title,
  description,
  requirements,
}: PagePlaceholderProps) {
  return (
    <section className="space-y-6">
      <h1 className="font-display text-3xl font-extrabold tracking-tight">{title}</h1>
      <div className="max-w-2xl space-y-4 rounded-card border border-dashed border-rule-strong bg-card p-6">
        <p className="label-mono text-ink-soft">Bientôt</p>
        <p className="text-ink-soft">{description}</p>
        <div className="flex flex-wrap gap-2">
          {requirements.map((requirement) => (
            <span
              key={requirement}
              className="rounded-btn bg-paper-alt px-2 py-0.5 font-mono text-xs text-ink-soft"
            >
              {requirement}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}
