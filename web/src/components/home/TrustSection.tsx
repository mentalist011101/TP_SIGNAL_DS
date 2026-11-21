import Reveal from './Reveal.tsx'

interface Dataset {
  name: string
  role: string
}

interface Commitment {
  title: string
  text: string
}

// Jeux de données du protocole (docs/datasets.md) et leur rôle.
const DATASETS: Dataset[] = [
  { name: 'CREMA-D', role: 'Émotions · entraînement' },
  { name: 'RAVDESS', role: 'Émotions · entraînement' },
  { name: 'ESC-50', role: 'Événements · 5 folds' },
  { name: 'CaFE', role: 'Test en français' },
  { name: 'African Accented French', role: 'Test sur accents africains' },
]

// Ce que l'application fait vraiment des audios (S6, suppression en base et sur disque).
const COMMITMENTS: Commitment[] = [
  {
    title: 'Vos audios restent chez vous',
    text: 'EchoLens tourne sur votre serveur : les audios et les résultats y sont stockés, et ne partent vers aucun service tiers.',
  },
  {
    title: 'Supprimés quand vous voulez',
    text: 'Une analyse supprimée l’est vraiment : la ligne en base, l’audio et le spectrogramme.',
  },
  {
    title: 'Des modèles évalués honnêtement',
    text: 'Aucun locuteur commun entre entraînement et test, des folds officiels jamais remélangés.',
  },
]

// Section confiance : d'où viennent les modèles, et ce qu'on fait de vos audios.
export default function TrustSection() {
  return (
    <section className="mx-auto max-w-6xl space-y-14 px-6 py-24">
      <Reveal className="space-y-6 text-center">
        <p className="label-mono text-ink-faint">Construit sur des jeux de données publics</p>
        <ul className="flex flex-wrap justify-center gap-x-10 gap-y-6">
          {DATASETS.map((dataset) => (
            <li key={dataset.name} className="space-y-1">
              <span className="block font-display text-3xl">{dataset.name}</span>
              <span className="block font-mono text-xs text-ink-faint">{dataset.role}</span>
            </li>
          ))}
        </ul>
      </Reveal>
      <Reveal>
        <ul className="grid gap-px overflow-hidden rounded-card border border-rule bg-rule md:grid-cols-3">
          {COMMITMENTS.map((commitment) => (
            <li key={commitment.title} className="space-y-3 bg-paper p-8">
              <h3 className="text-lg font-semibold">{commitment.title}</h3>
              <p className="leading-relaxed text-ink-soft">{commitment.text}</p>
            </li>
          ))}
        </ul>
      </Reveal>
    </section>
  )
}
