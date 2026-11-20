import type { Analysis } from '../../api/client.ts'

const BUTTON_CLASSES =
  'rounded-btn border border-rule-strong bg-card px-4 py-2 text-sm font-medium text-ink shadow-hard-sm transition-colors duration-200 ease-out-soft hover:bg-paper-alt disabled:cursor-not-allowed disabled:opacity-50'

// Indentation du fichier JSON, pour qu'il reste lisible si on l'ouvre dans un éditeur.
const JSON_INDENT = 2

// Télécharge l'analyse telle que l'API l'a renvoyée (EF-09) : on fabrique un fichier en mémoire
// (Blob), on lui donne une adresse locale, on simule un clic sur un lien, puis on libère
// l'adresse.
function downloadAnalysisJson(analysis: Analysis): void {
  const text = JSON.stringify(analysis, null, JSON_INDENT)
  const file = new Blob([text], { type: 'application/json' })
  const objectUrl = URL.createObjectURL(file)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = `echolens-${analysis.id}.json`
  link.click()
  URL.revokeObjectURL(objectUrl)
}

// Bouton d'export JSON, désactivé tant que l'analyse n'est pas terminée (rien à exporter).
export default function ExportJsonButton({ analysis }: { analysis: Analysis }) {
  const isDone = analysis.status === 'done'
  return (
    <button
      type="button"
      className={BUTTON_CLASSES}
      disabled={!isDone}
      onClick={() => downloadAnalysisJson(analysis)}
    >
      Exporter en JSON
    </button>
  )
}
