import type { McNemarTest } from '../../api/client.ts'
import { formatPValue } from './compareFormat.ts'

const HEADER_CLASSES = 'px-4 py-3 text-left text-xs font-medium text-ink-soft'
const CELL_CLASSES = 'px-4 py-3 align-top'
const NUMBER_CLASSES = `${CELL_CLASSES} font-mono whitespace-nowrap`

// p-valeur affichée : celle corrigée de Holm quand elle existe, sinon la p-valeur brute.
function shownPValue(test: McNemarTest): string {
  if (test.p_value_holm !== null) {
    return `${formatPValue(test.p_value_holm)} (Holm)`
  }
  return formatPValue(test.p_value)
}

// Conclusion du test, en mots.
function verdict(test: McNemarTest): string {
  if (test.significant) {
    return 'Écart significatif'
  }
  return 'Pas d’écart significatif'
}

// Un test : les deux modèles, leurs désaccords, la p-valeur et la conclusion.
function McNemarRow({ test }: { test: McNemarTest }) {
  let verdictClasses = `${CELL_CLASSES} text-ink-soft`
  if (test.significant) {
    verdictClasses = `${CELL_CLASSES} font-semibold`
  }
  return (
    <tr className="border-t border-rule">
      <td className={CELL_CLASSES}>
        {test.model_a} <span className="text-ink-soft">contre</span> {test.model_b}
      </td>
      <td className={NUMBER_CLASSES}>{test.only_a_right}</td>
      <td className={NUMBER_CLASSES}>{test.only_b_right}</td>
      <td className={NUMBER_CLASSES}>{shownPValue(test)}</td>
      <td className={verdictClasses}>{verdict(test)}</td>
    </tr>
  )
}

// Tests de McNemar (P8) : seuls les extraits où les deux modèles ne sont pas d'accord comptent.
export default function McNemarTable({ tests }: { tests: McNemarTest[] }) {
  return (
    <div className="overflow-x-auto rounded-card border border-rule bg-card">
      <table className="w-full min-w-[44rem] text-sm">
        <thead>
          <tr>
            <th className={HEADER_CLASSES}>Modèles comparés</th>
            <th className={HEADER_CLASSES}>Seul A juste</th>
            <th className={HEADER_CLASSES}>Seul B juste</th>
            <th className={HEADER_CLASSES}>p-valeur</th>
            <th className={HEADER_CLASSES}>Conclusion (p &lt; 0,05)</th>
          </tr>
        </thead>
        <tbody>
          {tests.map((test) => (
            <McNemarRow key={`${test.model_a}-${test.model_b}`} test={test} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
