// Lecture des jetons de la charte (web/src/index.css) pour ce qui ne comprend pas les classes
// Tailwind, comme le canvas de la forme d'onde. Seul fichier autorisé à lire les jetons
// directement (voir scripts/check-tokens.mjs).

// Valeur d'une variable CSS de la charte, par exemple readCssColor('--color-night').
// Elle suit le thème clair ou sombre en cours, puisque index.css redéfinit les variables.
export function readCssColor(name: string): string {
  const rootStyle = getComputedStyle(document.documentElement)
  const value = rootStyle.getPropertyValue(name)
  return value.trim()
}

export type Theme = 'dark' | 'light'

// Clé du choix de thème dans le navigateur.
const THEME_STORAGE_KEY = 'echolens-theme'

// Requête CSS qui dit si le système est réglé en sombre.
const DARK_SCHEME_QUERY = '(prefers-color-scheme: dark)'

// Thème choisi par la personne avec le bouton, ou null si elle n'a jamais choisi. Le
// stockage peut être indisponible (navigation privée, données bloquées) : null aussi.
export function readSavedTheme(): Theme | null {
  try {
    const saved = window.localStorage.getItem(THEME_STORAGE_KEY)
    if (saved === 'light' || saved === 'dark') {
      return saved
    }
  } catch {
    // Stockage refusé : aucun choix connu.
  }
  return null
}

// Thème du système (préférence prefers-color-scheme du navigateur).
export function systemTheme(): Theme {
  const prefersDark = window.matchMedia(DARK_SCHEME_QUERY).matches
  if (prefersDark) {
    return 'dark'
  }
  return 'light'
}

// Thème à l'ouverture : le choix enregistré s'il existe, sinon celui du système.
export function initialTheme(): Theme {
  const saved = readSavedTheme()
  if (saved !== null) {
    return saved
  }
  return systemTheme()
}

// Thème affiché en ce moment (index.css lit data-theme sur <html>).
export function currentTheme(): Theme {
  if (document.documentElement.dataset.theme === 'light') {
    return 'light'
  }
  return 'dark'
}

// Affiche un thème, sans le mémoriser.
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
}

// Mémorise le choix fait avec le bouton : il primera ensuite sur le thème du système.
export function saveTheme(theme: Theme): void {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    // Stockage refusé : le choix vaut pour cette visite seulement.
  }
}

// Tant que personne n'a choisi, la page suit le système, même s'il change pendant la visite.
export function followSystemTheme(): void {
  const query = window.matchMedia(DARK_SCHEME_QUERY)
  query.addEventListener('change', () => {
    if (readSavedTheme() === null) {
      applyTheme(systemTheme())
    }
  })
}
