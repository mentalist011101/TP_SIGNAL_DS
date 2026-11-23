import Reveal from './Reveal.tsx'

interface PipelineStep {
  title: string
  text: string
  decision: string
}

// La chaîne de traitement, telle que le serveur la fait (décisions de docs/specification.md).
const STEPS: PipelineStep[] = [
  {
    title: 'Audio',
    text: 'Un fichier ou le micro, jusqu’à 5 minutes et 100 Mo.',
    decision: 'D6',
  },
  {
    title: 'Décodage',
    text: 'ffmpeg le convertit en mono, 16 kHz, toujours de la même façon.',
    decision: 'D1, D2',
  },
  {
    title: 'Découpage',
    text: 'Fenêtres de 5 s qui se chevauchent de moitié pour les sons ; morceaux de parole trouvés par la VAD pour les émotions.',
    decision: 'D5',
  },
  {
    title: 'Représentation',
    text: 'Log-Mel pour la famille A, encodeur Whisper base gelé pour la famille B. Calculé par le serveur seulement.',
    decision: 'R2, R5',
  },
  {
    title: 'Modèles calibrés',
    text: 'Chaque modèle donne la probabilité de chaque classe ; ses scores sont divisés par une température T avant le softmax.',
    decision: 'ENF-06',
  },
  {
    title: 'Résultat',
    text: 'Moyenne des fenêtres pour les sons, moyenne pondérée par la durée pour les émotions, et chaque segment pour la frise.',
    decision: 'EF-05, EF-06, EF-12',
  },
]

// Section « chaîne de traitement » : les six étapes, de l'audio au résultat.
export default function Pipeline() {
  return (
    <section id="fonctionnement" className="mx-auto max-w-6xl space-y-12 px-6 py-24">
      <Reveal className="max-w-3xl space-y-4">
        <p className="label-mono text-ink-faint">Chaîne de traitement</p>
        <h2 className="font-display text-5xl leading-tight sm:text-6xl">
          De l’onde au résultat, <em className="text-ink-soft">étape par étape</em>.
        </h2>
      </Reveal>
      <Reveal>
        <ol className="grid gap-px overflow-hidden rounded-card border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-3">
          {STEPS.map((step, index) => (
            <li key={step.title} className="space-y-2 bg-paper p-6">
              <p className="flex items-baseline justify-between gap-3">
                <span className="font-mono text-xs text-ink-faint">Étape {index + 1}</span>
                <span className="font-mono text-xs text-ink-faint">{step.decision}</span>
              </p>
              <h3 className="text-lg font-semibold">{step.title}</h3>
              <p className="leading-relaxed text-ink-soft">{step.text}</p>
            </li>
          ))}
        </ol>
      </Reveal>
    </section>
  )
}
