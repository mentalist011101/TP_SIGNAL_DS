# echolens-sound-event-whisper-base — événements sonores, tête sur Whisper base (famille B)

Modèle du projet EchoLens (INF50101, ENSPY) : reconnaît l'événement sonore d'une fenêtre de
5 s parmi les 50 classes d'ESC-50. Profil **qualité** de l'application.

## Tâche et entrée

- Tâche : classification d'événements sonores, 50 classes d'ESC-50 (EF-06).
- Entrée : signal mono 16 kHz brut (R7), fenêtre de 5 s, passé dans l'**encodeur gelé** de
  `openai/whisper-base` à la révision `e37978b90ca9030d5170a5c07aadb050351a65bb` (dans
  `config.json`). Le log-Mel de Whisper est complété jusqu'à 30 s ; on moyenne chaque couche
  (entrée + 6 couches, dimension 512) sur les seules trames utiles (50 par seconde).
- Standardisation de chaque (couche, dimension) avec les statistiques de l'entraînement (R4).
- Sortie : 50 scores ; probabilités calibrées = softmax(scores / T), avec T = 1,461.

## Architecture

Tête seule (l'encodeur reste gelé) : somme pondérée apprise des 7 couches (poids =
softmax(a)), puis MLP 512 → 256 → 50 avec ReLU et Dropout 0,3. 144 185 paramètres, poids de
0,58 Mo. L'encodeur de Whisper base compte 20 590 592 paramètres.

## Données et entraînement

- ESC-50 (2 000 extraits, 5 folds officiels), licence CC BY-NC 3.0 ; encodeur Whisper sous
  licence MIT.
- Réglage par validation croisée (P3, C11), courbe complète de 100 époques. Modèle de
  production : réentraîné sur les **5 folds** avec la médiane des réglages des 5 tours (lr 1e-3,
  dropout 0,3, 75 époques), AdamW, cosinus, graine 42.

## Métriques

Le modèle de production a vu les 2 000 extraits ; les chiffres sont ceux de la **validation
croisée** (même recette, un fold de test à chaque tour).

| Métrique | Valeur |
| --- | --- |
| F1 macro (5 tours, moyenne ± écart-type) | 0,830 ± 0,015 |
| Accuracy | 0,835 ± 0,015 |
| IC 95 % du F1 macro (bootstrap, graine 42) | [0,821 ; 0,854] |
| Diagonale de la matrice en 5 catégories | animaux 0,90 · nature et eau 0,93 · humain non verbal 0,91 · intérieur 0,89 · extérieur et urbain 0,87 |
| ECE avant → après calibration (hors fold) | 0,044 → 0,033 |

Calibration (E2) : T réglée sur le fold de test de chacun des 5 tours (1,610 ; 0,992 ; 1,704 ;
1,603 ; 1,396), T = 1,461 leur moyenne ; ECE mesurée en calibrant chaque fold avec la moyenne
des 4 autres. T > 1 : la tête est trop sûre d'elle ; la calibration adoucit ses probabilités.

Comparaisons (McNemar, graine 42, 2 000 extraits) : meilleure que mHuBERT-147 (p = 4 × 10⁻⁶) et
wav2vec2-base (p = 2 × 10⁻⁴³) sur ESC-50 ; pas de différence significative avec le CRNN
(p = 0,33).

## Latence (E6, ENF-01)

Machine CPU de référence : Intel Core i5-6200U (2,30 GHz, 4 cœurs logiques), Windows 10,
torch 2.15 CPU. Chaîne complète par fenêtre (encodeur Whisper, moyennes, standardisation,
tête, calibration), décodage exclu, 200 fenêtres :

| Fenêtre | p50 | p95 | RTF au p95 |
| --- | --- | --- | --- |
| 2 s | 1 856 ms | 4 218 ms | 2,11 |
| 5 s | 2 142 ms | 4 732 ms | 0,95 |

L'encodeur traite toujours 30 s, même pour une fenêtre de 2 s : le coût ne baisse presque pas
avec la durée. Trop lent pour le flux (il faudrait p95 < 0,5 s) : modèle réservé au profil
qualité (analyse de fichiers).

## Limites et biais

- Classes les plus faibles : helicopter (F1 0,44), airplane (0,64), door_wood_creaks (0,66),
  washing_machine (0,66), engine (0,70).
- 50 classes fermées, un événement par fenêtre ; robustesse au bruit non mesurée (E3, C19).
- Usage non commercial uniquement (licence d'ESC-50).
