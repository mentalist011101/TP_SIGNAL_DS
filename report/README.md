# Rapport écrit

Rapport LaTeX (remise le 2 décembre 2026) : architecture, données, méthodologie, modèles,
expériences, résultats, discussion, limites et perspectives. Toutes les figures et tables sont
produites par le script d'évaluation du dépôt (décision E8), jamais copiées d'ailleurs : chaque
chiffre d'une table cite en commentaire le fichier de `training/results/` d'où il vient.

Rédaction coordonnée par Lynn ; partie équations par Steve.

## Compiler

```bash
cd report
latexmk -pdf main.tex
```

Le PDF n'est pas commité. Sur Overleaf, importer le dossier `report/` et compiler `main.tex`.

## Plan et répartition

Chaque section est un fichier de `sections/`. Tant qu'une partie n'est pas écrite, un encadré
orange « À rédiger » indique son porteur et son contenu ; on le retire quand la partie est
finie.

| Section | Fichier | Porteur | État |
| --- | --- | --- | --- |
| Résumé | `main.tex` | Luciano | à rédiger à la fin |
| 1. Introduction | `01_introduction.tex` | Luciano | à rédiger |
| 2. Signal et représentations (équations) | `02_signal.tex` | Steve | à rédiger |
| 3. Données et protocole | `03_donnees_protocole.tex` | Lynn | rédigée ; reste T6, ACE et C17 |
| 4. Architecture | `04_architecture.tex` | Luciano | à rédiger |
| 5. Modèles | `05_modeles.tex` | Luciano | à rédiger |
| 6. Application | `06_application.tex` | Nicole | à rédiger |
| 7.1 Métriques | `07_resultats.tex` | Steve | à rédiger |
| 7.2 à 7.3 Émotions, ESC-50 ; 7.7 explicabilité | `07_resultats.tex` | Nicole | à rédiger |
| 7.4 Locuteur | `07_resultats.tex` | Lynn | rédigée (C15) |
| 7.5 Transcription | `07_resultats.tex` | Lynn | rédigée (C17a, C17c) |
| 7.6 Analyse des erreurs | `07_resultats.tex` | Lynn, Steve (E4) | E3 et E4 à produire |
| 8. Discussion et limites | `08_discussion.tex` | toute l'équipe | à rédiger |
| 9. Conclusion | `09_conclusion.tex` | Luciano | à rédiger |
| Annexes | `annexes.tex` | selon les besoins | à rédiger |

## Calendrier proposé

| Date | Étape |
| --- | --- |
| 28 novembre | Chaque porteur a poussé une première version de ses sections |
| 30 novembre | Relecture croisée (chacun relit une section qui n'est pas la sienne) |
| 1er décembre | Discussion, conclusion, résumé ; plus aucun encadré « À rédiger » |
| 2 décembre | Remise |
