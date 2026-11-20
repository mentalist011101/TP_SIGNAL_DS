import { InfoIcon } from '../icons.tsx'

// Bandeau des résultats du faux prédicteur (model_id « demo », C13) : ses probabilités sont
// tirées au hasard. On ne présente jamais de faux chiffres comme vrais, d'où ce bandeau posé
// au-dessus des cartes. Pas de couleur danger : ce n'est pas une erreur.
export default function DemoNotice() {
  return (
    <p
      role="note"
      className="flex items-center gap-3 rounded-card border border-rule-strong bg-paper-alt px-4 py-3 text-sm font-semibold"
    >
      <InfoIcon className="h-5 w-5 shrink-0" />
      Probabilités de démonstration : les modèles ne sont pas encore branchés
    </p>
  )
}
