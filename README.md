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
sans outil de migration :

- une **table** ajoutée par une nouvelle version est créée toute seule au démarrage. C'est le cas
  de `analysis_summaries` (résumé de chaque analyse pour la page Historique) : au démarrage, le
  résumé de chaque analyse terminée qui n'en a pas encore est calculé à partir de ses résultats.
  Rien à faire, l'historique est conservé ; avec beaucoup d'analyses longues, ce premier
  démarrage peut prendre quelques secondes ;
- quand une version ajoute une **colonne** à une table existante (par exemple `results` en C13),
  le serveur refuse de démarrer avec un message clair : supprimez `var/echolens.db`, elle sera
  recréée vide au démarrage suivant (l'historique local est perdu).

### Prédicteur : faux ou vrais modèles

Le prédicteur des analyses se choisit dans `configs/app.yaml` (`inference_backend`) ou par la
variable d'environnement `ECHOLENS_INFERENCE_BACKEND` :

- `demo` (par défaut) : faux prédicteur, probabilités déterministes sans valeur
  (`model_id = "demo"`), **sans torch**. C'est le mode pour développer le front et pour la CI.
- `models` : vrais modèles de `configs/registry.yaml` (extra `[ml]` : `make setup-ml`). Les
  poids (safetensors) et leur `config.json` sont téléchargés depuis Hugging Face à la révision
  figée du registre, puis gardés en cache ; ou lus dans un dossier local avec
  `ECHOLENS_MODELS_DIR=<dossier>` (un sous-dossier par identifiant de modèle).

```bash
ECHOLENS_INFERENCE_BACKEND=models make run
```

Les modèles sont chargés une seule fois, à la première analyse qui en a besoin (un seul
encodeur Whisper pour les deux têtes). Pour la démo, `ECHOLENS_PRELOAD_MODELS=true` (ou
`preload_models: true`) les charge au démarrage, pour que la première analyse soit aussi
rapide que les suivantes.

### Docker (ENF-08)

Aucun prérequis hormis Docker ; ni GPU ni Node à l'exécution :

```bash
make docker       # construit l'image complète et lance http://localhost:5000
```

L'image complète (`docker/Dockerfile`) contient les vrais modèles (extra `[ml]`, torch en
version CPU) ; les poids sont téléchargés depuis Hugging Face au premier usage, puis gardés
dans le volume `echolens-var`. Variante légère, sans torch, avec le faux prédicteur :

```bash
docker build -f docker/Dockerfile --build-arg UV_EXTRAS="" \
  --build-arg INFERENCE_BACKEND=demo -t echolens-demo .
docker run -p 5000:5000 echolens-demo
```

Le clonage s'ajoute avec `--build-arg UV_EXTRAS="--extra ml --extra tts"` (environ 2,5 Go de
mémoire de plus, licence à accepter : voir la page Cloner). La CI construit les deux images à
chaque changement de `docker/`, `pyproject.toml` ou `uv.lock` (`.github/workflows/docker.yml`).

### Démo publique dans un Codespace

Un Codespace (4 cœurs, 16 Go) fait tourner tous les modèles, clonage compris, et donne une
adresse HTTPS publique, protégée par un mot de passe (S6) :

1. Dans les réglages GitHub du compte (Settings → Codespaces → Secrets), créer le secret
   `ECHOLENS_ACCESS_PASSWORD`, autorisé pour ce dépôt. Ne jamais l'écrire dans le dépôt.
2. Sur la page du dépôt : Code → Codespaces → Create codespace on main. La préparation
   (`.devcontainer/post-create.sh` : ffmpeg, dépendances, front) prend une dizaine de minutes.
3. Dans le terminal du Codespace : `bash .devcontainer/start-demo.sh`, ou
   `ACCEPT_CPML=true bash .devcontainer/start-demo.sh` pour activer le clonage (la personne qui
   lance accepte la Coqui Public Model License, usage non commercial).
4. L'adresse est `https://<nom du codespace>-5000.app.github.dev` ; le navigateur demande le
   mot de passe (n'importe quel nom d'utilisateur).

Limites : la démo ne répond que tant que le Codespace tourne. Il s'arrête après le délai
d'inactivité du compte (30 min par défaut, jusqu'à 4 h dans Settings → Codespaces), et le
quota gratuit d'un compte personnel est de 120 heures-cœur par mois, soit 30 h sur 4 cœurs.
Les données (voix, analyses) restent dans le Codespace : le supprimer les efface.

### Analyse en direct (page Direct)

La page Direct envoie le micro au serveur par le WebSocket `/ws/stream`. Toutes les 0,5 s, le
serveur analyse les 2 dernières secondes (émotion et événement, profil Temps réel) et renvoie
les résultats, le temps de calcul, le RTF et la latence. Le protocole est décrit dans
[`docs/api-flux-micro.md`](docs/api-flux-micro.md).

- Navigateur conseillé : **Chrome ou Edge**. Firefox a longtemps refusé de relier un micro à un
  contexte audio à 16 kHz ; si le navigateur refuse, la page le dit au lieu d'échouer en
  silence.
- Rien n'est enregistré par défaut. La case « Enregistrer cette session » demande un
  consentement écrit ; la session devient alors une analyse de l'Historique, supprimable comme
  les autres.
- Le micro n'est accessible qu'en `http://localhost` ou en `https://` (règle des navigateurs).

### Export des résultats

Une analyse terminée s'exporte depuis la page Résultat, ou par
`GET /api/v1/analyses/{id}/export?format=json|csv|pdf`. Le fichier s'appelle
`echolens_<nom du fichier>_<AAAA-MM-JJ>.<format>` :

- **JSON** : le détail complet de l'analyse, identique à `GET /api/v1/analyses/{id}`.
- **CSV** : une ligne par probabilité, globale puis de chaque segment (segments numérotés à
  partir de 1). Une tâche sans résultat (`no_speech`, `unavailable`) a une seule ligne, avec son
  statut dans `label`. Séparateur virgule, point décimal, UTF-8 avec BOM.
- **PDF** : rapport d'une à deux pages en français : fichier, date, durée, profil,
  spectrogramme, et pour chaque tâche les 3 premières classes, les segments (12 au plus, les
  autres sont dans le CSV) et le modèle.

Pour ouvrir le CSV dans un Excel en français, qui attend le point-virgule et la virgule
décimale : **Données > À partir d'un fichier texte/CSV**, choisir le séparateur **virgule**
(et le point comme séparateur décimal si Excel le demande). Un double-clic sur le fichier
mettrait toutes les colonnes dans une seule.

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
