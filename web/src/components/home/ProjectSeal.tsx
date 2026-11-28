// Cachet du projet, à côté du grand titre de l'accueil : le cours et la formation écrits en
// cercle, qui tournent lentement autour du mot « Projet ». Décoratif : le même texte est donné
// aux lecteurs d'écran par aria-label.

const SEAL_TEXT = 'INF50101 · TRAITEMENT MULTIMÉDIA DES DONNÉES · ENSPY · M2 DATA SCIENCE · '
const SEAL_LABEL =
  'Projet du cours INF50101, Traitement multimédia des données, ENSPY, M2 Data Science'

// className doit donner la position (relative ou absolute) : le texte et le centre sont posés en
// absolu dans le cachet.
interface ProjectSealProps {
  className?: string
}

export default function ProjectSeal({ className = '' }: ProjectSealProps) {
  return (
    <div
      className={`aspect-square rounded-full border border-rule-strong bg-card/80 backdrop-blur ${className}`}
      role="img"
      aria-label={SEAL_LABEL}
    >
      {/* Texte en cercle : un chemin circulaire de rayon 38 dans un carré de 100. */}
      <svg
        viewBox="0 0 100 100"
        className="absolute inset-0 h-full w-full motion-safe:animate-spin-slow"
        aria-hidden="true"
      >
        <defs>
          <path id="seal-circle" d="M 50 50 m -38 0 a 38 38 0 1 1 76 0 a 38 38 0 1 1 -76 0" />
        </defs>
        {/* textLength = le tour complet (2π × 38 ≈ 239) : le texte fait exactement un tour. */}
        <text className="fill-ink-soft font-mono" fontSize="5.2">
          <textPath href="#seal-circle" textLength="236" lengthAdjust="spacing">
            {SEAL_TEXT}
          </textPath>
        </text>
      </svg>
      <div className="absolute inset-[26%] flex flex-col items-center justify-center rounded-full border border-rule text-center">
        <span className="font-display text-xl leading-none italic">Projet</span>
        <span className="mt-1 font-mono text-[9px] text-ink-faint">2026</span>
      </div>
    </div>
  )
}
