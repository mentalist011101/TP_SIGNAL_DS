# Jeux de données

Aucun jeu n'est commité : les scripts de `training/data/` (sprint S1) les téléchargent dans `data/`
et vérifient leur somme de contrôle. Les licences non commerciales sont compatibles avec un usage
académique ; chaque jeu est cité dans le rapport. La description de chaque jeu (URL, licence,
fréquence d'origine, rôle) fait foi dans `configs/datasets.yaml` ; les 6 classes d'émotion communes
sont dans `configs/labels.yaml`.

| Tâche | Jeu | Rôle | Licence | Source |
| --- | --- | --- | --- | --- |
| Émotions | CREMA-D (7 442 extraits, 91 acteurs, 6 émotions) | Entraînement principal | ODbL 1.0 | https://www.tensorflow.org/datasets/catalog/crema_d |
| Émotions | RAVDESS (24 acteurs, 1 440 fichiers de parole) | Complément d'entraînement | CC BY-NC-SA 4.0 | https://zenodo.org/records/1188976 |
| Émotions | CaFE (français canadien, 12 acteurs) | Test hors domaine en français | CC BY-NC-SA 4.0 | https://zenodo.org/records/1478765 |
| Émotions | Akan Cinematic Emotions (308 locuteurs) | Test hors domaine africain, sous réserve d'accès | Non précisée | https://github.com/zehuiwu/Akan-Cinematic-Emotion |
| Événements | ESC-50 (2 000 extraits, 50 classes, 5 folds) | Entraînement et évaluation | CC BY-NC 3.0 | https://github.com/karolpiczak/esc-50 |
| Transcription, locuteur | African Accented French, OpenSLR 57 (~22 h) | Test WER, évaluation du locuteur | Apache 2.0 | https://www.openslr.org/57/ |
| Tous | Enregistrements de l'équipe | Démo, clonage, audios non vus | Usage interne, consentement écrit | — |

## Règles de protocole à respecter dans tout script

Résumé des règles qui touchent aux données ; le détail (correspondance des émotions, découpages,
enregistrements de l'équipe, tests de fuite) fait foi dans [`docs/protocole.md`](protocole.md).

- **P1** : émotions, aucun locuteur commun entre train, validation et test.
- **P2** : harmonisation sur 6 classes : neutral, happy, sad, angry, fear, disgust.
- **P3** : ESC-50, validation croisée sur les 5 folds officiels, jamais remélangés.
  Exception connue du jeu officiel : 4 enregistrements Freesound (`src_file` 131943, 134049,
  209698, 234879, soit 9 extraits) ont servi à deux classes voisines (clock_alarm / clock_tick,
  hen / rooster) placées dans deux folds. On garde les folds officiels, pour rester comparable
  à la littérature, et ces 4 sources sont tolérées par `check_manifest`
  (`KNOWN_CROSS_FOLD_SOURCES` dans `core/data/esc50.py`) ; toute autre source à cheval est refusée.
- **R4** : statistiques de normalisation calculées sur le train uniquement.

## Format des manifestes

Chaque jeu est décrit par un **manifeste** : un fichier CSV, une ligne par extrait audio. Les
manifestes ne contiennent que des métadonnées (aucun audio) et sont versionnés dans
`data/manifests/<id du jeu>.csv`. Ils sont lus et écrits uniquement avec
`echolens.core.data.manifest` (`load_manifest`, `save_manifest`), et vérifiés par `check_manifest`.

Encodage UTF-8, séparateur virgule, colonnes toujours dans cet ordre. Une cellule vide signifie
« valeur absente ».

> **Ne jamais éditer un manifeste à la main, ni l'ouvrir et l'enregistrer dans Excel.** Les
> manifestes sont générés par les scripts ; pour corriger une ligne, corriger le script et
> régénérer. Excel remplace souvent la virgule par « ; » et peut renommer ou réordonner les
> colonnes : `load_manifest` refuse alors le fichier et liste les colonnes manquantes et
> inattendues.

### Racine des jeux

La colonne `path` est relative à la racine du jeu, qui vaut toujours `<datasets_dir>/<id>`, où
`<id>` est l'identifiant du jeu dans `configs/datasets.yaml`. Le chemin complet d'un fichier est
donné par `audio_path(row, datasets_dir)` ; ne jamais construire ce chemin à la main.

- En local : `datasets_dir` vaut `data/` (par défaut), par exemple `data/esc50/audio/1-100032-A-0.wav`.
- Sur Kaggle : chaque jeu est publié en dataset privé dont le nom est **exactement** l'id de
  `configs/datasets.yaml` (`esc50`, `cremad`, `ravdess`, `cafe`, `openslr57`), et on définit
  `ECHOLENS_DATASETS_DIR=/kaggle/input`. Le même manifeste donne alors
  `/kaggle/input/esc50/audio/1-100032-A-0.wav`.

| Colonne | Obligatoire | Contenu |
| --- | --- | --- |
| `dataset` | oui | Identifiant du jeu, tel que dans `configs/datasets.yaml` (un seul jeu par manifeste). |
| `path` | oui | Chemin du fichier audio, relatif à la racine du jeu ; unique dans le manifeste. |
| `label` | non | Étiquette d'origine, écrite comme dans le jeu (`ANG`, `05`, `dog`). Vide pour OpenSLR 57. La correspondance vers nos 6 classes (P2) est appliquée plus tard, pas dans le manifeste. |
| `speaker` | non | Identifiant du locuteur dans le jeu ; sert au découpage par locuteur (P1). |
| `gender` | non | `F` ou `M`. |
| `duration_s` | oui | Durée en secondes, strictement positive. |
| `fold` | non | Fold officiel d'ESC-50 (entier de 1 à 5, P3). |
| `official_split` | non | Découpage officiel d'origine : `train`, `dev`, `devtest` ou `test` (OpenSLR 57). |
| `subset` | non | Sous-corpus d'origine (`yaounde`, `ca16`, `niger` pour OpenSLR 57). |
| `intensity` | non | Code d'intensité d'origine, tel quel. |
| `source` | non | Enregistrement d'origine (ex. `src_file` d'ESC-50) : deux lignes de même source ne sont jamais séparées entre deux folds. |
| `transcript` | non | Texte prononcé tel qu'écrit dans le jeu, sans normalisation ; sert au calcul du WER. |

Toutes les colonnes après `duration_s` sont optionnelles. Exemples, une ligne par jeu. Les
chemins de CaFE et d'OpenSLR 57, ainsi que le texte d'OpenSLR 57, sont illustratifs : ils seront
fixés par les scripts de téléchargement.

```csv
dataset,path,label,speaker,gender,duration_s,fold,official_split,subset,intensity,source,transcript
esc50,audio/1-100032-A-0.wav,dog,,,5.0,1,,,,100032,
cremad,AudioWAV/1001_DFA_ANG_XX.wav,ANG,1001,M,2.2755625,,,,XX,,
ravdess,Actor_01/03-01-05-01-01-01-01.wav,05,01,M,3.8705416666666665,,,,01,,
cafe,Colère/Faible/01-C-1-1.wav,C,01,,2.9,,,,1,,
openslr57,speech/train/ca16/gabon_m_074/gabon_m_074_001.wav,,gabon_m_074,M,4.2,,train,ca16,,,bonjour à tous
```

## Sources réellement utilisées

Les manifestes de `data/manifests/` ont été construits sur Kaggle par les notebooks de
`training/notebooks/`, à partir de ces copies :

| Jeu | Copie utilisée | Contrôle |
| --- | --- | --- |
| ESC-50 | archive officielle GitHub (https://github.com/karolpiczak/ESC-50) | 2 000 extraits, 400 par fold |
| CREMA-D | copie Kaggle `ejlok1/cremad` (https://www.kaggle.com/datasets/ejlok1/cremad), dossier `AudioWAV` | 7 442 WAV ; noms comparés un à un au dépôt officiel CheyneyComputerScience/CREMA-D |
| CREMA-D, genre | `VideoDemographics.csv` du dépôt officiel (https://github.com/CheyneyComputerScience/CREMA-D), téléchargé à chaque exécution, jamais commité (I8) | 91 acteurs, 48 M et 43 F |
| RAVDESS | copie Kaggle `uwrfkaggler/ravdess-emotional-speech-audio` (https://www.kaggle.com/datasets/uwrfkaggler/ravdess-emotional-speech-audio), dossiers `Actor_01` … `Actor_24` à la racine | 1 440 WAV ; la copie contient chaque fichier **en double** (une seconde fois sous `audio_speech_actors_01-24/`) : un seul des deux dossiers est pris, les doublons ne sont jamais comptés |

Écart connu : la copie Kaggle de CREMA-D nomme un fichier `1040_ITH_SAD_X.wav` (intensité `X`)
au lieu de `1040_ITH_SAD_XX.wav` dans le dépôt officiel ; c'est la seule différence sur les
7 442 fichiers. `KNOWN_MISNAMED_FILES` (`core/data/cremad.py`) lit ses champs sur le nom
officiel ; le chemin du manifeste garde le nom réel du fichier dans la copie.

## Fichiers défectueux

Un fichier illisible ou de durée nulle n'est **jamais** ignoré en silence : la construction du
manifeste échoue en le nommant (`audio_duration_s` dans `core/data/manifest.py`). Seuls les
fichiers listés dans la constante `KNOWN_BAD_FILES` du module du jeu sont exclus, chacun avec un
commentaire qui dit ce qui ne va pas et où on l'a constaté. Pour CREMA-D et RAVDESS, ces listes
sont vides : aucun fichier défectueux dans les copies utilisées.

## Correspondance des émotions et découpages (C4)

Les règles viennent de Ly2 ; le code est dans `echolens.core.data.emotions` et
`echolens.core.data.splits`, les paramètres dans `configs/labels.yaml` (`label_mapping`) et
`configs/splits.yaml`.

- **Émotions (P2)** : chaque étiquette d'origine est traduite en l'une des 6 classes communes,
  ou exclue (`null`) : calme (`02`) et surprise (`08`) de RAVDESS, surprise (`S`) de CaFE.
  Une étiquette absente de la table fait échouer le code.
- **Acteurs (P1)** : `training/scripts/make_emotion_split.py` tire une seule fois, graine 42,
  la partie de chaque acteur de CREMA-D et de RAVDESS. Validation et test reçoivent chacun
  15 % des acteurs, **autant d'hommes que de femmes** (pour l'analyse des biais, E4) ; le reste
  va en train. Le résultat, `data/splits/emotion_split.csv` (une ligne par acteur, sans audio),
  est versionné et ne se retire jamais.

| Jeu | Train | Validation | Test |
| --- | --- | --- | --- |
| CREMA-D | 63 (34 H, 29 F) | 14 (7 H, 7 F) | 14 (7 H, 7 F) |
| RAVDESS | 16 (8 H, 8 F) | 4 (2 H, 2 F) | 4 (2 H, 2 F) |

- **ESC-50 (P3)** : `esc50_round(k, 5)` donne, au tour k, le fold de test k, le fold de
  validation (k + 1, et 1 après 5) qui sert seulement à régler époques et hyperparamètres sur
  3 folds d'entraînement, puis les 4 folds hors test de l'entraînement final (comparabilité
  avec la littérature). Un modèle sans early stopping (MFCC + SVM) s'entraîne directement sur
  les 4 folds.
- **Hors domaine (P7)** : CaFE, ACE, OpenSLR 57 et nos enregistrements (`team`) sont toujours
  en test ; `split_of_row` ne leur donne jamais d'autre partie.
- **Tests** : `tests/unit/test_splits.py` vérifie chaque règle, y compris sur les vrais
  manifestes (effectifs de Ly2 : 7 442 extraits gardés pour CREMA-D, 1 056 gardés et 384 exclus
  pour RAVDESS) et sur le découpage versionné.

## Où se trouvent les informations dans chaque jeu

Chaque jeu range ses métadonnées à sa façon ; les scripts de construction des manifestes doivent
les lire aux endroits suivants.

| Jeu | Étiquette | Locuteur et genre | Autres |
| --- | --- | --- | --- |
| ESC-50 | `meta/esc50.csv`, colonne `category` | sans objet | `fold` et `src_file` dans le même CSV |
| CREMA-D | nom de fichier `1001_DFA_ANG_XX` : 3e champ (`ANG`, `DIS`, `FEA`, `HAP`, `NEU`, `SAD`) | acteur = 1er champ ; genre dans `VideoDemographics.csv` (colonne `Sex`) | intensité = 4e champ (`LO`, `MD`, `HI`, `XX`) ; récupérer uniquement `AudioWAV` via Git LFS |
| RAVDESS | nom de fichier, 3e code (`01` à `08`) | acteur = 7e code ; impair = homme, pair = femme | intensité = 4e code ; garder modalité `03` et canal `01` |
| CaFE | nom de fichier acteur-émotion-intensité-phrase, émotion `C`, `D`, `J`, `N`, `P`, `S`, `T` | acteur = 1er champ ; genre dans `Readme.txt` (à vérifier) | intensité `1` ou `2` (neutre toujours `1`) ; 936 fichiers ; ne jamais lire les noms de dossiers (accents mal encodés dans l'archive) |
| OpenSLR 57 | sans objet | dossier du locuteur ; pour `ca16`, `pays_genre_numéro` (`gabon_m_074`) ; `yaounde` et `niger` à vérifier | découpage officiel = dossier `speech/<split>` ; sous-corpus = dossier suivant ; transcriptions en 5 formats selon le sous-corpus, chemins absolus `/mnt/corpora/...` à réduire au nom de fichier |
