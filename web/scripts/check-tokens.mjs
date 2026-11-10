// Garde-fou de la charte (docs/design.md) : échoue si web/src contient une couleur de la palette
// Tailwind (« text-slate-500 ») ou un code hexadécimal en dur dans un composant .tsx.
// Les couleurs ne passent que par les jetons de src/index.css.
import { readdirSync, readFileSync } from 'node:fs'
import { join, relative } from 'node:path'

const SOURCE_DIR = 'src'

// Seul fichier autorisé à lire les jetons directement (lecture des variables CSS).
const ALLOWED_FILES = ['src/theme.ts']

const PALETTE_PATTERN =
    /\b(slate|gray|zinc|blue|sky|emerald|green|red|amber|indigo|violet|purple)-(50|[1-9]00|950)\b/
const HEX_PATTERN = /#[0-9a-fA-F]{3,8}\b/

// Tous les fichiers de src/, sous-dossiers compris.
function listFiles(directory) {
    const files = []
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
        const path = join(directory, entry.name)
        if (entry.isDirectory()) {
            files.push(...listFiles(path))
        } else {
            files.push(path)
        }
    }
    return files
}

// Problèmes d'un fichier, une ligne par couleur interdite trouvée.
function findProblems(file) {
    const problems = []
    const isComponent = file.endsWith('.tsx')
    const lines = readFileSync(file, 'utf8').split('\n')
    for (let index = 0; index < lines.length; index++) {
        const line = lines[index]
        const where = `${file}:${index + 1}`
        if (PALETTE_PATTERN.test(line)) {
            problems.push(`${where} : couleur de la palette Tailwind, utilisez un jeton`)
        }
        if (isComponent && HEX_PATTERN.test(line)) {
            problems.push(`${where} : code hexadécimal en dur, utilisez un jeton`)
        }
    }
    return problems
}

const problems = []
for (const path of listFiles(SOURCE_DIR)) {
    const file = relative('.', path).replaceAll('\\', '/')
    if (ALLOWED_FILES.includes(file)) {
        continue
    }
    problems.push(...findProblems(file))
}

if (problems.length > 0) {
    console.error(problems.join('\n'))
    console.error(`\n${problems.length} couleur(s) hors charte : voir docs/design.md.`)
    process.exit(1)
}
console.log('Charte respectée : aucune couleur en dur dans src/.')
