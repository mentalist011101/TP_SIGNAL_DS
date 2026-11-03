import { useQuery } from '@tanstack/react-query'

// Préfixe commun de l'API versionnée exposée par Flask.
export const API_BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Appel JSON générique : lève une ApiError lisible si la réponse n'est pas 2xx.
export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) {
    throw new ApiError(response.status, `Erreur ${response.status} sur ${path}`)
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
