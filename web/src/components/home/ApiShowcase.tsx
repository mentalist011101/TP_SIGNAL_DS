import { HOME_EXAMPLES, type HomeExample } from './examples.ts'
import Reveal from './Reveal.tsx'

// Une ligne de JSON : indentation, clé (vide pour une accolade seule) et valeur affichée.
interface JsonLine {
  indent: number
  key: string
  value: string
}

// Extrait raccourci de la vraie réponse de GET /api/v1/analyses/{id} pour l'exemple « Parole »
// (contrat de la PR #26), avec les valeurs figées par scripts/export-example.mjs.
function responseLines(example: HomeExample): JsonLine[] {
  const result = example.result
  return [
    { indent: 0, key: '', value: '{' },
    { indent: 1, key: 'status', value: '"done",' },
    { indent: 1, key: 'duration_s', value: `${example.duration_s},` },
    { indent: 1, key: 'results', value: '{' },
    { indent: 2, key: 'emotion', value: '{' },
    { indent: 3, key: 'label_fr', value: `"${result.label_fr}",` },
    { indent: 3, key: 'probabilities', value: `[ … ${result.probabilities.length} classes ],` },
    { indent: 3, key: 'model_id', value: `"${result.model_id}",` },
    { indent: 3, key: 'model_version', value: `"${result.model_version}",` },
    { indent: 3, key: 'calibrated', value: `${result.calibrated},` },
    { indent: 3, key: 'segments', value: '[ … ]' },
    { indent: 2, key: '', value: '},' },
    { indent: 2, key: 'sound_event', value: '{ … 50 classes }' },
    { indent: 1, key: '', value: '}' },
    { indent: 0, key: '', value: '}' },
  ]
}

const POINTS = [
  'Chaque résultat porte son modèle, sa version et sa calibration.',
  'Les probabilités de toutes les classes, globales et par segment.',
  'Un contrat documenté en OpenAPI, consultable sur /docs.',
]

// Une ligne du bloc de code : la clé en vert mousse, la valeur en clair.
function CodeLine({ line }: { line: JsonLine }) {
  const indentText = '  '.repeat(line.indent)
  return (
    <span className="block">
      {indentText}
      {line.key !== '' && <span className="text-accent-soft">"{line.key}"</span>}
      {line.key !== '' && <span className="text-on-night/60">: </span>}
      <span>{line.value}</span>
    </span>
  )
}

// Section pour les équipes techniques : l'API ouverte, avec un extrait de vraie réponse.
export default function ApiShowcase() {
  return (
    <section className="mx-auto grid max-w-6xl items-center gap-12 px-6 py-24 lg:grid-cols-2">
      <Reveal className="min-w-0 space-y-6">
        <p className="label-mono text-ink-faint">Pour les développeurs</p>
        <h2 className="font-display text-5xl leading-tight">
          Une API ouverte, <em className="text-ink-soft">rien de caché</em>.
        </h2>
        <p className="text-lg leading-relaxed text-ink-soft">
          L’interface n’invente rien : elle affiche ce que l’API renvoie. Vos outils peuvent lire
          exactement la même chose.
        </p>
        <ul className="space-y-3">
          {POINTS.map((point) => (
            <li key={point} className="flex gap-3">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
              <span>{point}</span>
            </li>
          ))}
        </ul>
        <a href="/docs" className="inline-flex font-semibold underline underline-offset-4">
          Lire la documentation de l’API
        </a>
      </Reveal>
      <Reveal className="min-w-0" delayMs={150}>
        <div className="overflow-hidden rounded-card border border-rule bg-night">
          <p className="border-b border-on-night/10 px-5 py-3 font-mono text-xs text-on-night/70">
            GET /api/v1/analyses/{'{id}'} · exemple « Parole »
          </p>
          <pre className="overflow-x-auto px-5 py-4 font-mono text-sm leading-6 text-on-night">
            <code>
              {responseLines(HOME_EXAMPLES[0]).map((line, index) => (
                <CodeLine key={index} line={line} />
              ))}
            </code>
          </pre>
        </div>
      </Reveal>
    </section>
  )
}
