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

// Thème choisi la dernière fois ; sombre par défaut (charte v2). Le stockage peut être
// indisponible (navigation privée, données bloquées) : on retombe alors sur le défaut.
export function readSavedTheme(): Theme {
  try {
    const saved = window.localStorage.getItem(THEME_STORAGE_KEY)
    if (saved === 'light') {
      return 'light'
    }
  } catch {
    // Stockage refusé : thème par défaut.
  }
  return 'dark'
}

// Applique le thème (index.css lit data-theme sur <html>) et le mémorise si possible.
export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme)
  } catch {
    // Stockage refusé : le thème vaut pour cette visite seulement.
  }
}
