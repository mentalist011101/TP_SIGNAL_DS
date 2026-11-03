# Contribuer à EchoLens

## Flux de travail

1. Partir d'une issue GitHub (fonctionnalité, bug ou expérience).
2. Créer une branche depuis `main` : `feat/export-csv`, `fix/decodage-webm`, `exp/crnn-emotions`.
3. Commiter en français au format Conventional Commits : `feat(api): ajoute l'export CSV`.
4. Lancer `make check` : tout doit être vert.
5. Ouvrir une Pull Request vers `main` en remplissant le modèle.
6. Luciano relit et fusionne. Personne ne pousse directement sur `main`.

## Réglages de la branche `main` (à faire une fois sur GitHub)

Settings → Branches → Add branch protection rule, motif `main` :

- Require a pull request before merging, avec 1 approbation
- Require status checks to pass : jobs `python` et `web` de la CI
- Do not allow bypassing the above settings ; pas de force-push ni de suppression

## Travailler avec Claude Code

Le fichier `CLAUDE.md` contient les règles d'architecture et de style. Les commandes du dossier
`.claude/commands/` automatisent les tâches répétitives (`/new-experiment`, `/model-card`, `/fiche`).

## Comprendre ce qu'on fusionne

Chaque membre défend une brique à l'oral. Avant d'approuver une PR qui touche votre brique, vous
devez pouvoir expliquer le code et le choix qu'il implémente. Si ce n'est pas le cas, posez la
question dans la PR : c'est le moment de l'apprendre.
