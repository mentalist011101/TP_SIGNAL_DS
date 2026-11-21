// Les 50 classes d'ESC-50 reconnues par EchoLens, avec leur libellé français : copie de
// configs/labels.yaml (esc50_classes) pour la vitrine. L'application, elle, lit ces libellés
// dans les réponses de l'API.
const FIRST_ROW = [
  'Chien',
  'Coq',
  'Cochon',
  'Vache',
  'Grenouille',
  'Chat',
  'Poule',
  'Insectes',
  'Mouton',
  'Corbeau',
  'Pluie',
  'Vagues',
  'Feu qui crépite',
  'Grillons',
  'Chants d’oiseaux',
  'Gouttes d’eau',
  'Vent',
  'Eau versée',
  'Chasse d’eau',
  'Orage',
  'Pleurs de bébé',
  'Éternuement',
  'Applaudissements',
  'Respiration',
  'Toux',
]

const SECOND_ROW = [
  'Bruits de pas',
  'Rires',
  'Brossage de dents',
  'Ronflement',
  'Gorgées',
  'Coups à la porte',
  'Clic de souris',
  'Frappe au clavier',
  'Grincement de porte',
  'Ouverture de canette',
  'Machine à laver',
  'Aspirateur',
  'Réveil',
  'Tic-tac d’horloge',
  'Verre brisé',
  'Hélicoptère',
  'Tronçonneuse',
  'Sirène',
  'Klaxon',
  'Moteur',
  'Train',
  'Cloches d’église',
  'Avion',
  'Feux d’artifice',
  'Scie à main',
]

const CHIP_CLASSES =
  'shrink-0 rounded-btn border border-rule bg-card px-4 py-2 text-sm whitespace-nowrap text-ink-soft'

// Une rangée qui défile sans fin : la liste est posée deux fois de suite, et l'animation glisse
// d'exactement une liste avant de recommencer, sans saut visible.
function MarqueeRow({ labels, isReversed }: { labels: string[]; isReversed: boolean }) {
  const doubled = [...labels, ...labels]
  let directionClasses = ''
  if (isReversed) {
    directionClasses = '[animation-direction:reverse]'
  }
  return (
    <div className="overflow-hidden">
      <ul className={`flex w-max gap-3 motion-safe:animate-marquee ${directionClasses}`}>
        {doubled.map((label, index) => (
          <li key={`${label}-${index}`} className={CHIP_CLASSES}>
            {label}
          </li>
        ))}
      </ul>
    </div>
  )
}

// Bandeau des sons reconnus, deux rangées qui glissent en sens contraires. Les bords
// s'estompent (masque en dégradé) pour que les étiquettes entrent et sortent en douceur.
export default function SoundMarquee() {
  return (
    <section className="space-y-6 py-16" aria-label="Les 50 sons reconnus">
      <p className="label-mono text-center text-ink-faint">
        50 sons du quotidien reconnus · jeu de données ESC-50
      </p>
      <div className="space-y-3 [mask-image:linear-gradient(to_right,transparent,black_12%,black_88%,transparent)]">
        <MarqueeRow labels={FIRST_ROW} isReversed={false} />
        <MarqueeRow labels={SECOND_ROW} isReversed={true} />
      </div>
    </section>
  )
}
