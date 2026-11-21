import type { ComponentType } from 'react'
import type { AnalysisProfile, AnalysisTask } from '../../api/client.ts'
import { EmotionIcon, SpeakersIcon, TranscriptIcon, WaveIcon } from '../icons.tsx'

interface TaskOption {
  value: AnalysisTask
  label: string
  detail: string
  icon: ComponentType<{ className?: string }>
}

// Outils proposés (valeurs du contrat de l'API), avec une icône et une précision.
const TASK_OPTIONS: TaskOption[] = [
  { value: 'emotion', label: 'Émotions', detail: '6 classes, sur la parole', icon: EmotionIcon },
  {
    value: 'sound_event',
    label: 'Événements sonores',
    detail: '50 sons du quotidien',
    icon: WaveIcon,
  },
  {
    value: 'transcription',
    label: 'Transcription',
    detail: 'Texte horodaté',
    icon: TranscriptIcon,
  },
  { value: 'speaker', label: 'Locuteurs', detail: 'Qui parle', icon: SpeakersIcon },
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

// Tuile cliquable : cochée, sa bordure prend l'accent (has-checked), qui marque ce qui se clique.
const TILE_CLASSES =
  'flex cursor-pointer items-center gap-3 rounded-2xl border border-rule bg-card p-3 transition-colors duration-200 ease-out-soft hover:bg-paper-alt has-checked:border-accent has-checked:bg-paper-alt'

// Segment du choix de profil : le segment choisi prend le style de la page active du menu.
// Le bouton radio est masqué : le contour de focus est donc porté par le segment.
const SEGMENT_CLASSES =
  'cursor-pointer rounded-btn px-3 py-1.5 text-center text-sm text-ink-soft transition-colors duration-200 ease-out-soft hover:text-ink has-checked:bg-accent has-checked:font-semibold has-checked:text-on-accent has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-accent-ink'

const SECTION_TITLE_CLASSES = 'label-mono text-ink-faint'

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

// Une tuile par outil : icône, nom et précision, puis la case à cocher.
function TaskCheckboxes({ tasks, onTasksChange }: TaskCheckboxesProps) {
  function handleTaskChange(task: AnalysisTask) {
    const newTasks = toggleTask(tasks, task)
    onTasksChange(newTasks)
  }

  return (
    <fieldset className="space-y-2">
      <legend className={SECTION_TITLE_CLASSES}>Outils</legend>
      <div className="space-y-2">
        {TASK_OPTIONS.map((option) => (
          <label key={option.value} className={TILE_CLASSES}>
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-paper-alt text-ink-soft">
              <option.icon className="h-[18px] w-[18px]" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold">{option.label}</span>
              <span className="block text-xs text-ink-soft">{option.detail}</span>
            </span>
            <input
              type="checkbox"
              className="h-4 w-4 accent-accent"
              checked={tasks.includes(option.value)}
              onChange={() => handleTaskChange(option.value)}
            />
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
