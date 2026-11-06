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
| Émotions | CaFE (français canadien, 12 acteurs) | Test hors domaine en français | CC BY-NC-SA 4.0 | https://zenodo.org/record/1219621 |
| Émotions | Akan Cinematic Emotions (308 locuteurs) | Test hors domaine africain, sous réserve d'accès | Non précisée | https://github.com/zehuiwu/Akan-Cinematic-Emotion |
| Événements | ESC-50 (2 000 extraits, 50 classes, 5 folds) | Entraînement et évaluation | CC BY-NC 3.0 | https://github.com/karolpiczak/esc-50 |
| Transcription, locuteur | African Accented French, OpenSLR 57 (~22 h) | Test WER, évaluation du locuteur | Apache 2.0 | https://www.openslr.org/57/ |
| Tous | Enregistrements de l'équipe | Démo, clonage, audios non vus | Usage interne, consentement écrit | — |

## Règles de protocole à respecter dans tout script

- **P1** : émotions, aucun locuteur commun entre train, validation et test.
- **P2** : harmonisation sur 6 classes : neutral, happy, sad, angry, fear, disgust.
- **P3** : ESC-50, validation croisée sur les 5 folds officiels, jamais remélangés.
- **R4** : statistiques de normalisation calculées sur le train uniquement.

## Format des manifestes

Chaque jeu est décrit par un **manifeste** : un fichier CSV, une ligne par extrait audio. Les
manifestes ne contiennent que des métadonnées (aucun audio) et sont versionnés dans
`data/manifests/<id du jeu>.csv`. Ils sont lus et écrits uniquement avec
`echolens.core.data.manifest` (`load_manifest`, `save_manifest`), et vérifiés par `check_manifest`.

Encodage UTF-8, séparateur virgule, colonnes toujours dans cet ordre. Une cellule vide signifie
« valeur absente ».

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
cremad,AudioWAV/1001_DFA_ANG_XX.wav,ANG,1001,M,2.275,,,,XX,,
ravdess,Actor_01/03-01-05-01-01-01-01.wav,05,01,M,3.737,,,,01,,
cafe,Colère/Faible/01-C-1-1.wav,C,01,,2.9,,,,1,,
openslr57,speech/train/ca16/gabon_m_074/gabon_m_074_001.wav,,gabon_m_074,M,4.2,,train,ca16,,,bonjour à tous
```

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
