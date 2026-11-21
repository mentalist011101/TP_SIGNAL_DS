import { Link } from 'react-router-dom'

const MESSAGE_CARD_CLASSES = 'space-y-4 rounded-card border border-rule bg-card p-5'

// Bouton secondaire de la charte, sous forme de lien.
const LINK_BUTTON_CLASSES =
  'inline-block rounded-btn border border-rule-strong bg-card px-3 py-1.5 text-sm font-semibold text-ink transition-colors duration-200 ease-out-soft hover:bg-paper-alt'

// Échec pendant le traitement : la raison donnée par le serveur, puis que faire (maquette,
// catalogue des erreurs S9 à S12). « Relancer » ramène sur Analyser, où l'on choisit l'audio.
export function FailedAnalysis({ reason }: { reason: string | null }) {
  return (
    <div className={MESSAGE_CARD_CLASSES}>
      <p>L’analyse n’a pas pu aboutir :</p>
      <p className="font-semibold text-danger">{reason}</p>
      <div className="flex flex-wrap gap-3">
        <Link to="/analyser" className={LINK_BUTTON_CLASSES}>
          Relancer l’analyse
        </Link>
        <Link to="/historique" className={LINK_BUTTON_CLASSES}>
          Voir l’historique
        </Link>
      </div>
    </div>
  )
}

// Lien périmé ou analyse supprimée (F12) : le texte du front remplace celui de l'API, qui
// contient l'identifiant technique.
export function AnalysisNotFound() {
  return (
    <div className={MESSAGE_CARD_CLASSES}>
      <p>Cette analyse n’existe pas ou a été supprimée.</p>
      <Link to="/historique" className={LINK_BUTTON_CLASSES}>
        Voir l’historique
      </Link>
    </div>
  )
}
