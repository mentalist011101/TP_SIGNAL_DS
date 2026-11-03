---
description: Prépare une nouvelle expérience (config, script, issue) selon le protocole EchoLens
argument-hint: <tâche> <modèle> [description]
---

Prépare une nouvelle expérience pour : $ARGUMENTS

1. Relis les décisions de protocole P1 à P8 et les hypothèses H1 à H4 de la spécification
   (résumées dans `CLAUDE.md` et `docs/`). Indique quelle hypothèse cette expérience sert à trancher.
2. Crée `configs/experiments/<tâche>-<modèle>.yaml` : jeu de données, découpage (indépendant du
   locuteur pour les émotions, folds officiels pour ESC-50), paramètres du modèle, optimiseur,
   graines (3 pour un résultat principal), métriques.
3. Crée ou complète le script d'entraînement dans `training/`, en important `echolens.core`
   (jamais de calcul de features en dehors de `echolens.core.features`).
4. Rédige le texte d'une issue « Expérience » (question, protocole, critère de décision).
5. Liste ce qu'il faudra savoir expliquer à l'oral sur cette expérience.

Commentaires et docstrings en français, code en anglais.
