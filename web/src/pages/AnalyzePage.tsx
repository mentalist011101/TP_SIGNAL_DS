import { useEffect, useRef, useState, type ReactNode } from 'react'
import {
  describeApiError,
  useAnalysis,
  useCreateAnalysis,
  type Analysis,
  type AnalysisProfile,
  type AnalysisRequest,
  type AnalysisTask,
} from '../api/client.ts'
import AnalysisStatus from '../components/analyze/AnalysisStatus.tsx'
import AudioPicker from '../components/analyze/AudioPicker.tsx'
import SpectrogramView from '../components/analyze/SpectrogramView.tsx'
import TaskSelector from '../components/analyze/TaskSelector.tsx'
import WaveformCanvas from '../components/analyze/WaveformCanvas.tsx'

// Tâches cochées à l'ouverture de la page.
const DEFAULT_TASKS: AnalysisTask[] = ['emotion', 'sound_event']

const ANALYZE_BUTTON_CLASSES =
  'rounded-btn bg-accent px-5 py-2 text-sm font-semibold text-on-accent transition-colors duration-200 ease-out-soft hover:bg-accent-deep disabled:cursor-not-allowed disabled:opacity-50'

// Carte posée sur le papier : un réglage (colonne de gauche) ou l'aperçu (colonne de droite).
const CARD_CLASSES = 'space-y-3 rounded-card border border-rule bg-card p-5 shadow-card'

// Zone d'attente de l'aperçu, en pointillés tant qu'aucun audio n'est choisi.
const EMPTY_PREVIEW_CLASSES =
  'flex min-h-80 items-center justify-center rounded-card border border-dashed border-rule-strong bg-card p-6 text-center text-ink-soft'

// Deux colonnes sur grand écran (réglages étroits à gauche, aperçu large à droite), une seule
// colonne empilée sur téléphone. minmax(0, …) empêche le canvas d'élargir sa colonne.
const LAYOUT_CLASSES = 'grid items-start gap-6 lg:grid-cols-[minmax(0,22rem)_minmax(0,1fr)]'

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

// Clé qui change à chaque nouveau fichier (un enregistrement a toujours une date différente).
function fileKey(file: File): string {
  return `${file.name}-${file.lastModified}`
}

// Lecteur audio : l'URL locale (blob:) est créée pour le fichier, puis libérée quand il change.
function AudioPlayer({ file }: { file: File }) {
  const audioRef = useRef<HTMLAudioElement>(null)
  useEffect(() => {
    const audio = audioRef.current
    if (audio === null) {
      return
    }
    const objectUrl = URL.createObjectURL(file)
    audio.src = objectUrl
    return () => {
      URL.revokeObjectURL(objectUrl)
    }
  }, [file])
  return <audio ref={audioRef} controls className="w-full" />
}

// Ce que la page sait de l'analyse lancée.
interface AnalysisRun {
  start: (request: AnalysisRequest) => void
  reset: () => void
  analysis: Analysis | undefined
  isSubmitting: boolean
  errorMessage: string | null
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
    errorMessage: describeError(error),
  }
}

interface AudioPreviewProps {
  file: File
  analysis: Analysis | undefined
}

// Lecteur, forme d'onde et spectrogramme de l'audio choisi. La forme d'onde et l'image du
// spectrogramme ont la même largeur (w-full) et couvrent la même durée : elles sont alignées.
// La page lui donne une clé par fichier : un nouvel audio repart d'un aperçu vierge.
function AudioPreview({ file, analysis }: AudioPreviewProps) {
  return (
    <div className={CARD_CLASSES}>
      <h2 className="font-display text-lg font-bold">Écoute</h2>
      <AudioPlayer file={file} />
      <h2 className="font-display text-lg font-bold">Forme d’onde</h2>
      <WaveformCanvas file={file} />
      <h2 className="font-display text-lg font-bold">Spectrogramme</h2>
      <SpectrogramView analysis={analysis} />
    </div>
  )
}

interface AnalyzeButtonProps {
  hint: string | null
  isSubmitting: boolean
  onClick: () => void
}

// Bouton Analyser, désactivé avec une explication tant qu'il manque le fichier ou une tâche.
function AnalyzeButton({ hint, isSubmitting, onClick }: AnalyzeButtonProps) {
  const isDisabled = hint !== null || isSubmitting
  return (
    <div className="space-y-2">
      <button
        type="button"
        className={ANALYZE_BUTTON_CLASSES}
        disabled={isDisabled}
        onClick={onClick}
      >
        Analyser
      </button>
      {hint !== null && <p className="text-sm text-ink-soft">{hint}</p>}
    </div>
  )
}

interface AnalysisPanelProps {
  run: AnalysisRun
  hint: string | null
  onAnalyze: () => void
}

// Bouton Analyser suivi du statut de l'analyse lancée.
function AnalysisPanel({ run, hint, onAnalyze }: AnalysisPanelProps) {
  return (
    <>
      <AnalyzeButton hint={hint} isSubmitting={run.isSubmitting} onClick={onAnalyze} />
      <AnalysisStatus
        analysis={run.analysis}
        isSubmitting={run.isSubmitting}
        errorMessage={run.errorMessage}
      />
    </>
  )
}

// Titre et consigne de la page.
function PageIntro() {
  return (
    <div className="space-y-2">
      <h1 className="font-display text-3xl font-extrabold tracking-tight">Analyser un audio</h1>
      <p className="text-ink-soft">
        Suivez les trois étapes ; l’aperçu montre l’audio choisi en forme d’onde, puis en
        spectrogramme une fois l’analyse terminée.
      </p>
    </div>
  )
}

interface StepCardProps {
  step: number
  title: string
  children: ReactNode
}

// Carte d'une étape de réglage : numéro discret, titre, puis son contenu.
function StepCard({ step, title, children }: StepCardProps) {
  return (
    <div className={CARD_CLASSES}>
      <p className="label-mono text-ink-faint">Étape {step}</p>
      <h2 className="font-display text-lg font-bold">{title}</h2>
      {children}
    </div>
  )
}

// Rappel du fichier choisi, sous les boutons d'import et de micro.
function ChosenFile({ file }: { file: File | null }) {
  if (file === null) {
    return <p className="text-sm text-ink-soft">Aucun audio choisi pour l’instant.</p>
  }
  return (
    <p className="text-sm text-ink-soft">
      Choisi : <span className="font-mono break-all text-ink">{file.name}</span>
    </p>
  )
}

// Colonne de droite : l'aperçu de l'audio, ou une zone d'attente tant qu'il n'y en a pas.
function PreviewColumn({ file, analysis }: { file: File | null; analysis: Analysis | undefined }) {
  if (file === null) {
    return (
      <div className={EMPTY_PREVIEW_CLASSES}>
        La forme d’onde et le spectrogramme apparaîtront ici dès que vous aurez choisi un audio.
      </div>
    )
  }
  // Une clé par fichier : un nouvel audio repart d'un aperçu vierge.
  return <AudioPreview key={fileKey(file)} file={file} analysis={analysis} />
}

interface SettingsColumnProps {
  audioFile: File | null
  tasks: AnalysisTask[]
  profile: AnalysisProfile
  run: AnalysisRun
  hint: string | null
  onAudioSelected: (file: File) => void
  onTasksChange: (tasks: AnalysisTask[]) => void
  onProfileChange: (profile: AnalysisProfile) => void
  onAnalyze: () => void
}

// Colonne de gauche : les trois étapes de réglage, dans l'ordre où on les fait.
function SettingsColumn(props: SettingsColumnProps) {
  return (
    <div className="space-y-4">
      <StepCard step={1} title="Choisir l’audio">
        <AudioPicker onAudioSelected={props.onAudioSelected} />
        <ChosenFile file={props.audioFile} />
      </StepCard>
      <StepCard step={2} title="Que souhaitez-vous analyser ?">
        <TaskSelector
          tasks={props.tasks}
          profile={props.profile}
          onTasksChange={props.onTasksChange}
          onProfileChange={props.onProfileChange}
        />
      </StepCard>
      <StepCard step={3} title="Lancer l’analyse">
        <AnalysisPanel run={props.run} hint={props.hint} onAnalyze={props.onAnalyze} />
      </StepCard>
    </div>
  )
}

// Page Analyser (C20) : les trois étapes de réglage à gauche, l'aperçu de l'audio à droite
// (empilés sur téléphone).
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

  return (
    <section className="space-y-6">
      <PageIntro />
      <div className={LAYOUT_CLASSES}>
        <SettingsColumn
          audioFile={audioFile}
          tasks={tasks}
          profile={profile}
          run={run}
          hint={hint}
          onAudioSelected={handleAudioSelected}
          onTasksChange={setTasks}
          onProfileChange={setProfile}
          onAnalyze={handleAnalyze}
        />
        <PreviewColumn file={audioFile} analysis={run.analysis} />
      </div>
    </section>
  )
}
