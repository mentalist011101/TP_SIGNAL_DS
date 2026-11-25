import {
  describeApiError,
  useComparisons,
  type Comparisons,
  type TaskTable,
} from '../api/client.ts'
import LatencyTable from '../components/compare/LatencyTable.tsx'
import McNemarTable from '../components/compare/McNemarTable.tsx'
import ScoreTable from '../components/compare/ScoreTable.tsx'
import TranscriptionTable from '../components/compare/TranscriptionTable.tsx'

// Titre de chaque tâche de classification.
const TASK_TITLES: Record<TaskTable['task'], string> = {
  sound_event: 'Événements sonores',
  emotion: 'Émotions',
}

const NOTE_CLASSES = 'text-xs text-ink-soft'

// Une tâche : le protocole, les scores de chaque modèle, puis les tests de McNemar.
function TaskSection({ table }: { table: TaskTable }) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold">{TASK_TITLES[table.task]}</h2>
      <p className={NOTE_CLASSES}>{table.protocol}</p>
      <ScoreTable models={table.models} />
      <h3 className="pt-2 text-sm font-semibold">Les écarts sont-ils réels ? Tests de McNemar</h3>
      <McNemarTable tests={table.tests} />
      <p className={NOTE_CLASSES}>
        On ne compte que les extraits de test où un seul des deux modèles a raison. Si ces
        désaccords penchent nettement d’un côté (p &lt; 0,05), l’écart n’est pas dû au hasard.
      </p>
    </section>
  )
}

// Tous les tableaux, dans l'ordre : classification, transcription, puis vitesse.
function ComparisonContent({ data }: { data: Comparisons }) {
  return (
    <>
      {data.classification.map((table) => (
        <TaskSection key={table.task} table={table} />
      ))}
      <section className="space-y-3">
        <h2 className="text-base font-semibold">Transcription</h2>
        <p className={NOTE_CLASSES}>
          WER : part des mots mal transcrits ; CER : part des caractères. Plus bas, c’est mieux.
        </p>
        <TranscriptionTable rows={data.transcription} />
      </section>
      <section className="space-y-3">
        <h2 className="text-base font-semibold">Taille et vitesse sur CPU</h2>
        <p className={NOTE_CLASSES}>
          RTF = temps de calcul ÷ durée du son. En dessous de 1, le modèle va plus vite que le son :
          c’est la condition du temps réel.
        </p>
        <LatencyTable rows={data.latency} />
      </section>
    </>
  )
}

// Page Comparer : les résultats de test de chaque approche, lus par le serveur dans
// training/results (GET /api/v1/comparisons). Rien n'est recalculé dans le navigateur.
export default function ComparePage() {
  const query = useComparisons()

  let content = <p className="text-sm text-ink-soft">Chargement des résultats…</p>
  if (query.error !== null) {
    content = <p className="text-sm text-danger">{describeApiError(query.error)}</p>
  }
  if (query.data !== undefined) {
    content = <ComparisonContent data={query.data} />
  }

  return (
    <section className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-5xl leading-tight">Comparer les modèles</h1>
        <p className="text-ink-soft">
          La référence classique, la famille A et la famille B, mesurées sur les mêmes données de
          test : scores, significativité des écarts, transcription et vitesse.
        </p>
      </div>
      {content}
    </section>
  )
}
