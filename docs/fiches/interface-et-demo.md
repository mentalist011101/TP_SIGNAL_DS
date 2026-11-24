# Fiche — L'interface web et la démo

Brique 7 (interface, démo, comparaison des résultats). Défendue par : Nicole.
Tâches : C7 (première page Analyser), C20 (Analyser), C21 (Résultat), C22 (Historique), N5
(scénario de la démo).
Exigences et décisions : **EF-01 à EF-09**, **ENF-06**, **ENF-12**, **R5**, **U1 à U7**,
charte `docs/design.md` (v2).

> **État au 24 novembre 2026.** Dans `main` : les pages **Analyser**, **Résultat** et
> **Historique** (PR #28, qui reprend les branches C20, C21 et C22). Ont été relues et fusionnées,
> mais **pas encore dans `main`** (fusionnées dans la branche de la PR #28 après elle) : la page
> d'accueil, la frise temporelle (EF-12), « Hésite entre X et Y » (#29 à #31), la page Modèles
> (#32) et l'exemple réel de l'accueil (#33). Pas encore codés : Direct (micro en temps réel),
> Comparer, Locuteurs, Grad-CAM (EF-13), exports CSV et PDF.

## 1. L'idée en trois phrases

1. L'interface est une application **React** qui ne fait qu'**afficher** : elle envoie l'audio à
   l'API Flask, puis montre ce que le serveur a calculé. Aucun calcul sur le signal n'est fait
   dans le navigateur (R5).
2. Le parcours tient en trois pages : **Analyser** (on dépose un audio, on choisit les tâches),
   **Résultat** (les probabilités, l'écoute, le spectrogramme), **Historique** (les analyses
   passées, à rouvrir ou supprimer).
3. L'interface est **honnête** : elle dit quand un chiffre vient d'un faux modèle de démonstration,
   affiche « Aucune parole détectée » au lieu d'inventer une émotion, et écrit chaque pourcentage
   en texte.

## 2. Le schéma

### Le parcours

```
            ┌───────────────────── Analyser (/analyser) ─────────────────────┐
            │  audio (dépôt, import ou micro)       réglages : tâches, profil │
 l'usager → │  lecteur + forme d'onde (canvas)      [ Analyser ]              │
            │                                       suivi : Envoi → Attente → │
            │                                               Analyse → Résultat│
            └───────────────────────────────┬────────────────────────────────┘
                                            │ statut « done » : ouverture automatique
                                            ▼
            ┌─────────────── Résultat (/analyses/{id}) ──────────────────────┐
            │  en-tête (fichier, statut, durée, profil, JSON à télécharger)  │
            │  bandeau « démonstration » si faux prédicteur                  │
            │  chiffres clés → écoute + spectrogramme → une carte par tâche  │
            └───────────────────────────────┬────────────────────────────────┘
                                            │ menu
                                            ▼
            ┌─────────────── Historique (/historique) ───────────────────────┐
            │  chiffres clés (analyses, durée, réussite, 7 jours)            │
            │  recherche, filtres statut + période → liste → rouvrir/suppr.  │
            └────────────────────────────────────────────────────────────────┘
```

### Ce qui se passe entre la page et le serveur

```
 Page Analyser                                  API Flask (/api/v1)
 ─────────────                                  ───────────────────
 useCreateAnalysis ── POST /analyses (fichier, tâches, profil) ──► 202 + id, statut pending
 useAnalysis(id)   ── GET /analyses/{id}   toutes les 1 s ───────► pending → processing → done
                      (TanStack Query : refetchInterval s'arrête à done ou failed)
 Page Résultat     ── lit analysis.results (contrat C13) : un objet par tâche demandée
                   ── <img> GET /analyses/{id}/spectrogram · <audio> GET /analyses/{id}/audio
 Page Historique   ── GET /analyses?limit=100 · DELETE /analyses/{id}
```

## 3. Les nombres et formules à savoir

**Rafraîchissement du statut** : la page interroge le serveur toutes les
`POLL_INTERVAL_MS = 1000` ms tant que le statut vaut `pending` ou `processing`, puis s'arrête.

**Les probabilités affichées ne sont pas recalculées par le front.** Le serveur les calcule ainsi
(C13, D5), et la page les dessine telles quelles :

- événements sonores, fenêtres de 5 s : $p_{\text{global}}(c) = \frac{1}{N} \sum_{i=1}^{N} p_i(c)$
  (moyenne simple des N fenêtres) ;
- émotions, morceaux de parole de durée $d_i$ :
  $p_{\text{global}}(c) = \frac{\sum_i d_i \, p_i(c)}{\sum_i d_i}$ (un long passage pèse plus qu'un
  « oui » bref) ;
- calibration (ENF-06) : $p = \text{softmax}(z / T)$, où $z$ sont les scores du modèle et $T$ la
  température apprise ; d'où la mention « probabilités calibrées ».

Dans chaque cas, la somme sur toutes les classes vaut 1 (100 %).

**Affichage d'une probabilité** : format français, une décimale au plus (« 62 % », « 0,5 % ») ;
sous 0,1 %, on écrit « < 0,1 % » pour ne pas faire croire qu'une classe est impossible.

**Contraste (WCAG AA)** : au moins **4,5 : 1** entre un texte et son fond, dans les deux thèmes.

## 4. Les choix faits, et l'alternative écartée

| Choix | Pourquoi | Écarté |
| --- | --- | --- |
| **React + TypeScript strict** (U1) | Composants réutilisables ; TypeScript refuse au moment de compiler un champ mal nommé du contrat de l'API | JavaScript sans types |
| **TanStack Query** pour les appels | Il gère pour nous le chargement, les erreurs, le cache et le rafraîchissement toutes les secondes | Des `fetch` et des `setInterval` écrits à la main |
| **Interrogation toutes les 1 s** plutôt qu'un WebSocket | Une analyse de fichier dure quelques secondes : une requête par seconde suffit, et c'est plus simple | WebSocket (gardé pour le micro en direct, D8) |
| **Traitement en arrière-plan, réponse 202** | La requête rend la main tout de suite ; la page montre les étapes | Attendre la fin dans la requête (page figée, délai dépassé) |
| **Barres en CSS** (U5, révisée le 21 nov.) | 6 ou 50 barres horizontales : du HTML suffit, sans 380 kB de bibliothèque | Recharts (essayé dans C21, retiré) |
| **Forme d'onde en canvas** (U6) | Un trait vertical min–max par colonne de pixels : on voit tout le signal, même long | wavesurfer.js |
| **Spectrogramme calculé par le serveur** (R5) | Le même code que l'entraînement (`core.features`) ; le front n'affiche qu'une image | Calcul dans le navigateur (risque d'un spectrogramme différent de celui du modèle) |
| **Jetons de couleur nommés par rôle** | On change toute la charte sans toucher aux pages ; un script vérifie qu'aucune couleur n'est écrite en dur | Couleurs Tailwind directement dans les composants |
| **Thème du système, puis choix mémorisé** | Respecte le réglage de l'ordinateur, mais laisse choisir | Thème clair imposé |
| **Suppression en deux temps** | Elle efface la ligne en base et les fichiers : pas de retour possible | Suppression en un clic |

## 5. Où se trouve le code

| Fichier | Ce qu'il faut savoir y lire |
| --- | --- |
| `web/src/App.tsx` | La table des routes : `/analyser`, `/analyses/:analysisId`, `/historique` ; `/` mène à `/analyser` |
| `web/src/api/client.ts` | Les types du contrat (`Analysis`, `TaskResult`) et les hooks : `useCreateAnalysis` (POST), `useAnalysis` (GET toutes les secondes, via `nextPollDelay`), `useAnalysisHistory`, `useDeleteAnalysis` |
| `web/src/pages/AnalyzePage.tsx` | `useAnalysisRun` (envoi puis suivi), `analyzeHint` (pourquoi le bouton est grisé), `<Navigate>` vers le résultat quand c'est fini |
| `web/src/components/analyze/AnalysisProgress.tsx` | Les quatre étapes (Envoi, Attente, Analyse, Résultat), choisies d'après le statut de l'API (`currentStepIndex`) |
| `web/src/components/analyze/WaveformCanvas.tsx` | `decodeFirstChannel`, puis `drawWaveform` : un trait du min au max par colonne de pixels |
| `web/src/components/analyze/AudioPicker.tsx` | Le micro : `getUserMedia`, `MediaRecorder`, nom de fichier selon le format, arrêt des pistes |
| `web/src/pages/ResultPage.tsx` | Les états : introuvable, échec, en cours, terminé ; le bandeau de démo passe avant tout chiffre |
| `web/src/components/result/ProbabilityBars.tsx` | Une ligne par classe : libellé, barre (largeur = probabilité), pourcentage écrit |
| `web/src/components/result/taskResult.ts` | `formatProbability` (règle « < 0,1 % »), `isDemoResult` |
| `web/src/pages/HistoryPage.tsx`, `components/history/` | `historyFilters.ts` (filtres purs par statut et période), `historyStats.ts` (chiffres clés), `DeleteControl.tsx` |
| `web/src/theme.ts`, `web/src/index.css` | Les jetons de couleur, le thème clair ou sombre, `readCssColor` pour le canvas |

## 6. Ce qu'on a vérifié (résultats)

Vérifié par Luciano avec les **vrais modèles** (PR #28), sur une base vide :

| Audio | Ce que montre l'interface |
| --- | --- |
| Parole en colère (CREMA-D, acteur du **test**) | Émotion « Colère » à 98,7 % ; événement : Éternuement 79,8 % (ESC-50 n'a pas de classe « parole ») |
| Pluie (ESC-50) | Événement « Pluie » à 99,8 % ; émotion « Joie » à 92 % (la détection de parole s'est trompée) |
| 3 s de silence | Refus du serveur affiché sous le bouton ; l'audio et les choix sont gardés |

**À savoir interpréter** :
- l'extrait de pluie fait partie d'ESC-50, sur lequel le modèle a été entraîné : ses 99,8 % ne
  prouvent pas que le modèle généralise ;
- « Joie » sur de la pluie n'est pas une erreur de l'interface : la page affiche fidèlement ce que
  l'API renvoie. C'est une limite de la détection de parole (webrtcvad), à présenter comme telle.

## 7. La démo (scénario N5, `slides/plan.md`)

En 3 minutes, au milieu de la présentation :
1. **Analyser** : déposer un enregistrement de l'équipe (avec la case « démo » cochée sur le
   consentement), cocher Émotion et Événement, lancer : les quatre étapes défilent.
2. **Résultat** : lire le résultat principal et sa probabilité, montrer les barres, le
   spectrogramme, le modèle utilisé et « probabilités calibrées ».
3. **Historique** : l'analyse apparaît, la rouvrir.

La veille : vrais modèles et préchargement activés (`ECHOLENS_INFERENCE_BACKEND=models`,
`ECHOLENS_PRELOAD_MODELS=true`), aucune étiquette « Démo » visible, poids déjà téléchargés (pas
d'internet), vidéo de secours ouverte dans un onglet.

## 8. Dix questions probables du jury

1. **Le navigateur calcule-t-il quelque chose sur le son ?** Seulement la forme d'onde, qui est un
   simple dessin des échantillons. Le spectrogramme et toutes les probabilités viennent du serveur,
   calculés par le même code que l'entraînement (R5).
2. **Comment la page sait-elle que l'analyse est finie ?** Elle redemande le statut à l'API toutes
   les secondes (TanStack Query) ; dès qu'il vaut `done` ou `failed`, elle arrête et ouvre le
   résultat.
3. **Pourquoi l'API répond-elle 202 et pas 200 ?** 202 veut dire « accepté, traitement en cours » :
   l'analyse tourne en arrière-plan, la réponse n'attend pas sa fin.
4. **Que veut dire « probabilités calibrées » ?** Qu'un modèle qui annonce 80 % a raison environ
   8 fois sur 10. On l'obtient en divisant les scores par une température T apprise sur la
   validation, avant le softmax.
5. **Pourquoi affichez-vous « Aucune parole détectée » au lieu d'une émotion ?** Parce qu'il n'y a
   rien à classer : on préfère le dire plutôt qu'inventer une émotion à un bruit de moteur.
6. **Pourquoi seulement 5 événements sur 50 au départ ?** Pour la lisibilité ; un bouton « Voir les
   50 classes » montre tout, et la somme fait toujours 100 %.
7. **Comment garantissez-vous l'accessibilité ?** Contraste AA dans les deux thèmes, chaque
   pourcentage écrit en texte (pas seulement une barre), animations coupées si le système le
   demande.
8. **Que se passe-t-il si le serveur tombe pendant l'analyse ?** Un bandeau « serveur
   injoignable » s'affiche ; une analyse interrompue est marquée en échec au redémarrage, avec sa
   raison.
9. **Pourquoi avoir retiré Recharts ?** Six barres horizontales n'ont pas besoin d'une bibliothèque
   de graphiques : le CSS suffit et la page est deux fois plus légère. Recharts reste prévu pour un
   vrai graphique (décision U5 du 21 novembre).
10. **Comment éviter qu'on prenne les chiffres de démonstration au sérieux ?** Quand le faux
    prédicteur est utilisé (`model_id = "demo"`), un bandeau l'annonce **avant** tout chiffre, et
    chaque carte porte l'étiquette « Démo ».
