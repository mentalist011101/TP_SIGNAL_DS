# echolens-emotion-whisper-base — émotions, tête sur Whisper base (famille B)

Modèle du projet EchoLens (INF50101, ENSPY) : reconnaît l'émotion d'un segment de parole parmi
6 classes. Profil **qualité** de l'application.

## Tâche et entrée

- Tâche : classification de l'émotion, 6 classes communes (P2, EF-05) : neutral, happy, sad,
  angry, fear, disgust.
- Entrée : signal mono 16 kHz brut (R7), segment de parole de 5 s au plus (VAD, D5), passé
  dans l'**encodeur gelé** de `openai/whisper-base` à la révision
  `e37978b90ca9030d5170a5c07aadb050351a65bb` ; moyenne de chaque couche (entrée + 6 couches,
  dimension 512) sur les seules trames utiles.
- Standardisation de chaque (couche, dimension) avec les statistiques du train (R4).
- Sortie : 6 scores ; probabilités calibrées = softmax(scores / T), avec T = 1,109.

## Architecture

Tête seule (l'encodeur reste gelé) : somme pondérée apprise des 7 couches, puis MLP
512 → 256 → 6 avec ReLU et Dropout 0,3. 132 877 paramètres, poids de 0,53 Mo. L'encodeur de
Whisper base compte 20 590 592 paramètres.

## Données et entraînement

- CREMA-D (ODbL) et RAVDESS (CC BY-NC-SA 4.0), découpage **par acteur** (P1) : aucun acteur du
  test n'a servi à l'entraînement. Test : 1 324 extraits, 18 acteurs (9 femmes, 9 hommes).
- Tête finale de C11, graine 42 : lr 1e-3, dropout 0,3, meilleure époque (3) choisie sur la
  validation, sur la courbe complète de 100 époques.

## Métriques (test, 1 324 extraits)

| Métrique | Valeur |
| --- | --- |
| F1 macro (3 graines, moyenne ± écart-type) | 0,753 ± 0,003 |
| Accuracy | 0,749 |
| IC 95 % du F1 macro (bootstrap, graine 42) | [0,728 ; 0,774] |
| F1 par jeu | CREMA-D 0,745 · RAVDESS 0,798 |
| F1 par genre | femmes 0,805 · hommes 0,702 |
| F1 par classe | neutral 0,837 · angry 0,805 · happy 0,749 · disgust 0,737 · sad 0,698 · fear 0,675 |
| ECE avant → après calibration | 0,030 → 0,022 |

Calibration (E2) : T réglée sur la validation (prédictions de la tête de la graine 42), ECE
mesurée sur le test. T = 1,109 > 1 : la tête est un peu trop sûre d'elle.

Comparaison : sur les émotions, les trois encodeurs de C11 sont à égalité (McNemar non
significatif) ; mHuBERT-147 a le F1 le plus haut (0,769), mais whisper-base est retenu pour ne
garder qu'un seul encodeur en mémoire pour les deux têtes du profil qualité.

## Latence (E6, ENF-01)

Machine CPU de référence : Intel Core i5-6200U (2,30 GHz, 4 cœurs logiques), Windows 10,
torch 2.15 CPU. Chaîne complète par fenêtre, décodage exclu, 200 fenêtres :

| Fenêtre | p50 | p95 | RTF au p95 |
| --- | --- | --- | --- |
| 2 s | 1 623 ms | 4 266 ms | 2,13 |
| 5 s | 1 456 ms | 3 037 ms | 0,61 |

Trop lent pour le flux (il faudrait p95 < 0,5 s) : profil qualité seulement. Le profil temps
réel n'a pas encore de modèle d'émotion.

## Limites et biais

- Écart net entre les genres : F1 0,805 pour les voix féminines, 0,702 pour les voix
  masculines (E4). Avec 9 acteurs par genre, l'écart peut venir des acteurs tirés autant que du
  genre.
- Émotions jouées par des acteurs anglophones, en studio : le transfert au français (CaFE), aux
  voix africaines et aux enregistrements de l'équipe n'est pas encore mesuré (P7).
- L'application n'envoie au modèle que les segments où la VAD détecte de la parole. Silero
  (production) laisse passer 7,2 % des sons non vocaux d'ESC-50, surtout des cris d'animaux ;
  sur CREMA-D, 91 % des extraits de parole reconnus comme parole sur au moins la moitié de
  leur durée ;
  sans torch, webrtcvad (secours) prend la plupart des sons continus pour de la parole
  (voir D5).
- Usage non commercial, partage à l'identique (licence de RAVDESS).
