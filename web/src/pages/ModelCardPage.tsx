import { Link, useParams } from 'react-router-dom'
import { describeApiError, useModelCard, type ModelCard } from '../api/client.ts'
import ConfusionMatrixView from '../components/models/ConfusionMatrixView.tsx'
import { formatScore } from '../components/models/modelFormat.ts'
import PerClassF1 from '../components/models/PerClassF1.tsx'
import { FAMILY_LABELS, PROFILE_LABELS } from '../labels.ts'

// Fiche d'un modèle (EF-16) : ses scores, sa calibration, sa matrice de confusion et le F1 de
// chaque classe, tels que les notebooks les ont mesurés, avec la source de chaque chiffre.

// Dépôt public du projet : lien vers le fichier de résultats, au commit qui l'a produit.
const REPOSITORY_URL = 'https://github.com/mentalist011101/TP_SIGNAL_DS'

const TILE_CLASSES = 'space-y-1 bg-card px-5 py-4'
const SECTION_CLASSES = 'space-y-3 rounded-card border border-rule bg-card p-5'

// « 0,066 » : une ECE, au millième ; tiret sans calibration.
function formatEce(ece: number | null): string {
  if (ece === null) {
    return '—'
  }
  return ece.toLocaleString('fr-FR', { minimumFractionDigits: 3, maximumFractionDigits: 3 })
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className={TILE_CLASSES}>
      <p className="label-mono text-ink-faint">{label}</p>
      <p className="font-display text-3xl leading-tight">{value}</p>
    </div>
  )
}

// Chiffres clés : scores de test et calibration (T, puis ECE avant → après).
function KeyNumbers({ card }: { card: ModelCard }) {
  let temperature = '—'
  if (card.temperature !== null) {
    temperature = card.temperature.toLocaleString('fr-FR', { maximumFractionDigits: 3 })
  }
  const ece = `${formatEce(card.ece_before)} → ${formatEce(card.ece_after)}`
  return (
    <div className="grid gap-px overflow-hidden rounded-card border border-rule bg-rule sm:grid-cols-2 lg:grid-cols-4">
      <Tile label="F1 macro de test" value={formatScore(card.f1_macro)} />
      <Tile label="Accuracy de test" value={formatScore(card.accuracy)} />
      <Tile label="Température T" value={temperature} />
      <Tile label="ECE avant → après" value={ece} />
    </div>
  )
}

// D'où viennent les chiffres : protocole, fichier du dépôt et commit du code.
function Source({ card }: { card: ModelCard }) {
  if (card.results_file === null) {
    return null
  }
  // Lien vers main : le fichier de résultats est commité après le calcul, il n'existe pas
  // forcément au commit du code qui l'a produit.
  const href = `${REPOSITORY_URL}/blob/main/${card.results_file}`
  return (
    <p className="text-xs text-ink-soft">
      {card.evaluation} Source :{' '}
      <a href={href} className="font-mono text-accent-ink underline underline-offset-2">
        {card.results_file}
      </a>
      {card.results_commit !== null && (
        <>
          , code du commit <span className="font-mono">{card.results_commit.slice(0, 8)}</span>
        </>
      )}
      .
    </p>
  )
}

function CardHeader({ card }: { card: ModelCard }) {
  const profiles = card.profiles.map((profile) => PROFILE_LABELS[profile]).join(', ')
  return (
    <div className="space-y-2">
      <p className="font-mono text-xs text-ink-faint">
        <Link to="/modeles" className="hover:underline">
          Modèles
        </Link>{' '}
        / Fiche
      </p>
      <h1 className="font-mono text-3xl leading-tight break-all">{card.id}</h1>
      <p className="text-sm text-ink-soft">
        {FAMILY_LABELS[card.family]} · profil {profiles} · version{' '}
        <span className="font-mono">{card.version}</span>
        {card.huggingface_url !== null && (
          <>
            {' · '}
            <a href={card.huggingface_url} className="text-accent-ink underline underline-offset-2">
              poids sur Hugging Face
            </a>
          </>
        )}
      </p>
      <p className="max-w-3xl text-ink-soft">{card.description}</p>
    </div>
  )
}

function CardBody({ card }: { card: ModelCard }) {
  return (
    <div className="space-y-6">
      <KeyNumbers card={card} />
      <Source card={card} />
      {card.confusion !== null && (
        <section className={SECTION_CLASSES}>
          <h2 className="text-base font-semibold">Matrice de confusion</h2>
          <ConfusionMatrixView confusion={card.confusion} />
        </section>
      )}
      {card.per_class_f1.length > 0 && (
        <section className={SECTION_CLASSES}>
          <h2 className="text-base font-semibold">F1 par classe</h2>
          <PerClassF1 rows={card.per_class_f1} />
        </section>
      )}
      {card.confusion === null && (
        <p className="text-sm text-ink-soft">
          Pas de matrice de confusion : ce modèle ne classe pas l’audio parmi des classes fixes. Ses
          scores sont dans sa description.
        </p>
      )}
    </div>
  )
}

export default function ModelCardPage() {
  const { modelId } = useParams()
  const query = useModelCard(modelId)
  if (query.error !== null) {
    return <p className="text-sm text-danger">{describeApiError(query.error)}</p>
  }
  if (query.data === undefined) {
    return <p className="text-sm text-ink-soft">Chargement de la fiche…</p>
  }
  return (
    <section className="space-y-8">
      <CardHeader card={query.data} />
      <CardBody card={query.data} />
    </section>
  )
}
