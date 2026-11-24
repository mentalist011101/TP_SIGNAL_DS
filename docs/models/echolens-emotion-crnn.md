# echolens-emotion-crnn — émotion de la voix, CRNN sur log-Mel (famille A)

Modèle du projet EchoLens (INF50101, ENSPY) : reconnaît l'émotion d'une fenêtre de voix de 3 s
parmi 6 classes. Profil **temps réel** de l'application ; le profil qualité garde la tête
whisper-base (echolens-emotion-whisper-base).

## Tâche et entrée

- Tâche : reconnaissance de l'émotion de la voix, 6 classes communes à CREMA-D et RAVDESS
  (P2) : neutral, happy, sad, angry, fear, disgust (EF-05).
- Entrée : signal mono 16 kHz. Log-Mel 64 bandes en dB absolus (R1, R2), calculé par
  `echolens.core.features` avec `configs/features.yaml`, ramené à **301 trames (3 s)** :
  fenêtre centrale d'un extrait plus long, silence (−100 dB) ajouté à la fin d'un extrait
  plus court. `config.json` donne l'empreinte des paramètres des features, que l'application
  vérifie avant de charger le modèle.
- Standardisation par bande avec les moyennes et écarts-types de l'entraînement (R4), dans
  `config.json`.
- Sortie : 6 scores ; probabilités calibrées = softmax(scores / T), avec T = 1,088.

## Architecture

Le même CRNN que pour les événements sonores (C9), avec 6 sorties : 4 blocs Conv2d 3×3 →
BatchNorm → ReLU → MaxPool 2×2 (32, 64, 128, 256 canaux), moyenne sur la fréquence, BiGRU de
128 par sens, pooling par attention, Dropout 0,3, couche linéaire vers 6 classes.
687 047 paramètres, poids de 2,8 Mo (`model.safetensors`).

## Données et entraînement

- CREMA-D (ODbL) et RAVDESS (CC BY-NC-SA 4.0), classes calm et surprise exclues (P2).
- Découpage par acteur (P1, `data/splits/emotion_split.csv`) : 79 acteurs en train (5 850
  extraits), 18 en validation (1 324), 18 en test (1 324) ; aucun acteur dans deux parties.
- Fenêtre de 3 s : tirée au hasard dans l'extrait à chaque lot en entraînement, centrale en
  validation et en test. Silence ajouté en moyenne : 17,4 % de la fenêtre sur CREMA-D, 0 % sur
  RAVDESS (extraits d'au moins 3 s).
- Recette de C9 : AdamW (décroissance 0,01), cosinus sur 100 époques, courbe complète sans
  arrêt anticipé, lots de 32. Augmentations (P6) : gain ±6 dB, rotation des trames,
  SpecAugment, mixup α = 0,2.
- Taux d'apprentissage choisi sur la validation avec la graine 42 : 1e-3 (F1 de validation
  0,686, contre 0,678 pour 3e-4). Modèle de production : graine 42, sa meilleure époque de
  validation (96 sur 100). Pas de réentraînement : le test reste indépendant.

## Métriques (test, 1 324 extraits, 18 acteurs)

| Métrique | Valeur |
| --- | --- |
| F1 macro (3 graines, moyenne ± écart-type) | 0,668 ± 0,014 |
| Accuracy | 0,666 ± 0,012 |
| F1 macro du modèle de production (graine 42) | 0,680, IC 95 % (bootstrap) [0,656 ; 0,705] |
| F1 macro CREMA-D / RAVDESS | 0,669 ± 0,013 / 0,638 ± 0,023 |
| F1 macro femmes / hommes | 0,737 ± 0,012 / 0,598 ± 0,018 |
| ECE avant → après calibration (test) | 0,050 → 0,033 |

F1 par classe (moyenne des 3 graines) : neutral 0,80 · angry 0,75 · disgust 0,65 · sad 0,64 ·
happy 0,60 · fear 0,58.

Calibration (E2) : T réglée sur la validation, ECE mesurée sur le test. T > 1 : le réseau est
un peu trop sûr de lui ; la calibration adoucit ses probabilités.

Comparaisons (McNemar, graine 42, 1 324 extraits, p corrigées par Holm sur les 2 tests de
C12) : meilleur que le CNN (162 extraits contre 97, p = 7 × 10⁻⁵) ; moins bon que la tête
whisper-base de C11 (107 contre 201, p = 2 × 10⁻⁷), qui reste le modèle du profil qualité.

## Latence (E6, ENF-01)

Machine CPU de référence : Intel Core i5-6200U (2,30 GHz, 4 cœurs logiques), Windows 10,
torch 2.15 CPU. Chaîne complète par fenêtre (log-Mel, découpe de 3 s, standardisation,
réseau, calibration), décodage du fichier exclu, 200 fenêtres :

| Fenêtre | p50 | p95 | RTF au p95 |
| --- | --- | --- | --- |
| 2 s | 59 ms | 347 ms | 0,17 |
| 5 s | 50 ms | 137 ms | 0,03 |

Les deux fenêtres sont ramenées à 3 s avant le réseau : leur coût est le même, l'écart entre
les deux lignes est du bruit de mesure. Le p95 est pessimiste : la machine n'était pas
entièrement au repos (autres processus, environ 30 à 60 % du CPU).

Sous la limite du flux (calcul < H = 0,5 s pour W = 2 s, soit RTF < 0,25) : modèle retenu
pour le profil temps réel.

## Limites et biais

- Écart entre genres : F1 macro 0,74 sur les femmes, 0,60 sur les hommes (même sens que la
  tête whisper-base : 0,80 contre 0,70). Mais la dispersion entre acteurs d'un même genre est
  aussi grande (écart-type 0,09 chez les femmes, 0,11 chez les hommes ; de 0,33 à 0,70 chez
  les hommes) : avec 9 acteurs par genre en test, l'écart tient autant aux acteurs qu'au genre.
- Classes les plus confondues (graine 42) : fear prise pour sad (23 % des extraits fear), happy prise pour
  angry (15 %).
- Émotions jouées par des acteurs, en anglais, en studio : la voix spontanée, les autres
  langues et le bruit ne sont pas mesurés.
- En flux, une fenêtre de 2 s est complétée par 1 s de silence pour atteindre 3 s.
- Usage non commercial uniquement (licence de RAVDESS, partage à l'identique).
