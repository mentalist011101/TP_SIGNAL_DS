# Plan de la présentation Beamer — soutenance du 9 décembre 2026

Tâche N5, coordonnée par Nicole. Brouillon à valider en équipe.

Trame imposée (`slides/README.md`) : problème → architecture → méthode → application → résultats
→ conclusion, avec une **démonstration obligatoire** et une vidéo de secours (préparée en S5).

> **Hypothèse de durée : 20 min de présentation, suivies des questions.** Le dépôt ne fixe pas la
> durée. Si elle est différente, on garde l'ordre et on ajuste la colonne « Durée ».
> Les résultats chiffrés n'existent pas encore (aucun modèle de la famille A ou B n'est entraîné) :
> les diapositives de résultats indiquent seulement **quelle figure** y mettre.

## Principes

- **Chaque membre présente sa brique** (répartition de `docs/README.md`). Le jury note la maîtrise
  individuelle (25 %) : chacun doit parler environ 5 min, et pouvoir répondre seul.
- **Une idée par diapositive**, un titre qui est une phrase (« Le log-Mel est en dB absolus pour
  qu'un silence reste un silence »), peu de texte, une figure.
- **Toutes les figures viennent du script d'évaluation du dépôt** (E8), jamais d'ailleurs.
- **La démo arrive au milieu**, après l'architecture et avant les résultats : le jury a compris ce
  que fait le système, il le voit marcher, puis on mesure à quel point il marche.

## Vue d'ensemble

| Partie | Diapositives | Qui | Durée | Cumul |
| --- | --- | --- | --- | --- |
| 1. Problème et objectifs | 1 à 3 | Luciano | 2 min | 2 min |
| 2. Signal et représentations | 4 à 5 | Steve | 2 min 30 | 4 min 30 |
| 3. Données et protocole | 6 à 7 | Lynn | 2 min | 6 min 30 |
| 4. Architecture et modèles | 8 à 11 | Luciano | 3 min 30 | 10 min |
| 5. Application et **démo** | 12 à 13 | Nicole | 4 min 30 | 14 min 30 |
| 6. Résultats | 14 à 19 | Steve, Nicole, Lynn | 4 min 30 | 19 min |
| 7. Conclusion | 20 à 21 | Luciano | 1 min | 20 min |
| Annexes (questions) | A1 à A6 | selon la question | — | — |

Temps de parole par personne, si les résultats se répartissent en 45 s pour Steve (diapositive
14), 3 min pour Nicole (15 à 18) et 45 s pour Lynn (19) : Nicole ≈ 7 min 30, Luciano ≈ 6 min 30,
Steve ≈ 3 min 15, Lynn ≈ 2 min 45. **À équilibrer** : par exemple, Lynn présente aussi la
diapositive 15 (émotions, ses données) et Steve la 17 (significativité et efficacité, ses
métriques) ; chacun parle alors 4 à 6 min.

## Déroulé diapositive par diapositive

### Partie 1 — Problème et objectifs (Luciano, 2 min)

| # | Titre (proposition) | Contenu | Source |
| --- | --- | --- | --- |
| 1 | EchoLens : comprendre un audio en un clic | Titre, équipe, cours INF50101, ENSPY, M2 Data Science, date | — |
| 2 | Un audio, quatre questions | Émotion, événement sonore, transcription, locuteur ; l'obligation de comparer CNN/CRNN sur spectrogrammes et encodeurs pré-entraînés | `docs/specification.md` §1 |
| 3 | Plan | Les 7 parties, avec le nom de la personne qui présente chacune | — |

### Partie 2 — Signal et représentations (Steve, 2 min 30)

| # | Titre | Contenu | Source |
| --- | --- | --- | --- |
| 4 | Du fichier au signal propre | Chaîne : décodage ffmpeg → mono 16 kHz → normalisation RMS → VAD (webrtcvad) ; limite : rien au-dessus de 8 kHz | D1 à D5 ; figure du script débruitage et segmentation (C2) |
| 5 | Le spectrogramme log-Mel, entrée de la famille A | STFT 25 ms / 10 ms, 64 bandes Mel HTK, dB absolus (un silence vaut −100 dB) ; MFCC pour la référence ; **un seul module** pour l'entraînement et l'application | R1 à R5 ; `report/figures/analyser_spectrogramme.png` |

### Partie 3 — Données et protocole (Lynn, 2 min)

| # | Titre | Contenu | Source |
| --- | --- | --- | --- |
| 6 | Six jeux, quatre tâches | Tableau : CREMA-D, RAVDESS, CaFE, ESC-50, OpenSLR 57, nos enregistrements ; 6 émotions communes | §7 de la spécification, P2 |
| 7 | Un protocole sans fuite | Aucun acteur dans deux découpages (P1) ; folds ESC-50 jamais remélangés (P3) ; normalisation calculée sur le train seul (R4) ; 3 niveaux de test (P7) | P1, P3, P7, R4 |

### Partie 4 — Architecture et modèles (Luciano, 3 min 30)

| # | Titre | Contenu | Source |
| --- | --- | --- | --- |
| 8 | Quatre couches, une seule direction | Diagramme de composants : web → api → services → core ; `core` s'installe seul sur Kaggle | `docs/uml/composants.md` |
| 9 | Famille A : CNN et CRNN sur log-Mel | Schéma des 4 blocs ; le CRNN ajoute un BiGRU et un pooling par attention | §8 de la spécification |
| 10 | Famille B : encodeurs pré-entraînés | wav2vec 2.0, mHuBERT-147, encodeur Whisper ; somme pondérée apprise des couches, moyenne temporelle, MLP | §8, R7 |
| 11 | Transcription et locuteur | Whisper base contre small (faster-whisper int8) ; ECAPA-TDNN, similarité cosinus et seuil « inconnu » | §8 |

### Partie 5 — Application et démo (Nicole, 4 min 30)

| # | Titre | Contenu | Source |
| --- | --- | --- | --- |
| 12 | Une application web, du fichier au résultat | Parcours utilisateur en une image : Analyser → Résultat → Historique ; capture de la page Analyser ; « l'interface ne calcule rien, le serveur fait tout » (R5) | `docs/maquettes/analyser-et-resultat.md` |
| 13 | **Démonstration** | Diapositive vide avec le mot « Démo » : on bascule sur le navigateur. Scénario ci-dessous | — |

### Partie 6 — Résultats (4 min 30)

| # | Titre | Qui | Contenu | Source |
| --- | --- | --- | --- | --- |
| 14 | Comment on mesure | Steve | F1 macro (métrique principale), accuracy, WER, EER ; pourquoi le F1 macro plutôt que l'accuracy (classes déséquilibrées) | P4, E1 |
| 15 | Émotions : famille A contre famille B | Nicole | Tableau F1 macro en domaine et hors domaine (CaFE), avec intervalles de confiance ; verdict sur H1 et H2 | **À produire** (E8) |
| 16 | Événements sonores (ESC-50) | Nicole | Référence MFCC + SVM, puis familles A et B ; matrice de confusion en 5 catégories ; verdict sur H3 et H4 | `report/figures/esc50_svm_confusion_categories.png` pour la référence ; le reste **à produire** |
| 17 | Est-ce que l'écart est réel ? | Nicole | Test de McNemar entre familles ; efficacité : taille, latence p50 et p95, RTF (le temps réel tient-il ?) | E5, E6 ; **à produire** |
| 18 | Que regarde le modèle ? | Nicole | Une carte Grad-CAM sur un extrait « colère » ; résultat du test de masquage ; diagramme de fiabilité (calibration) | E2, E7 ; `docs/fiches/grad-cam.md` |
| 19 | Où le modèle se trompe | Lynn | Robustesse au bruit (F1 selon le SNR) ; biais par genre ; exemples d'erreurs écoutés | E3, E4 ; **à produire** |

### Partie 7 — Conclusion (Luciano, 1 min)

| # | Titre | Contenu |
| --- | --- | --- |
| 20 | Ce qu'il faut retenir | 3 phrases : la réponse à H1, la réponse à H3, et ce que l'application apporte ; puis les limites (pas de diarisation, rien au-dessus de 8 kHz, peu de données en français) et les perspectives |
| 21 | Merci — vos questions | Lien du dépôt ; remerciements |

### Annexes — réservées aux questions du jury

Diapositives placées après « Merci », montrées seulement si une question les appelle.

| # | Contenu | Pour répondre à… |
| --- | --- | --- |
| A1 | Équations : STFT, échelle Mel HTK, DCT des MFCC | « Comment calcule-t-on un MFCC ? » (Steve) |
| A2 | Équations de Grad-CAM | « Comment est faite la carte ? » (Nicole) |
| A3 | Détail des découpages par acteur et par genre | « Comment évitez-vous les fuites ? » (Lynn) |
| A4 | Diagramme de séquence du flux micro (fenêtre 2 s, décalage 0,5 s) | « Comment marche le direct ? » (Nicole, Luciano) |
| A5 | Diagramme de déploiement (Docker, Gunicorn, Kaggle, Hugging Face Hub) | « Comment l'installe-t-on ? » (Luciano) |
| A6 | MCD de l'historique | « Que garde la base de données ? » (Nicole) |

## La démo (diapositive 13, 3 min dans les 4 min 30 de la partie 5)

### Scénario

| Temps | Action à l'écran | Ce que Nicole dit |
| --- | --- | --- |
| 0:00 | Page Analyser ; importer un enregistrement de l'équipe joué en colère | « Un membre de l'équipe a enregistré cette phrase en colère : le modèle ne l'a jamais entendue. » |
| 0:20 | Forme d'onde et spectrogramme affichés ; cocher Émotion, Événement, Transcription, Locuteur ; Analyser | « Le spectrogramme est calculé par le serveur, avec le même code qu'à l'entraînement. » |
| 0:40 | Page Résultat : probabilités, transcription, locuteur reconnu | Lire à voix haute la probabilité affichée pour la colère, le nom du locuteur reconnu et le texte transcrit |
| 1:20 | Activer la carte Grad-CAM | « Voici les zones du spectrogramme qui ont fait dire “colère” au modèle. » |
| 1:45 | Page Direct : parler au micro quelques secondes | « En direct, un résultat toutes les 0,5 s ; la latence et le RTF sont affichés : le temps réel tient. » |
| 2:30 | Historique, puis export PDF | « Tout est gardé et exportable. » |
| 3:00 | Retour aux diapositives | — |

**Les fonctionnalités de la démo n'existent pas toutes encore** (page Résultat, modèles, Grad-CAM,
Direct). On ne montre le 9 décembre que ce qui marche, et on raccourcit le scénario en
conséquence. **Décision à prendre en équipe le 2 décembre**, à la remise.

### Préparation, la veille

- [ ] Image Docker construite **à l'avance** sur le PC de la démo (`make docker`), poids des
      modèles déjà téléchargés : la démo ne dépend **pas d'internet**.
- [ ] ffmpeg présent (il est dans l'image Docker ; à vérifier si l'on lance hors Docker).
- [ ] 2 ou 3 audios de démo choisis dans les enregistrements de l'équipe, **avec la case « démo »
      cochée sur le formulaire de consentement**, copiés sur le Bureau.
- [ ] Historique préchargé avec 3 ou 4 analyses déjà terminées.
- [ ] Micro testé dans la salle ; la page tourne sur `localhost`, sinon le navigateur bloque le
      micro (il faut https).
- [ ] Modèles préchauffés (une analyse lancée juste avant de passer), pour éviter une première
      réponse lente.
- [ ] Navigateur en plein écran, zoom à 125 %, notifications coupées, onglets inutiles fermés.

### Plan de secours

| Problème | Réaction | Temps perdu |
| --- | --- | --- |
| L'application ne démarre pas | Lancer la **vidéo de démonstration** (S5), déjà ouverte dans un onglet | 10 s |
| Le micro ne marche pas | Sauter l'étape Direct, la montrer dans la vidéo | 0 |
| Analyse trop lente | Ouvrir une analyse déjà terminée dans l'Historique | 10 s |
| Le vidéoprojecteur coupe le navigateur | Captures d'écran de secours dans une diapositive cachée | 20 s |

## Calendrier proposé

| Date | Étape |
| --- | --- |
| 22 nov. | Plan validé en équipe ; squelette Beamer dans `slides/` |
| 29 nov. | Diapositives des parties 1 à 5 rédigées ; démo jouée une première fois |
| 2 déc. | Remise ; résultats figés ; diapositives 14 à 19 remplies avec les figures du script (E8) ; vidéo de secours enregistrée |
| 5 déc. | Répétition complète chronométrée, avec questions croisées |
| 8 déc. | Répétition finale sur le PC de la démo ; préparation de la veille |
| 9 déc. | Soutenance |

## Points à trancher en équipe

1. La durée réelle de la présentation et des questions (demander à l'enseignant).
2. L'équilibre du temps de parole : qui présente les diapositives 15 et 17 ?
3. Le thème Beamer, aligné sur la charte graphique (`docs/design.md`) ?
4. La démo en direct ou la vidéo en premier choix, selon ce qui sera prêt le 2 décembre.
