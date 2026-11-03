---
description: Rédige la fiche d'un modèle entraîné et met à jour le registre
argument-hint: <identifiant du modèle>
---

Rédige la fiche du modèle `$ARGUMENTS` :

1. Retrouve sa configuration et ses résultats (run Weights & Biases, fichiers d'évaluation).
2. Écris `docs/models/$ARGUMENTS.md` en français : tâche, famille (A ou B), architecture,
   données et découpage, métriques (F1 macro, accuracy, matrice de confusion, ECE), latence
   p50/p95 et RTF sur CPU, limites et biais observés.
3. Mets à jour l'entrée correspondante dans `configs/registry.yaml` (version, poids, labels,
   métriques), puis lance `make test` pour valider le registre.

N'invente aucun chiffre : si une métrique manque, écris « non mesuré » et signale-le.
