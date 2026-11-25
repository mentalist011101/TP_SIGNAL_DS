# echolens-transcription-whisper-small — transcription du français, Whisper small (pré-entraîné)

Modèle de transcription de l'application EchoLens (EF-10, C17b) : écrit ce qui est dit dans
chaque segment de parole. Profil **qualité** ; le profil temps réel utilise whisper-base
(echolens-transcription-whisper-base).

## Source et révision

- Modèle : Whisper small d'OpenAI (244 M de paramètres), converti au format CTranslate2 pour
  faster-whisper par Systran.
- Poids : `hf://Systran/faster-whisper-small`, révision figée
  `536b0662742c02347bc0e980a01041f333bce120` (la même que l'évaluation C17a).
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

## Métriques

| Métrique | Valeur |
| --- | --- |
| WER, test officiel d'OpenSLR 57 | en attente de C17a (#47) |
| WER, sous-corpus de Yaoundé | en attente de C17a (#47) |
| Écart de WER float16 (GPU) / int8 (CPU) | en attente de C17a (#47) |

## Latence (E6, ENF-01)

Machine CPU de référence : Intel Core i5-6200U (2,30 GHz, 4 cœurs logiques), Windows 10, int8,
4 fils. Protocole de C17a : phrases de Yaoundé mises bout à bout jusqu'à 30 s, médiane de
3 essais, RTF = temps de calcul / durée de l'audio.

| Audio | RTF |
| --- | --- |
| 30 s | 0,517 |

Au-dessus de la limite du flux (RTF < 0,25, ENF-01) : réservé au profil qualité, pour l'analyse
de fichiers. Un audio de 5 min demanderait environ 2 min 35 s de calcul (RTF extrapolé).

## Limites

- WER non encore mesuré sur le français d'Afrique centrale : voir C17a (#47).
- Whisper est entraîné sur des données du web peu documentées : biais d'accent et de vocabulaire
  possibles, non mesurés ici.
- Un segment de parole très court (moins d'une seconde) ou couvert par du bruit peut donner un
  texte vide (seuils anti-hallucination) ou approximatif.
- Les coupures à 30 s tombent au milieu d'un mot possible : le mot coupé peut être mal transcrit.
