import { useState } from 'react'
import { applyTheme, currentTheme, saveTheme, type Theme } from '../theme.ts'
import { MoonIcon, SunIcon } from './icons.tsx'

const BUTTON_CLASSES =
  'flex h-9 w-9 items-center justify-center rounded-btn border border-rule text-ink-soft transition-colors duration-200 ease-out-soft hover:bg-paper-alt hover:text-ink'
// Variante discrète (menu de l'accueil) : une simple icône, sans cadre, qui ne se fait pas
// passer pour une action principale.
const DISCREET_CLASSES =
  'flex h-8 w-8 items-center justify-center rounded-btn text-ink-faint transition-colors duration-200 ease-out-soft hover:text-ink'

interface ThemeToggleProps {
  discreet?: boolean
}

// Bouton qui passe du thème sombre au thème clair, et inversement. Par défaut la page suit le
// système ; le choix fait ici est mémorisé dans le navigateur et prime ensuite (theme.ts).
export default function ThemeToggle({ discreet = false }: ThemeToggleProps) {
  const [theme, setTheme] = useState<Theme>(currentTheme)

  function toggle() {
    let nextTheme: Theme = 'light'
    if (theme === 'light') {
      nextTheme = 'dark'
    }
    applyTheme(nextTheme)
    saveTheme(nextTheme)
    setTheme(nextTheme)
  }

  // Le bouton montre le thème vers lequel on va : le soleil en sombre, la lune en clair.
  let label = 'Passer au thème clair'
  let icon = <SunIcon />
  if (theme === 'light') {
    label = 'Passer au thème sombre'
    icon = <MoonIcon />
  }
  let classes = BUTTON_CLASSES
  if (discreet) {
    classes = DISCREET_CLASSES
  }
  return (
    <button type="button" className={classes} aria-label={label} title={label} onClick={toggle}>
      {icon}
    </button>
  )
}
