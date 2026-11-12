# Diagrammes

Sources textuelles (Mermaid ou PlantUML) versionnées ici, exportées en PDF pour le rapport et le Beamer.

| Diagramme | Fichier | Notation | Statut |
| --- | --- | --- | --- |
| Séquence du flux micro (navigateur → WebSocket → tampon → inférence → frise) | `sequence-flux-micro.md` | UML, séquence | Brouillon, à relire (flux pas encore codé) |
| Composants (web, api, services, core, stockage) | `composants.md` | UML, composants | Brouillon, à relire |
| Déploiement (Docker, Gunicorn, Kaggle, Hugging Face Hub) | `deploiement.md` | UML, déploiement | Brouillon, à relire |
| Historique des analyses (analyses, segments, prédictions, locuteurs) | `mcd-historique.md` | MERISE, MCD | Brouillon : ANALYSE conforme au code, le reste proposé |

Les sources sont en Mermaid : GitHub et l'aperçu Markdown de VS Code les affichent directement.
Mermaid n'a pas de notation dédiée aux composants, au déploiement ni au MCD MERISE : ces trois
diagrammes sont dessinés avec des groupes et des formes, et les stéréotypes UML (« «device» »,
« «artifact» »…) sont écrits dans les libellés. Partout, les **pointillés** marquent ce qui
n'existe pas encore dans le code.
