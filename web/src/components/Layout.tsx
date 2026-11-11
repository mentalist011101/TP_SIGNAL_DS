import { NavLink, Outlet } from 'react-router-dom'
import { useHealth } from '../api/client.ts'

const NAV_ITEMS = [
  { to: '/', label: 'Analyser' },
  { to: '/direct', label: 'Direct' },
  { to: '/comparer', label: 'Comparer' },
  { to: '/historique', label: 'Historique' },
  { to: '/locuteurs', label: 'Locuteurs' },
  { to: '/modeles', label: 'Modèles' },
] as const

const PILL_CLASSES = 'rounded-btn px-3 py-1.5 text-sm transition-colors duration-200 ease-out-soft'
const ACTIVE_PILL_CLASSES = `${PILL_CLASSES} bg-ink text-paper`
const INACTIVE_PILL_CLASSES = `${PILL_CLASSES} text-ink-soft hover:bg-paper-alt hover:text-ink`

// Pastille de navigation : fond ink pour la page active, texte ink-soft pour les autres.
function pillClasses({ isActive }: { isActive: boolean }): string {
  if (isActive) {
    return ACTIVE_PILL_CLASSES
  }
  return INACTIVE_PILL_CLASSES
}

// Nom de l'application et cadre du projet.
function Brand() {
  return (
    <div className="flex flex-col">
      <span className="font-display text-2xl font-extrabold tracking-tight">EchoLens</span>
      <span className="label-mono text-ink-faint">INF50101 · Projet 1</span>
    </div>
  )
}

// Liste des pages de l'application.
function Navigation() {
  return (
    <ul className="flex flex-wrap gap-1">
      {NAV_ITEMS.map((item) => (
        <li key={item.to}>
          <NavLink to={item.to} end={item.to === '/'} className={pillClasses}>
            {item.label}
          </NavLink>
        </li>
      ))}
    </ul>
  )
}

// État de la connexion à l'API, affiché dans le pied de page.
function apiStatusText(health: ReturnType<typeof useHealth>): string {
  if (health.isSuccess) {
    return `API connectée · version ${health.data.version}`
  }
  if (health.isError) {
    return 'API injoignable : vérifiez que l’application est lancée'
  }
  return 'Connexion à l’API…'
}

function Footer() {
  const health = useHealth()
  const statusText = apiStatusText(health)
  return (
    <footer className="border-t border-rule px-4 py-3 text-center font-mono text-xs text-ink-soft">
      {statusText}
    </footer>
  )
}

// Gabarit commun : en-tête, contenu de la page, pied de page. Le grain du papier reste sur le
// fond de page ; les cartes et les tracés posés dessus n'en ont pas.
export default function Layout() {
  return (
    <div className="paper-grain flex min-h-screen flex-col bg-paper text-ink">
      <header className="border-b border-rule">
        <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-8 px-4 py-4">
          <Brand />
          <Navigation />
        </nav>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>

      <Footer />
    </div>
  )
}
