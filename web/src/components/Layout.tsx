import type { ComponentType } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useHealth } from '../api/client.ts'
import {
  CompareIcon,
  HistoryIcon,
  LiveIcon,
  ModelsIcon,
  PlusIcon,
  SpeakersIcon,
  WaveIcon,
} from './icons.tsx'

interface NavItem {
  to: string
  label: string
  icon: ComponentType<{ className?: string }>
}

// Pages déjà utilisables.
const MAIN_ITEMS: NavItem[] = [{ to: '/historique', label: 'Historique', icon: HistoryIcon }]

// Pages prévues par la spécification, encore vides : on les annonce sans les cacher.
const SOON_ITEMS: NavItem[] = [
  { to: '/direct', label: 'Direct', icon: LiveIcon },
  { to: '/comparer', label: 'Comparer', icon: CompareIcon },
  { to: '/locuteurs', label: 'Locuteurs', icon: SpeakersIcon },
  { to: '/modeles', label: 'Modèles', icon: ModelsIcon },
]

const NEW_ANALYSIS_CLASSES =
  'flex items-center justify-center gap-2 rounded-btn bg-accent px-3 py-2 text-sm font-semibold text-on-accent transition-colors duration-200 ease-out-soft hover:bg-accent-deep'

// La bordure est toujours là (transparente) pour que l'entrée active ne fasse pas bouger le menu.
const ITEM_CLASSES =
  'flex items-center gap-3 rounded-btn border px-2.5 py-1.5 text-sm transition-colors duration-200 ease-out-soft'
const ACTIVE_ITEM_CLASSES = `${ITEM_CLASSES} border-rule bg-card font-semibold text-ink`
const INACTIVE_ITEM_CLASSES = `${ITEM_CLASSES} border-transparent text-ink-soft hover:bg-card hover:text-ink`

const MOBILE_ITEM_CLASSES = 'rounded-btn px-3 py-1 text-sm whitespace-nowrap'
const MOBILE_ACTIVE_CLASSES = `${MOBILE_ITEM_CLASSES} bg-ink font-semibold text-paper`
const MOBILE_INACTIVE_CLASSES = `${MOBILE_ITEM_CLASSES} text-ink-soft`

function itemClasses({ isActive }: { isActive: boolean }): string {
  if (isActive) {
    return ACTIVE_ITEM_CLASSES
  }
  return INACTIVE_ITEM_CLASSES
}

function mobileItemClasses({ isActive }: { isActive: boolean }): string {
  if (isActive) {
    return MOBILE_ACTIVE_CLASSES
  }
  return MOBILE_INACTIVE_CLASSES
}

// Logo : la forme d'onde dans un carré d'encre, puis le nom et le cadre du projet.
function Brand() {
  return (
    <Link to="/" className="flex items-center gap-2.5">
      <span className="flex h-8 w-8 items-center justify-center rounded-btn bg-ink text-paper">
        <WaveIcon className="h-5 w-5" />
      </span>
      <span className="flex flex-col leading-tight">
        <span className="font-display text-lg font-extrabold tracking-tight">EchoLens</span>
        <span className="label-mono text-ink-faint">INF50101</span>
      </span>
    </Link>
  )
}

// Une rubrique du menu : son titre discret, puis ses entrées avec icône.
function NavSection({ title, items }: { title: string; items: NavItem[] }) {
  return (
    <div className="space-y-1">
      <p className="label-mono px-2.5 pb-1 text-ink-faint">{title}</p>
      {items.map((item) => (
        <NavLink key={item.to} to={item.to} className={itemClasses}>
          <item.icon className="h-4 w-4 shrink-0" />
          {item.label}
        </NavLink>
      ))}
    </div>
  )
}

// Barre latérale (grand écran) : logo, action principale, puis le menu. Le fond occupe toute
// la hauteur de la page ; le contenu, lui, reste fixe à l'écran pendant le défilement.
function Sidebar() {
  return (
    <aside className="hidden w-60 shrink-0 border-r border-rule bg-paper-alt lg:block">
      <div className="sticky top-0 flex h-screen flex-col gap-6 px-3 py-5">
        <div className="px-1.5">
          <Brand />
        </div>
        <Link to="/" className={NEW_ANALYSIS_CLASSES}>
          <PlusIcon />
          Nouvelle analyse
        </Link>
        <nav className="space-y-6" aria-label="Menu principal">
          <NavSection title="Espace" items={MAIN_ITEMS} />
          <NavSection title="Bientôt" items={SOON_ITEMS} />
        </nav>
      </div>
    </aside>
  )
}

// Barre du haut (téléphone) : logo et action principale, puis le menu qui défile de côté.
function MobileBar() {
  const allItems = [...MAIN_ITEMS, ...SOON_ITEMS]
  return (
    <header className="sticky top-0 z-10 space-y-3 border-b border-rule bg-paper/85 px-4 py-3 backdrop-blur lg:hidden">
      <div className="flex items-center justify-between gap-3">
        <Brand />
        <Link to="/" className={NEW_ANALYSIS_CLASSES}>
          <PlusIcon />
          Analyser
        </Link>
      </div>
      <nav className="flex gap-1 overflow-x-auto" aria-label="Menu principal">
        {allItems.map((item) => (
          <NavLink key={item.to} to={item.to} className={mobileItemClasses}>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </header>
  )
}

// Rien quand tout va bien ; un bandeau seulement si le serveur ne répond plus (F1).
function ServerDownBanner() {
  const health = useHealth()
  if (!health.isError) {
    return null
  }
  return (
    <p className="mb-6 rounded-card border border-danger bg-card px-4 py-3 text-sm text-danger">
      Le serveur ne répond pas. Vérifiez qu’il est lancé, puis réessayez.
    </p>
  )
}

// Coque de l'application, à la manière des outils comme Linear : menu à gauche, contenu à
// droite. Le grain du papier reste sur le fond ; les surfaces posées dessus n'en ont pas.
export default function Layout() {
  return (
    <div className="paper-grain min-h-screen bg-paper text-ink lg:flex">
      <Sidebar />
      <MobileBar />
      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-6xl px-4 py-8 lg:px-10 lg:py-10">
          <ServerDownBanner />
          <Outlet />
        </div>
      </main>
    </div>
  )
}
