# Fiche — Grad-CAM, la carte d'explicabilité

Brique 5 (évaluation et explicabilité) et brique 7 (interface).
Décisions et exigences : **E7**, **EF-13**, en lien avec **EF-04**, **R2**, **R7**, **U6**.
Article de référence : R. R. Selvaraju et al., *Grad-CAM: Visual Explanations from Deep Networks
via Gradient-based Localization*, ICCV 2017.

> **État au 27 novembre 2026 (C14) : la carte est calculée et affichée.** Les choix « à
> trancher » ont été tranchés par Luciano le 27 novembre (section 4). Le test de fidélité par
> masquage a son code ; ses résultats viendront de son notebook Kaggle (section 6).

## 1. L'idée en trois phrases

1. Quand le CNN prédit « colère » pour un extrait, Grad-CAM produit une carte qui montre **quelles
   zones du spectrogramme** (quel moment, quelles fréquences) ont le plus poussé le modèle vers
   cette classe.
2. Pour cela, on regarde la dernière couche de convolution et on mesure, grâce aux gradients, à
   quel point chacun de ses filtres compte pour la classe prédite. On additionne ensuite les
   cartes de ces filtres, pondérées par leur importance.
3. L'application superpose cette carte au spectrogramme Mel (EF-13). On vérifie qu'elle dit vrai
   avec un test de masquage : si l'on efface les zones « chaudes », la confiance du modèle doit
   chuter (E7).

## 2. Le schéma

```
 audio 16 kHz mono
        │
        ▼
 log_mel_spectrogram (core/features.py)        ← même module que l'affichage (EF-04, R5)
        │   forme (64 bandes Mel, T trames de 10 ms)
        ▼
 ┌──────────────────────────── CNN famille A ───────────────────────────┐
 │ bloc 1 → bloc 2 → bloc 3 → bloc 4  (Conv → BatchNorm → ReLU → MaxPool)│
 │                               │                                      │
 │                     cartes A¹ … Aᴷ  (K filtres, petite grille h × w)   │
 │                               │                                      │
 │                     pooling → couches finales → score yᶜ par classe  │
 └───────────────────────────────┬──────────────────────────────────────┘
                                 │
        ┌────────────────────────┘
        ▼
 1. rétropropagation de yᶜ jusqu'aux cartes Aᵏ  →  gradients ∂yᶜ/∂Aᵏ
 2. moyenne des gradients sur la grille          →  un poids αᵏ par filtre
 3. ReLU( Σₖ αᵏ · Aᵏ )                            →  carte h × w
 4. agrandissement à 64 × T, normalisation 0–1   →  carte de la taille du spectrogramme
        │
        ▼
 interface : spectrogramme + carte en surimpression, activable (EF-13)
```

## 3. Les équations

Équations de l'article (section 3), écrites avec les notations de notre cas.

**Poids d'un filtre :**

$$\alpha_k^c = \frac{1}{Z} \sum_{i} \sum_{j} \frac{\partial y^c}{\partial A^k_{ij}}$$

**Carte Grad-CAM :**

$$L^c_{\text{Grad-CAM}} = \mathrm{ReLU}\left(\sum_k \alpha_k^c \, A^k\right)$$

| Symbole | Signification |
| --- | --- |
| $c$ | La classe expliquée, en général la classe prédite (ex. « angry ») |
| $y^c$ | Le score de la classe $c$ **avant** le softmax (logit) |
| $A^k$ | La carte d'activation du filtre $k$ de la dernière couche de convolution |
| $A^k_{ij}$ | Sa valeur en ligne $i$ (axe des fréquences) et colonne $j$ (axe du temps) |
| $\partial y^c / \partial A^k_{ij}$ | Le gradient : de combien le score bouge si cette case augmente un peu |
| $Z$ | Le nombre de cases de la carte ($h \times w$) : la double somme divisée par $Z$ est une moyenne |
| $\alpha_k^c$ | L'importance du filtre $k$ pour la classe $c$ |
| $\mathrm{ReLU}$ | Garde seulement les valeurs positives, c'est-à-dire les zones qui **soutiennent** la classe $c$ |

Ce qu'il faut savoir dire :

- **Pourquoi le logit et pas la probabilité ?** Le softmax couple toutes les classes : le gradient
  d'une probabilité dépend aussi des autres classes. Le logit isole la classe $c$.
- **Pourquoi la ReLU ?** Les valeurs négatives correspondent à des zones qui poussent vers
  d'autres classes. On ne les affiche pas, sinon la carte mélangerait « pour » et « contre ».
- **Pourquoi la dernière couche de convolution ?** C'est la dernière à garder une organisation
  fréquence × temps, avec les motifs les plus abstraits. Après, le pooling efface la position.

## 4. Les choix et leur justification

| Choix | Statut | Justification | Alternative écartée |
| --- | --- | --- | --- |
| Grad-CAM pour la famille A seulement | Décidé (E7) | La famille A prend en entrée le log-Mel : la carte se superpose directement au spectrogramme | Grad-CAM sur la famille B : impossible tel quel, car elle reçoit le signal brut sans Mel (R7). On affiche à la place les **poids des couches** appris (E7) |
| Carte superposée au spectrogramme Mel, activable | Décidé (EF-13) | La carte n'a de sens que posée sur l'entrée exacte du modèle. On peut la masquer pour voir le spectrogramme seul | Afficher la carte seule, sans repère visuel |
| Spectrogramme affiché = entrée du modèle | Décidé (EF-04, R5, U6) | Calculé par `log_mel_spectrogram`, côté serveur, avec `configs/features.yaml` : on explique bien ce que le modèle a vu | Spectrogramme calculé dans le navigateur, interdit par R5 (le faux spectrogramme du front a été retiré dans la PR #7) |
| Log-Mel en dB absolus | Décidé (R2) | Un silence vaut toujours −100 dB : la carte ne peut pas « s'allumer » sur un silence rendu artificiellement fort | dB relatifs au maximum de l'extrait |
| Test de fidélité par masquage | Décidé (E7) | Une carte jolie n'est pas forcément vraie : on vérifie qu'effacer les zones chaudes fait vraiment baisser le score | Se contenter d'une inspection visuelle |
| Couche ciblée : sortie du bloc 4 | Décidé (C14) | Dernière couche de convolution, recommandée par l'article | Bloc 3 : carte plus fine, mais motifs moins abstraits |
| Classe expliquée : la classe prédite de chaque fenêtre | Décidé (C14) | C'est la question naturelle de l'utilisateur (« pourquoi colère ? ») | Choix de la classe dans l'interface |
| Valeur de remplissage du masquage | Décidé (C14) : **moyenne du train** (0 après la standardisation R4) | Une zone « neutre » pour le modèle, qui ne crée pas d'entrée extrême ; choix courant des tests de suppression | −100 dB (plancher R2) : le modèle pourrait réagir au silence lui-même plutôt qu'à la perte d'information |
| Grad-CAM sur le CRNN | Décidé (C14) : ce sont les modèles en production (profil Temps réel) | Possible : on prend la sortie du bloc 4, avant le BiGRU, et le gradient traverse le BiGRU | Grad-CAM sur le CNN uniquement |

**Résolution de la carte (vérifiée sur le CRNN de production).** Chaque bloc finit par un MaxPool
2 × 2 (`core/models/family_a.py`) : la carte du bloc 4 mesure 64 / 16 = **4 lignes** en fréquence et une colonne pour
16 × 10 ms = **160 ms**. La carte est donc très grossière en fréquence : elle dit « plutôt dans les
graves » ou « plutôt dans les aigus », mais pas « à 440 Hz ». Il faut le dire au jury avant qu'il
le demande.

## 5. Où se trouve le code

| Élément | Emplacement | État |
| --- | --- | --- |
| Spectrogramme log-Mel (entrée du CNN et image affichée) | `src/echolens/core/features.py:log_mel_spectrogram` | Fait. Forme `(n_mels, n_frames)` = `(64, T)`. À savoir lire : étape 1 (STFT + filtres Mel HTK), étape 2 (dB absolus, plancher −100 dB) |
| Paramètres | `configs/features.yaml` | Fait. 25 ms de fenêtre, 10 ms de pas, 64 bandes de 0 à 8 kHz |
| Image du spectrogramme dans l'interface | `web/src/components/analyze/SpectrogramView.tsx` | Fait |
| CNN et CRNN de la famille A | `configs/registry.yaml` (CRNN des émotions et des événements, profil Temps réel) | Fait (C9, C12) |
| Calcul de la carte d'une fenêtre | `src/echolens/core/models/grad_cam.py` (`grad_cam`) | Fait (C14) |
| Carte de tout l'audio (fenêtres réunies sur l'axe du temps) | `src/echolens/core/explain.py` (`combine_window_maps`, calcul pur) | Fait (C14) |
| Même entrée que la prédiction | `src/echolens/services/model_predictor.py` (`explain`) | Fait (C14) |
| Exposition par l'API | `GET /api/v1/analyses/{id}/gradcam?task=sound_event\|emotion` : PNG transparent de la taille du spectrogramme, 409 avec un message si pas de carte | Fait (C14) |
| Superposition activable | Page Résultat, sous le spectrogramme : « Carte Grad-CAM : Aucune / Événement / Émotion » | Fait (C14, EF-13) |
| Test de fidélité par masquage | Code testé et notebook Kaggle (C14b) | Résultats à produire |

Ce qu'il faut savoir lire dans `grad_cam` (les étapes sont numérotées dans le code) :

1. l'endroit où l'on récupère les activations $A^k$ et leurs gradients ;
2. la moyenne des gradients, qui donne $\alpha_k^c$ ;
3. la somme pondérée suivie de la ReLU ;
4. l'agrandissement de la carte à la taille `(64, T)` du spectrogramme.

## 6. Résultats

**Pas encore de résultat chiffré** : la mesure de fidélité attend son notebook Kaggle (C14b).

Première observation, à confirmer sur plus d'extraits (essai du 27 nov., extrait « pluie et
parole » de 15,5 s, profil Temps réel) : la carte du CRNN des **événements** s'allume aussi sur un
passage de silence numérique, alors que celle du CRNN des **émotions** reste sur les morceaux de
parole. C'est le genre de raccourci que la section 7 annonçait, à vérifier avec le test de
fidélité avant d'en tirer une conclusion.

À produire (brique 5, script unique des figures, E8) :

- des cartes sur quelques extraits par classe : émotions (CREMA-D, CaFE) et événements (ESC-50) ;
- la **courbe de suppression** : score de la classe prédite en fonction du pourcentage de zones
  masquées, en masquant les zones les plus chaudes d'abord, puis en masquant au hasard. La carte
  est fidèle si la première courbe descend nettement plus vite que la seconde ;
- une lecture critique des cartes. Le modèle regarde-t-il la voix, ou le silence et le bruit de
  fond ? Une carte allumée sur le début ou la fin d'un extrait CREMA-D signalerait un raccourci
  appris (biais du jeu) plutôt qu'un indice d'émotion.

## 7. Dix questions probables du jury

1. **Que montre exactement la carte ?**
   Les zones du spectrogramme (temps × fréquence) dont l'augmentation ferait monter le score de la
   classe prédite. C'est une **corrélation locale** avec la décision, pas une causalité ; c'est
   pour ça qu'on fait le test de masquage.

2. **Pourquoi la dernière couche de convolution ?**
   Elle garde encore la position (fréquence, temps) et contient les motifs les plus abstraits.
   Après le pooling global, la position est perdue.

3. **Pourquoi utiliser le score avant le softmax ?**
   Le softmax mélange toutes les classes. Le gradient du logit $y^c$ ne dépend que de la classe
   expliquée.

4. **À quoi sert la ReLU ?**
   À ne garder que les zones qui soutiennent la classe. Les valeurs négatives poussent vers
   d'autres classes.

5. **Quelle est la précision de la carte ?**
   Celle de la dernière couche de convolution. Avec les MaxPool 2 × 2 du CRNN, on
   obtient 4 bandes en fréquence et 160 ms en temps : c'est grossier. L'agrandissement
   lisse l'image mais n'ajoute pas d'information.

6. **Pourquoi pas de Grad-CAM pour wav2vec 2.0, HuBERT ou Whisper ?**
   Ces modèles reçoivent le signal brut, pas notre spectrogramme (R7) : il n'y a pas d'image à
   superposer. Pour eux, on montre les **poids appris des couches** (E7), c'est-à-dire quelles
   couches de l'encodeur servent à la tâche.

7. **Comment savez-vous que la carte ne ment pas ?**
   Avec le test de fidélité (E7) : on masque les zones les plus chaudes et on mesure la baisse du
   score, comparée à un masquage au hasard. Si les deux baisses se valent, la carte n'explique rien.

8. **Par quoi remplacez-vous une zone masquée ?**
   Par la moyenne du train (0 après la standardisation R4), décision de C14. Le choix compte : une
   valeur extrême, comme le silence à −100 dB de R2, ferait réagir le modèle au silence lui-même
   plutôt qu'à la perte d'information.

9. **Le spectrogramme affiché est-il bien celui que voit le modèle ?**
   Oui, par construction : tous deux viennent de `log_mel_spectrogram` avec `configs/features.yaml`
   (R5, EF-04), calculés côté serveur (U6). Sinon, la carte serait posée sur une autre image.

10. **Qu'avez-vous appris grâce aux cartes ?**
    **Pas encore de résultat.** On cherchera surtout des raccourcis : un modèle qui regarde le
    silence ou le bruit de fond plutôt que la voix, ou toujours les mêmes fréquences quelle que
    soit l'émotion.
