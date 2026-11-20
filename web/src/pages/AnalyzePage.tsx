import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import {
  describeApiError,
  isAnalysisRunning,
  useAnalysis,
  useCreateAnalysis,
  type Analysis,
  type AnalysisProfile,
  type AnalysisRequest,
  type AnalysisTask,
} from '../api/client.ts'
import AnalysisProgress from '../components/analyze/AnalysisProgress.tsx'
import AudioPanel from '../components/analyze/AudioPanel.tsx'
import TaskSelector from '../components/analyze/TaskSelector.tsx'

// Tâches cochées à l'ouverture de la page.
const DEFAULT_TASKS: AnalysisTask[] = ['emotion', 'sound_event']

const ANALYZE_BUTTON_CLASSES =
  'w-full rounded-btn bg-accent px-5 py-2.5 font-semibold text-on-accent transition-colors duration-200 ease-out-soft hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-50'

// Colonne des réglages : reste visible quand on fait défiler un long aperçu (grand écran).
const SETTINGS_CLASSES = 'space-y-5 rounded-card border border-rule bg-card p-5 lg:sticky lg:top-10'

// L'audio en grand à gauche, les réglages dans une colonne étroite à droite ; une seule colonne
// sur téléphone. minmax(0, …) empêche le canvas d'élargir sa colonne.
const LAYOUT_CLASSES = 'grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_21rem]'

// Message à afficher pour une erreur, ou null s'il n'y en a pas.
function describeError(error: Error | null): string | null {
  if (error === null) {
    return null
  }
  return describeApiError(error)
}

// Explique pourquoi le bouton Analyser est désactivé ; null quand tout est prêt.
function analyzeHint(hasFile: boolean, hasTasks: boolean): string | null {
  if (!hasFile) {
    return 'Importez un fichier ou enregistrez-vous au micro pour commencer.'
  }
  if (!hasTasks) {
    return 'Cochez au moins une tâche pour lancer l’analyse.'
  }
  return null
}

// Ce que la page sait de l'analyse lancée.
interface AnalysisRun {
  start: (request: AnalysisRequest) => void
  reset: () => void
  analysis: Analysis | undefined
  isSubmitting: boolean
  // Vrai de l'envoi jusqu'à la fin du traitement : on ne relance pas pendant ce temps.
  isBusy: boolean
  errorMessage: string | null
}

// Vrai pendant l'envoi, puis tant que le serveur n'a pas fini (en attente ou en cours).
function isRunBusy(isSubmitting: boolean, analysis: Analysis | undefined): boolean {
  if (isSubmitting) {
    return true
  }
  if (analysis === undefined) {
    return false
  }
  return isAnalysisRunning(analysis)
}

// Envoi (POST) puis suivi (GET chaque seconde) d'une analyse.
function useAnalysisRun(): AnalysisRun {
  const createAnalysis = useCreateAnalysis()
  const createdAnalysis = createAnalysis.data
  const analysisId = createdAnalysis === undefined ? null : createdAnalysis.id
  const analysisQuery = useAnalysis(analysisId)
  // Tant que le premier GET n'a pas répondu, on affiche l'analyse renvoyée par le POST.
  const latestAnalysis = analysisQuery.data ?? createdAnalysis
  const error = createAnalysis.error ?? analysisQuery.error
  return {
    start: createAnalysis.mutate,
    reset: createAnalysis.reset,
    analysis: latestAnalysis,
    isSubmitting: createAnalysis.isPending,
    isBusy: isRunBusy(createAnalysis.isPending, latestAnalysis),
    errorMessage: describeError(error),
  }
}

interface AnalyzeButtonProps {
  hint: string | null
  isBusy: boolean
  onClick: () => void
}

// Bouton Analyser : désactivé avec une explication tant qu'il manque le fichier ou une tâche,
// et pendant qu'une analyse tourne.
function AnalyzeButton({ hint, isBusy, onClick }: AnalyzeButtonProps) {
  const isDisabled = hint !== null || isBusy
  let label = 'Analyser'
  if (isBusy) {
    label = 'Analyse en cours…'
  }
  return (
    <div className="space-y-2">
      <button
        type="button"
        className={ANALYZE_BUTTON_CLASSES}
        disabled={isDisabled}
        onClick={onClick}
      >
        {label}
      </button>
      {hint !== null && <p className="text-sm text-ink-soft">{hint}</p>}
    </div>
  )
}

interface SettingsPanelProps {
  tasks: AnalysisTask[]
  profile: AnalysisProfile
  run: AnalysisRun
  hint: string | null
  onTasksChange: (tasks: AnalysisTask[]) => void
  onProfileChange: (profile: AnalysisProfile) => void
  onAnalyze: () => void
}

// Colonne des réglages : tâches, profil, puis le bouton Analyser et le suivi de l'envoi.
function SettingsPanel(props: SettingsPanelProps) {
  return (
    <aside className={SETTINGS_CLASSES} aria-label="Réglages de l’analyse">
      <TaskSelector
        tasks={props.tasks}
        profile={props.profile}
        onTasksChange={props.onTasksChange}
        onProfileChange={props.onProfileChange}
      />
      <div className="space-y-3 border-t border-rule pt-5">
        <AnalyzeButton hint={props.hint} isBusy={props.run.isBusy} onClick={props.onAnalyze} />
        <AnalysisProgress
          analysis={props.run.analysis}
          isSubmitting={props.run.isSubmitting}
          errorMessage={props.run.errorMessage}
        />
      </div>
    </aside>
  )
}

// Page Analyser (C20) : l'audio en grand à gauche, les réglages à droite (empilés sur
// téléphone). Quand l'analyse est terminée, sa page Résultat s'ouvre.
export default function AnalyzePage() {
  const [audioFile, setAudioFile] = useState<File | null>(null)
  const [tasks, setTasks] = useState<AnalysisTask[]>(DEFAULT_TASKS)
  const [profile, setProfile] = useState<AnalysisProfile>('quality')
  const run = useAnalysisRun()
  const hint = analyzeHint(audioFile !== null, tasks.length > 0)

  // Un nouvel audio efface le suivi de l'analyse précédente.
  function handleAudioSelected(file: File) {
    setAudioFile(file)
    run.reset()
  }

  function handleAnalyze() {
    if (audioFile !== null) {
      run.start({ file: audioFile, tasks, profile })
    }
  }

  // Analyse terminée : on passe à sa page Résultat (C21). En cas d'échec, on reste ici avec la
  // raison, sans perdre l'audio ni les choix.
  const latestAnalysis = run.analysis
  if (latestAnalysis !== undefined && latestAnalysis.status === 'done') {
    return <Navigate to={`/analyses/${latestAnalysis.id}`} />
  }

  return (
    <section className="space-y-6">
      <div className="space-y-2">
        <h1 className="font-display text-3xl font-extrabold tracking-tight">Analyser un audio</h1>
        <p className="text-ink-soft">
          Choisissez un audio, les tâches et le profil : le résultat s’ouvre dès qu’il est prêt.
        </p>
      </div>
      <div className={LAYOUT_CLASSES}>
        <AudioPanel file={audioFile} onAudioSelected={handleAudioSelected} />
        <SettingsPanel
          tasks={tasks}
          profile={profile}
          run={run}
          hint={hint}
          onTasksChange={setTasks}
          onProfileChange={setProfile}
          onAnalyze={handleAnalyze}
        />
      </div>
    </section>
  )
}
