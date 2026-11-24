# Fiche — Les diagrammes UML et le MCD

Tâche N3. Diagrammes : `docs/uml/` (séquence, composants, déploiement, MCD).
Défendue par : Nicole.

> **Comment utiliser cette fiche.** Lis d'abord la partie 1 (les notations), une seule fois.
> Ensuite, pour chaque diagramme, ouvre son image (`docs/uml/images/<nom>.png`) à côté de la
> fiche et suis la lecture pas à pas. La phrase en encadré est celle à dire au jury. Les
> diagrammes sont dessinés dans draw.io : la source modifiable est `docs/uml/<nom>.drawio`.

## 1. L'idée en trois phrases

1. Un diagramme montre **une seule facette** du système : qui parle à qui et dans quel ordre
   (séquence), comment le code est découpé (composants), où il tourne (déploiement), quelles
   informations on garde (MCD).
2. Les quatre diagrammes répondent à quatre questions du jury : « que se passe-t-il quand on
   parle au micro ? », « comment est organisé votre code ? », « comment on le lance ? »,
   « que gardez-vous en base ? ».
3. Partout, **les pointillés marquent ce qui n'existe pas encore** dans le code : on ne présente
   jamais une proposition comme un fait.

## 2. Les notations, une fois pour toutes

### UML (séquence, composants, déploiement)

UML est un langage de dessin standard pour décrire un logiciel. Il en existe 14 sortes ; on en
utilise trois.

| Symbole | Sens |
| --- | --- |
| `«composant»`, `«device»`, `«artifact»` | Un **stéréotype** : un mot entre guillemets « » qui dit de quelle sorte de boîte il s'agit |
| Rectangle avec deux petits onglets à gauche | Un **composant** : un module du code |
| Cube | Un **nœud** : une machine (`«device»`) ou un logiciel qui en fait tourner d'autres (`«execution environment»`, comme Docker ou le navigateur) |
| Feuille au coin plié | Un **artefact** : un fichier déployé (l'application, le front compilé, les poids) |
| Cylindre | Un stockage (base de données, fichiers, volume) |
| Flèche **en tirets** (composants) | Une **dépendance** : A **utilise** B |
| Flèche **pleine** (déploiement) | Une communication ou un transfert : « le navigateur parle au serveur en HTTP » |
| Flèche bleue épaisse | Le seul passage du front vers le serveur : HTTP `/api/v1` |
| Gris en pointillés, mot `«prévu»` | Prévu, pas encore codé |
| Boîte dans une boîte | « Tourne à l'intérieur de » (déploiement) ou « fait partie de » (composants) |

Dans un diagramme de **séquence**, le temps descend : chaque colonne est un acteur, chaque flèche
horizontale un message ; une flèche pleine est une demande, une flèche en tirets une réponse.
`loop` = se répète, `opt` = seulement si la condition est vraie.

### MERISE (le MCD)

MERISE est une méthode française pour concevoir une base de données. Le **MCD** (modèle
conceptuel des données) décrit les informations **sans parler de tables** : c'est l'étape
d'avant.

| Élément | Dessin | Exemple |
| --- | --- | --- |
| **Entité** | Rectangle, avec son identifiant précédé de `#` | ANALYSE, `# id_analyse` |
| **Attribut** | Ligne dans le rectangle | `duree_s` |
| **Association** | Forme arrondie, avec un verbe | DEMANDER |
| **Cardinalité** | `(min,max)` sur chaque patte | `(1,n)` |

**Lire une cardinalité** : on part de l'entité, on traverse l'association, on arrive à l'autre
entité. « Une ANALYSE DEMANDE **(1,n)** TÂCHE » se lit : *une* analyse demande *au moins une*
(1) et *au plus plusieurs* (n) tâches.

| Cardinalité | Se dit | Exemple |
| --- | --- | --- |
| `(0,1)` | zéro ou un | un résultat vient d'au plus un modèle |
| `(1,1)` | exactement un | un résultat appartient à une seule analyse |
| `(0,n)` | zéro ou plusieurs | une analyse en cours n'a encore aucun résultat |
| `(1,n)` | au moins un | une analyse demande au moins une tâche |

## 3. Diagramme de composants — « comment est organisé notre code ? »

Fichier : `docs/uml/composants.md`.

**Lecture pas à pas**

1. **Quatre grandes boîtes, de haut en bas** : `web` (ce qu'on voit), `api` (la porte d'entrée),
   `services` (l'organisation du travail), `core` (le calcul).
2. **Toutes les flèches descendent.** `web` n'appelle que `api`, `api` n'appelle que `services`,
   `services` appelle `core`. `core` ne connaît personne au-dessus de lui.
3. En bas, les **stockages** (base SQLite, fichiers, `configs/*.yaml`) et deux **dépendances
   extérieures** : ffmpeg (décoder l'audio) et Hugging Face Hub (les poids des modèles).
4. À droite, `training` (Kaggle) utilise **le même `core`** que l'application.
5. Au centre de `services`, l'**interface `Predictor`** : deux prédicteurs interchangeables,
   `DemoPredictor` (faux, pour tester) et `ModelPredictor` (vrais modèles).

> **À dire :** « Notre code est en quatre couches, et les dépendances ne remontent jamais. Le
> calcul, dans `core`, ne connaît pas Flask. On peut donc l'installer seul dans un notebook
> Kaggle, et on est sûrs que le spectrogramme de l'entraînement est calculé par exactement le même
> code que celui de l'application. »

**Piège** : la page web ne calcule rien sur le son. Même le spectrogramme affiché est une image
calculée par le serveur (R5).

## 4. Diagramme de séquence — « que se passe-t-il quand on parle au micro ? »

Fichier : `docs/uml/sequence-flux-micro.md`. **Entièrement en proposition : rien n'est codé.**

**Lecture pas à pas**

1. Six colonnes : l'utilisateur, la page Direct, la route WebSocket, le tampon de la session,
   le prédicteur, `core`.
2. **Démarrage** : clic → le navigateur demande l'autorisation du micro → il ouvre un
   **WebSocket** (une connexion qui reste ouverte, au lieu d'une requête par morceau de son).
3. **Boucle principale** (`loop`) : toutes les 0,1 s, le navigateur envoie un petit morceau de son
   en 16 kHz, Int16. Le serveur l'ajoute au tampon.
4. **Toutes les 0,5 s** (`opt`, H = 0,5 s) : on prend les **2 dernières secondes** (W = 2 s), on
   calcule le log-Mel, le modèle temps réel donne les probabilités, le résultat revient à la
   page avec la **latence** et le **RTF**.
5. **À la fin d'une phrase** (détectée par la VAD) : transcription de la phrase entière.
6. **Arrêt** : on coupe le micro et on libère le tampon.

> **À dire :** « Toutes les demi-secondes, on analyse les deux dernières secondes. Les fenêtres
> se recouvrent : on a un résultat fréquent, mais calculé sur assez de son pour reconnaître une
> émotion. Pour que ça tienne en temps réel, il faut que le calcul d'une fenêtre prenne moins
> d'une demi-seconde : c'est la condition RTF < 1. »

**Les deux formules à savoir**

$$\text{RTF} = \frac{\text{temps de calcul}}{\text{durée du son analysé}} \qquad
\text{latence} \approx H + \text{temps de calcul}$$

Si le calcul dépasse H, les fenêtres s'empilent et le retard grandit sans fin.

## 5. Diagramme de déploiement — « comment on le lance ? »

Fichier : `docs/uml/deploiement.md`.

**Lecture pas à pas**

1. Chaque grande boîte `«device»` est **une machine** : le PC de l'utilisateur, la machine hôte,
   Hugging Face, Kaggle, GitHub.
2. Sur la machine hôte, **Docker** fait tourner **un conteneur** : Gunicorn reçoit les requêtes et
   les passe à Flask ; un pool de 2 threads traite les analyses en arrière-plan ; ffmpeg, torch et
   le front compilé sont dedans.
3. À côté du conteneur, le **volume** `echolens-var` garde la base et les audios : l'historique
   survit à un redémarrage.
4. **Le trajet d'un modèle** : entraîné sur Kaggle (GPU) → publié sur Hugging Face en
   safetensors → téléchargé par l'application à une **révision figée**.
5. **GitHub Actions** vérifie chaque PR (lint, types, tests, build).

> **À dire :** « L'application se lance en une commande, `make docker`, sans GPU et sans Node.
> Les modèles sont entraînés sur Kaggle, publiés sur Hugging Face, et l'application les télécharge
> à une version figée : le modèle de la démo est exactement celui qu'on a évalué. »

**Pourquoi un seul worker Gunicorn ?** Les analyses en cours et les modèles en mémoire vivent
dans un processus. Avec deux workers, chacun chargerait ses propres modèles, et un worker ne
verrait pas les analyses de l'autre.

**Pourquoi safetensors ?** Un fichier pickle (le format par défaut de torch) peut exécuter du code
caché quand on l'ouvre ; un fichier safetensors ne contient que des nombres.

**Point faible connu** : les poids téléchargés restent dans le conteneur, hors du volume. S'il
est recréé, il faut internet pour les retélécharger (correction proposée dans le fichier).

## 6. MCD — « que gardez-vous en base ? »

Fichier : `docs/uml/mcd-historique.md`.

**Lecture pas à pas, en suivant une analyse**

1. **ANALYSE** : un audio importé, avec son statut (`pending` → `processing` → `done` ou
   `failed`), sa durée et son profil.
2. Elle **DEMANDE (1,n)** des **TÂCHES** : au moins une, parmi émotion, événement,
   transcription, locuteur.
3. Une fois terminée, elle **OBTIENT (0,n)** des **RÉSULTATS** : zéro tant qu'elle tourne, puis un
   par tâche demandée. Chaque résultat **PORTE SUR (1,1)** une seule tâche.
4. Un résultat est **PRODUIT (0,1)** par un **MODÈLE** : zéro si la tâche n'est pas encore
   branchée (`unavailable`).
5. Un résultat est **DÉCOUPÉ (0,n)** en **SEGMENTS**, les morceaux de la frise : aucun si personne
   ne parle (`no_speech`).
6. Les **PROBABILITÉS** (une classe, un nombre entre 0 et 1) décrivent soit le résultat global
   (RÉSUMER), soit un segment (DÉTAILLER), jamais les deux : c'est une **contrainte
   d'exclusion**.
7. En pointillés, **LOCUTEUR** et **IDENTIFIER** : prévus pour l'identification du locuteur.

> **À dire :** « Le MCD décrit les informations ; la base, elle, n'a qu'une table, `analyses`.
> Les résultats sont rangés dans une colonne JSON, parce qu'ils sont écrits en une fois à la fin
> du traitement et relus en une fois par la page Résultat. On ne cherche jamais "tous les segments
> en colère". Si un jour on en a besoin, le MCD dit déjà quelles tables créer. »

**Pourquoi une entité TÂCHE alors que le code range une liste ?** En MERISE, un attribut ne peut
pas contenir une liste (première forme normale). Le MCD crée donc l'entité TÂCHE et
l'association DEMANDER ; le code, lui, garde `["emotion", "sound_event"]` en JSON par
simplicité, puisqu'il n'y a que 4 tâches fixes.

## 7. Où se trouve le code

| Diagramme | Ce qu'il faut savoir ouvrir |
| --- | --- |
| Composants | `src/echolens/` (dossiers `api`, `services`, `core`), `web/src/` |
| Composants | `src/echolens/services/predictor.py` : l'interface `Predictor` et `DemoPredictor` |
| Déploiement | `docker/Dockerfile`, `docker/docker-compose.yml`, `configs/registry.yaml` (révisions figées) |
| MCD | `src/echolens/services/storage.py:AnalysisRecord` (la table), `src/echolens/api/result_schemas.py` (le contenu de `results`) |
| Séquence | Rien encore : `web/src/pages/LivePage.tsx` est une page provisoire |

## 8. Dix questions probables du jury

1. **Pourquoi quatre couches ?** Pour que le calcul (`core`) soit indépendant du web : il est
   testable seul et réutilisé tel quel à l'entraînement, ce qui garantit les mêmes features.
2. **Qu'est-ce qu'un stéréotype UML ?** Le mot entre « » (`«device»`, `«artifact»`) qui précise
   la sorte d'élément, quand le dessin seul ne suffit pas.
3. **Lisez-moi la cardinalité (0,n) entre ANALYSE et RÉSULTAT.** Une analyse peut n'avoir aucun
   résultat (en cours ou en échec) ou en avoir plusieurs (un par tâche demandée).
4. **Votre MCD a sept entités, votre base une table : n'est-ce pas contradictoire ?** Non : le MCD
   décrit les informations, le modèle physique choisit leur rangement. Les résultats sont un
   document écrit et lu en bloc, d'où une colonne JSON.
5. **Pourquoi un WebSocket pour le micro ?** Le son arrive en continu : une connexion ouverte
   évite une requête HTTP toutes les 0,1 s, et le serveur peut renvoyer un résultat quand il veut.
6. **Que se passe-t-il si le calcul d'une fenêtre dure plus de 0,5 s ?** Le RTF dépasse 1, les
   fenêtres s'accumulent et le retard grandit ; il faudrait sauter des fenêtres (point encore
   ouvert).
7. **Pourquoi la transcription n'est-elle pas faite toutes les 0,5 s ?** Whisper a besoin d'une
   phrase entière et serait trop lent ; on attend la fin d'un énoncé (VAD).
8. **Pourquoi Docker ?** Une seule commande lance tout, avec ffmpeg et les bonnes versions, sur
   n'importe quelle machine, sans installer Python ni Node à la main.
9. **Comment êtes-vous sûrs que le modèle de la démo est celui évalué ?** Le registre fige la
   révision Hugging Face de chaque modèle, et l'application vérifie au chargement que ses classes
   sont celles de `configs/labels.yaml` (et, pour le CRNN, que les paramètres du log-Mel n'ont
   pas changé depuis l'entraînement).
10. **Qu'est-ce qui est en pointillés, et pourquoi le montrer ?** Le flux micro et les locuteurs :
    on montre la conception prévue, en distinguant honnêtement ce qui est fait de ce qui reste.
