// Emplacement du spectrogramme. Il sera calculé par le serveur avec echolens.core.features :
// la règle R5 interdit tout calcul de features (STFT, log-Mel) dans le front.
export default function SpectrogramPlaceholder() {
  return (
    <div className="flex h-40 items-center justify-center rounded-md border border-dashed border-slate-300 text-sm text-slate-500 dark:border-slate-700">
      Spectrogramme calculé par le serveur — bientôt disponible
    </div>
  )
}
