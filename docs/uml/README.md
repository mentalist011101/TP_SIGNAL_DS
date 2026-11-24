# Diagrammes

Sources textuelles (Mermaid ou PlantUML) versionnées ici, exportées en PDF pour le rapport et le Beamer.

| Diagramme | Fichier | Notation | Statut |
| --- | --- | --- | --- |
| Séquence du flux micro (navigateur → WebSocket → tampon → inférence → frise) | `sequence-flux-micro.md` | UML, séquence | Proposition : le flux n'est pas encore codé |
| Composants (web, api, services, core, stockage) | `composants.md` | UML, composants | Conforme au code du 24 novembre (après C13 et la PR #28) |
| Déploiement (Docker, Gunicorn, Kaggle, Hugging Face Hub) | `deploiement.md` | UML, déploiement | Conforme au code du 24 novembre ; signale le risque du cache des modèles |
| Historique des analyses (analyses, tâches, résultats, segments, probabilités, locuteurs) | `mcd-historique.md` | MERISE, MCD | Conforme au code (colonne JSON `results`), sauf LOCUTEUR, proposé |

Pour comprendre et expliquer chaque diagramme à l'oral : `docs/fiches/diagrammes-uml.md`.

Les sources sont en Mermaid : GitHub et l'aperçu Markdown de VS Code les affichent directement.
Mermaid n'a pas de notation dédiée aux composants, au déploiement ni au MCD MERISE : ces trois
diagrammes sont dessinés avec des groupes et des formes, et les stéréotypes UML (« «device» »,
« «artifact» »…) sont écrits dans les libellés. Partout, les **pointillés** marquent ce qui
n'existe pas encore dans le code.
