# Diagrammes

Diagrammes dessinés avec **draw.io**. Pour chacun :
- la source modifiable `<nom>.drawio` ;
- l'image exportée `images/<nom>.png`, utilisée dans le rapport et le Beamer ;
- une page `<nom>.md` qui montre l'image et explique sa lecture.

| Diagramme | Source | Image | Notation | Statut |
| --- | --- | --- | --- | --- |
| Composants (web, api, services, core, stockage) | `composants.drawio` | `images/composants.png` | UML, composants | Conforme au code du 24 novembre (après C13 et la PR #28) |
| Déploiement (Docker, Gunicorn, Kaggle, Hugging Face Hub) | `deploiement.drawio` | `images/deploiement.png` | UML, déploiement | Conforme au code du 24 novembre ; signale le risque du cache des modèles |
| Séquence du flux micro (navigateur → WebSocket → tampon → inférence → frise) | `sequence-flux-micro.drawio` | `images/sequence-flux-micro.png` | UML, séquence | Proposition : le flux n'est pas encore codé |
| Historique des analyses (analyses, tâches, résultats, segments, probabilités, locuteurs) | `mcd-historique.drawio` | `images/mcd-historique.png` | MERISE, MCD | Conforme au code (colonne JSON `results`), sauf LOCUTEUR, proposé |

Pour comprendre et expliquer chaque diagramme à l'oral : `docs/fiches/diagrammes-uml.md`.

**Modifier un diagramme** :
1. Ouvrir le `.drawio` dans draw.io (application de bureau, ou app.diagrams.net > Ouvrir depuis l'appareil).
2. Faire la modification et enregistrer.
3. Réexporter l'image : Fichier > Exporter en > PNG, zoom 200 %, bordure 20, en remplaçant le fichier de `images/`.

Partout, le gris en **pointillés** et le stéréotype `«prévu»` marquent ce qui n'existe pas encore dans le code.
