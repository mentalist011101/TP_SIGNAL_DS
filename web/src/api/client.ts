import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

// Préfixe commun de l'API versionnée exposée par Flask.
export const API_BASE = '/api/v1'

// Délai entre deux interrogations du statut d'une analyse en cours.
const POLL_INTERVAL_MS = 1000

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Corps des réponses d'erreur de l'API : « message » est en français, affichable tel quel.
interface ApiErrorBody {
  message?: unknown
}

// Lit le champ « message » du JSON d'erreur ; message générique si le corps n'est pas lisible.
async function readErrorMessage(response: Response, path: string): Promise<string> {
  const fallbackMessage = `Erreur ${response.status} sur ${path}`
  try {
    const body = (await response.json()) as ApiErrorBody
    if (typeof body.message === 'string') {
      return body.message
    }
  } catch {
    // Corps vide ou non JSON : on garde le message générique.
  }
  return fallbackMessage
}

// Message à afficher pour une erreur d'appel : celui de l'API (en français), ou « serveur
// injoignable » quand fetch n'a obtenu aucune réponse (son propre message est en anglais).
export function describeApiError(error: Error): string {
  if (error instanceof ApiError) {
    return error.message
  }
  return 'Serveur injoignable : vérifiez que l’application est lancée, puis réessayez.'
}

// Appel JSON générique : lève une ApiError lisible si la réponse n'est pas 2xx.
export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) {
    const message = await readErrorMessage(response, path)
    throw new ApiError(response.status, message)
  }
  return (await response.json()) as T
}

// Envoi d'un formulaire multipart (fichier + champs) : le navigateur fixe lui-même l'en-tête.
export async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method: 'POST', body: form })
  if (!response.ok) {
    const message = await readErrorMessage(response, path)
    throw new ApiError(response.status, message)
  }
  return (await response.json()) as T
}

// Suppression : l'API répond 204 (sans corps) ; on ne lit donc pas de JSON en retour.
export async function apiDelete(path: string): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, { method: 'DELETE' })
  if (!response.ok) {
    const message = await readErrorMessage(response, path)
    throw new ApiError(response.status, message)
  }
}

export interface HealthResponse {
  status: string
  version: string
}

// Santé du serveur : affichée dans le pied de page pour vérifier la connexion à Flask.
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiGet<HealthResponse>('/health'),
    refetchInterval: 30_000,
  })
}

// Types du contrat /api/v1/analyses (visible sur /docs), écrits à la main en attendant
// que « npm run gen:api » soit en place.
export type AnalysisTask = 'emotion' | 'sound_event' | 'transcription' | 'speaker'
export type AnalysisProfile = 'quality' | 'realtime'
export type AnalysisStatusValue = 'pending' | 'processing' | 'done' | 'failed'

// Une graduation de l'axe des fréquences : position = hauteur relative depuis le bas de
// l'image (0 en bas, 1 en haut). L'axe suit l'échelle Mel : ne pas interpoler en Hz.
export interface FrequencyTick {
  hz: number
  position: number
}

// Axes et légende de l'image du spectrogramme, calculés par le serveur (U6, R5).
export interface SpectrogramInfo {
  n_mels: number
  f_min_hz: number
  f_max_hz: number
  frequency_ticks: FrequencyTick[]
  frame_step_s: number
  db_min: number
  db_max: number
  colormap: string
  colormap_stops: string[]
}

// Résultats d'une analyse terminée (C13, schémas de src/echolens/api/result_schemas.py).
// done : résultat calculé ; no_speech : émotion demandée mais aucune parole détectée ;
// unavailable : tâche pas encore branchée. Dans les deux derniers cas, « message » dit pourquoi.
export type TaskResultStatus = 'done' | 'no_speech' | 'unavailable'

// Probabilité d'une classe, entre 0 et 1 ; label_fr est le libellé à afficher.
export interface ClassProbability {
  label: string
  label_fr: string
  probability: number
}

// Résultat d'un morceau de l'audio, pour la frise temporelle (EF-12). Transcription : label et
// label_fr à null, probabilities vide, et le texte dit sur ce morceau dans text (null pour les
// autres tâches).
export interface SegmentResult {
  start_s: number
  end_s: number
  label: string | null
  label_fr: string | null
  probabilities: ClassProbability[]
  text: string | null
}

// Résultat d'une tâche. Les probabilités arrivent triées de la plus probable à la moins
// probable, de somme 1 : le front les affiche sans les recalculer (R5). Transcription (EF-10) :
// pas de classe ni de probabilités, le texte complet dans text (null pour les autres tâches).
export interface TaskResult {
  status: TaskResultStatus
  message: string | null
  label: string | null
  label_fr: string | null
  probabilities: ClassProbability[]
  model_id: string | null
  model_version: string | null
  calibrated: boolean | null
  segments: SegmentResult[]
  text: string | null
}

// Un résultat par tâche demandée ; une tâche non demandée est absente.
export interface AnalysisResults {
  emotion?: TaskResult
  sound_event?: TaskResult
  transcription?: TaskResult
  speaker?: TaskResult
}

export interface Analysis {
  id: string
  created_at: string
  original_filename: string
  status: AnalysisStatusValue
  error_message: string | null
  duration_s: number | null
  tasks: AnalysisTask[]
  profile: AnalysisProfile
  audio_url: string | null
  spectrogram_url: string | null
  spectrogram: SpectrogramInfo | null
  // null tant que l'analyse n'est pas terminée (et en cas d'échec).
  results: AnalysisResults | null
}

// Résumé d'une tâche dans l'historique (TaskSummarySchema) : le premier choix et sa
// probabilité, sans segments ni liste de probabilités.
export interface TaskResultSummary {
  status: TaskResultStatus
  message: string | null
  label: string | null
  label_fr: string | null
  probability: number | null
  model_id: string | null
  model_version: string | null
  calibrated: boolean | null
}

export interface AnalysisResultsSummary {
  emotion?: TaskResultSummary
  sound_event?: TaskResultSummary
  transcription?: TaskResultSummary
  speaker?: TaskResultSummary
}

// Analyse telle que la renvoie l'historique (GET /analyses) : ni audio, ni spectrogramme, et
// des résultats résumés. Le détail complet se lit avec useAnalysis.
export interface AnalysisSummary {
  id: string
  created_at: string
  original_filename: string
  status: AnalysisStatusValue
  error_message: string | null
  duration_s: number | null
  tasks: AnalysisTask[]
  profile: AnalysisProfile
  results: AnalysisResultsSummary | null
}

export interface AnalysisRequest {
  file: File
  tasks: AnalysisTask[]
  profile: AnalysisProfile
}

// Formulaire de POST /analyses : le champ « tasks » est répété une fois par tâche.
function buildAnalysisForm(request: AnalysisRequest): FormData {
  const form = new FormData()
  form.append('file', request.file)
  for (const task of request.tasks) {
    form.append('tasks', task)
  }
  form.append('profile', request.profile)
  return form
}

// Envoi d'un audio à analyser : l'API répond 202 avec l'analyse en attente.
export function useCreateAnalysis() {
  return useMutation({
    mutationFn: (request: AnalysisRequest) => {
      const form = buildAnalysisForm(request)
      return apiPostForm<Analysis>('/analyses', form)
    },
  })
}

// Une analyse est encore en cours tant que le serveur n'a pas fini (done) ou échoué (failed).
export function isAnalysisRunning(analysis: Analysis | AnalysisSummary): boolean {
  if (analysis.status === 'pending') {
    return true
  }
  return analysis.status === 'processing'
}

// Prochaine interrogation : dans 1 s si l'analyse tourne encore, sinon arrêt (false).
function nextPollDelay(analysis: Analysis | undefined): number | false {
  if (analysis === undefined) {
    return false
  }
  if (isAnalysisRunning(analysis)) {
    return POLL_INTERVAL_MS
  }
  return false
}

// Suivi d'une analyse : interroge GET /analyses/{id} chaque seconde jusqu'à done ou failed.
export function useAnalysis(analysisId: string | null) {
  return useQuery({
    queryKey: ['analysis', analysisId],
    queryFn: () => {
      const path = `/analyses/${analysisId}`
      return apiGet<Analysis>(path)
    },
    enabled: analysisId !== null,
    refetchInterval: (query) => {
      const analysis = query.state.data
      return nextPollDelay(analysis)
    },
  })
}

// Nombre d'analyses chargées par l'historique : le maximum accepté par l'API (MAX_PAGE_SIZE).
const HISTORY_LIMIT = 100

// Clé du cache de l'historique, partagée par la lecture et la suppression.
const HISTORY_QUERY_KEY = ['analyses']

// Vrai si au moins une analyse de la liste tourne encore (pending ou processing).
function hasRunningAnalysis(analyses: AnalysisSummary[]): boolean {
  for (const analysis of analyses) {
    if (isAnalysisRunning(analysis)) {
      return true
    }
  }
  return false
}

// Historique : les analyses les plus récentes d'abord, en version résumée (EF-08). Rafraîchi chaque seconde tant
// qu'une analyse de la liste tourne encore, pour que son statut se mette à jour tout seul.
export function useAnalysisHistory() {
  return useQuery({
    queryKey: HISTORY_QUERY_KEY,
    queryFn: () => {
      const path = `/analyses?limit=${HISTORY_LIMIT}`
      return apiGet<AnalysisSummary[]>(path)
    },
    refetchInterval: (query) => {
      const analyses = query.state.data
      if (analyses === undefined) {
        return false
      }
      if (hasRunningAnalysis(analyses)) {
        return POLL_INTERVAL_MS
      }
      return false
    },
  })
}

// Suppression d'une analyse, puis rechargement de l'historique pour la faire disparaître.
export function useDeleteAnalysis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (analysisId: string) => {
      const path = `/analyses/${analysisId}`
      return apiDelete(path)
    },
    onSuccess: () => {
      return queryClient.invalidateQueries({ queryKey: HISTORY_QUERY_KEY })
    },
  })
}

// Un modèle du registre (GET /api/v1/models, EF-16) : identité, famille, scores de test,
// calibration et lien vers ses poids. Écrit à la main d'après ModelSchema (api/models.py).
export interface ModelInfo {
  id: string
  task: AnalysisTask | 'voice_cloning'
  family: 'baseline' | 'A' | 'B' | 'pretrained'
  profiles: AnalysisProfile[]
  version: string
  f1_macro: number | null
  accuracy: number | null
  temperature: number | null
  calibrated: boolean
  huggingface_url: string | null
  revision: string | null
  description: string
}

// Catalogue des modèles : il ne change qu'avec le registre, donc une seule lecture suffit.
export function useModels() {
  return useQuery({
    queryKey: ['models'],
    queryFn: () => apiGet<ModelInfo[]>('/models'),
    staleTime: Infinity,
  })
}

// Tâches comparables (EF-15) : celles qui ont plusieurs modèles au registre.
export type ComparedTask = 'emotion' | 'sound_event' | 'transcription'

// Passage d'un modèle sur le fichier comparé (ModelRunSchema, api/compare.py) : son identité,
// ses profils, son temps de calcul (VAD exclue) et son résultat au format d'une analyse.
export interface ModelRun {
  model_id: string
  model_version: string
  profiles: AnalysisProfile[]
  compute_s: number
  result: TaskResult
}

// Comparaison telle que la liste de l'Historique l'affiche, sans les résultats.
export interface ComparisonSummary {
  id: string
  created_at: string
  original_filename: string
  status: AnalysisStatusValue
  error_message: string | null
  duration_s: number | null
  tasks: ComparedTask[]
}

// Comparaison complète : pour chaque tâche, un passage par modèle (null tant que le calcul
// tourne).
export interface Comparison extends ComparisonSummary {
  results: Partial<Record<ComparedTask, ModelRun[]>> | null
  audio_url: string | null
}

export interface ComparisonRequest {
  file: File
  tasks: ComparedTask[]
}

// Clé du cache de la liste des comparaisons, partagée par la lecture et la suppression.
const COMPARISONS_QUERY_KEY = ['comparisons']

// Formulaire de POST /compare : le champ « tasks » est répété une fois par tâche.
function buildComparisonForm(request: ComparisonRequest): FormData {
  const form = new FormData()
  form.append('file', request.file)
  for (const task of request.tasks) {
    form.append('tasks', task)
  }
  return form
}

// Envoi d'un audio à comparer : l'API répond 202 avec la comparaison en attente.
export function useCreateComparison() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (request: ComparisonRequest) => {
      const form = buildComparisonForm(request)
      return apiPostForm<Comparison>('/compare', form)
    },
    onSuccess: () => {
      return queryClient.invalidateQueries({ queryKey: COMPARISONS_QUERY_KEY })
    },
  })
}

// Vrai tant que le serveur n'a pas fini (en attente ou en cours).
function isComparisonRunning(comparison: ComparisonSummary | undefined): boolean {
  if (comparison === undefined) {
    return false
  }
  return comparison.status === 'pending' || comparison.status === 'processing'
}

// Suivi d'une comparaison : interroge GET /compare/{id} chaque seconde jusqu'à la fin.
export function useComparison(comparisonId: string | null) {
  return useQuery({
    queryKey: ['comparison', comparisonId],
    queryFn: () => apiGet<Comparison>(`/compare/${comparisonId}`),
    enabled: comparisonId !== null,
    refetchInterval: (query) => {
      if (isComparisonRunning(query.state.data)) {
        return POLL_INTERVAL_MS
      }
      return false
    },
  })
}

// Comparaisons passées, les plus récentes d'abord (Historique).
export function useComparisons() {
  return useQuery({
    queryKey: COMPARISONS_QUERY_KEY,
    queryFn: () => apiGet<ComparisonSummary[]>(`/compare?limit=${HISTORY_LIMIT}`),
  })
}

// Suppression d'une comparaison et de son audio, puis rechargement de la liste.
export function useDeleteComparison() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (comparisonId: string) => apiDelete(`/compare/${comparisonId}`),
    onSuccess: () => {
      return queryClient.invalidateQueries({ queryKey: COMPARISONS_QUERY_KEY })
    },
  })
}
