import Reveal from './Reveal.tsx'

// Section « limites » : ce que les modèles ne savent pas encore faire, une carte par limite,
// avec son chiffre quand il est mesuré. Sources : fiches des modèles, training/results/, essais
// sur des audios réels.

interface Limit {
  area: string
  // Chiffre clé, en grand ; vide si la limite n'est pas chiffrée.
  figure: string
  figureCaption: string
  title: string
  text: string
}

const LIMITS: Limit[] = [
  {
    area: 'Émotions',
    figure: '0,805 / 0,702',
    figureCaption: 'F1 voix féminines / masculines',
    title: 'Plus juste sur les voix féminines',
    text: 'Écart mesuré sur le test de CREMA-D et RAVDESS (famille B ; 0,737 contre 0,598 pour la famille A). Voix d’acteurs, en anglais.',
  },
  {
    area: 'Transcription',
    figure: '1 % → 3 %',
    figureCaption: 'mots faux (WER), test → Yaoundé',
    title: 'Les accents restent difficiles',
    text: 'Whisper small, profil Qualité : 1 % de mots faux sur le test d’OpenSLR 57, 3 % sur les textes lus à Yaoundé.',
  },
  {
    area: 'Événements',
    figure: '1',
    figureCaption: 'événement par fenêtre de 5 s',
    title: 'Un son à la fois',
    text: 'Deux sons simultanés ne sont pas séparés. ESC-50 n’a pas de classe « parole » : une voix est rangée dans le son le plus proche.',
  },
  {
    area: 'Détection de parole',
    figure: '7, %',
    figureCaption: 'sons non vocaux pris pour de la parole',
    title: 'Un bruit régulier peut passer pour une voix',
    text: 'Mesuré sur ESC-50 sans ses classes vocales (Silero VAD). Une émotion peut alors être estimée alors que personne ne parle.',
  },
  {
    area: 'Locuteurs',
    figure: '< 1 s',
    figureCaption: 'morceaux écartés, trop courts',
    title: 'Les morceaux courts sont fragiles',
    text: 'Sur des morceaux d’une seconde, une même voix obtient des scores proches du seuil « inconnu ». Il faut au moins 10 s pour enregistrer une voix.',
  },
  {
    area: 'Clonage',
    figure: '2,5 Go',
    figureCaption: 'de mémoire pour XTTS-v2',
    title: 'Lent sur CPU, marquage simple',
    text: 'Le premier clonage charge le modèle (environ 2 min 30 sur un PC de 8 Go). Le bip de marquage s’entend mais peut se couper : ce n’est pas un filigrane.',
  },
  {
    area: 'Robustesse',
    figure: '0–20 dB',
    figureCaption: 'bruit encore en cours de mesure',
    title: 'Bruit et micros de téléphone',
    text: 'L’effet du bruit ambiant et des micros bon marché est en cours de mesure (débruitage, C19) : à confirmer avant tout usage réel.',
  },
  {
    area: 'Licences',
    figure: 'NC',
    figureCaption: 'licences non commerciales',
    title: 'Usage académique seulement',
    text: 'ESC-50, RAVDESS, CaFE et XTTS-v2 interdisent l’usage commercial : EchoLens reste un projet d’enseignement.',
  },
]

function LimitCard({ limit }: { limit: Limit }) {
  return (
    <article className="group flex h-full flex-col gap-4 rounded-card border border-rule bg-card p-6 transition-[transform,border-color] duration-300 ease-out-soft hover:-translate-y-1 hover:border-rule-strong">
      <p className="label-mono text-ink-faint">{limit.area}</p>
      <div>
        <p className="font-display text-4xl leading-none">{limit.figure}</p>
        <p className="mt-1 font-mono text-[11px] text-ink-faint">{limit.figureCaption}</p>
      </div>
      <div className="space-y-2">
        <h3 className="font-semibold">{limit.title}</h3>
        <p className="text-sm leading-relaxed text-ink-soft">{limit.text}</p>
      </div>
    </article>
  )
}

export default function Limits() {
  return (
    <section className="mx-auto max-w-6xl space-y-10 px-6 py-24">
      <Reveal className="max-w-3xl space-y-4">
        <p className="label-mono text-ink-faint">Limites</p>
        <h2 className="font-display text-5xl leading-tight">
          Ce qu’EchoLens <em className="text-ink-soft">ne sait pas encore</em> faire.
        </h2>
        <p className="text-lg leading-relaxed text-ink-soft">
          Présentées franchement, chiffrées quand c’est possible : ce sont aussi nos pistes de
          travail.
        </p>
      </Reveal>
      <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {LIMITS.map((limit, index) => (
          <li key={limit.title}>
            <Reveal className="h-full" delayMs={(index % 4) * 90}>
              <LimitCard limit={limit} />
            </Reveal>
          </li>
        ))}
      </ul>
    </section>
  )
}
