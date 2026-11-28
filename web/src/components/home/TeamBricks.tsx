import Reveal from './Reveal.tsx'

// Section « équipe et briques » : les quatre membres, chacun avec son profil GitHub (comptes des
// contributeurs du dépôt), puis les 8 briques de la spécification (docs/specification.md).

interface Member {
  name: string
  role: string
  github: string
}

const TEAM: Member[] = [
  { name: 'Luciano Fokouo', role: 'Responsable technique', github: 'mentalist011101' },
  { name: 'Steve', role: 'Membre de l’équipe', github: 'DIFFO-web' },
  { name: 'Lynn', role: 'Membre de l’équipe', github: 'Lynn2129' },
  { name: 'Nicole', role: 'Membre de l’équipe', github: 'serenanicole' },
]

const GITHUB_URL = 'https://github.com/'
// Taille demandée à GitHub pour l'avatar, en pixels (affiché en 56 px, net sur écran dense).
const AVATAR_SIZE = 112

interface Brick {
  title: string
  text: string
}

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
  { title: 'Ingénierie', text: 'Outillage, tests, intégration continue, Docker.' },
]

// Carte d'un membre : avatar GitHub, nom, rôle, lien vers le profil.
function MemberCard({ member }: { member: Member }) {
  const profile = `${GITHUB_URL}${member.github}`
  return (
    <a
      href={profile}
      target="_blank"
      rel="noreferrer"
      className="group flex items-center gap-4 rounded-card border border-rule bg-card p-4 transition-[transform,border-color] duration-300 ease-out-soft hover:-translate-y-1 hover:border-rule-strong"
    >
      <img
        src={`${profile}.png?size=${AVATAR_SIZE}`}
        alt=""
        width={56}
        height={56}
        loading="lazy"
        className="h-14 w-14 shrink-0 rounded-full border border-rule bg-paper-alt"
      />
      <span className="min-w-0 space-y-0.5">
        <span className="block font-semibold">{member.name}</span>
        <span className="block text-sm text-ink-soft">{member.role}</span>
        <span className="block truncate font-mono text-xs text-ink-faint group-hover:text-ink">
          @{member.github} ↗
        </span>
      </span>
    </a>
  )
}

export default function TeamBricks() {
  return (
    <section className="mx-auto max-w-6xl space-y-10 px-6 py-24">
      <Reveal className="max-w-3xl space-y-4">
        <p className="label-mono text-ink-faint">Équipe et briques</p>
        <h2 className="font-display text-5xl leading-tight">
          Quatre personnes, <em className="text-ink-soft">huit briques</em>.
        </h2>
        <p className="text-lg text-ink-soft">M2 Data Science, ENSPY, cours INF50101.</p>
      </Reveal>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {TEAM.map((member, index) => (
          <li key={member.github}>
            <Reveal delayMs={index * 90}>
              <MemberCard member={member} />
            </Reveal>
          </li>
        ))}
      </ul>
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
