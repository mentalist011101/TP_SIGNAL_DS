# Flux micro en direct : protocole du WebSocket `/ws/stream`

Exigences et décisions : EF-14 (analyse du flux micro, latence et RTF affichés), D8 (PCM
16 kHz Int16 par WebSocket, fenêtre W = 2 s, décalage H = 0,5 s), ENF-01 (calcul d'une fenêtre
< H au p95, soit RTF < 0,25), ENF-02 (latence perçue ≈ H + calcul), ENF-10 (consentement avant
tout enregistrement de voix), D5 (VAD Silero).

Un WebSocket n'apparaît pas dans l'OpenAPI (`/docs`) : ce fichier en est la référence. Le code
est dans `src/echolens/api/stream.py` (route), `src/echolens/services/stream_service.py`
(session) et `src/echolens/core/stream.py` (tampon et fenêtres). Les réglages sont dans
`configs/inference.yaml`, section `stream`.

## Déroulé

1. Le navigateur ouvre `ws://<hôte>/ws/stream` et envoie le message `start`.
2. Le serveur répond `ready`.
3. Le navigateur envoie le son en continu, en messages binaires.
4. Dès que 2 s de son sont arrivées, puis toutes les 0,5 s de son reçu, le serveur analyse les
   2 dernières secondes et répond `window`.
5. Le navigateur envoie `stop`. Si la session est enregistrée, le serveur répond `saved`, puis
   il ferme la connexion.

Si le calcul d'une fenêtre dure plus que H, les morceaux arrivés pendant ce temps sont lus
d'un coup, et seule la fenêtre la plus récente est analysée : les autres sont **sautées** et
comptées (`skipped`). La latence reste ainsi bornée au lieu de grandir sans fin.

## Navigateur → serveur

| Message | Forme | Quand |
| --- | --- | --- |
| `start` | texte JSON `{"type": "start", "record": false}` | Premier message, obligatoire |
| `start` avec enregistrement | `{"type": "start", "record": true, "consent": {"accepted": true, "version": "direct-v1"}}` | Seulement si l'utilisateur a coché « J'ai lu et j'accepte » |
| son | binaire : PCM Int16 petit-boutiste, mono, 16 kHz, 1 s au plus par message | En continu (la page envoie des morceaux de 100 ms) |
| `stop` | texte JSON `{"type": "stop"}` | Fin de la session |

Le rééchantillonnage à 16 kHz est fait par le navigateur (`AudioContext` à 16 kHz), pas par le
serveur : le front ne calcule aucune feature (R5), il ne fait que convertir le son.

## Serveur → navigateur

| Message | Contenu |
| --- | --- |
| `ready` | `window_s`, `hop_s`, `sample_rate`, `tasks`, `record` |
| `window` | `end_s` : fin de la fenêtre, en secondes depuis le début du flux ; `results` : pour l'émotion et l'événement, le résumé du contrat C13 (`status`, `label`, `label_fr`, `probability`, `model_id`…) ; `speech` : la VAD a trouvé de la parole (vrai, faux, ou null sans émotion demandée) ; `compute_ms` et `rtf` de cette fenêtre ; `compute_p50_ms` et `compute_p95_ms` de la session ; `skipped`, `window_count`, `skipped_count` |
| `saved` | `analysis_id` de l'analyse créée ; `truncated` vrai si la session a dépassé 5 min |
| `error` | `message` en français, affichable tel quel ; le serveur ferme ensuite la connexion |

RTF = temps de calcul ÷ durée du son analysé (2 s). La latence perçue (ENF-02) se mesure côté
navigateur : arrivée de la réponse moins envoi du dernier morceau de la fenêtre.

## Enregistrement avec consentement (ENF-10)

- Sans consentement, rien n'est gardé : le tampon ne contient que les 2 dernières secondes, et il
  est libéré à la fermeture.
- Avec `record: true` et un consentement accepté dans la bonne version, tout le son de la
  session est gardé, au plus `max_audio_seconds` (5 min, comme un fichier importé).
- À l'arrêt, il devient une analyse ordinaire de l'Historique (fichier `direct_<date>.wav`),
  avec les mêmes contrôles qu'un import et les tâches et le profil de `recording_tasks` et
  `recording_profile`.
- La version du texte accepté et la date sont enregistrées dans la table `recording_consents`,
  dans le même commit que l'analyse. Supprimer l'analyse supprime aussi le consentement.
- Changer le texte du consentement oblige à changer `consent_version`, ici et dans le front : un
  consentement donné sur un autre texte est refusé.
