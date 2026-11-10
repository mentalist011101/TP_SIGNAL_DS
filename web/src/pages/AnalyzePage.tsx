import { useEffect, useRef, useState } from 'react'
import {
  ApiError,
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

// Message à afficher pour une erreur : celui de l'API, ou serveur injoignable (erreur réseau).
function describeError(error: Error | null): string | null {
  if (error === null) {
    return null
  }
  if (error instanceof ApiError) {
    return error.message
  }
  return 'Serveur injoignable : vérifiez que l’application est lancée, puis réessayez.'
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
    <div className="space-y-3">
      <p className="text-sm text-ink-soft">
        Fichier : <span className="font-mono">{file.name}</span>
      </p>
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
    <>
      <h1 className="font-display text-3xl font-extrabold tracking-tight">Analyser un audio</h1>
      <p className="text-ink-soft">
        Importez un fichier ou enregistrez-vous au micro, choisissez les tâches, puis lancez
        l’analyse.
      </p>
    </>
  )
}

// Page Analyser : choix de l'audio, des tâches et du profil, puis suivi de l'analyse.
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
      <AudioPicker onAudioSelected={handleAudioSelected} />
      {audioFile !== null && (
        <AudioPreview key={fileKey(audioFile)} file={audioFile} analysis={run.analysis} />
      )}
      <TaskSelector
        tasks={tasks}
        profile={profile}
        onTasksChange={setTasks}
        onProfileChange={setProfile}
      />
      <AnalysisPanel run={run} hint={hint} onAnalyze={handleAnalyze} />
    </section>
  )
}
