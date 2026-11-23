import type { CSSProperties } from 'react'
import type { Analysis } from '../../api/client.ts'

type StepState = 'done' | 'active' | 'todo'

interface Step {
  title: string
  detail: string
}

// Les étapes que l'utilisateur voit défiler, dans l'ordre du traitement par le serveur (S2).
// Les titres sont courts : ils tiennent sous les ronds, côte à côte.
const STEPS: Step[] = [
  { title: 'Envoi', detail: 'Le fichier part vers le serveur…' },
  { title: 'Attente', detail: 'L’analyse attend qu’un traitement se libère…' },
  { title: 'Analyse', detail: 'Conversion, spectrogramme, puis les modèles…' },
  { title: 'Résultat', detail: 'Le résultat est prêt.' },
]

const LAST_STEP_INDEX = STEPS.length - 1

const ERROR_PANEL_CLASSES = 'rounded-card border border-danger px-3 py-2 text-sm text-danger'

interface AnalysisProgressProps {
  analysis: Analysis | undefined
  isSubmitting: boolean
  errorMessage: string | null
}

// Numéro de l'étape en cours (0 à 3), d'après l'envoi puis le statut renvoyé par l'API.
function currentStepIndex(isSubmitting: boolean, analysis: Analysis | undefined): number {
  if (isSubmitting || analysis === undefined) {
    return 0
  }
  if (analysis.status === 'pending') {
    return 1
  }
  if (analysis.status === 'processing') {
    return 2
  }
  return 3
}

// Une étape est faite, en cours, ou à venir, selon sa place par rapport à l'étape en cours.
function stepState(index: number, currentIndex: number): StepState {
  if (index < currentIndex) {
    return 'done'
  }
  if (index === currentIndex) {
    return 'active'
  }
  return 'todo'
}

// Longueur du trait plein entre les ronds : la part du chemin déjà parcourue.
function filledLineStyle(currentIndex: number): CSSProperties {
  const percent = (currentIndex / LAST_STEP_INDEX) * 100
  return { width: `${percent}%` }
}

// Rond de l'étape : plein si faite, avec un halo qui pulse si en cours, vide si à venir.
function StepDot({ state }: { state: StepState }) {
  if (state === 'done') {
    return <span className="block h-3 w-3 rounded-full bg-ink" />
  }
  if (state === 'active') {
    return (
      <span className="relative block h-3 w-3">
        <span className="absolute inset-0 rounded-full bg-ink motion-safe:animate-ping" />
        <span className="absolute inset-0 rounded-full bg-ink" />
      </span>
    )
  }
  return <span className="block h-3 w-3 rounded-full border border-rule-strong bg-card" />
}

// Les quatre ronds sur un trait : le trait se remplit à mesure que l'analyse avance.
function StepTrack({ currentIndex }: { currentIndex: number }) {
  return (
    <div className="relative">
      {/* Le trait va du centre du premier rond au centre du dernier (1/8 de chaque côté). */}
      <div className="absolute top-1.5 right-[12.5%] left-[12.5%] h-px bg-rule-strong">
        <div
          className="h-full bg-ink transition-all duration-500 ease-out-soft"
          style={filledLineStyle(currentIndex)}
        />
      </div>
      <ol className="relative grid grid-cols-4">
        {STEPS.map((step, index) => {
          const state = stepState(index, currentIndex)
          let labelClasses = 'text-ink-faint'
          if (state !== 'todo') {
            labelClasses = 'font-semibold text-ink'
          }
          return (
            <li key={step.title} className="flex flex-col items-center gap-1.5">
              <StepDot state={state} />
              <span className={`text-xs ${labelClasses}`}>{step.title}</span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

// Suivi animé d'une analyse : erreur de l'API, échec du traitement, ou étapes qui avancent au
// rythme du statut (rafraîchi chaque seconde par useAnalysis).
export default function AnalysisProgress(props: AnalysisProgressProps) {
  if (props.errorMessage !== null) {
    return <p className={ERROR_PANEL_CLASSES}>{props.errorMessage}</p>
  }
  const analysis = props.analysis
  // Le message du serveur dit déjà qu'il s'agit d'un échec (« Échec du traitement : … »).
  if (analysis !== undefined && analysis.status === 'failed') {
    return <p className={ERROR_PANEL_CLASSES}>{analysis.error_message}</p>
  }
  if (!props.isSubmitting && analysis === undefined) {
    return null
  }
  const currentIndex = currentStepIndex(props.isSubmitting, analysis)
  const currentStep = STEPS[currentIndex]
  return (
    <div className="space-y-2" role="status" aria-live="polite">
      <StepTrack currentIndex={currentIndex} />
      <p className="text-center text-xs text-ink-soft">{currentStep.detail}</p>
    </div>
  )
}
