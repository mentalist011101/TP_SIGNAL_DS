import type { Analysis } from '../../api/client.ts'

type StepState = 'done' | 'active' | 'todo'

interface Step {
  title: string
  detail: string
}

// Les étapes que l'utilisateur voit défiler, dans l'ordre du traitement par le serveur (S2).
const STEPS: Step[] = [
  { title: 'Envoi du fichier', detail: 'Le fichier part vers le serveur.' },
  { title: 'File d’attente', detail: 'L’analyse attend qu’un traitement se libère.' },
  { title: 'Analyse', detail: 'Conversion, spectrogramme, puis les modèles.' },
  { title: 'Résultat', detail: 'Le résultat est prêt.' },
]

const ERROR_PANEL_CLASSES = 'rounded-card bg-paper-alt p-3 text-sm text-danger'

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

// Rond de l'étape : coche si faite, point qui pulse si en cours, numéro si à venir.
function StepMarker({ state, number }: { state: StepState; number: number }) {
  if (state === 'done') {
    return (
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-ink text-paper">
        <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" fill="none" aria-hidden="true">
          <path d="M3 8.5l3 3 7-7" stroke="currentColor" strokeWidth="2" />
        </svg>
      </span>
    )
  }
  if (state === 'active') {
    return (
      <span className="relative flex h-6 w-6 items-center justify-center rounded-full border-2 border-ink">
        <span className="absolute h-2.5 w-2.5 rounded-full bg-ink motion-safe:animate-ping" />
        <span className="h-2.5 w-2.5 rounded-full bg-ink" />
      </span>
    )
  }
  return (
    <span className="flex h-6 w-6 items-center justify-center rounded-full border border-rule-strong font-mono text-xs text-ink-faint">
      {number}
    </span>
  )
}

// Une ligne de la liste : rond, titre, et le détail pour l'étape en cours seulement.
function StepRow({ step, state, number }: { step: Step; state: StepState; number: number }) {
  let titleClasses = 'text-sm text-ink-soft'
  if (state === 'active') {
    titleClasses = 'text-sm font-semibold text-ink'
  }
  if (state === 'todo') {
    titleClasses = 'text-sm text-ink-faint'
  }
  return (
    <li className="flex items-start gap-3">
      <StepMarker state={state} number={number} />
      <div className="pt-0.5">
        <p className={titleClasses}>{step.title}</p>
        {state === 'active' && <p className="text-xs text-ink-soft">{step.detail}</p>}
      </div>
    </li>
  )
}

// Barre sans pourcentage : le serveur ne dit pas où il en est, seulement qu'il travaille.
function IndeterminateBar() {
  return (
    <div className="h-1 overflow-hidden rounded-btn bg-paper-alt" aria-hidden="true">
      <div className="h-full w-2/5 rounded-btn bg-ink motion-safe:animate-indeterminate" />
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
  return (
    <div className="space-y-4" role="status" aria-live="polite">
      <IndeterminateBar />
      <ol className="space-y-3">
        {STEPS.map((step, index) => (
          <StepRow
            key={step.title}
            step={step}
            state={stepState(index, currentIndex)}
            number={index + 1}
          />
        ))}
      </ol>
    </div>
  )
}
