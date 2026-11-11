# CLAUDE.md — EchoLens

Instructions pour Claude Code sur ce dépôt. À lire avant toute modification.

## Contexte

EchoLens est le Projet 1 du cours INF50101 (Traitement multimédia des données, ENSPY, M2 Data
Science) : une application web Flask qui analyse un audio (fichier ou micro) et en extrait émotion,
événements sonores, transcription et identité du locuteur. Le jury évalue la qualité scientifique,
l'architecture IA, l'application, les résultats, la présentation et la **maîtrise individuelle** de
chaque membre (25 %). Le code doit donc être lisible et explicable par toute l'équipe.

Échéances : remise le 2 décembre 2026, soutenance le 9 décembre 2026.

La spécification technique (8 briques, exigences EF/ENF, décisions D, R, P, S, U, I, E) fait foi :
sa version de référence pour le code est `docs/specification.md`.
Toute décision qui la contredit doit être discutée avant d'être codée.

## Architecture (règles non négociables)

1. `src/echolens/core/` est du calcul pur : il n'importe **jamais** Flask, `echolens.api` ni
   `echolens.services`. Il est installé tel quel dans les notebooks Kaggle.
2. Toute feature (STFT, log-Mel, MFCC) passe par `echolens.core.features` avec les paramètres de
   `configs/features.yaml`. Aucun calcul de features ailleurs, ni dans le front (décision R5).
3. Le signal entre dans le cœur en mono 16 kHz float32 via `echolens.core.audio.load_audio` (D1, D2).
4. Flask n'est qu'une façade : la logique métier vit dans `services/`, le calcul dans `core/`.
5. Toute route d'API est déclarée avec flask-smorest et un schéma marshmallow, sous `/api/v1`,
   pour apparaître dans l'OpenAPI (`/docs`). Le front consomme les types générés (`npm run gen:api`).
6. Les modèles sont déclarés dans `configs/registry.yaml`, jamais codés en dur.
7. Le front React ne communique qu'avec l'API ; il est compilé dans `web/dist` et servi par Flask.

## Langues

- Identifiants, noms de fichiers et code : **anglais**.
- Commentaires, docstrings, messages d'erreur visibles, interface, documentation : **français**.
- Messages de commit : **français**, au format Conventional Commits (`feat(api): ajoute l'export CSV`).
  Types : feat, fix, docs, test, refactor, perf, chore, ci, exp (expérience).
- Aucune ligne d'attribution dans les commits ni dans les PR : pas de `Co-Authored-By`, pas de lien
  de session, pas de mention « Generated with Claude Code ».

## Code simple d'abord (règle prioritaire)

Chaque membre de l'équipe doit pouvoir lire ce code ligne à ligne et l'expliquer au tableau, sans
être développeur. La lisibilité passe avant la concision et avant la performance (sauf goulot
mesuré). Concrètement :

- **Une ligne = une opération.** Découper toute expression longue en plusieurs lignes courtes avec
  des variables intermédiaires aux noms explicites.
- **Interdits** : compréhensions imbriquées ou avec condition complexe, lambdas, chaînes d'appels
  de plus de deux méthodes, ternaires imbriqués, opérateur morse (`:=`), astuces « one-liner »,
  indexation numpy sophistiquée quand une étape intermédiaire nommée est possible.
- **Autorisés et encouragés** : boucles `for` explicites, `if` simples, retours anticipés,
  compréhensions de liste simples sur une ligne courte.
- **Fonctions courtes** (30 lignes au plus) avec une seule responsabilité. Pas de classe,
  décorateur maison, métaclasse ou générique quand une fonction suffit.
- **Commentaires d'étape** : avant chaque bloc, un commentaire en français qui dit l'étape et sa
  raison (`# Étape 2 : passage en dB absolus, pour qu'un silence reste un silence (R1)`).
- **Pas de paramètre implicite** : quand on appelle une bibliothèque (librosa, torch, sklearn),
  passer explicitement les arguments qui comptent pour la spécification.

Exemple à suivre :

```python
# À éviter : tout sur une ligne, illisible à l'oral.
stats = np.concatenate([m.mean(1), m.std(1)]) if (m := mfcc(x, cfg)).size else np.zeros(80)

# À préférer : une étape par ligne, chaque variable nommée.
coefficients = mfcc(signal, config)
mean_per_coefficient = coefficients.mean(axis=1)
std_per_coefficient = coefficients.std(axis=1)
summary = np.concatenate([mean_per_coefficient, std_per_coefficient])
```

La même règle s'applique au front TypeScript : petites fonctions, variables intermédiaires
nommées, pas de chaînes de `.map().filter().reduce()` difficiles à suivre.

## Style de code

- Python 3.11, typage complet ; `mypy` strict sur `echolens.core`.
- ruff gère lint et formatage (ligne de 100 caractères).
- Fonctions nommées par ce qu'elles font ; une docstring en français pour toute fonction
  publique, qui cite la décision de la spécification concernée quand il y en a une (« D3 », « R1 »).
- Commentaires : l'étape et le *pourquoi* (choix, équation, piège), jamais une paraphrase du code.
- Pas de nombres magiques dans le code : paramètres dans `configs/`.
- Front : TypeScript strict, composants fonctionnels, TanStack Query pour les appels API,
  Tailwind pour le style, Prettier (sans point-virgule, guillemets simples).

## Tests

- Toute fonction de `core/` a des tests unitaires dans `tests/unit/`, avec des signaux de synthèse
  (sinusoïdes, bruit) plutôt que des fichiers réels.
- Toute route d'API a un test dans `tests/integration/`.
- Tests lourds (vrais modèles) : marqueur `@pytest.mark.slow` ou `@pytest.mark.ml`, exclus de la CI.

## Avant de proposer une PR

```bash
make check   # ruff, mypy, pytest, oxlint, prettier, build du front
```

Une PR = un sujet. Branches : `feat/…`, `fix/…`, `exp/…`, `docs/…`. Remplir le modèle de PR,
lier l'issue et les exigences (EF-xx, ENF-xx) concernées.

Avant d'ouvrir la PR, relire chaque fichier modifié avec la règle « Code simple d'abord » et
découper toute ligne qu'un membre non développeur ne pourrait pas expliquer. La PR est ouverte
par le porteur de la brique ; Luciano la relit, l'améliore si besoin et la fusionne.

## À ne jamais faire

- Commiter des données, des poids de modèles, des fichiers `.env` ou des secrets (dépôt public).
- Mélanger locuteurs entre train et test pour les émotions (protocole P1).
- Remélanger les folds d'ESC-50 (protocole P3).
- Calculer des statistiques de normalisation sur autre chose que le train (R4).
- Pousser directement sur `main`.

## Où trouver quoi

| Besoin | Emplacement |
| --- | --- |
| Décisions numérotées (D, R, P, S, U, I, E, H) et exigences | `docs/specification.md` |
| Paramètres des features | `configs/features.yaml` |
| Modèles disponibles | `configs/registry.yaml` |
| Décisions d'architecture | `docs/adr/` |
| Charte graphique (jetons, règles) | [`docs/design.md`](docs/design.md) |
| Fiches de révision pour l'oral | `docs/fiches/` |
| Notebooks Kaggle | `training/notebooks/` |
| Rapport et Beamer | `report/`, `slides/` |
