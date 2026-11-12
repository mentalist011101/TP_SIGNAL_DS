# Diagramme de composants

Décisions : architecture en quatre couches (`docs/adr/0001-architecture-en-couches.md`), U1 à
U4 (front), S1 à S4 (service et API), R5 (features), règles d'architecture de `CLAUDE.md`.

Mermaid n'a pas de notation UML de composants : le diagramme utilise des groupes (un par couche)
et des flèches de dépendance. Les éléments en **pointillés** n'existent pas encore.

## Diagramme

```mermaid
flowchart TB
    subgraph WEB["«composant» web — React + TypeScript (web/src)"]
        PAGES["Pages<br>Analyser, Direct, Comparer,<br>Historique, Locuteurs, Modèles"]
        ANALYZE["components/analyze<br>AudioPicker, TaskSelector,<br>WaveformCanvas, AnalysisStatus"]
        CLIENT["api/client.ts<br>apiGet, apiPostForm,<br>hooks TanStack Query"]
        PAGES --> ANALYZE
        PAGES --> CLIENT
    end

    subgraph API["«composant» api — façade Flask (src/echolens/api)"]
        ANALYSES["analyses.py<br>/api/v1/analyses …"]
        HEALTH["health.py<br>/api/v1/health"]
        ERRORS["errors.py<br>format unique des erreurs"]
        FRONT["service du front compilé<br>(create_app)"]
        WSROUTE["/ws/stream<br>(flask-sock)"]
    end

    subgraph SERVICES["«composant» services — orchestration (src/echolens/services)"]
        ASERVICE["AnalysisService<br>contrôle, file de traitement"]
        STORAGE["storage.py<br>AnalysisRecord (SQLAlchemy)"]
        SPECIMG["spectrogram_image.py<br>image PNG du log-Mel"]
        INFER["InferenceService<br>(modèles)"]
        STREAM["StreamSession<br>(tampon du flux)"]
    end

    subgraph CORE["«composant» core — calcul pur, sans Flask (src/echolens/core)"]
        AUDIO["audio<br>load_audio, is_silent"]
        FEATURES["features.py<br>log_mel_spectrogram, mfcc"]
        DATA["data<br>manifestes, découpages"]
        REGISTRY["models/registry.py<br>lecture du registre"]
    end

    subgraph STORE["«stockage»"]
        DB[("SQLite<br>var/echolens.db")]
        FILES[("Fichiers<br>var/analyses/&lt;id&gt;/")]
        CONFIGS[("configs/*.yaml")]
    end

    FFMPEG[["ffmpeg<br>(dépendance système)"]]
    TRAINING["«composant» training<br>(src/echolens/training, notebooks Kaggle)"]

    CLIENT -- "HTTP JSON / multipart<br>/api/v1" --> ANALYSES
    CLIENT --> HEALTH
    PAGES -. "WebSocket /ws" .-> WSROUTE

    ANALYSES --> ASERVICE
    WSROUTE -.-> STREAM
    STREAM -.-> INFER
    ASERVICE -.-> INFER

    ASERVICE --> STORAGE
    ASERVICE --> SPECIMG
    ASERVICE --> AUDIO
    ASERVICE --> FEATURES
    INFER -.-> FEATURES
    INFER -.-> REGISTRY

    STORAGE --> DB
    ASERVICE --> FILES
    AUDIO --> FFMPEG
    FEATURES --> CONFIGS
    REGISTRY --> CONFIGS

    TRAINING --> FEATURES
    TRAINING --> DATA
    TRAINING --> AUDIO

    classDef prevu stroke-dasharray: 5 5
    class WSROUTE,INFER,STREAM prevu
```

## Rôle de chaque composant

| Composant | Rôle | Ce qu'il a le droit d'appeler |
| --- | --- | --- |
| **web** | Interface en français, compilée dans `web/dist` | **Seulement l'API** (règle 7 de `CLAUDE.md`) ; aucun calcul de features (R5) |
| **api** | Traduit HTTP ↔ service ; documente l'API (`/docs`) ; sert le front compilé | `services` ; aucune logique métier (règle 4) |
| **services** | Contrôle des fichiers, traitement en arrière-plan (pool de threads, S2), base de données (S3), images | `core`, le stockage |
| **core** | Calcul pur : décodage, features, données, registre | Rien de Flask, ni `api` ni `services` (règle 1) ; installé tel quel sur Kaggle |
| **training** | Entraînement et évaluation (SVM sur ESC-50, évaluation) | `core`, pour utiliser **le même code de features** qu'en production (R5, ENF-07) |
| **stockage** | Base SQLite pour l'historique ; audios et images sur disque ; paramètres en YAML | — |

## Règle à savoir expliquer : les dépendances ne remontent jamais

Les flèches vont toujours vers le bas : web → api → services → core. `core` ne connaît ni Flask
ni la base de données. C'est ce qui permet d'installer `core` seul dans un notebook Kaggle, et
d'être sûr que **le spectrogramme de l'entraînement est calculé par le même code** que celui de
l'application.

## Interfaces existantes entre api et services

`AnalysisService` (`src/echolens/services/analysis_service.py`) : `create_analysis`,
`get_analysis`, `list_analyses`, `delete_analysis`, `converted_audio_path`, `spectrogram_path`.
