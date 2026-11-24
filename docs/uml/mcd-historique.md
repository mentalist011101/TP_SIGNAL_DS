# MCD MERISE — historique des analyses

Décisions : S3 (SQLite via SQLAlchemy, fichiers sur disque), EF-08 (historique), EF-05, EF-06,
EF-10, EF-11, EF-12 (résultats par segment), C13 (contrat des résultats).

Source : la table `analyses` de `src/echolens/services/storage.py` (classe `AnalysisRecord`) et le
contrat des résultats de `src/echolens/api/result_schemas.py`. **Une seule table existe** :
tout ce qui concerne les résultats est rangé dans sa colonne JSON `results` (voir « Du MCD au
code »). Seul le LOCUTEUR est encore une proposition.

## Diagramme

Légende : rectangle = entité (identifiant précédé de `#`), ellipse = association,
`(min,max)` = cardinalité, lue du côté de l'entité. En **pointillés** : ce qui n'existe pas encore.

![MCD MERISE de l'historique des analyses](images/mcd-historique.png)

Source modifiable : [`mcd-historique.drawio`](mcd-historique.drawio), à ouvrir dans draw.io (application ou app.diagrams.net). Après une modification, réexporter l'image : Fichier > Exporter en > PNG, zoom 200 %, dans `images/mcd-historique.png`.

## Les entités

| Entité | Ce qu'elle représente | Exemple |
| --- | --- | --- |
| ANALYSE | Un audio importé et son traitement | `entretien.wav`, terminée, 41,2 s, profil Qualité |
| TÂCHE | Ce qu'on peut demander : émotion, événement sonore, transcription, locuteur | `emotion` / « Émotion » |
| RÉSULTAT | La réponse pour **une** tâche demandée d'**une** analyse | émotion : `done`, « Colère » |
| MODÈLE | Le modèle du registre qui a produit le résultat | `echolens-emotion-whisper-base` 1.0.0, calibré |
| SEGMENT | Un morceau de l'audio et sa classe la plus probable, pour la frise (EF-12) | de 5,0 à 10,0 s : « Pluie » |
| PROBABILITÉ | Une classe et sa probabilité | `angry`, « Colère », 0,58 |
| LOCUTEUR *(proposé)* | Une personne enregistrée avec son consentement (EF-11, ENF-10) | p04 |

## Les associations et leurs cardinalités

On lit chaque cardinalité du côté de l'entité : « une ANALYSE DEMANDE (1,n) TÂCHE » veut dire
« une analyse demande au moins une, et au plus plusieurs tâches ».

| Association | Côté gauche | Côté droit | Ce que ça dit |
| --- | --- | --- | --- |
| DEMANDER | ANALYSE `(1,n)` | TÂCHE `(0,n)` | Une analyse demande au moins une tâche (l'API refuse une liste vide) ; une tâche peut n'être demandée par aucune analyse |
| OBTENIR | ANALYSE `(0,n)` | RÉSULTAT `(1,1)` | Aucun résultat tant que l'analyse n'est pas terminée, puis un par tâche demandée ; un résultat appartient à une seule analyse |
| PORTER SUR | RÉSULTAT `(1,1)` | TÂCHE `(0,n)` | Un résultat porte sur une seule tâche |
| PRODUIRE | MODÈLE `(0,n)` | RÉSULTAT `(0,1)` | Un résultat vient d'au plus un modèle : aucun si la tâche n'est pas branchée (`unavailable`) |
| DÉCOUPER | RÉSULTAT `(0,n)` | SEGMENT `(1,1)` | Aucun segment si `no_speech` ou `unavailable` ; sinon les fenêtres de 5 s (événements) ou les morceaux de parole (émotions) |
| RÉSUMER | RÉSULTAT `(0,n)` | PROBABILITÉ `(0,1)` | Le résultat global : toutes les classes (6 émotions ou 50 événements), somme 1 |
| DÉTAILLER | SEGMENT `(1,n)` | PROBABILITÉ `(0,1)` | Les probabilités de chaque segment |
| IDENTIFIER *(proposée)* | SEGMENT `(0,1)` | LOCUTEUR `(0,n)` | Un segment est attribué à au plus un locuteur ; aucun si la similarité est sous le seuil (« inconnu ») |

**Contrainte d'exclusion** : une PROBABILITÉ appartient soit à un RÉSULTAT (le global), soit à un
SEGMENT, jamais aux deux. C'est pourquoi chacune de ses deux pattes vaut `(0,1)` et non `(1,1)`.

**Contrainte de cohérence** : un RÉSULTAT ne peut PORTER SUR qu'une tâche que son ANALYSE a
DEMANDÉE.

## Du MCD au code : une seule table

Le MCD décrit les **informations** ; le code choisit comment les **ranger**.

| Partie du MCD | Rangement dans le code |
| --- | --- |
| ANALYSE | Une ligne de la table `analyses` (colonnes ci-dessous) |
| DEMANDER (liste des tâches) | Colonne JSON `tasks`, par exemple `["emotion", "sound_event"]` |
| RÉSULTAT, MODÈLE, SEGMENT, PROBABILITÉ, et leurs associations | Colonne JSON `results` : un objet par tâche demandée, qui contient son statut, son modèle, ses probabilités globales et ses segments (contrat de `result_schemas.py`) |
| résumé (premier choix de chaque tâche) | Table `analysis_summaries`, 1-1 avec `analyses` : copie calculée pour l'historique (EF-08) |
| TÂCHE | Pas de table : les 4 tâches sont fixes, dans le code (`Task`) |
| MODÈLE | Pas de table : le registre `configs/registry.yaml` reste la seule source (S1) ; le résultat ne garde que `model_id`, `model_version` et `calibrated` |
| Fichiers audio et image | Sur disque, dans `var/analyses/<id_analyse>/` (`original.<ext>`, `audio.wav`, `spectrogram.png`) : la base ne garde que l'identifiant (S3) |

| Attribut du MCD | Colonne de `analyses` | Type | Remarque |
| --- | --- | --- | --- |
| `# id_analyse` | `id` | `String(36)`, clé primaire | UUID généré par le service |
| `date_creation` | `created_at` | `DateTime(timezone=True)` | En UTC |
| `nom_fichier_original` | `original_filename` | `String(255)` | Nom nettoyé |
| `statut` | `status` | `String(16)` | `pending` → `processing` → `done` ou `failed` |
| `message_erreur` | `error_message` | `String`, peut être vide | Rempli seulement si `failed` |
| `duree_s` | `duration_s` | `float`, peut être vide | Connue à la fin |
| `profil` | `profile` | `String(16)` | `quality` ou `realtime` |
| *(DEMANDER)* | `tasks` | `JSON` | Liste des tâches |
| *(OBTENIR et tout ce qui suit)* | `results` | `JSON`, vide tant que `status ≠ done` | Contrat C13 |

**Pourquoi du JSON plutôt que quatre tables ?** Les résultats d'une analyse sont écrits **en une
fois**, à la fin du traitement, et relus **en une fois**, par la page Résultat. On ne cherche
jamais « tous les segments où la colère dépasse 50 % ». Une colonne JSON évite donc des jointures
inutiles, et le JSON stocké est exactement celui que renvoie l'API. Si un jour il faut chercher
dans les résultats, le MCD dit déjà quelles tables créer : RÉSULTAT, SEGMENT et PROBABILITÉ.

La table `analysis_summaries` est une copie voulue (dénormalisation) : elle recopie de `results`
le premier choix de chaque tâche, pour que l'historique n'ait pas à lire `results`, et elle est
écrite dans la même transaction que `results`.

## Points encore ouverts

1. **LOCUTEUR** (EF-11) : l'empreinte vocale dans la base ou sur disque ? Le retrait du
   consentement doit effacer la personne et toutes ses identifications.
2. Supprimer une analyse supprime déjà ses résultats (même ligne) et son dossier de fichiers
   (`delete_analysis`).
