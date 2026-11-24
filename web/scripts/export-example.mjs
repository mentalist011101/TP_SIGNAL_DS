// Fige les exemples réels de la page d'accueil, à partir de l'API d'un serveur EchoLens lancé
// avec les vrais modèles (ECHOLENS_INFERENCE_BACKEND=models).
//
// Usage : node scripts/export-example.mjs <adresse du serveur> <id parole> <id son d'ambiance>
// Exemple : node scripts/export-example.mjs http://localhost:5053 d7b923bc-… 2436fc75-…
//
// Écrit :
// - public/exemple/<nom>.png : le spectrogramme calculé par le serveur pour chaque exemple ;
// - src/components/home/examples.json : ce que l'accueil affiche (résultat de la tâche montrée,
//   axes du spectrogramme, modèles du registre avec leur F1 et leur T).
// Aucun audio n'est copié : seuls l'image et les chiffres renvoyés par l'API sont gardés.
import { mkdirSync, writeFileSync } from 'node:fs'

const PNG_DIR = 'public/exemple'
const JSON_PATH = 'src/components/home/examples.json'

// Référence MFCC + SVM sur ESC-50 (C5, PR #11, recalculée dans la PR #23) : elle n'est pas dans
// le registre (aucun modèle en service), d'où sa copie ici, avec sa source.
const REFERENCE = {
  name: 'MFCC + SVM',
  task: 'sound_event',
  f1_macro: 0.403,
  source: 'C5, PR #11 (F1 macro 0,4029 ± 0,0397 sur les 5 folds)',
}

// Les deux exemples : l'extrait, d'où il vient, et la tâche montrée sur l'accueil.
function exampleSpecs(parolId, ambianceId) {
  return [
    {
      slug: 'parole',
      id: parolId,
      title: 'Parole',
      task: 'emotion',
      source: 'CREMA-D, extrait 1001_DFA_ANG_XX : acteur du jeu de test, jamais entendu à l’entraînement, phrase jouée en colère',
      licence: 'ODbL 1.0',
    },
    {
      slug: 'ambiance',
      id: ambianceId,
      title: 'Son d’ambiance',
      task: 'sound_event',
      source: 'ESC-50, extrait 1-17367-A-10 (pluie)',
      licence: 'CC BY-NC 3.0',
    },
  ]
}

// Lit une réponse JSON de l'API ; arrête le script si elle échoue.
async function getJson(url) {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`${url} : ${response.status}`)
  }
  return response.json()
}

// Télécharge l'image du spectrogramme d'une analyse dans public/exemple/.
async function saveSpectrogram(baseUrl, analysis, slug) {
  const response = await fetch(baseUrl + analysis.spectrogram_url)
  if (!response.ok) {
    throw new Error(`spectrogramme de ${analysis.id} : ${response.status}`)
  }
  const bytes = Buffer.from(await response.arrayBuffer())
  writeFileSync(`${PNG_DIR}/${slug}.png`, bytes)
}

// Ce que l'accueil garde d'une analyse : la durée, les axes du spectrogramme et le résultat de
// la tâche montrée, sans les segments.
function keepForHome(spec, analysis) {
  const result = analysis.results[spec.task]
  return {
    slug: spec.slug,
    title: spec.title,
    task: spec.task,
    source: spec.source,
    licence: spec.licence,
    duration_s: analysis.duration_s,
    created_at: analysis.created_at,
    spectrogram: analysis.spectrogram,
    result: {
      status: result.status,
      label_fr: result.label_fr,
      probabilities: result.probabilities,
      model_id: result.model_id,
      model_version: result.model_version,
      calibrated: result.calibrated,
    },
  }
}

const [baseUrl, parolId, ambianceId] = process.argv.slice(2)
if (ambianceId === undefined) {
  console.error('Usage : node scripts/export-example.mjs <adresse> <id parole> <id son d’ambiance>')
  process.exit(1)
}

mkdirSync(PNG_DIR, { recursive: true })
const examples = []
for (const spec of exampleSpecs(parolId, ambianceId)) {
  const analysis = await getJson(`${baseUrl}/api/v1/analyses/${spec.id}`)
  await saveSpectrogram(baseUrl, analysis, spec.slug)
  examples.push(keepForHome(spec, analysis))
}
const models = await getJson(`${baseUrl}/api/v1/models`)
const output = { generated_at: new Date().toISOString(), examples, models, reference: REFERENCE }
writeFileSync(JSON_PATH, JSON.stringify(output, null, 2) + '\n')
console.log(`Écrit : ${JSON_PATH} et ${examples.length} spectrogrammes dans ${PNG_DIR}`)
