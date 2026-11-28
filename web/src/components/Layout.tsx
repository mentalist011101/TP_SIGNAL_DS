import type { ComponentType } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { useHealth } from '../api/client.ts'
import AccountChip from './AccountChip.tsx'
import Brand from './Brand.tsx'
import {
  CompareIcon,
  HistoryIcon,
  LiveIcon,
  MicIcon,
  ModelsIcon,
  PlusIcon,
  SpeakersIcon,
  WaveIcon,
} from './icons.tsx'
import ThemeToggle from './ThemeToggle.tsx'

interface NavItem {
  to: string
  label: string
  icon: ComponentType<{ className?: string }>
}

// Pages du menu, dans l'ordre d'usage : analyser un fichier ou le micro, comparer, gérer et
// cloner les voix, puis l'historique et les modèles.
const MAIN_ITEMS: NavItem[] = [
  { to: '/analyser', label: 'Analyser', icon: WaveIcon },
  { to: '/direct', label: 'Direct', icon: LiveIcon },
  { to: '/comparer', label: 'Comparer', icon: CompareIcon },
  { to: '/locuteurs', label: 'Locuteurs', icon: SpeakersIcon },
  { to: '/cloner', label: 'Cloner', icon: MicIcon },
  { to: '/historique', label: 'Historique', icon: HistoryIcon },
  { to: '/modeles', label: 'Modèles', icon: ModelsIcon },
]

const NEW_ANALYSIS_CLASSES =
  'flex items-center justify-center gap-2 rounded-btn bg-accent px-4 py-2.5 text-sm font-semibold text-on-accent transition-colors duration-200 ease-out-soft hover:bg-accent-deep'

const ITEM_CLASSES =
  'flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors duration-200 ease-out-soft'
const ACTIVE_ITEM_CLASSES = `${ITEM_CLASSES} bg-paper-alt font-semibold text-ink`
const INACTIVE_ITEM_CLASSES = `${ITEM_CLASSES} text-ink-soft hover:bg-paper-alt hover:text-ink`

const MOBILE_ITEM_CLASSES = 'rounded-btn px-3 py-1 text-sm whitespace-nowrap'
const MOBILE_ACTIVE_CLASSES = `${MOBILE_ITEM_CLASSES} bg-accent font-semibold text-on-accent`
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

// Une rubrique du menu : son titre discret, puis ses entrées avec icône.
function NavSection({ title, items }: { title: string; items: NavItem[] }) {
  return (
    <div className="space-y-0.5">
      <p className="label-mono px-3 pb-1.5 text-ink-faint">{title}</p>
      {items.map((item) => (
        <NavLink key={item.to} to={item.to} className={itemClasses}>
          <item.icon className="h-4 w-4 shrink-0" />
          {item.label}
        </NavLink>
      ))}
    </div>
  )
}

// Barre latérale (grand écran) : logo, action principale, menu. Le thème et le compte sont en
// haut à droite du contenu (TopBar). Le fond occupe toute la hauteur de la page ; le contenu
// reste fixe pendant le défilement.
function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 border-r border-rule bg-card lg:block">
      <div className="sticky top-0 flex h-screen flex-col gap-6 px-4 py-5">
        <div className="px-1.5">
          <Brand />
        </div>
        <Link to="/analyser" className={NEW_ANALYSIS_CLASSES}>
          <PlusIcon />
          Nouvelle analyse
        </Link>
        <nav className="space-y-6" aria-label="Menu de l’application">
          <NavSection title="Espace" items={MAIN_ITEMS} />
        </nav>
      </div>
    </aside>
  )
}

// Barre du haut (téléphone) : logo, thème, compte et action principale, puis le menu qui
// défile.
function MobileBar() {
  return (
    <header className="sticky top-0 z-10 space-y-3 border-b border-rule bg-paper/85 px-4 py-3 backdrop-blur lg:hidden">
      <div className="flex items-center justify-between gap-3">
        <Brand />
        <div className="flex items-center gap-2">
          <ThemeToggle discreet />
          <AccountChip compact />
          <Link to="/analyser" className={NEW_ANALYSIS_CLASSES}>
            <PlusIcon />
            Analyser
          </Link>
        </div>
      </div>
      <nav className="flex gap-1 overflow-x-auto" aria-label="Menu de l’application">
        {MAIN_ITEMS.map((item) => (
          <NavLink key={item.to} to={item.to} className={mobileItemClasses}>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </header>
  )
}

// Barre du haut (grand écran), à droite du contenu : le thème, discret, et le compte.
function TopBar() {
  return (
    <div className="hidden items-center justify-end gap-3 px-12 pt-5 lg:flex">
      <ThemeToggle discreet />
      <AccountChip />
    </div>
  )
}

// Rien quand tout va bien ; un bandeau seulement si le serveur ne répond plus (F1).
function ServerDownBanner() {
  const health = useHealth()
  if (!health.isError) {
    return null
  }
  return (
    <p className="mb-6 rounded-card border border-danger px-4 py-3 text-sm text-danger">
      Le serveur ne répond pas. Vérifiez qu’il est lancé, puis réessayez.
    </p>
  )
}

// Coque de l'application, à la manière des outils comme Linear : menu à gauche, contenu à
// droite sur la grille de points.
export default function Layout() {
  return (
    <div className="min-h-screen bg-paper text-ink lg:flex">
      <Sidebar />
      <MobileBar />
      <main className="dot-grid min-w-0 flex-1">
        <TopBar />
        <div className="mx-auto max-w-6xl px-4 py-8 lg:px-12 lg:pt-4 lg:pb-10">
          <ServerDownBanner />
          <Outlet />
        </div>
      </main>
    </div>
  )
}
