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

// Gabarit commun : en-tête de navigation, contenu de la page, état de l'API.
export default function Layout() {
  const health = useHealth()

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900">
        <nav className="mx-auto flex max-w-6xl flex-wrap items-center gap-6 px-4 py-3">
          <span className="text-lg font-semibold tracking-tight">EchoLens</span>
          <ul className="flex flex-wrap gap-1">
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `rounded-md px-3 py-1.5 text-sm transition-colors ${
                      isActive
                        ? 'bg-brand-50 text-brand-600 dark:bg-slate-800 dark:text-white'
                        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 px-4 py-3 text-center text-xs text-slate-500 dark:border-slate-800">
        {health.isSuccess
          ? `API connectée · version ${health.data.version}`
          : health.isError
            ? 'API injoignable : lancez le serveur Flask (make run)'
            : 'Connexion à l’API…'}
      </footer>
    </div>
  )
}
