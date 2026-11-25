# echolens-transcription-whisper-base — transcription du français, Whisper base (pré-entraîné)

Modèle de transcription de l'application EchoLens (EF-10, C17b) : écrit ce qui est dit dans
chaque segment de parole. Profil **temps réel** ; le profil qualité utilise whisper-small
(echolens-transcription-whisper-small).

## Source et révision

- Modèle : Whisper base d'OpenAI (74 M de paramètres), converti au format CTranslate2 pour
  faster-whisper par Systran.
- Poids : `hf://Systran/faster-whisper-base`, révision figée
  `ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66` (la même que l'évaluation C17a).
- Licence : MIT (Whisper et sa conversion).
- Pas d'entraînement ni d'ajustement dans le projet : famille « pretrained » du registre.

## Tâche et entrée

- Tâche : transcription de la parole en texte, français imposé (pas de détection de langue).
- Entrée : morceaux de parole mono 16 kHz. Les segments viennent de la VAD de l'application
  (Silero, D5, la même que pour les émotions) ; un segment de plus de 30 s est coupé en
  morceaux égaux de 30 s au plus (`configs/inference.yaml`, section `transcription`).
- Sortie : un texte par morceau ; le texte complet est celui des morceaux joints par une espace.
  Pas de probabilités ni de calibration.

## Exécution

| Réglage | Valeur | Raison |
| --- | --- | --- |
| Moteur | faster-whisper 1.2 (CTranslate2) | Jusqu'à 4 fois plus rapide que Whisper d'origine, selon ses auteurs ; moins de mémoire en int8 |
| Précision | int8, CPU, 4 fils | Machine CPU de référence (ENF-01) |
| `language` | `fr` | Langue imposée |
| `beam_size` | 5 | Recherche en faisceau |
| `vad_filter` | `false` | La VAD de l'application a déjà découpé la parole |
| `condition_on_previous_text` | `false` | Chaque segment est transcrit seul : une erreur ne se propage pas |
| `temperature` | 0 ; 0,2 ; 0,4 ; 0,6 ; 0,8 ; 1,0 | Replis de faster-whisper si le texte est jugé mauvais |
| `no_speech_threshold`, `log_prob_threshold` | 0,6 et −1,0 (valeurs par défaut) | Seuils anti-hallucination : un morceau sans parole donne un texte vide |

Ces réglages sont ceux de l'évaluation C17a (#47) : l'application transcrit comme le modèle a
été mesuré. Le modèle est chargé une seule fois, à la première transcription, ou au démarrage
avec `ECHOLENS_PRELOAD_MODELS=true`.

## Métriques (C17a, #47)

Mesurées par l'évaluation C17a (`training/results/c17_transcription.json`), avec les mêmes
réglages de décodage que l'application, en float16 sur GPU (Kaggle). Corpus OpenSLR 57 (P10),
qui ne sert qu'à l'évaluation : test officiel (515 phrases, 12 locuteurs, 0,31 h) et partie
lue du sous-corpus de Yaoundé, `yaounde/read` (6 299 phrases, 84 locuteurs, 8,53 h).
Intervalles à 95 % par bootstrap sur les locuteurs (1 000 tirages, graine 42) :
les phrases d'un même locuteur ne sont pas indépendantes.

| Corpus | WER [IC 95 %] | CER [IC 95 %] |
| --- | --- | --- |
| Test officiel | 0,279 [0,235 ; 0,320] | 0,133 [0,110 ; 0,157] |
| `yaounde/read` | 0,505 [0,487 ; 0,523] | 0,253 [0,240 ; 0,264] |

- Contre whisper-small, écart de WER small − base : −0,135 [−0,165 ; −0,105] sur le test et
  −0,160 [−0,169 ; −0,151] sur `yaounde/read` : base fait significativement plus d'erreurs.
  C'est le prix de la vitesse du profil temps réel.
- int8 sur CPU (l'application) contre float16 sur GPU (l'évaluation), sur 100 phrases tirées
  au hasard (graine 42) dans les deux corpus : WER 0,484 en float16, 0,488 en int8 ; écart
  +0,004 [−0,030 ; +0,043], **non significatif**. Les chiffres du tableau valent donc pour
  l'application.

## Latence (E6, ENF-01)

Machine CPU de référence : Intel Core i5-6200U (2,30 GHz, 2 cœurs, 4 fils, 8 Go), int8,
4 fils de calcul. Protocole de C17a : phrases de Yaoundé mises bout à bout jusqu'à 30 s,
médiane de 3 essais, RTF = temps de calcul / durée de l'audio.

| Audio | Médiane (3 essais : 4,87 ; 4,96 ; 5,10 s) | RTF |
| --- | --- | --- |
| 30 s | 4,96 s | 0,165 |

Sous la limite du flux (RTF < 0,25, ENF-01) : modèle du profil temps réel. Un audio de 5 min
demanderait environ 50 s de calcul (RTF extrapolé).

## Limites

- Le WER est bien plus élevé sur la partie lue de Yaoundé (0,505) que sur le test officiel
  (0,279). Les deux corpus diffèrent par le contenu, la longueur des phrases, l'enregistrement
  et les locuteurs, et le test contient aussi des locuteurs camerounais : cette mesure ne
  permet pas d'isoler l'effet de l'accent.
- La partie `yaounde/answers` (réponses à des questions) n'est pas mesurée : sa référence est
  la question posée, pas la réponse (P10).
- 9 phrases du test où base et small se trompent sur tous les mots (`suspect_references`) :
  après vérification, ce sont des erreurs de reconnaissance, dont 3 d'un même locuteur, et non
  des références fausses.
- Whisper est entraîné sur des données du web peu documentées : biais d'accent et de vocabulaire
  possibles, non mesurés ici.
- Un segment de parole très court (moins d'une seconde) ou couvert par du bruit peut donner un
  texte vide (seuils anti-hallucination) ou approximatif.
- Les coupures à 30 s tombent au milieu d'un mot possible : le mot coupé peut être mal transcrit.
- Sur un audio sans parole envoyé directement au modèle (hors application), les replis de
  température rendent le calcul long : environ 69 s pour 10 s de silence et de bruit, mesurés
  pendant C17b, pour un texte vide. Dans l'application, la VAD n'envoie que la parole.
