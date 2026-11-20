import type { AnalysisProfile, AnalysisTask } from '../../api/client.ts'

interface TaskOption {
  value: AnalysisTask
  label: string
  detail: string
}

// Tâches proposées (valeurs du contrat de l'API), avec une précision sous le libellé.
const TASK_OPTIONS: TaskOption[] = [
  { value: 'emotion', label: 'Émotion', detail: '6 classes' },
  { value: 'sound_event', label: 'Événement sonore', detail: '50 classes' },
  { value: 'transcription', label: 'Transcription', detail: 'Texte parlé' },
  { value: 'speaker', label: 'Locuteur', detail: 'Qui parle' },
]

// Le profil choisit les modèles, pas la source du son (EF-07).
const PROFILE_OPTIONS: { value: AnalysisProfile; label: string }[] = [
  { value: 'quality', label: 'Qualité' },
  { value: 'realtime', label: 'Temps réel' },
]

// Phrase d'aide affichée sous le choix, selon le profil choisi.
const PROFILE_HELP: Record<AnalysisProfile, string> = {
  quality: 'Modèles les plus précis, analyse plus lente.',
  realtime: 'Modèles légers et rapides, ceux du micro en direct.',
}

// Ligne cliquable : la case cochée colore sa bordure (has-checked), l'accent marquant ce qui
// se clique.
const TILE_CLASSES =
  'flex cursor-pointer items-center gap-3 rounded-btn border border-rule-strong bg-card px-3 py-2.5 transition-colors duration-200 ease-out-soft hover:bg-paper-alt has-checked:border-accent has-checked:bg-paper-alt'

// Segment du choix de profil : le segment choisi prend le style de la page active du menu.
// Le bouton radio est masqué : le contour de focus est donc porté par le segment.
const SEGMENT_CLASSES =
  'cursor-pointer rounded-btn px-3 py-1.5 text-center text-sm text-ink-soft transition-colors duration-200 ease-out-soft hover:text-ink has-checked:bg-ink has-checked:font-semibold has-checked:text-paper has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-accent-ink'

const SECTION_TITLE_CLASSES = 'label-mono text-ink-soft'

interface TaskCheckboxesProps {
  tasks: AnalysisTask[]
  onTasksChange: (tasks: AnalysisTask[]) => void
}

interface ProfileSelectProps {
  profile: AnalysisProfile
  onProfileChange: (profile: AnalysisProfile) => void
}

type TaskSelectorProps = TaskCheckboxesProps & ProfileSelectProps

// Coche ou décoche une tâche : renvoie une nouvelle liste, sans modifier l'ancienne.
function toggleTask(tasks: AnalysisTask[], task: AnalysisTask): AnalysisTask[] {
  if (tasks.includes(task)) {
    return tasks.filter((item) => item !== task)
  }
  return [...tasks, task]
}

// Une ligne à cocher par tâche : le libellé à gauche, sa précision à droite.
function TaskCheckboxes({ tasks, onTasksChange }: TaskCheckboxesProps) {
  function handleTaskChange(task: AnalysisTask) {
    const newTasks = toggleTask(tasks, task)
    onTasksChange(newTasks)
  }

  return (
    <fieldset className="space-y-2">
      <legend className={SECTION_TITLE_CLASSES}>Tâches</legend>
      <div className="space-y-2">
        {TASK_OPTIONS.map((option) => (
          <label key={option.value} className={TILE_CLASSES}>
            <input
              type="checkbox"
              className="accent-accent"
              checked={tasks.includes(option.value)}
              onChange={() => handleTaskChange(option.value)}
            />
            <span className="flex-1 text-sm font-semibold">{option.label}</span>
            <span className="text-xs text-ink-soft">{option.detail}</span>
          </label>
        ))}
      </div>
    </fieldset>
  )
}

// Choix du profil en deux segments (boutons radio), suivi d'une phrase qui l'explique.
function ProfileSelect({ profile, onProfileChange }: ProfileSelectProps) {
  const help = PROFILE_HELP[profile]
  return (
    <fieldset className="space-y-2">
      <legend className={SECTION_TITLE_CLASSES}>Profil</legend>
      <div className="grid grid-cols-2 gap-1 rounded-btn border border-rule-strong bg-card p-1">
        {PROFILE_OPTIONS.map((option) => (
          <label key={option.value} className={SEGMENT_CLASSES}>
            <input
              type="radio"
              name="profile"
              className="sr-only"
              checked={profile === option.value}
              onChange={() => onProfileChange(option.value)}
            />
            {option.label}
          </label>
        ))}
      </div>
      <p className="text-xs text-ink-soft">{help}</p>
    </fieldset>
  )
}

// Choix des tâches et du profil avant l'analyse (EF-07).
export default function TaskSelector(props: TaskSelectorProps) {
  return (
    <div className="space-y-5">
      <TaskCheckboxes tasks={props.tasks} onTasksChange={props.onTasksChange} />
      <ProfileSelect profile={props.profile} onProfileChange={props.onProfileChange} />
    </div>
  )
}
