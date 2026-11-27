import { TASK_LABELS } from '../../labels.ts'
import type { GradCamTask } from './gradCam.ts'

// Choix de la carte Grad-CAM posée sur le spectrogramme (EF-13, activable) : aucune, celle de
// l'événement ou celle de l'émotion. Même style que les filtres de l'historique.

const SEGMENT_CLASSES =
  'cursor-pointer rounded-btn px-3 py-1 text-center text-sm text-ink-soft transition-colors duration-200 ease-out-soft hover:text-ink has-checked:bg-ink has-checked:font-semibold has-checked:text-paper has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-accent-ink'

interface GradCamControlsProps {
  tasks: GradCamTask[]
  selected: GradCamTask | null
  onSelect: (task: GradCamTask | null) => void
}

interface Choice {
  value: GradCamTask | null
  label: string
}

// « Aucune », puis une entrée par tâche qui a une carte.
function choices(tasks: GradCamTask[]): Choice[] {
  const list: Choice[] = [{ value: null, label: 'Aucune' }]
  for (const task of tasks) {
    list.push({ value: task, label: TASK_LABELS[task] })
  }
  return list
}

export default function GradCamControls({ tasks, selected, onSelect }: GradCamControlsProps) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <span className="label-mono text-ink-faint">Carte Grad-CAM</span>
        <fieldset className="flex flex-wrap gap-1 rounded-btn border border-rule-strong bg-card p-1">
          <legend className="sr-only">Carte Grad-CAM posée sur le spectrogramme</legend>
          {choices(tasks).map((choice) => (
            <label key={choice.label} className={SEGMENT_CLASSES}>
              <input
                type="radio"
                name="grad-cam"
                className="sr-only"
                checked={selected === choice.value}
                onChange={() => onSelect(choice.value)}
              />
              {choice.label}
            </label>
          ))}
        </fieldset>
      </div>
      {selected !== null && (
        <p className="text-xs text-ink-soft">
          Zones claires : ce qui a le plus poussé le CRNN vers la classe prédite de chaque fenêtre.
          Carte grossière (4 bandes de fréquence, une colonne toutes les 160 ms) : elle montre où le
          modèle a regardé, pas pourquoi.
        </p>
      )}
    </div>
  )
}

// Analyse en profil Qualité : les têtes Whisper ne lisent pas le spectrogramme.
export function RealtimeOnlyNote() {
  return (
    <p className="text-xs text-ink-soft">
      Carte Grad-CAM : modèles de la famille A seulement (CRNN du profil Temps réel). Relancez
      l’analyse en profil Temps réel pour la voir.
    </p>
  )
}
