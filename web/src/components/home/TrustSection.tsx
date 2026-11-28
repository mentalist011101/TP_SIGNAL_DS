import Reveal from './Reveal.tsx'

// Section confiance : les jeux de données publics du protocole (docs/datasets.md), une carte
// par jeu avec un lien vers sa page officielle, puis ce que l'application fait de vos audios.

interface Dataset {
  name: string
  tasks: string[]
  language: string
  // Chiffres clés, en police mono : extraits, locuteurs, durée.
  facts: string
  role: string
  // Page officielle du jeu ; null pour les enregistrements de l'équipe (jamais publiés).
  url: string | null
  licence: string
  licenceUrl: string | null
}

const DATASETS: Dataset[] = [
  {
    name: 'CREMA-D',
    tasks: ['Émotions'],
    language: 'EN',
    facts: '7 442 extraits · 91 acteurs · 6 émotions',
    role: 'Entraînement principal des émotions. Acteurs répartis entre entraînement, validation et test, jamais partagés (P1).',
    url: 'https://github.com/CheyneyComputerScience/CREMA-D',
    licence: 'ODbL 1.0',
    licenceUrl: 'https://opendatacommons.org/licenses/odbl/1-0/',
  },
  {
    name: 'RAVDESS',
    tasks: ['Émotions'],
    language: 'EN',
    facts: '1 440 extraits · 24 acteurs · 8 émotions',
    role: 'Complément d’entraînement des émotions, ramené aux 6 classes communes (P2).',
    url: 'https://zenodo.org/records/1188976',
    licence: 'CC BY-NC-SA 4.0',
    licenceUrl: 'https://creativecommons.org/licenses/by-nc-sa/4.0/',
  },
  {
    name: 'ESC-50',
    tasks: ['Événements'],
    language: '—',
    facts: '2 000 extraits · 50 classes · 5 folds',
    role: 'Entraînement et évaluation des événements sonores, en validation croisée sur les 5 folds officiels (P3).',
    url: 'https://github.com/karolpiczak/ESC-50',
    licence: 'CC BY-NC 3.0',
    licenceUrl: 'https://creativecommons.org/licenses/by-nc/3.0/',
  },
  {
    name: 'CaFE',
    tasks: ['Émotions'],
    language: 'FR',
    facts: '936 extraits · 12 acteurs · français canadien',
    role: 'Test hors domaine : nos modèles d’émotion, appris en anglais, face au français.',
    url: 'https://zenodo.org/records/1478765',
    licence: 'CC BY-NC-SA 4.0',
    licenceUrl: 'https://creativecommons.org/licenses/by-nc-sa/4.0/',
  },
  {
    name: 'African Accented French',
    tasks: ['Transcription', 'Locuteurs'],
    language: 'FR',
    facts: '16 656 extraits · 19,9 h · Yaoundé, Gabon, Niger',
    role: 'WER de la transcription sur des accents africains, et évaluation de l’identification du locuteur (OpenSLR 57).',
    url: 'https://www.openslr.org/57/',
    licence: 'Apache 2.0',
    licenceUrl: 'https://www.apache.org/licenses/LICENSE-2.0',
  },
  {
    name: 'Enregistrements de l’équipe',
    tasks: ['Démo', 'Clonage'],
    language: 'FR',
    facts: 'voix des membres · consentement écrit',
    role: 'Audios jamais vus pour la démo, et seules voix clonées pour l’évaluation de XTTS-v2 (ENF-10).',
    url: null,
    licence: 'Usage interne',
    licenceUrl: null,
  },
]

interface Commitment {
  title: string
  text: string
}

// Ce que l'application fait vraiment des audios (S6, ENF-10).
const COMMITMENTS: Commitment[] = [
  {
    title: 'Vos audios restent chez vous',
    text: 'EchoLens tourne sur votre serveur : les audios et les résultats y sont stockés, et ne partent vers aucun service tiers.',
  },
  {
    title: 'Supprimés quand vous voulez',
    text: 'Une analyse, une voix enregistrée ou un extrait synthétique supprimé l’est vraiment : la ligne en base et les fichiers.',
  },
  {
    title: 'Des modèles évalués honnêtement',
    text: 'Aucun locuteur commun entre entraînement et test, des folds officiels jamais remélangés.',
  },
]

const CHIP_CLASSES = 'rounded-btn border border-rule-strong px-2 py-0.5 text-xs text-ink-soft'

// Pastille de la licence : un lien vers son texte quand il existe.
function LicenceChip({ dataset }: { dataset: Dataset }) {
  if (dataset.licenceUrl === null) {
    return <span className={CHIP_CLASSES}>{dataset.licence}</span>
  }
  return (
    <a
      href={dataset.licenceUrl}
      target="_blank"
      rel="noreferrer"
      className={`${CHIP_CLASSES} transition-colors duration-200 ease-out-soft hover:border-ink-soft hover:text-ink`}
    >
      {dataset.licence} ↗
    </a>
  )
}

// Pied de la carte : le lien vers le jeu, ou la raison de son absence.
function DatasetLink({ dataset }: { dataset: Dataset }) {
  if (dataset.url === null) {
    return <span className="text-sm text-ink-faint">Jamais publiés : usage interne</span>
  }
  return (
    <a
      href={dataset.url}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1 text-sm font-semibold transition-colors duration-200 ease-out-soft hover:text-ink-soft"
    >
      Voir le jeu de données <span aria-hidden="true">↗</span>
    </a>
  )
}

function DatasetCard({ dataset }: { dataset: Dataset }) {
  return (
    <article className="flex h-full flex-col gap-4 rounded-card border border-rule bg-card p-6 transition-[transform,border-color] duration-300 ease-out-soft hover:-translate-y-1 hover:border-rule-strong">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-btn bg-paper-alt px-2 py-0.5 font-mono text-xs">
          {dataset.language}
        </span>
        {dataset.tasks.map((task) => (
          <span key={task} className={CHIP_CLASSES}>
            {task}
          </span>
        ))}
        <LicenceChip dataset={dataset} />
      </div>
      <div className="space-y-1">
        <h3 className="text-xl font-semibold">{dataset.name}</h3>
        <p className="font-mono text-xs text-ink-faint">{dataset.facts}</p>
      </div>
      <p className="leading-relaxed text-ink-soft">{dataset.role}</p>
      <div className="mt-auto border-t border-rule pt-4">
        <DatasetLink dataset={dataset} />
      </div>
    </article>
  )
}

export default function TrustSection() {
  return (
    <section className="mx-auto max-w-6xl space-y-14 px-6 py-24">
      <Reveal className="max-w-3xl space-y-4">
        <p className="label-mono text-ink-faint">Jeux de données</p>
        <h2 className="font-display text-5xl leading-tight">
          Construit sur des jeux <em className="text-ink-soft">publics et cités</em>.
        </h2>
        <p className="text-lg leading-relaxed text-ink-soft">
          Aucun audio n’est dans le dépôt : chaque jeu se télécharge à sa source officielle, et sa
          licence est respectée (usage académique pour les licences non commerciales).
        </p>
      </Reveal>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {DATASETS.map((dataset, index) => (
          <li key={dataset.name}>
            <Reveal className="h-full" delayMs={(index % 3) * 100}>
              <DatasetCard dataset={dataset} />
            </Reveal>
          </li>
        ))}
      </ul>
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
