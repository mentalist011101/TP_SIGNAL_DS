# ADR 0001 — Architecture en couches, cœur de calcul partagé

- Statut : acceptée
- Date : 2026-11-03

## Contexte

L'application doit être une application Flask exploitable, les modèles sont entraînés sur Kaggle et
la démonstration tourne sur CPU. Le risque principal d'un tel projet est un écart entre les features
calculées à l'entraînement et celles calculées en démonstration.

## Décision

Quatre couches : `web/` (React, compilé et servi par Flask), `api/` (Flask, REST et WebSocket),
`services/` (orchestration), `core/` (calcul pur). `core/` n'importe jamais Flask et est installé
tel quel dans les notebooks Kaggle (`pip install -e`). Toute feature passe par
`echolens.core.features` et `configs/features.yaml`.

## Conséquences

- Features identiques à l'entraînement et en démo, par construction.
- Le cœur se teste sans serveur web.
- Une couche d'indirection de plus (services) à maintenir.
- React impose une chaîne Node en développement, mais pas au lancement : Flask sert `web/dist`.
