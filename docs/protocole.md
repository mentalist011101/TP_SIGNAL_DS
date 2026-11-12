# Protocole expérimental

Ce document fixe les règles de la brique 3 : quelles données servent à quoi, comment on les
découpe sans fuite, et comment on enregistre les voix de l'équipe. Il fait foi pour le code :
`echolens.core.data` (manifestes, correspondance des étiquettes, découpages) et les tests de
`tests/unit/` l'appliquent règle par règle.

Origine : les documents de Lynn « Ly2 — Règles de protocole » (7 novembre 2026) et « Ly5 —
Consentement et protocole d'enregistrement » (8 novembre 2026), avec les décisions validées
ensuite par l'équipe. Les identifiants entre parenthèses renvoient à `docs/specification.md`.

## 1. Rôle de chaque jeu (P7, P10)

On apprend sur de l'anglais joué, puis on mesure l'écart sur trois niveaux de test de plus en
plus éloignés : en domaine, hors domaine, et nos propres voix.

| Jeu | Tâche | Rôle | Niveau de test |
| --- | --- | --- | --- |
| CREMA-D | Émotions | Entraînement, validation, test | En domaine |
| RAVDESS | Émotions | Entraînement, validation, test | En domaine |
| ESC-50 | Événements sonores | Validation croisée sur 5 folds | En domaine |
| CaFE | Émotions | Test seulement | Hors domaine, français |
| ACE | Émotions | Test seulement, si l'accès est obtenu | Hors domaine, voix africaines |
| OpenSLR 57 | Transcription, locuteur | Test seulement | Hors domaine, accent africain |
| Nos enregistrements | Toutes | Test seulement, et démo | Voix jamais entendues |

Un jeu de test n'entre jamais en entraînement ni en validation.

## 2. Correspondance des émotions (P2, P9)

On garde 6 classes communes : `neutral`, `happy`, `sad`, `angry`, `fear`, `disgust`. Le
manifeste garde l'étiquette d'origine ; la correspondance s'applique ensuite, dans le code
(`echolens.core.data.emotions`, table `label_mapping` de `configs/labels.yaml`).

| Classe commune | CREMA-D | RAVDESS | CaFE | ACE |
| --- | --- | --- | --- | --- |
| neutral | NEU | 01 | N | Neutral |
| happy | HAP | 03 | J | Happy |
| sad | SAD | 04 | T | Sadness |
| angry | ANG | 05 | C | Anger |
| fear | FEA | 06 | P | Fear |
| disgust | DIS | 07 | D | Disgust |
| exclue | — | 02 (calme), 08 (surprise) | S (surprise) | Surprise |

- **Calme exclu** plutôt que fusionné avec neutre : c'est une consigne de jeu à part, absente
  des autres jeux, et la fusion triplerait les neutres de RAVDESS (de 96 à 288).
- **Surprise exclue** : CREMA-D, notre jeu principal, n'en contient pas.
- **RAVDESS** : uniquement la modalité 03 (audio seul) et le canal 01 (parole), soit 1 440
  fichiers avant exclusion.
- **Toutes les intensités sont gardées** et conservées dans le manifeste, pour analyser les
  erreurs par intensité.

### Effectifs, vérifiés sur les manifestes réels (C3)

| Jeu | Fichiers | Exclus | Gardés | neutral | Chacune des 5 autres |
| --- | --- | --- | --- | --- | --- |
| CREMA-D | 7 442 | 0 | 7 442 | 1 087 | 1 271 |
| RAVDESS | 1 440 | 384 | 1 056 | 96 | 192 |
| CaFE (attendu, sprint 2) | 936 | 144 | 792 | 72 | 144 |

Sur l'entraînement (CREMA-D + RAVDESS), neutral est un peu moins fréquent (1 183 contre 1 463
pour chacune des autres classes). Le F1 macro (P4) en tient compte.

## 3. Découpage des émotions par acteur (P1)

On répartit les **acteurs**, jamais les fichiers, entre entraînement, validation et test.
Sinon le modèle reconnaît la voix d'un acteur déjà entendu au lieu de l'émotion, et le score
est gonflé.

**Règle** (`configs/splits.yaml`, code dans `echolens.core.data.splits`) :

1. La validation et le test reçoivent chacun `round(0,15 × nombre d'acteurs / 2)` acteurs
   de chaque genre. Tous les autres vont à l'entraînement.
2. Tirage avec `random.Random(42)` de Python, un seul générateur, d'abord chez les femmes puis
   chez les hommes, sur la liste triée des acteurs de chaque genre : les premiers vont en test,
   les suivants en validation, le reste en entraînement. Le générateur est recréé avec la même
   graine pour chaque jeu (`split_emotion_speakers`).
3. Le résultat est écrit une seule fois dans `data/splits/emotion_split.csv` (une ligne par
   acteur, sans audio) par `training/scripts/make_emotion_split.py`, et versionné. On ne le
   retire jamais au hasard ensuite.
4. Un acteur est identifié par le couple jeu et identifiant : colonnes `dataset` et `speaker`
   (`cremad`, `1001`), comme dans les manifestes.

| Jeu | Acteurs | Entraînement | Validation | Test |
| --- | --- | --- | --- | --- |
| CREMA-D | 91 (48 H, 43 F) | 63 (34 H, 29 F) | 14 (7 H, 7 F) | 14 (7 H, 7 F) |
| RAVDESS | 24 (12 H, 12 F) | 16 (8 H, 8 F) | 4 (2 H, 2 F) | 4 (2 H, 2 F) |

Le test est ainsi parfaitement équilibré en genre, ce qui permet l'analyse des biais (E4).

## 4. ESC-50 : les 5 folds officiels (P3)

On utilise la colonne `fold` de `meta/esc50.csv` telle quelle. On ne remélange jamais : les
fragments d'un même enregistrement d'origine (`src_file`) sont rangés dans le même fold.

**Exception connue du jeu officiel** : 4 enregistrements (9 extraits) sont répartis sur deux
folds, chacun avec deux classes voisines (clock_alarm / clock_tick, hen / rooster). On garde
les folds officiels pour rester comparable à la littérature ; ces 4 sources sont listées dans
`esc50.py`, et toute autre source à cheval sur deux folds est refusée.

À chaque tour k (k = 1 à 5) :

1. le fold k sert de test ;
2. réglage : on entraîne sur 3 folds et on utilise le fold k + 1 (1 après 5) uniquement pour
   choisir le nombre d'époques et les hyperparamètres ;
3. entraînement final : avec ces réglages fixés, on réentraîne sur les 4 folds hors test, puis
   on évalue une seule fois sur le fold k. On apprend ainsi sur 4 folds, comme les articles.

Un modèle sans early stopping (la référence MFCC + SVM) choisit ses hyperparamètres sur le
fold k + 1, puis s'entraîne directement sur 4 folds. On rapporte la moyenne et l'écart-type du
F1 macro et de l'accuracy sur les 5 tours ; l'écart-type est celui de population (ddof = 0),
le même pour tous les modèles.

## 5. Règles communes à tous les modèles

1. **Validation** : early stopping, choix des hyperparamètres et calibrage par température (E2).
   Le **test** n'est utilisé qu'une fois, pour les résultats finaux.
2. **Standardisation (R4)** : moyenne et écart-type par bande calculés sur l'entraînement seul.
3. **Augmentation (P6)** : après le découpage, sur l'entraînement seul. Une version augmentée
   d'un fichier de test ne doit jamais se retrouver en entraînement.
4. **Valeur des masques** (SpecAugment et test de fidélité de Grad-CAM) : les masques sont
   appliqués **après** la standardisation, avec la valeur 0, qui vaut alors la moyenne de
   l'entraînement. Jamais avant : notre log-Mel est en dB absolus, et 0 dB y est un son fort
   (le plancher est à −100 dB). Masquer avec 0 avant la standardisation ajouterait de
   l'énergie au lieu d'en retirer.
5. **Résultats de test** : par jeu, puis tous jeux confondus.

## 6. Identification du locuteur (P11)

On ne sépare pas les locuteurs, sinon on ne pourrait pas les reconnaître : on sépare leurs
phrases.

1. Pour chaque locuteur, 5 phrases tirées au hasard (graine 42) servent à l'enregistrement de
   sa voix ; les autres servent au test.
2. On ne garde que les locuteurs qui ont au moins 10 phrases.
3. Le seuil « locuteur inconnu » est choisi sur un groupe de locuteurs et évalué sur un autre.

## 7. Normalisation du WER (P10, P12)

Le WER est mesuré sur le test officiel d'OpenSLR 57 et sur le sous-corpus `yaounde` (rangé dans
`train`, mais Whisper n'est pas entraîné sur OpenSLR). Référence et transcription sont
normalisées de la même façon avant la première mesure :

1. tout en minuscules ;
2. ponctuation retirée, sauf l'apostrophe et le trait d'union à l'intérieur d'un mot ;
3. apostrophes unifiées (’ devient ') et espaces autour retirés : « c' est » devient « c'est » ;
4. nombres en chiffres écrits en lettres : « 7 h 30 » devient « sept heures trente » ;
5. espaces multiples réduits à un seul.

## 8. Enregistrements de l'équipe (P13)

Ils servent au troisième niveau de test (voix camerounaises en français), à la démo et à
l'identification du locuteur. Rien ne sert à l'entraînement, et rien ne va sur GitHub (dépôt
public) : seul le manifeste, sans audio ni nom réel, peut y aller.

**Organisation** : pas de séance commune. Chacun enregistre de son côté, sur téléphone puis sur
ordinateur, après avoir signé le formulaire de consentement (annexe de Ly5, photo ou PDF signé
dans le dossier `consentements` du Drive).

| Partie | Contenu | Usage |
| --- | --- | --- |
| A | Les 20 phrases ci-dessous, lues d'un ton neutre | WER, voix du locuteur |
| B | 2 phrases neutres, jouées avec chacune des 6 émotions | Émotions en français |
| C | 1 ou 2 sons de 5 s, au téléphone, pris dans la liste ci-dessous | Événements sonores |

**Conditions** : pièce calme, appareil à environ 30 cm, 1 s de silence avant et après chaque
phrase, émotion jouée franchement sans saturer, réécoute d'un fichier par appareil. Format par
défaut de l'appareil (m4a, wav ou webm), sans conversion : ffmpeg convertit à l'import (D1).
Chacun note le modèle de son téléphone et de son ordinateur (analyse par appareil, E3).

**Nommage** : `<personne>_<appareil>_<partie>_<numéro sur 2 chiffres>_<étiquette>.<extension>`

| Partie | Exemple | Étiquette |
| --- | --- | --- |
| A | `p01_tel_A_07_lecture.m4a` | toujours `lecture` ; le texte est retrouvé par le numéro |
| B | `p01_pc_B_02_angry.wav` | l'émotion jouée ; le numéro est celui de la phrase (01 ou 02) |
| C | `p03_tel_C_01_rooster.m4a` | la classe ESC-50 |

Personnes : `p01` à `p04`. Appareils : `tel` ou `pc`. La correspondance entre identifiant et nom
reste sur une feuille à part, avec les formulaires. Une table sans noms (identifiant, genre,
modèles d'appareils) alimente la colonne `gender` du manifeste.

**Stockage** : audios dans `enregistrements/pXX/` du Drive EchoLens (4 membres seulement),
supprimés au plus tard le 31 janvier 2027.

### Partie A : les 20 phrases

1. Le taxi m'a déposé devant la poste centrale de Yaoundé.
2. Il pleut beaucoup depuis le début de la semaine.
3. Nous avons rendez-vous à l'école polytechnique demain matin.
4. Ma sœur prépare du ndolé pour le repas de dimanche.
5. Le marché de Mokolo est très animé le samedi.
6. Peux-tu fermer la fenêtre avant de partir ?
7. Le professeur a repoussé l'examen à la semaine prochaine.
8. J'ai acheté trois mangues et un ananas au bord de la route.
9. La connexion internet est lente dans ce quartier.
10. Le train pour Douala part à sept heures trente.
11. Il faut recharger le téléphone avant la réunion.
12. Les enfants jouent au football dans la cour.
13. Cette chanson passe souvent à la radio.
14. Nous devons rendre le rapport avant le deux décembre.
15. Le moto-taxi a pris un raccourci par le petit chemin.
16. Mon grand-père raconte toujours la même histoire.
17. La boulangerie ouvre très tôt le matin.
18. Est-ce que tu as vu mes clés quelque part ?
19. Le courant a été coupé pendant toute la soirée.
20. Je préfère le jus de gingembre bien frais.

### Partie B : les 2 phrases neutres

1. Le bus arrive dans dix minutes.
2. J'ai posé le dossier sur la table.

Ordre de jeu : neutral, happy, sad, angry, fear, disgust. L'émotion jouée devient l'étiquette.

### Partie C : les 12 classes d'ESC-50 à rapporter

| Classe ESC-50 | Où l'enregistrer |
| --- | --- |
| rooster | Le matin, dans un quartier |
| hen | Près d'une basse-cour |
| dog | Un chien qui aboie |
| crying_baby | À la maison, avec l'accord des parents |
| car_horn | Au bord d'une route |
| engine | Une moto ou une voiture au ralenti |
| rain | Pendant une averse |
| thunderstorm | Pendant un orage |
| church_bells | À côté d'une église |
| door_wood_knock | Quelqu'un qui frappe à une porte en bois |
| footsteps | Des pas sur un sol dur |
| pouring_water | De l'eau versée dans un seau |

Chacun annonce ses classes dans le groupe pour éviter les doublons. On n'enregistre aucune voix
reconnaissable d'une personne qui n'a pas donné son accord.

**Piste pour le sprint 2** (proposée par Nicole) : 3 phrases de la partie A enregistrées avec un
bruit de fond (musique, ventilateur), pour mesurer la robustesse au bruit (E3).

## 9. Tests de fuite (C4)

Chaque règle devient un test de `tests/unit/`. C4 est terminée quand tous passent en CI.

- Aucun acteur ne figure dans deux découpages d'émotions.
- Chaque fichier gardé a exactement un découpage.
- Après correspondance, toutes les étiquettes appartiennent aux 6 classes ; les exclusions
  valent 384 pour RAVDESS et 0 pour CREMA-D (144 pour CaFE au sprint 2).
- Les effectifs d'acteurs par découpage et par genre sont ceux de la section 3.
- Le découpage est déterministe : le régénérer donne exactement le fichier versionné.
- ESC-50 : 400 extraits par fold, et chaque source dans un seul fold, sauf les 4 exceptions.
- CaFE, ACE, OpenSLR 57 et nos enregistrements n'ont aucune ligne en entraînement ni en
  validation (sprint 2).
- Locuteur : aucune phrase n'est à la fois en enregistrement et en test (sprint 2).

Les tests de logique utilisent de petits manifestes inventés ; les tests d'effectifs lisent
les manifestes versionnés (métadonnées seulement, sans audio).

## 10. Limites à écrire dans le rapport

- **Phrases communes** : CREMA-D utilise les mêmes 12 phrases pour tous les acteurs, RAVDESS
  les mêmes 2. Le texte est donc commun au train et au test ; CaFE et nos enregistrements
  couvrent les phrases nouvelles.
- **Intensités de CREMA-D déséquilibrées** : 6 077 extraits en XX contre 455 pour chacun de LO,
  MD et HI (une seule des 12 phrases a été jouée à trois intensités). Une analyse par intensité
  ne porte donc que sur cette phrase.
- **Repères humains** : sur l'audio seul de CREMA-D, les humains reconnaissent l'émotion voulue
  dans 40,9 % des cas ; sur ESC-50, 81,3 %. Ce sont des repères, pas des plafonds : un modèle
  peut les dépasser en apprenant les conventions de jeu des acteurs. Chaque score se compare
  aussi au hasard : 16,7 % pour 6 émotions, 2 % pour 50 sons.
- **16 kHz** : tout ce qui dépasse 8 kHz est perdu, ce qui pénalise certains sons d'ESC-50.
- **ESC-50** : 9 extraits à cheval sur deux folds officiels (section 4).
- **Copie Kaggle de CREMA-D** : un fichier mal nommé (`1040_ITH_SAD_X.wav`), traité dans
  `cremad.py`.
- **Nos enregistrements** : 4 locuteurs non acteurs, des conditions qui varient d'une personne
  à l'autre (enregistrement chacun de son côté), et 96 extraits d'émotion. Les résultats sur
  ces voix sont illustratifs, pas statistiquement concluants.
