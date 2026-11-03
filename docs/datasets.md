# Jeux de données

Aucun jeu n'est commité : les scripts de `training/data/` (sprint S1) les téléchargent dans `data/`
et vérifient leur somme de contrôle. Les licences non commerciales sont compatibles avec un usage
académique ; chaque jeu est cité dans le rapport.

| Tâche | Jeu | Rôle | Licence | Source |
| --- | --- | --- | --- | --- |
| Émotions | CREMA-D (7 442 extraits, 91 acteurs, 6 émotions) | Entraînement principal | À vérifier | https://www.tensorflow.org/datasets/catalog/crema_d |
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
