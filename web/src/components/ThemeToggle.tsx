import { useState } from 'react'
import { applyTheme, readSavedTheme, type Theme } from '../theme.ts'
import { MoonIcon, SunIcon } from './icons.tsx'

const BUTTON_CLASSES =
  'flex h-9 w-9 items-center justify-center rounded-btn border border-rule text-ink-soft transition-colors duration-200 ease-out-soft hover:bg-paper-alt hover:text-ink'

// Bouton qui passe du thème sombre (par défaut) au thème clair, et inversement. Le choix est
// mémorisé dans le navigateur (theme.ts).
export default function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(readSavedTheme)

  function toggle() {
    let nextTheme: Theme = 'light'
    if (theme === 'light') {
      nextTheme = 'dark'
    }
    applyTheme(nextTheme)
    setTheme(nextTheme)
  }

  // Le bouton montre le thème vers lequel on va : le soleil en sombre, la lune en clair.
  let label = 'Passer au thème clair'
  let icon = <SunIcon />
  if (theme === 'light') {
    label = 'Passer au thème sombre'
    icon = <MoonIcon />
  }
  return (
    <button
      type="button"
      className={BUTTON_CLASSES}
      aria-label={label}
      title={label}
      onClick={toggle}
    >
      {icon}
    </button>
  )
}
