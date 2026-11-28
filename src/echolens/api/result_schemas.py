"""Schémas des résultats d'une analyse (contrat de GET /api/v1/analyses/{id}, C13).

Deux formes :
- complète (ResultsSchema), avec les segments, pour la page Résultat (colonne results) ;
- résumée (ResultsSummarySchema), le premier choix seul, pour l'historique (GET /analyses,
  table analysis_summaries).

Un objet par tâche demandée. Chaque objet a le même format, que la tâche ait un résultat
(done), qu'aucune parole n'ait été trouvée (no_speech) ou qu'elle ne soit pas encore branchée
(unavailable) : le front lit toujours les mêmes champs.
"""

from __future__ import annotations

from marshmallow import Schema, fields, validate

TASK_RESULT_STATUSES = ["done", "no_speech", "unavailable"]


class ClassProbabilitySchema(Schema):
    """Probabilité d'une classe."""

    label = fields.String(
        metadata={"description": "Identifiant de la classe (anglais), par exemple « rain »."}
    )
    label_fr = fields.String(
        metadata={"description": "Libellé français à afficher, par exemple « Pluie »."}
    )
    probability = fields.Float(
        metadata={
            "description": "Probabilité entre 0 et 1. La somme sur toutes les classes vaut 1."
        }
    )


class SegmentResultSchema(Schema):
    """Résultat d'un segment de l'audio, pour la frise temporelle (EF-12)."""

    start_s = fields.Float(metadata={"description": "Début du segment, en secondes."})
    end_s = fields.Float(metadata={"description": "Fin du segment, en secondes."})
    label = fields.String(
        allow_none=True,
        metadata={
            "description": "Classe la plus probable sur ce segment ; null pour la transcription."
        },
    )
    label_fr = fields.String(
        allow_none=True,
        metadata={"description": "Libellé français de cette classe ; null pour la transcription."},
    )
    probabilities = fields.List(
        fields.Nested(ClassProbabilitySchema),
        metadata={
            "description": "Probabilités de toutes les classes sur ce segment, de la plus "
            "probable à la moins probable ; liste vide pour la transcription."
        },
    )
    # dump_default : un résultat enregistré avant l'ajout de text (C17b) renvoie null.
    text = fields.String(
        allow_none=True,
        dump_default=None,
        metadata={
            "description": "Transcription : texte dit sur ce segment (chaîne vide si Whisper "
            "n'y a rien entendu). null pour les autres tâches."
        },
    )
    score = fields.Float(
        allow_none=True,
        dump_default=None,
        metadata={
            "description": "Locuteur : similarité cosinus (−1 à 1) avec la voix enregistrée la "
            "plus proche, même si elle reste sous le seuil « inconnu » (EF-11). label est "
            "l'identifiant du locuteur (ou « unknown »), label_fr son nom (ou « Inconnu »). "
            "null pour les autres tâches."
        },
    )


class TaskResultSchema(Schema):
    """Résultat d'une tâche (émotion, événement sonore, transcription ou locuteur)."""

    status = fields.String(
        validate=validate.OneOf(TASK_RESULT_STATUSES),
        metadata={
            "description": "done : résultat calculé ; no_speech : émotion, transcription ou "
            "locuteur demandé mais aucune parole détectée, rien n'est inventé ; unavailable : "
            "pas de modèle pour cette tâche, ou locuteur demandé sans voix enregistrée ; "
            "l'analyse réussit quand même."
        },
    )
    message = fields.String(
        allow_none=True,
        metadata={
            "description": "Message en français à afficher en gris si status ≠ done "
            "(« Aucune parole détectée », « Disponible prochainement ») ; sinon null."
        },
    )
    label = fields.String(
        allow_none=True,
        metadata={
            "description": "Classe la plus probable sur tout l'audio ; null si status ≠ done "
            "et pour la transcription."
        },
    )
    label_fr = fields.String(
        allow_none=True,
        metadata={
            "description": "Libellé français de cette classe ; null si status ≠ done et "
            "pour la transcription."
        },
    )
    probabilities = fields.List(
        fields.Nested(ClassProbabilitySchema),
        metadata={
            "description": "Résultat global : toutes les classes, de la plus probable à la "
            "moins probable, somme 1. Il est calculé à partir des segments : moyenne des "
            "fenêtres pour les événements, moyenne pondérée par la durée pour les émotions, "
            "part du temps de parole de chacun pour le locuteur. Liste vide si status ≠ done, "
            "et toujours pour la transcription."
        },
    )
    model_id = fields.String(
        allow_none=True,
        metadata={
            "description": "Identifiant du modèle (registre) ; « demo » pour le faux "
            "prédicteur ; null si la tâche n'est pas branchée."
        },
    )
    model_version = fields.String(
        allow_none=True,
        metadata={"description": "Version du modèle ; null si la tâche n'est pas branchée."},
    )
    calibrated = fields.Boolean(
        allow_none=True,
        metadata={
            "description": "Vrai si les probabilités sont calibrées (temperature scaling, "
            "ENF-06) ; faux pour la transcription (pas de probabilités) ; null si la tâche "
            "n'est pas branchée."
        },
    )
    segments = fields.List(
        fields.Nested(SegmentResultSchema),
        metadata={
            "description": "Résultats par segment, dans l'ordre du temps (frise, EF-12) : "
            "fenêtres de 5 s à 50 % de recouvrement pour les événements, morceaux de parole "
            "de 5 s au plus pour les émotions, de 30 s au plus pour la transcription. Liste "
            "vide si status ≠ done."
        },
    )
    text = fields.String(
        allow_none=True,
        dump_default=None,
        metadata={
            "description": "Transcription : texte complet, textes des segments joints par "
            "une espace. null si status ≠ done et pour les autres tâches."
        },
    )


class TaskSummarySchema(Schema):
    """Résumé d'une tâche pour l'historique : le premier choix et le modèle, rien de plus.

    Il est calculé une fois à la fin de l'analyse (services.results.summarize_results) et lu
    dans la table analysis_summaries : l'historique ne charge jamais les résultats complets.
    """

    status = fields.String(
        validate=validate.OneOf(TASK_RESULT_STATUSES),
        metadata={"description": "Même valeur que dans le résultat complet."},
    )
    message = fields.String(
        allow_none=True,
        metadata={"description": "Message en français si status ≠ done ; sinon null."},
    )
    label = fields.String(
        allow_none=True,
        metadata={
            "description": "Classe la plus probable sur tout l'audio ; null si status ≠ done."
        },
    )
    label_fr = fields.String(
        allow_none=True,
        metadata={"description": "Libellé français de cette classe ; null si status ≠ done."},
    )
    # dump_only : champ calculé, en lecture seule (readOnly dans l'OpenAPI, comme avant).
    probability = fields.Float(
        allow_none=True,
        dump_only=True,
        metadata={
            "description": "Probabilité de cette classe (premier choix), entre 0 et 1 ; null "
            "si status ≠ done.",
        },
    )
    model_id = fields.String(
        allow_none=True,
        metadata={"description": "Identifiant du modèle (registre) ; « demo » ou null."},
    )
    model_version = fields.String(
        allow_none=True,
        metadata={"description": "Version du modèle ; null si la tâche n'est pas branchée."},
    )
    calibrated = fields.Boolean(
        allow_none=True,
        metadata={
            "description": "Vrai si les probabilités sont calibrées (ENF-06) ; null si la "
            "tâche n'est pas branchée."
        },
    )


class ResultsSummarySchema(Schema):
    """Résumé des résultats pour l'historique : une entrée par tâche demandée."""

    emotion = fields.Nested(TaskSummarySchema)
    sound_event = fields.Nested(TaskSummarySchema)
    transcription = fields.Nested(TaskSummarySchema)
    speaker = fields.Nested(TaskSummarySchema)


class ResultsSchema(Schema):
    """Résultats d'une analyse terminée : seules les tâches demandées sont présentes."""

    emotion = fields.Nested(
        TaskResultSchema, metadata={"description": "Émotion (EF-05), 6 classes."}
    )
    sound_event = fields.Nested(
        TaskResultSchema, metadata={"description": "Événement sonore (EF-06), 50 classes."}
    )
    transcription = fields.Nested(
        TaskResultSchema,
        metadata={
            "description": "Transcription (EF-10) : un texte par segment de parole, sans "
            "probabilités."
        },
    )
    speaker = fields.Nested(
        TaskResultSchema,
        metadata={"description": "Locuteur (EF-11) : unavailable pour l'instant."},
    )
