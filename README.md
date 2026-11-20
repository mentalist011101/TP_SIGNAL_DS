# EchoLens

Plateforme web d'analyse audio : à partir d'un fichier importé ou d'un enregistrement micro, EchoLens
calcule les représentations temps-fréquence du signal et en extrait automatiquement l'**émotion**,
les **événements sonores**, la **transcription** et l'**identité du locuteur**.

Projet 1 du cours INF50101 — Traitement multimédia des données (Dr-Ing. TCHAGNA A), Master 2 Data
Science, ENSPY. Remise le 2 décembre 2026, soutenance le 9 décembre 2026.

## Architecture en bref

```
web/ (React)  ──REST /api/v1, WebSocket──▶  api/ (Flask)  ──▶  services/  ──▶  core/
                                                                              audio, features,
training/ (Kaggle)  ──── importe le même core/ ────────────────────────────▶  modèles, explicabilité
```

- `src/echolens/core/` : calcul pur (audio, features, modèles). N'importe jamais Flask.
- `src/echolens/services/` : orchestration (analyses en arrière-plan, flux, locuteurs, clonage).
- `src/echolens/api/` : API REST documentée (OpenAPI sur `/docs`) et WebSocket ; sert le front compilé.
- `web/` : interface React + TypeScript (Vite, Tailwind), compilée dans `web/dist`.
- `training/` : notebooks et scripts d'entraînement exécutés sur Kaggle.

La spécification technique complète décrit les 8 briques, les exigences, le protocole et le planning
(voir `docs/README.md`).

## Prérequis

- Python 3.11 et [uv](https://docs.astral.sh/uv/)
- ffmpeg (décodage audio, dépendance système obligatoire)
- Node 20 ou plus, uniquement pour développer le front

## Démarrage rapide

```bash
make setup        # environnement Python + dépendances du front + hooks pre-commit
make web-build    # compile le front dans web/dist
make run          # lance Flask sur http://localhost:5000
```

Pour développer le front avec rechargement à chaud : `make run` dans un terminal, `make web-dev`
dans un autre, puis ouvrir http://localhost:5173.

La base locale (`var/echolens.db`, l'historique des analyses) est créée au premier démarrage,
sans migrations. Quand une version ajoute une colonne (par exemple `results` en C13), le serveur
refuse de démarrer avec un message clair : supprimez `var/echolens.db`, elle sera recréée vide
au démarrage suivant (l'historique local est perdu).

Les analyses utilisent pour l'instant un faux prédicteur (`inference_backend: demo` dans
`configs/app.yaml`) : les probabilités sont déterministes mais n'ont aucune valeur, et chaque
résultat porte `model_id = "demo"`.

Avec Docker (aucun prérequis hormis Docker) :

```bash
make docker       # construit l'image et lance http://localhost:5000
```

## Commandes utiles

| Commande | Effet |
| --- | --- |
| `make setup` | Installe l'environnement de développement |
| `make setup-ml` | Ajoute les dépendances des modèles (torch, transformers, …) |
| `make lint` | ruff, mypy, oxlint et prettier |
| `make test` | Tests Python avec couverture |
| `make check` | Tout ce que la CI vérifie, à lancer avant chaque PR |
| `make run` | Serveur Flask de développement |
| `make requirements` | Régénère `requirements.txt` |

## Contribuer

Toute modification passe par une Pull Request vers `main` : voir [CONTRIBUTING.md](CONTRIBUTING.md).

## Équipe

Luciano (responsable technique), Steve, Lynn, Nicole — M2 Data Science, ENSPY.

## Données et licences

Les jeux de données ne sont jamais commités. Ils sont téléchargés par script et restent soumis à
leurs licences respectives (plusieurs sont non commerciales), listées dans `docs/datasets.md`.
