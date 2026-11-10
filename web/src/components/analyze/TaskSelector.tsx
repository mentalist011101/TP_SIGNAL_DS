import type { ChangeEvent } from 'react'
import type { AnalysisProfile, AnalysisTask } from '../../api/client.ts'

// Tâches proposées, avec leur libellé affiché (valeurs du contrat de l'API).
const TASK_OPTIONS: { value: AnalysisTask; label: string }[] = [
  { value: 'emotion', label: 'Émotion' },
  { value: 'sound_event', label: 'Événement sonore' },
  { value: 'transcription', label: 'Transcription' },
  { value: 'speaker', label: 'Locuteur' },
]

const PROFILE_OPTIONS: { value: AnalysisProfile; label: string }[] = [
  { value: 'quality', label: 'Qualité' },
  { value: 'realtime', label: 'Temps réel' },
]

const SELECT_CLASSES =
  'rounded-md border border-slate-300 bg-white px-2 py-1 dark:border-slate-700 dark:bg-slate-900'

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

// Une case à cocher par tâche.
function TaskCheckboxes({ tasks, onTasksChange }: TaskCheckboxesProps) {
  function handleTaskChange(task: AnalysisTask) {
    const newTasks = toggleTask(tasks, task)
    onTasksChange(newTasks)
  }

  return TASK_OPTIONS.map((option) => (
    <label key={option.value} className="flex items-center gap-2">
      <input
        type="checkbox"
        checked={tasks.includes(option.value)}
        onChange={() => handleTaskChange(option.value)}
      />
      {option.label}
    </label>
  ))
}

// Liste déroulante du profil : qualité (fichier importé) ou temps réel.
function ProfileSelect({ profile, onProfileChange }: ProfileSelectProps) {
  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    // Les seules valeurs possibles sont celles de PROFILE_OPTIONS.
    const newProfile = event.target.value as AnalysisProfile
    onProfileChange(newProfile)
  }

  return (
    <label className="flex items-center gap-2 pt-2">
      Profil :
      <select className={SELECT_CLASSES} value={profile} onChange={handleChange}>
        {PROFILE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  )
}

// Choix des tâches et du profil avant l'analyse (EF-07).
export default function TaskSelector(props: TaskSelectorProps) {
  return (
    <fieldset className="space-y-3">
      <legend className="font-medium">Que souhaitez-vous analyser ?</legend>
      <TaskCheckboxes tasks={props.tasks} onTasksChange={props.onTasksChange} />
      <ProfileSelect profile={props.profile} onProfileChange={props.onProfileChange} />
    </fieldset>
  )
}
