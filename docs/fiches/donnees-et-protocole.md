# Fiche — Données et protocole : apprendre et mesurer sans fuite

Brique 3 (données, protocole, analyse d'erreurs), portée par Lynn.
Décisions et exigences : **P1** à **P13**, **R4**, **E4**. Documents de référence :
`docs/protocole.md` (qui fait foi), `docs/datasets.md`, `docs/specification.md` §7.

> **État au 24 novembre 2026.** Les manifestes des cinq jeux publics sont construits et
> versionnés (C3, C5, C16). Les découpages P1, P3 et P11 sont codés, testés et versionnés. Ne sont
> **pas encore faits** : l'évaluation des émotions sur CaFE, le WER sur OpenSLR 57 (C17), le jeu
> ACE (accès non obtenu), le manifeste de nos enregistrements (T6) et l'analyse des biais par
> genre et de la robustesse au bruit (E3, E4). L'évaluation du locuteur (C15) est dans la
> PR #42, pas encore fusionnée.

## 1. L'idée en trois phrases

1. On apprend sur des voix d'acteurs anglophones (CREMA-D, RAVDESS) et sur des sons (ESC-50),
   puis on mesure sur trois niveaux de test de plus en plus éloignés : en domaine, hors domaine
   (CaFE en français, OpenSLR 57 avec l'accent africain), et nos propres voix.
2. Chaque fichier audio est décrit par une ligne d'un **manifeste** (un CSV sans audio) : chemin,
   étiquette, locuteur, genre, durée, fold ou découpage officiel, transcription.
3. On découpe de façon à ce qu'aucune information du test ne fuie vers l'entraînement : on sépare
   les **acteurs** pour les émotions, on garde les **folds officiels** d'ESC-50, on calcule la
   **standardisation sur l'entraînement seul**, et pour le locuteur on sépare ses **phrases**.

## 2. Le schéma

```
 copies et archives officielles (Kaggle, GitHub, Zenodo, OpenSLR)
        │   notebooks Kaggle c3, c5, c16 : rien n'est téléchargé dans le dépôt
        ▼
 constructeurs de manifeste  core/data/<jeu>.py
        │   lisent les NOMS de fichiers (01-C-1-1.wav, 1001_DFA_ANG_XX.wav…)
        │   check_manifest : un seul jeu, chemins uniques, une source = un fold
        ▼
 data/manifests/<jeu>.csv   (versionné, métadonnées seulement, I8)
        │
        ├── émotions : correspondance → 6 classes communes (P2) ; surprise et calme exclus
        │        │
        │        └── découpage PAR ACTEUR, équilibré en genre (P1)
        │              data/splits/emotion_split.csv
        │              ┌────────────┬────────────┬────────────┐
        │              │   train    │ validation │    test    │   CREMA-D + RAVDESS
        │              │ 63 + 16 ac.│ 14 + 4 ac. │ 14 + 4 ac. │   (aucun acteur partagé)
        │              └────────────┴────────────┴────────────┘
        │
        ├── ESC-50 : 5 folds officiels, jamais remélangés (P3)
        │        tour k : test = fold k ; réglage sur fold k+1 ; final sur les 4 autres
        │
        ├── hors domaine : CaFE, OpenSLR 57 → TEST SEULEMENT (P7, P10)
        │
        └── locuteur (OpenSLR 57) : on sépare les PHRASES de chaque personne (P11)
                 5 phrases → « voix enregistrée » │ les autres → test
                 locuteurs répartis en calibration (seuil) / évaluation (scores)
                 data/splits/openslr57_speakers.csv

 Pendant l'entraînement : moyenne et écart-type par bande Mel calculés sur le TRAIN seul (R4),
 puis appliqués tels quels à la validation et au test.
```

## 3. Les équations essentielles

**Standardisation par bande (R4).** Pour chaque bande Mel *b* :

```
            1
  μ_b  =  ───── · Σ  Σ  X[n, b, t]          σ_b = √( moyenne de (X[n, b, t] − μ_b)² )
          N · T   n  t

  X̃[n, b, t] = ( X[n, b, t] − μ_b ) / σ_b
```

- *X[n, b, t]* : log-Mel (en dB) de l'extrait *n*, bande *b*, trame *t* ;
- *N* : nombre d'extraits **de l'entraînement seulement**, *T* : nombre de trames ;
- *μ_b*, *σ_b* : moyenne et écart-type de la bande *b* ; ils sont calculés une fois, puis
  réutilisés tels quels pour la validation, le test et l'application.

**Nombre d'acteurs tenus à part (P1).** Pour un jeu de *A* acteurs et une part *r* = 0,15 :

```
  acteurs par genre en validation = acteurs par genre en test = round( r · A / 2 )
```

CREMA-D : round(0,15 × 91 / 2) = round(6,8) = 7 femmes et 7 hommes en test, autant en
validation. RAVDESS : round(0,15 × 24 / 2) = round(1,8) = 2 et 2.

**Fold de réglage d'ESC-50 (P3).** Au tour *k* (fold de test), le fold de validation est
*v* = (*k* mod 5) + 1 : 2 pour le tour 1, …, 1 pour le tour 5.

**F1 macro (P4)**, la métrique principale : moyenne simple des F1 de chaque classe, pour que
la classe neutre, moins fréquente, compte autant que les autres.

```
  F1_c = 2 · P_c · R_c / (P_c + R_c)        F1 macro = (1 / C) · Σ_c F1_c
```

*P_c* : précision de la classe *c* (part des prédictions *c* qui sont justes) ; *R_c* : rappel
(part des vrais *c* retrouvés) ; *C* : nombre de classes (6 émotions, 50 sons).

## 4. Les choix faits

| Choix | Pourquoi | Alternative écartée |
| --- | --- | --- |
| Découper par **acteur** (P1) | Sinon le modèle reconnaît la voix d'un acteur déjà entendu, pas l'émotion : le score est gonflé | Découpage aléatoire par fichier |
| Test **équilibré en genre** (P1) | Permet de mesurer un biais homme/femme (E4) sans que l'effectif le fausse | Tirage sans tenir compte du genre |
| Découpage **écrit une fois et versionné** | Tout le monde utilise exactement les mêmes acteurs, et on peut le vérifier | Le refaire à chaque lancement |
| **Folds officiels** d'ESC-50 (P3) | Les fragments d'un même enregistrement restent dans le même fold ; nos scores restent comparables aux articles | Remélanger les 2 000 extraits |
| Réglage sur le fold *k*+1, final sur 4 folds | On ne regarde jamais le fold de test pour choisir les réglages, et on apprend sur 4 folds comme la littérature | Choisir l'époque sur le fold de test |
| Standardisation sur le **train seul** (R4) | Les statistiques du test sont une information sur le test : les utiliser serait une fuite | Statistiques sur tout le jeu |
| 6 classes communes ; **calme** et **surprise** exclus (P2) | CREMA-D n'a ni l'un ni l'autre ; fusionner calme et neutre triplerait les neutres de RAVDESS | Fusionner calme avec neutre |
| Le manifeste garde l'**étiquette d'origine** (P9) | Le manifeste décrit le jeu tel quel ; la correspondance se fait dans le code, on peut la changer sans tout reconstruire | Écrire directement les 6 classes |
| CaFE et OpenSLR 57 en **test seulement** (P7, P10) | Ils mesurent la généralisation à une autre langue ou un autre accent ; les entraîner l'effacerait | Les ajouter à l'entraînement |
| Locuteur : séparer les **phrases**, pas les personnes (P11) | Pour reconnaître une voix, il faut l'avoir entendue avant | Découper par personne (impossible ici) |
| Seuil « inconnu » choisi sur **un autre groupe** de locuteurs (P11) | Choisir et mesurer sur les mêmes voix gonflerait le score | Seuil choisi sur le groupe évalué |
| Lire les **noms de fichiers** de CaFE, pas les dossiers | Les accents des dossiers (« Colère ») peuvent être mal encodés selon l'outil de décompression | Lire le nom du dossier |

## 5. Où se trouve le code

| Fichier : fonction | Ce qu'il faut savoir en lire |
| --- | --- |
| `src/echolens/core/data/manifest.py:ManifestRow` | Les 12 colonnes du manifeste et leurs types ; une ligne = un fichier audio |
| `src/echolens/core/data/manifest.py:check_manifest` | Les trois règles vérifiées sur chaque manifeste : un seul jeu, chemins uniques, une source dans un seul fold |
| `src/echolens/core/data/cremad.py:build_cremad_manifest` | Lecture des noms `1001_DFA_ANG_XX.wav` ; genre tiré de `VideoDemographics.csv` ; un fichier mal nommé connu |
| `src/echolens/core/data/cafe.py:build_cafe_manifest` | Lecture des noms `01-C-1-1.wav` (acteur, émotion, intensité, phrase) ; acteur impair = homme, pair = femme |
| `src/echolens/core/data/openslr57.py:build_openslr57_manifest` | Découpage officiel et sous-corpus lus dans le chemin ; transcriptions jointes par identifiant |
| `src/echolens/core/data/openslr57.py:parse_transcript_line` | Pourquoi on ne prend pas `Path.stem` : les noms contiennent des points (`16.06.12`) |
| `src/echolens/core/data/emotions.py:common_emotion` | Passage de l'étiquette d'origine à l'une des 6 classes, ou exclusion |
| `src/echolens/core/data/splits.py:split_emotion_speakers` | Le tirage P1 : un générateur, femmes puis hommes, les premiers en test, puis validation, puis train |
| `src/echolens/core/data/splits.py:check_no_speaker_leak` | Lève une erreur si un acteur est dans deux parties |
| `src/echolens/core/data/splits.py:esc50_round` | Rôle des folds au tour *k* : test, réglage (*k*+1), entraînement final |
| `src/echolens/core/data/speaker_enrollment.py:split_enrollment` | Le découpage P11 (PR #42) : 5 phrases d'enregistrement, groupes calibration et évaluation |
| `src/echolens/training/family_a.py:band_statistics`, `standardize` | R4 : statistiques calculées sur le seul tableau d'entraînement, réappliquées ensuite |
| `configs/splits.yaml`, `configs/labels.yaml`, `configs/speaker.yaml` | Graine 42, parts 15 %, table des étiquettes : aucun nombre n'est écrit dans le code |
| `tests/unit/test_splits.py`, `test_emotion_manifests.py`, `test_out_of_domain_manifests.py` | Les tests de fuite de C4 : chaque règle du protocole est un test |

## 6. Les résultats et leur interprétation

**Effectifs vérifiés sur les manifestes réels.**

| Jeu | Fichiers | Gardés pour les émotions | Rôle |
| --- | --- | --- | --- |
| CREMA-D | 7 442 (91 acteurs) | 7 442 | train / validation / test |
| RAVDESS | 1 440 (24 acteurs) | 1 056 (calme et surprise exclus) | train / validation / test |
| ESC-50 | 2 000 (400 par fold) | — | validation croisée sur 5 folds |
| CaFE | 936 (12 acteurs, 6 H et 6 F) | 792 (surprise exclue) | test hors domaine |
| OpenSLR 57 | 16 656 (19,9 h) | — | WER et locuteur, test seulement |

- Le test d'émotions en domaine contient **1 324 extraits** (14 acteurs de CREMA-D et 4 de
  RAVDESS), équilibré en genre. C'est sur lui que sont calculés les F1 macro des familles A
  et B (`training/results/emotions_*.json`).
- OpenSLR 57 : les 515 phrases du test officiel ont toutes leur transcription ; il en manque
  dans `ca16` (devtest 481 / 761, train 3 063 / 5 997), faute de ligne dans l'archive. Le WER
  (C17) se fera donc sur le test officiel et sur `yaounde`, qui sont complets.
- Le genre d'OpenSLR 57 n'est connu que pour les 12 locuteurs du test officiel : l'analyse des
  biais par genre (E4) y sera très limitée.

**Locuteur (C15, PR #42, pas encore fusionnée).** Sur 112 locuteurs du groupe d'évaluation et
8 016 phrases de test : ECAPA-TDNN reconnaît la bonne personne dans **97,7 %** des cas (EER
2,7 %), mHuBERT dans 71,1 % (EER 10,2 %). Avec le seuil choisi sur l'autre groupe, ECAPA ne
rejette que 27,7 % des voix inconnues : le seuil pris à l'EER sur des paires isolées est trop
bas pour une décision « meilleur score parmi 112 voix ». C'est une limite à discuter.

**Pas encore disponible** : F1 sur CaFE (hors domaine), WER (C17), résultats sur nos
enregistrements (T6), robustesse au bruit et biais par genre (E3, E4).

## 7. Dix questions probables du jury

1. **Pourquoi découper par acteur et pas au hasard ?**
   Sinon les phrases d'un même acteur sont dans le train et le test : le modèle reconnaît sa
   voix, pas l'émotion, et le score est artificiellement gonflé.

2. **Comment savez-vous qu'il n'y a pas de fuite ?**
   Chaque règle est un test automatique (`tests/unit/test_splits.py` et suivants) lancé à chaque
   PR : aucun acteur dans deux parties, chaque fichier dans une seule partie, ESC-50 avec 400
   extraits par fold, jeux hors domaine absents du train.

3. **Pourquoi la standardisation n'utilise-t-elle que l'entraînement ?**
   La moyenne et l'écart-type du test sont des informations sur le test. Les utiliser, c'est
   laisser le modèle « voir » le test avant de l'évaluer (R4).

4. **Pourquoi ne pas remélanger ESC-50 ?**
   Les 2 000 extraits sont des fragments de plus longs enregistrements, rangés par fold. Remélanger
   mettrait deux fragments du même enregistrement en train et en test. Et les articles utilisent
   ces folds : nos scores restent comparables.

5. **Pourquoi exclure la surprise et le calme ?**
   CREMA-D, notre jeu principal, n'en a pas. On garde les 6 émotions communes à tous les jeux,
   sinon le modèle apprendrait une classe qu'il ne verrait jamais en test hors domaine.

6. **À quoi sert CaFE si on ne l'entraîne pas ?**
   À mesurer la généralisation : un modèle appris sur de l'anglais reconnaît-il une émotion en
   français ? C'est le deuxième niveau de test (P7). *L'évaluation n'est pas encore faite.*

7. **Pourquoi le test d'émotions est-il équilibré en genre ?**
   Pour pouvoir comparer les scores des femmes et des hommes (E4) sans qu'une différence
   d'effectif fausse la comparaison : 7 et 7 acteurs pour CREMA-D, 2 et 2 pour RAVDESS.

8. **Pour le locuteur, pourquoi séparer les phrases et pas les personnes ?**
   On ne peut reconnaître que quelqu'un dont on a déjà entendu la voix. 5 phrases servent à
   l'enregistrer, les autres à le reconnaître ; et le seuil « inconnu » est réglé sur d'autres
   personnes que celles évaluées.

9. **Le neutre est moins fréquent : est-ce un problème ?**
   Un peu (1 183 neutres contre 1 463 pour chaque autre classe à l'entraînement). C'est pour cela
   que la métrique principale est le F1 macro, où chaque classe pèse autant.

10. **Quelles sont les limites de vos données ?**
    CREMA-D et RAVDESS répètent les mêmes phrases pour tous les acteurs (12 et 2) ; tout est à
    16 kHz, donc rien au-dessus de 8 kHz ; le genre manque dans la plupart d'OpenSLR 57 ; nos
    propres enregistrements ne seront que 4 voix, donc illustratifs et non concluants.
