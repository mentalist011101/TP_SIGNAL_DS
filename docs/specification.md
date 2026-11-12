# EchoLens — Spécification technique (référence du dépôt)

Ce fichier est la référence technique pour le code : il recense les exigences et toutes les
décisions numérotées (D, R, P, S, U, I, E, H) auxquelles renvoient `CLAUDE.md`, les docstrings et
les PR. Le contexte, l'organisation de l'équipe, le planning et les risques sont dans la
spécification complète partagée par l'équipe (document en ligne).

Une décision qui change se modifie ici **et** dans le document partagé, dans la même journée.
Le journal des changements est en fin de fichier.

## 1. Objectif et périmètre

EchoLens est une application web Flask qui charge ou enregistre un audio, le transforme en
représentations temps-fréquence et en extrait l'émotion, les événements sonores, la transcription
et l'identité du locuteur (Projet 1, INF50101, ENSPY). Le sujet impose de comparer deux familles
de modèles : CNN/CRNN sur spectrogrammes, et encodeurs pré-entraînés (wav2vec 2.0, HuBERT, Whisper).

| Priorité | Contenu |
| --- | --- |
| P1, indispensable | Chaîne audio complète ; émotions et événements sonores avec les deux familles comparées ; Flask avec import et enregistrement, forme d'onde, spectrogramme, probabilités, historique, export |
| P2, attendu | Transcription (Whisper) ; identification du locuteur ; frise temporelle ; Grad-CAM ; flux micro quasi temps réel ; comparaison des modèles |
| P3, bonus | Clonage de voix (XTTS-v2), voix consentantes uniquement ; décision le 22 novembre |

Hors périmètre : diarisation complète, entraînement d'un modèle de transcription, événements
polyphoniques, déploiement public, application mobile.

## 2. Exigences fonctionnelles

| ID | Exigence | Priorité |
| --- | --- | --- |
| EF-01 | Importer un fichier audio (wav, mp3, flac, ogg, webm), 5 min maximum | P1 |
| EF-02 | Enregistrer un audio depuis le micro du navigateur | P1 |
| EF-03 | Afficher la forme d'onde avec lecture et curseur synchronisé | P1 |
| EF-04 | Afficher le spectrogramme Mel calculé par le même module que l'entrée des modèles | P1 |
| EF-05 | Classer l'émotion (6 classes) avec probabilités par classe | P1 |
| EF-06 | Reconnaître l'événement sonore (50 classes ESC-50) avec probabilités | P1 |
| EF-07 | Choisir les tâches et le profil (qualité ou temps réel) avant l'analyse | P1 |
| EF-08 | Conserver l'historique des analyses, filtrable, réouvrable, supprimable | P1 |
| EF-09 | Télécharger les résultats en JSON, CSV et PDF | P1 |
| EF-10 | Transcrire la parole en français avec horodatage par segment | P2 |
| EF-11 | Enregistrer des locuteurs (avec consentement) et identifier le locuteur, ou le déclarer inconnu | P2 |
| EF-12 | Segmenter l'audio et afficher une frise temporelle émotion, événement, locuteur, texte | P2 |
| EF-13 | Superposer la carte Grad-CAM au spectrogramme, activable | P2 |
| EF-14 | Analyser le flux micro en direct, avec affichage de la latence et du RTF | P2 |
| EF-15 | Comparer plusieurs modèles sur un même fichier | P2 |
| EF-16 | Consulter la fiche de chaque modèle : métriques, matrice de confusion, calibration | P2 |
| EF-17 | Documenter l'API (OpenAPI, Swagger sur `/docs`) | P2 |
| EF-18 | Cloner une voix consentante, marquer la sortie « voix synthétique », l'évaluer | P3 |

## 3. Exigences non fonctionnelles

| ID | Domaine | Exigence |
| --- | --- | --- |
| ENF-01 | Temps réel | En flux micro, inférence d'une fenêtre plus courte que le décalage H = 0,5 s (RTF < 1) sur la machine CPU de référence |
| ENF-02 | Latence | Latence perçue ≈ H + temps d'inférence, mesurée en p50 et p95 |
| ENF-03 | Fichiers | Une analyse de fichier ne bloque jamais l'interface (arrière-plan avec statut) |
| ENF-04 | Performance | Cibles de F1 macro, accuracy, WER et EER fixées après les premières références |
| ENF-05 | Robustesse | Comportement documenté face au bruit (0 à 20 dB de SNR), aux extraits courts, au changement d'appareil |
| ENF-06 | Calibration | Probabilités affichées calibrées (ECE mesurée, temperature scaling) |
| ENF-07 | Reproductibilité | Graines fixées, configuration sauvegardée avec chaque modèle, même code de features partout |
| ENF-08 | Portabilité | Lancement en une commande via Docker, sans GPU ni Node |
| ENF-09 | Sécurité | Upload limité, type vérifié, noms nettoyés, aucun secret dans le dépôt public |
| ENF-10 | Éthique | Consentement écrit avant tout enregistrement de voix ; clonage limité aux voix consentantes et signalé |
| ENF-11 | Qualité | Lint, typage et tests verts en CI avant toute fusion ; code simple (règle de `CLAUDE.md`) |
| ENF-12 | Ergonomie | Interface en français, responsive, thème clair et sombre, erreurs compréhensibles |

## 4. Architecture

Quatre couches : `web/` (React, compilé et servi par Flask) → `api/` (Flask, REST et WebSocket) →
`services/` (orchestration) → `core/` (calcul pur, sans Flask, installé tel quel sur Kaggle).
Voir `docs/adr/0001-architecture-en-couches.md`.

## 5. Brique 1 — Ingestion et prétraitement

| ID | Décision |
| --- | --- |
| D1 | Décodage par ffmpeg, dépendance système obligatoire |
| D2 | Rééchantillonnage en mono 16 kHz float32 ; limite : rien au-dessus de 8 kHz (Nyquist) |
| D3 | Normalisation RMS vers un niveau cible en dBFS, puis écrêtage de sécurité |
| D4 | Débruitage par spectral gating seulement pour la parole : désactivé par défaut ; force 0,8 provisoire ; ablation au sprint 2 : sans / 0,5 / 0,8 / 1,0 sur la validation, propre et bruitée à 20, 10 et 0 dB, avec le WER (Whisper) et le F1 macro (émotions) ; on retient le meilleur score moyen, la plus faible force en cas d'égalité ; seuil fixé à 1,5 |
| D5 | Segmentation : détection d'activité vocale **sans torch** (webrtcvad (webrtcvad-wheels), trames de 30 ms, agressivité 2, fusion des écarts < 300 ms, segments ≥ 100 ms, marge de 100 ms) pour la parole ; fenêtres fixes avec recouvrement pour les événements ; fenêtres glissantes pour le flux ; segments d'au moins 100 ms |
| D6 | Garde-fous : 5 min maximum, formats autorisés, rejet des fichiers silencieux |
| D7 | OpenAPI généré depuis le code (flask-smorest) |
| D8 | Flux : PCM 16 kHz Int16 par WebSocket (flask-sock), tampon par session, fenêtre W = 2 s, décalage H = 0,5 s ; transcription déclenchée en fin d'énoncé |
| D9 | Ablations : 32 kHz pour les événements (famille A), 8 kHz pour les émotions |

## 6. Brique 2 — Représentations temps-fréquence

Paramètres dans `configs/features.yaml`, code unique dans `echolens.core.features`.

| ID | Décision |
| --- | --- |
| R1 | STFT : fenêtre de Hann, n_fft = 400 (25 ms), pas de 160 (10 ms), Δf = 40 Hz, trames centrées avec padding par réflexion, spectre de puissance |
| R2 | Spectrogramme Mel : 64 bandes de 0 à 8 kHz, échelle **HTK** (`htk=True`, `norm=None`), en **dB absolus** avec un plancher fixe à −100 dB (`ref=1.0`, `amin=1e-10`). Jamais en dB relatifs au maximum de l'extrait : un silence vaudrait 0 dB et un même son changerait selon son contexte |
| R3 | MFCC : 40 coefficients par DCT-II orthonormée du log-Mel, plus Δ et ΔΔ (régression sur 9 trames, environ 90 ms minimum) |
| R4 | Standardisation par bande, statistiques calculées sur le train uniquement |
| R5 | Module unique fondé sur **librosa**, tous les paramètres passés explicitement (aucune valeur par défaut implicite), utilisé à l'entraînement et dans l'application |
| R6 | Features précalculées une fois, stockées en dataset Kaggle |
| R7 | Famille B : signal brut 16 kHz envoyé à l'extracteur du modèle, sans Mel |

## 7. Brique 3 — Données et protocole

Détail des jeux, des manifestes et de la racine des jeux : `docs/datasets.md`,
`configs/datasets.yaml`, `configs/labels.yaml`.

| Jeu | Rôle | Licence |
| --- | --- | --- |
| CREMA-D (7 442 extraits, 91 acteurs) | Entraînement principal, émotions | ODbL 1.0 |
| RAVDESS (1 440 fichiers de parole, 24 acteurs) | Complément d'entraînement, émotions | CC BY-NC-SA 4.0 |
| CaFE, version 48 kHz (936 fichiers, 12 acteurs) | Test hors domaine en français | CC BY-NC-SA 4.0 |
| ESC-50 (2 000 extraits, 5 folds) | Entraînement et évaluation, événements | CC BY-NC 3.0 |
| OpenSLR 57 (16 656 fichiers, 16 kHz mono) | Évaluation de la transcription et du locuteur | Apache 2.0 |
| Akan Cinematic Emotions | Test africain des émotions, sous réserve d'accès | Non précisée |
| Enregistrements de l'équipe | Démo, clonage, audios non vus | Usage interne, consentement écrit |

| ID | Décision |
| --- | --- |
| P1 | Émotions : découpage indépendant du locuteur, aucun acteur dans deux découpages ; validation et test reçoivent chacun round(15 % × nombre d'acteurs / 2) acteurs de chaque genre, le reste en entraînement ; graine 42, tirage unique ; le résultat (identifiants d'acteurs, sans audio) est versionné dans `data/splits/` |
| P2 | 6 classes d'émotion communes : neutral, happy, sad, angry, fear, disgust ; correspondance depuis les étiquettes d'origine fixée par les règles de protocole (`docs/protocole.md`) |
| P3 | ESC-50 : validation croisée sur les 5 folds officiels, jamais remélangés ; les extraits d'une même source restent dans le même fold. Au tour k, le fold k+1 sert seulement à régler époques et hyperparamètres, puis on réentraîne sur les 4 folds hors test (comparabilité avec la littérature) |
| P4 | Métrique principale F1 macro ; plus accuracy, F1 par classe, matrice normalisée (agrégée en 5 catégories pour ESC-50) |
| P5 | Référence classique MFCC + SVM ou MLP |
| P6 | Augmentation au train seulement : bruit à SNR contrôlé, décalage, gain, SpecAugment, mixup ; masques appliqués après la standardisation (R4), valeur 0 = moyenne du train |
| P7 | Trois niveaux de test : en domaine, hors domaine (CaFE, ACE), nos enregistrements |
| P8 | Test de McNemar entre familles, intervalles de confiance par bootstrap |
| P9 | Un manifeste CSV par jeu au format commun (`echolens.core.data.manifest`), étiquette d'origine conservée telle quelle |
| P10 | OpenSLR 57 sert uniquement à l'évaluation (rien n'y est entraîné) : WER sur le `test` officiel et sur le sous-corpus de Yaoundé (accent camerounais), bien qu'il soit rangé dans `train` |
| P11 | Identification du locuteur : les phrases de chaque locuteur sont séparées entre enregistrement et test (les découpages officiels séparent les locuteurs, ce qui empêcherait de les reconnaître) |
| P12 | WER : référence et transcription normalisées de la même façon : minuscules, ponctuation retirée sauf apostrophe et trait d'union internes, apostrophes unifiées (« c' est » devient « c'est »), nombres en chiffres écrits en lettres (« 7 h 30 » devient « sept heures trente »), espaces réduits |
| P13 | Enregistrements de l'équipe : consentement signé avant tout enregistrement ; nommage `<personne>_<appareil>_<partie>_<numéro sur 2 chiffres>_<étiquette>` ; genre de p01 à p04 dans une table sans noms ; audios uniquement sur le Drive privé, jamais sur GitHub ; test seulement |

Le détail des règles fait foi dans `docs/protocole.md`.

## 8. Brique 4 — Modèles

| Famille | Modèles |
| --- | --- |
| Référence | MFCC + statistiques (moyenne, écart-type) puis SVM ou MLP |
| A | CNN (4 blocs Conv → BatchNorm → ReLU → MaxPool) et CRNN (mêmes blocs, BiGRU, pooling par attention) sur log-Mel |
| B | wav2vec 2.0 base, mHuBERT-147, encodeur Whisper (base puis small) ; somme pondérée apprise des couches, moyenne temporelle, MLP |
| Locuteur | ECAPA-TDNN (SpeechBrain), comparé à mHuBERT ; similarité cosinus et seuil « inconnu » |
| Transcription | Whisper base contre small, français forcé, faster-whisper int8 sur CPU |
| Clonage (P3) | XTTS-v2, voix consentantes uniquement |

Points à respecter : moyennes par couche calculées une seule fois (la moyenne commute avec la
somme pondérée) ; pour Whisper, ignorer les trames de remplissage jusqu'à 30 s ; entraînement
AdamW, schedule cosinus, early stopping sur le F1 macro de validation, 3 graines pour les
résultats principaux ; deux profils, « qualité » (fichiers) et « temps réel » (flux).

| ID | Hypothèse à trancher |
| --- | --- |
| H1 | La famille B dépasse la famille A sur les émotions en domaine |
| H2 | mHuBERT dépasse wav2vec 2.0 anglais sur le français |
| H3 | Les encodeurs de parole se transfèrent moins bien aux événements sonores que l'encodeur Whisper |
| H4 | Le CRNN dépasse le CNN sur les émotions, mais pas sur les événements |

## 9. Brique 5 — Évaluation et explicabilité

| ID | Décision |
| --- | --- |
| E1 | F1 macro, accuracy, F1 par classe, matrice de confusion ; WER et CER ; accuracy et EER du locuteur |
| E2 | Calibration : ECE, diagramme de fiabilité, temperature scaling sur la validation |
| E3 | Robustesse : F1 selon le SNR (20 à 0 dB), la durée et l'appareil |
| E4 | Biais : performance par genre et par locuteur |
| E5 | Significativité : McNemar, bootstrap |
| E6 | Efficacité : paramètres, taille, latence p50 et p95, RTF |
| E7 | Explicabilité : Grad-CAM (A), poids des couches (B), test de fidélité par masquage |
| E8 | Traçabilité : Weights & Biases ; un seul script produit tableaux et figures du rapport |

## 10. Brique 6 — Service d'inférence et API

| ID | Décision |
| --- | --- |
| S1 | Registre de modèles `configs/registry.yaml`, chargement à la demande, cache, préchauffage |
| S2 | Tâches longues en arrière-plan (ThreadPoolExecutor), statut en base, interrogation par le front |
| S3 | SQLite via SQLAlchemy pour l'historique (d'après le MCD MERISE), fichiers sur disque |
| S4 | API v1 documentée (flask-smorest, `/docs`) |
| S5 | Docker multi-étapes, Gunicorn en mode threads |
| S6 | Upload limité, type vérifié, noms nettoyés, consentement pour voix et clonage |

| Méthode | Route | Rôle |
| --- | --- | --- |
| POST | `/api/v1/analyses` | Import, choix des tâches et du profil, renvoie un identifiant |
| GET | `/api/v1/analyses/{id}` | Statut et résultats |
| GET | `/api/v1/analyses` | Historique filtrable |
| GET | `/api/v1/analyses/{id}/export` | Export `json`, `csv` ou `pdf` |
| GET | `/api/v1/models` | Registre et métriques |
| POST | `/api/v1/compare` | Même fichier dans plusieurs modèles |
| POST | `/api/v1/speakers` | Enregistrement d'un locuteur |
| POST | `/api/v1/tts` | Clonage de voix (P3) |
| WS | `/ws/stream` | Flux micro |

## 11. Brique 7 — Interface

| ID | Décision |
| --- | --- |
| U1 | Vite + React + TypeScript, compilé dans `web/dist` et servi par Flask |
| U2 | Tailwind CSS (+ shadcn/ui) |
| U3 | TanStack Query, React Router |
| U4 | Types TypeScript générés depuis l'OpenAPI (`npm run gen:api`) |
| U5 | wavesurfer.js (plugin regions), Recharts, WebSocket natif |
| U6 | Spectrogramme calculé côté serveur par `core` |
| U7 | Erreurs soignées, interface en français |

Pages : Analyser, Résultat, Direct, Comparer, Historique, Locuteurs, Studio voix (P3), Modèles,
et `/docs`.

## 12. Brique 8 — Ingénierie

| ID | Décision |
| --- | --- |
| I1 | Python 3.11 et uv ; Node uniquement pour développer le front |
| I2 | ruff, mypy strict sur `core/`, pytest ; oxlint et Prettier pour `web/` |
| I3 | pre-commit avec détection de secrets |
| I4 | CI GitHub Actions : lint, typage, tests, build du front |
| I5 | `main` protégée : PR obligatoire, relecture, CI verte |
| I6 | Conventional Commits en français, sans ligne d'attribution |
| I7 | Poids sur le Hugging Face Hub |
| I8 | Données jamais commitées ; manifestes versionnés dans `data/manifests/` |
| I9 | Kaggle : dépôt installé en mode éditable, secrets via Kaggle Secrets, un dataset privé par jeu nommé comme son id |
| I10 | Configurations YAML validées par pydantic |
| I11 | Code en anglais ; commentaires, docstrings, commits, documentation et interface en français |
| I12 | Code simple d'abord : une opération par ligne, variables nommées, commentaires d'étape (`CLAUDE.md`) ; le porteur de chaque brique écrit son code et Luciano relit |

## Journal des changements

| Date | Changement |
| --- | --- |
| 5 nov. 2026 | Version initiale de la spécification |
| 5 nov. 2026 | R5 : librosa à la place de torchaudio, paramètres explicites |
| 6 nov. 2026 | R2 : dB absolus avec plancher fixe (revue de la PR #1) ; D5 : VAD sans torch, segments d'au moins 100 ms ; I12 : règle « code simple » et répartition du code par brique |
| 6 nov. 2026 | Brique 3 : licence ODbL de CREMA-D, version 48 kHz de CaFE, décisions P9 à P12 après exploration des fichiers réels |
| 9 nov. 2026 | Brique 3, d'après les règles de protocole de Lynn (Ly2, Ly5) : P1 précisé (tirage par genre, découpage versionné), P3 (réglage sur le fold k+1 puis réentraînement sur 4 folds), P12 (règle de normalisation fixée, nombres en lettres), P13 (enregistrements de l'équipe) ; R2 appliqué dans le code (PR #1) |
| 11 nov. 2026 | Protocole publié dans docs/protocole.md (Ly2 et Ly5 de Lynn, décisions du 9 au 11 novembre) ; P6 : valeur des masques ; P1 : règle exacte du tirage alignée sur le protocole |
| 12 nov. 2026 | Brique 1 (C2, PR #19) : D4 désactivé par défaut, force 0,8 provisoire, protocole d'ablation du sprint 2 ; D5 : webrtcvad à la place de Silero VAD, paramètres de nettoyage des segments fixés ; paramètres dans configs/preprocess.yaml |
