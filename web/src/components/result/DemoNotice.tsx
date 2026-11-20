// Bandeau des résultats du faux prédicteur (model_id « demo », C13) : ses probabilités sont
// tirées au hasard. On ne présente jamais de faux chiffres comme vrais, d'où ce bandeau posé
// au-dessus des barres. Pas de couleur danger : ce n'est pas une erreur.
export default function DemoNotice() {
  return (
    <p
      role="note"
      className="rounded-card border border-l-4 border-rule-strong border-l-ink bg-paper-alt px-3 py-2 text-sm font-semibold"
    >
      Probabilités de démonstration : les modèles ne sont pas encore branchés
    </p>
  )
}
