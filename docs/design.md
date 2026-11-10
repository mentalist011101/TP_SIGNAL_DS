# Charte graphique d'EchoLens

La charte reprend celle du portfolio de Luciano (papier, encre, polices, rayons, ombres), avec un
accent propre à EchoLens : un vert mousse. Les jetons sont définis dans `web/src/index.css` ; le
thème sombre suit la préférence du système et ne change que leurs valeurs.

## Jetons

Les noms disent le **rôle**, jamais la couleur.

| Jeton | Clair | Sombre | Rôle |
| --- | --- | --- | --- |
| `paper` | `#f7f3ea` | `#12151c` | Fond de la page |
| `paper-alt` | `#efe9dc` | `#171b24` | Zones en retrait, survols discrets |
| `card` | `#fffdf8` | `#1b202b` | Fond des cartes |
| `ink` | `#16181d` | `#f1efe8` | Texte principal |
| `ink-soft` | `#5c6069` | `#b6bac4` | Texte secondaire : consignes, libellés |
| `ink-faint` | `#8a8d95` | `#7e8492` | Mentions discrètes |
| `rule` | encre à 14 % | blanc à 12 % | Filets et bordures légères |
| `rule-strong` | encre à 32 % | blanc à 26 % | Bordures marquées : boutons secondaires, champs |
| `night` | `#151c2e` | `#090b10` | Fond des tracés (forme d'onde) |
| `on-night` | `#f1efe8` | `#f1efe8` | Texte posé sur `night` ou sur les données |
| `accent` | `#4a7a3a` | `#4a7a3a` | Tout ce qui se clique |
| `accent-deep` | `#355a29` | `#355a29` | Accent au survol |
| `accent-soft` | `#9cc58a` | `#9cc58a` | Texte ou tracé sur fond sombre (forme d'onde) |
| `on-accent` | `#ffffff` | `#ffffff` | Texte posé sur l'accent (bouton principal) |
| `accent-ink` | `#4a7a3a` | `#9cc58a` | Accent employé comme texte (liens) ou contour de focus |
| `danger` | `#b4400f` | `#e8763a` | Erreurs uniquement |

Polices : `font-display` (Archivo 700/800), `font-sans` (Inter 400/500/600), `font-mono`
(JetBrains Mono 400/500). Rayons : `radius-card` (3 px), `radius-btn` (6 px). Ombres :
`shadow-card` (cartes), `shadow-hard-sm` (boutons secondaires). Transition : `ease-out-soft`.

## Règles

- **Uniquement des jetons** : aucune couleur Tailwind (`slate-500`…) ni code hexadécimal dans
  les composants. `npm run check:tokens` le vérifie, en local et dans la CI. Le canvas lit les
  jetons avec `readCssColor` (`web/src/theme.ts`).
- **Accent = ce qui se clique** : bouton principal, cases à cocher, focus. Rien d'autre.
- **Contraste WCAG AA (4,5:1 pour le texte)** :
  - texte d'un bouton principal en `on-accent` (blanc) : 5,08:1 sur l'accent, alors que
    `on-night` ne donnait que 4,41:1 ;
  - en mode sombre, **jamais l'accent comme couleur de texte** : il ne fait que 3,60:1 sur le
    papier sombre. Liens et focus utilisent `accent-ink`, qui vaut `accent-soft` en sombre
    (9,36:1 sur le papier sombre) et l'accent en clair (4,58:1 sur le papier clair).
- **Danger = les erreurs** : messages d'échec, refus de fichier. Pas pour décorer.
- **Magma réservé aux données** : la palette du spectrogramme ne sert à rien d'autre, et
  l'interface n'utilise pas ses couleurs (d'où un accent vert, absent de magma).
- **Pas de motif derrière les données** : le grain du papier (`paper-grain`) est sur le fond de
  page seulement ; cartes, forme d'onde et spectrogramme restent unis.
- **Trois polices, trois rôles** : Archivo pour les titres, Inter pour le texte, JetBrains Mono
  pour les valeurs techniques (Hz, dB, durées, noms de fichiers).

## Origine

Jetons, polices, rayons, ombres et grain viennent de la charte du portfolio de Luciano
(`src/app/globals.css`), qui fait foi. Différences propres à EchoLens : l'accent vert mousse et
les jetons `on-night`, `on-accent` et `accent-ink`, le danger en rouille (la couleur d'accent du portfolio), et le thème sombre
qui suit la préférence du système au lieu d'un bouton.
