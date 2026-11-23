import Reveal from './Reveal.tsx'

interface Brick {
  title: string
  text: string
}

// L'équipe (README) et les 8 briques de la spécification (docs/specification.md).
const TEAM = ['Luciano (responsable technique)', 'Steve', 'Lynn', 'Nicole']

const BRICKS: Brick[] = [
  {
    title: 'Ingestion et prétraitement',
    text: 'Décodage, mono 16 kHz, débruitage, détection de parole.',
  },
  {
    title: 'Représentations temps-fréquence',
    text: 'STFT, log-Mel, MFCC : un seul code, côté serveur.',
  },
  {
    title: 'Données et protocole',
    text: 'Jeux, manifestes, découpages sans fuite entre entraînement et test.',
  },
  {
    title: 'Modèles',
    text: 'Référence MFCC + SVM, famille A (CNN, CRNN), famille B (encodeurs gelés).',
  },
  { title: 'Évaluation et explicabilité', text: 'F1, calibration, comparaisons, Grad-CAM.' },
  { title: 'Service d’inférence et API', text: 'Registre des modèles, découpage, API documentée.' },
  {
    title: 'Interface',
    text: 'Application web : analyser, lire le résultat, retrouver l’historique.',
  },
  { title: 'Ingénierie', text: 'Outillage, tests, intégration continue.' },
]

// Section « équipe et briques » : qui a construit EchoLens, et comment le projet est découpé.
export default function TeamBricks() {
  return (
    <section className="mx-auto max-w-6xl space-y-10 px-6 py-24">
      <Reveal className="max-w-3xl space-y-4">
        <p className="label-mono text-ink-faint">Équipe et briques</p>
        <h2 className="font-display text-5xl leading-tight">
          Quatre personnes, <em className="text-ink-soft">huit briques</em>.
        </h2>
        <p className="text-lg text-ink-soft">
          {TEAM.join(' · ')} · M2 Data Science, ENSPY, cours INF50101.
        </p>
      </Reveal>
      <Reveal>
        <ol className="grid gap-px overflow-hidden rounded-card border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-4">
          {BRICKS.map((brick, index) => (
            <li key={brick.title} className="space-y-2 bg-paper p-6">
              <span className="font-mono text-xs text-ink-faint">Brique {index + 1}</span>
              <h3 className="font-semibold">{brick.title}</h3>
              <p className="text-sm leading-relaxed text-ink-soft">{brick.text}</p>
            </li>
          ))}
        </ol>
      </Reveal>
    </section>
  )
}
