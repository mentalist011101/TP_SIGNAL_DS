import { useMutation, useQuery } from '@tanstack/react-query'

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
export function isAnalysisRunning(analysis: Analysis): boolean {
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
