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
