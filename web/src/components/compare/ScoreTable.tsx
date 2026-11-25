import type { ModelScore } from '../../api/client.ts'
import { FAMILY_LABELS } from '../../labels.ts'
import { formatInterval, formatMeanStd } from './compareFormat.ts'

const HEADER_CLASSES = 'px-4 py-3 text-left text-xs font-medium text-ink-soft'
const CELL_CLASSES = 'px-4 py-3 align-top'
const NUMBER_CLASSES = `${CELL_CLASSES} font-mono whitespace-nowrap`

// F1 macro moyen le plus haut de la tâche, pour mettre son modèle en gras.
function bestF1(models: ModelScore[]): number {
  let best = 0
  for (const model of models) {
    if (model.f1_macro_mean > best) {
      best = model.f1_macro_mean
    }
  }
  return best
}

// Une ligne par modèle ; le meilleur F1 macro de la tâche est en gras.
function ScoreRow({ model, isBest }: { model: ModelScore; isBest: boolean }) {
  let nameClasses = CELL_CLASSES
  if (isBest) {
    nameClasses = `${CELL_CLASSES} font-semibold`
  }
  return (
    <tr className="border-t border-rule">
      <td className={nameClasses}>{model.label}</td>
      <td className={`${CELL_CLASSES} whitespace-nowrap`}>{FAMILY_LABELS[model.family]}</td>
      <td className={NUMBER_CLASSES}>{formatMeanStd(model.f1_macro_mean, model.f1_macro_std)}</td>
      <td className={NUMBER_CLASSES}>{formatInterval(model.f1_macro_ci)}</td>
      <td className={NUMBER_CLASSES}>{formatMeanStd(model.accuracy_mean, model.accuracy_std)}</td>
    </tr>
  )
}

// Scores de test de chaque modèle sur une tâche ; le tableau défile de côté sur téléphone.
export default function ScoreTable({ models }: { models: ModelScore[] }) {
  const best = bestF1(models)
  return (
    <div className="overflow-x-auto rounded-card border border-rule bg-card">
      <table className="w-full min-w-[44rem] text-sm">
        <thead>
          <tr>
            <th className={HEADER_CLASSES}>Modèle</th>
            <th className={HEADER_CLASSES}>Famille</th>
            <th className={HEADER_CLASSES}>F1 macro</th>
            <th className={HEADER_CLASSES}>IC 95 % du F1</th>
            <th className={HEADER_CLASSES}>Accuracy</th>
          </tr>
        </thead>
        <tbody>
          {models.map((model) => (
            <ScoreRow key={model.model} model={model} isBest={model.f1_macro_mean === best} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
