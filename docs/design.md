# Charte graphique d'EchoLens (v2)

EchoLens se présente comme un produit : une plateforme où l'on dépose un audio pour en extraire
événements sonores, émotions, transcription et locuteurs. La charte v2 s'inspire des outils
SaaS actuels (Linear, ElevenLabs, Cluster) en gardant l'identité de la v1 : le papier et l'encre,
le vert mousse, les étiquettes en mono et la palette magma réservée aux données.

Les jetons sont définis dans `web/src/index.css`, pour un thème sombre (anthracite chaud) et un
thème clair « papier ». **Par défaut, la page suit le thème du système** (`prefers-color-scheme`),
y compris s'il change pendant la visite. Le bouton de thème (barre latérale) bascule de l'un à
l'autre et mémorise ce choix dans le navigateur, qui prime ensuite sur le système
(`web/src/theme.ts`, attribut `data-theme` sur `<html>`).

## Jetons

Les noms disent le **rôle**, jamais la couleur.

| Jeton | Sombre | Clair | Rôle |
| --- | --- | --- | --- |
| `paper` | `#131211` | `#f7f3ea` | Fond de la page |
| `paper-alt` | `#24221f` | `#ebe4d4` | Zones en retrait, survols, pistes des barres |
| `card` | `#1a1917` | `#fffdf8` | Surfaces : cartes, barre latérale |
| `ink` | `#f2efe8` | `#16181d` | Texte principal |
| `ink-soft` | `#b5afa5` | `#55595f` | Texte secondaire : consignes, libellés |
| `ink-faint` | `#8f897f` | `#6b6e74` | Mentions discrètes (4,5:1 au moins sur le fond) |
| `rule` | crème à 9 % | encre à 10 % | Filets et bordures légères |
| `rule-strong` | crème à 18 % | encre à 22 % | Bordures marquées : boutons secondaires, champs |
| `night` | `#0b0a09` | `#151c2e` | Fond des tracés (forme d'onde) |
| `on-night` | `#f1efe8` | `#f1efe8` | Texte posé sur `night` ou sur les données |
| `accent` | `#f2efe8` | `#16181d` | Tout ce qui se clique : bouton principal, cases, segment choisi |
| `accent-deep` | `#d9d3c7` | `#2b2e35` | Accent au survol |
| `on-accent` | `#131211` | `#f7f3ea` | Texte posé sur l'accent |
| `accent-ink` | `#f2efe8` | `#16181d` | Liens et contour de focus |
| `accent-soft` | `#9cc58a` | `#9cc58a` | Tracé de la forme d'onde sur `night` |
| `brand` | `#9cc58a` | `#4a7a3a` | Marque : logo, statut « terminée », « en direct », mot mis en valeur |
| `danger` | `#e8763a` | `#b4400f` | Erreurs uniquement |

Polices : `font-display` (Instrument Serif, une seule graisse) pour les grands titres,
`font-sans` (Inter 400/500/600) pour le texte et les petits titres, `font-mono`
(JetBrains Mono 400/500) pour les valeurs techniques et les étiquettes (`label-mono`).
Rayons : `radius-card` (16 px), `radius-btn` (pilule). Pas d'ombre portée : les surfaces se
distinguent par une bordure fine. Fond de page : grille de points (`dot-grid`). Transition :
`ease-out-soft`.

## Règles

- **Uniquement des jetons** : aucune couleur Tailwind (`slate-500`…) ni code hexadécimal dans
  les composants. `npm run check:tokens` le vérifie, en local et dans la CI. Le canvas lit les
  jetons avec `readCssColor` (`web/src/theme.ts`, seul fichier autorisé à lire les couleurs).
- **Accent monochrome = ce qui se clique** : bouton principal en pilule crème (sombre) ou
  encre (clair), cases à cocher, segment choisi, focus. Aucun des outils de référence n'a de
  bouton principal coloré : la couleur reste rare.
- **Vert mousse = la marque** : logo, statut « terminée », indicateur « en direct », mot mis
  en valeur dans un titre, et sur la frise temporelle la parole détectée, la tête de lecture
  et le remplissage des fenêtres d'événements (opacité selon la probabilité, plafonnée pour
  garder le texte lisible). Jamais un bouton.
- **Danger = les erreurs** : messages d'échec, refus de fichier. Pas pour décorer.
- **Magma réservé aux données** : la palette du spectrogramme ne sert à rien d'autre, et
  l'interface n'utilise pas ses couleurs.
- **Pas de motif derrière les données** : la grille de points est sur le fond de page
  seulement ; cartes, forme d'onde et spectrogramme restent unis.
- **Serif pour les grands titres seulement** (titres de page, chiffres clés, résultat
  principal) ; Inter demi-gras pour les titres de carte ; mono pour Hz, dB, durées, noms de
  fichiers et étiquettes.
- **Honnêteté** : des probabilités du faux
  prédicteur sont signalées par le bandeau « démo », une fonction pas encore branchée est
  marquée « bientôt ».
- **Mouvement** : les animations (ruban d'ondes, points « en direct », suivi d'analyse)
  s'arrêtent quand le système demande moins d'animations (`motion-safe`,
  `prefers-reduced-motion`).
- **Contraste WCAG AA** (4,5:1 pour le texte) dans les deux thèmes.

## Origine

La v1 reprenait la charte du portfolio de Luciano (papier, encre, Archivo, rayons de 3 et
6 px, ombres dures). La v2 en garde le papier et l'encre (thème clair), le vert mousse, les
étiquettes mono et la palette magma, et adopte un thème sombre (le système choisit), le serif pour les titres,
les boutons en pilule et les surfaces plates.
