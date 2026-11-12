# Diagramme de déploiement

Décisions : S5 (Docker multi-étapes, Gunicorn en mode threads), ENF-08 (lancement en une
commande via Docker, sans GPU ni Node), I4 (CI GitHub Actions), I7 (poids sur le Hugging Face
Hub), I9 (Kaggle), S2 (traitements en arrière-plan).

Sources : `docker/Dockerfile`, `docker/docker-compose.yml`, `.github/workflows/ci.yml`.
Mermaid n'a pas de notation UML de déploiement : les nœuds sont des groupes, les artefacts des
rectangles. Les éléments en **pointillés** n'existent pas encore.

## Diagramme

```mermaid
flowchart LR
    subgraph CLIENT["«device» PC ou téléphone de l'utilisateur"]
        BROWSER["«execution environment»<br>Navigateur<br>(front React)"]
    end

    subgraph HOST["«device» Machine hôte, CPU, sans GPU"]
        subgraph DOCKER["«execution environment» Docker Engine"]
            subgraph CONT["«container» echolens (python:3.11-slim)"]
                GUNI["Gunicorn<br>1 worker, 8 threads (gthread)"]
                FLASK["«artifact»<br>application Flask<br>echolens.wsgi:app"]
                POOL["Pool de threads<br>2 analyses en parallèle (S2)"]
                DIST["«artifact»<br>web/dist (front compilé)"]
                CONF["«artifact»<br>configs/*.yaml"]
                FFM["ffmpeg"]
                GUNI --> FLASK
                FLASK --> POOL
                FLASK --> DIST
            end
            VOLVAR[("«volume» echolens-var<br>/app/var<br>SQLite + audios")]
            VOLMOD[("«bind mount» models/<br>/app/models (lecture seule)<br>poids des modèles")]
        end
    end

    subgraph HF["«device» Hugging Face Hub"]
        WEIGHTS["«artifact»<br>poids des modèles (I7)"]
    end

    subgraph KAGGLE["«device» Kaggle (GPU)"]
        NB["«execution environment»<br>notebooks d'entraînement"]
        KDATA[("datasets privés,<br>un par jeu (I9)")]
    end

    subgraph GH["«device» GitHub"]
        REPO["«artifact»<br>dépôt public"]
        CI["«execution environment»<br>GitHub Actions (CI)"]
    end

    BROWSER -- "HTTP :5000" --> GUNI
    BROWSER -. "WebSocket :5000 /ws/stream" .-> GUNI
    FLASK --> VOLVAR
    FLASK --> VOLMOD
    VOLMOD -. "make models (à créer)" .-> WEIGHTS
    NB --> KDATA
    NB -- "installation du dépôt<br>en mode éditable" --> REPO
    NB -. "publication des poids" .-> WEIGHTS
    REPO --> CI

    classDef prevu stroke-dasharray: 5 5
    class WEIGHTS prevu
```

## Lecture du diagramme

| Nœud | Ce qui s'y exécute | Justification |
| --- | --- | --- |
| Navigateur | Le front React compilé, servi par Flask | Aucun Node chez l'utilisateur (ENF-08) |
| Conteneur `echolens` | Gunicorn → Flask, plus le pool de threads des analyses, plus ffmpeg | Une seule commande : `make docker` (ENF-08) |
| Gunicorn `gthread`, 1 worker, 8 threads | Les requêtes HTTP et, plus tard, les WebSockets | Un WebSocket occupe un thread tant qu'il est ouvert : il faut des threads, pas un worker par requête (commentaire du `Dockerfile`). **Un seul** worker, car le pool d'analyses et la mémoire des modèles vivent dans ce processus |
| Volume `echolens-var` | Base SQLite, audios importés, spectrogrammes | L'historique survit à un redémarrage du conteneur |
| Montage `models/` en lecture seule | Les poids téléchargés | Les poids ne sont jamais dans l'image ni dans le dépôt (I7) |
| Kaggle | Entraînement sur GPU, avec les datasets privés | Pas de GPU sur la machine hôte ; données jamais dans le dépôt (I8, I9) |
| Hugging Face Hub | Stockage des poids entraînés | Lien entre l'entraînement (Kaggle) et l'application (I7) |
| GitHub Actions | Lint, typage, tests, build du front | `main` protégée : CI verte avant fusion (I4, I5) |

**Construction de l'image en deux étapes (S5) :** une étape Node compile le front (`npm run build`),
puis une image Python légère ne récupère que `web/dist`. L'image finale ne contient donc pas Node.

## Écarts avec le code actuel

1. `docker-compose.yml` monte `../models` et son commentaire cite `make models`, mais **cette
   cible n'existe pas encore** dans le `Makefile`. Le téléchargement des poids depuis le Hugging
   Face Hub est donc à écrire.
2. Aucun modèle n'est publié sur le Hub (`configs/registry.yaml` est vide).
3. La route WebSocket n'existe pas encore (voir `sequence-flux-micro.md`).
