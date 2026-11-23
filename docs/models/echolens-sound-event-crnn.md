# echolens-sound-event-crnn — événements sonores, CRNN sur log-Mel (famille A)

Modèle du projet EchoLens (INF50101, ENSPY) : reconnaît l'événement sonore d'une fenêtre de
5 s parmi les 50 classes d'ESC-50. Profil **temps réel** de l'application.

## Tâche et entrée

- Tâche : classification d'événements sonores, 50 classes d'ESC-50 (EF-06).
- Entrée : signal mono 16 kHz, fenêtre de 5 s. Log-Mel 64 bandes, 501 trames, en dB absolus
  (R1, R2), calculé par `echolens.core.features` avec `configs/features.yaml` ; `config.json`
  donne l'empreinte de ces paramètres, que l'application vérifie avant de charger le modèle.
- Standardisation par bande avec les moyennes et écarts-types de l'entraînement (R4), dans
  `config.json`.
- Sortie : 50 scores ; probabilités calibrées = softmax(scores / T), avec T = 0,786.

## Architecture

4 blocs Conv2d 3×3 → BatchNorm → ReLU → MaxPool 2×2 (32, 64, 128, 256 canaux), moyenne sur la
fréquence, BiGRU de 128 par sens, pooling par attention, Dropout 0,3, couche linéaire vers
50 classes. 698 355 paramètres, poids de 2,8 Mo (`model.safetensors`).

## Données et entraînement

- ESC-50 (2 000 extraits de 5 s, 5 folds officiels), licence CC BY-NC 3.0.
- Réglage par validation croisée (P3, C9) : courbe complète de 150 époques, meilleure époque
  choisie sur le fold k + 1. Modèle de production : réentraîné sur les **5 folds** avec la
  médiane des réglages des 5 tours (lr 1e-3, 129 époques), AdamW, cosinus, graine 42.
- Augmentations (P6) : gain ±6 dB, rotation des trames, SpecAugment, mixup α = 0,2.

## Métriques

Le modèle de production a vu les 2 000 extraits : il n'a plus de test indépendant. Les
chiffres ci-dessous sont ceux de la **validation croisée** sur les 5 folds (même recette, un
fold de test à chaque tour), c'est-à-dire l'estimation de ses performances.

| Métrique | Valeur |
| --- | --- |
| F1 macro (5 tours, moyenne ± écart-type) | 0,827 ± 0,014 |
| Accuracy | 0,832 ± 0,013 |
| IC 95 % du F1 macro (bootstrap, graine 42) | [0,812 ; 0,844] |
| Diagonale de la matrice en 5 catégories | animaux 0,91 · nature et eau 0,95 · humain non verbal 0,89 · intérieur 0,85 · extérieur et urbain 0,83 |
| ECE avant → après calibration (hors fold) | 0,066 → 0,016 |

Calibration (E2) : T réglée sur le fold de test de chacun des 5 tours (0,766 ; 0,767 ; 0,838 ;
0,738 ; 0,820), T = 0,786 leur moyenne ; l'ECE est mesurée en calibrant chaque fold avec la
moyenne des 4 autres températures. T < 1 : le CRNN est trop peu sûr de lui (effet attendu du
mixup, qui apprend sur des cibles mélangées) ; la calibration accentue ses probabilités.

Comparaisons (McNemar, graine 42, 2 000 extraits) : meilleur que le CNN (p = 5 × 10⁻⁷) et que la
référence MFCC + SVM (p = 2 × 10⁻¹⁶³) ; pas de différence significative avec la tête
whisper-base (p = 0,33).

## Latence (E6, ENF-01)

Machine CPU de référence : Intel Core i5-6200U (2,30 GHz, 4 cœurs logiques), Windows 10,
torch 2.15 CPU. Chaîne complète par fenêtre (log-Mel, standardisation, réseau, calibration),
décodage du fichier exclu, 200 fenêtres :

| Fenêtre | p50 | p95 | RTF au p95 |
| --- | --- | --- | --- |
| 2 s | 38 ms | 157 ms | 0,08 |
| 5 s | 82 ms | 401 ms | 0,08 |

Sous la limite du flux (calcul < H = 0,5 s pour W = 2 s, soit RTF < 0,25) : modèle retenu
pour le profil temps réel.

## Limites et biais

- Classes les plus faibles : helicopter (F1 0,53), washing_machine (0,55), wind (0,57),
  airplane (0,62), fireworks (0,72) : bruits larges et stationnaires, sans motif temporel.
- Un seul événement par fenêtre (pas de son polyphonique) ; 50 classes fermées : un son hors
  d'ESC-50 reçoit quand même l'une des 50 classes.
- Entraîné sur des extraits courts et propres d'ESC-50 ; la robustesse au bruit et aux
  appareils n'est pas encore mesurée (E3, C19).
- Usage non commercial uniquement (licence d'ESC-50).
