import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App.tsx'
import './index.css'
import { applyTheme, followSystemTheme, initialTheme } from './theme.ts'

// Thème appliqué avant le premier affichage, pour éviter un éclair de l'autre thème : le choix
// enregistré, sinon celui du système, que la page suit tant qu'aucun choix n'est fait.
applyTheme(initialTheme())
followSystemTheme()

// Client de requêtes partagé : cache et états de chargement des appels à l'API.
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
