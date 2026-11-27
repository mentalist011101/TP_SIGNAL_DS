"""Comparaison de modèles sur un même fichier (EF-15, S2, S3) : chaque modèle du registre de
chaque tâche demandée tourne sur le même audio, avec son temps de calcul.

On parcourt les deux profils : le registre a un seul modèle par tâche et par profil (S1), donc
chaque modèle est atteint par l'un de ses profils, et un modèle présent dans les deux profils
ne tourne qu'une fois. Le découpage et la VAD sont ceux d'une analyse ordinaire (D5) ; la VAD
tourne une seule fois, avant les modèles, et n'entre pas dans leur temps de calcul.

Le résultat de chaque modèle a exactement le format d'une analyse (services.results). La
comparaison est gardée dans l'Historique, avec l'audio converti pour la réécoute.
"""

from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from sqlalchemy import select, update
from werkzeug.datastructures import FileStorage

from echolens.core.audio import load_audio
from echolens.core.audio.io import TARGET_SAMPLE_RATE
from echolens.core.audio.segment import Segment
from echolens.core.inference import FloatArray
from echolens.core.models.registry import Profile, Task
from echolens.services.analysis_service import (
    CONVERTED_AUDIO_NAME,
    CONVERTED_AUDIO_SUBTYPE,
    INTERRUPTED_MESSAGE,
    AnalysisRejectedError,
    AnalysisService,
    clean_filename,
)
from echolens.services.results import ResultContext, needs_speech_segments, task_result
from echolens.services.storage import AnalysisStatus, ComparisonRecord

# Tâches comparables : celles qui ont plusieurs modèles au registre (le locuteur n'en a qu'un).
COMPARED_TASKS = [Task.EMOTION, Task.SOUND_EVENT, Task.TRANSCRIPTION]
PROFILES = [Profile.QUALITY, Profile.REALTIME]


class ComparisonNotFoundError(LookupError):
    """Aucune comparaison ne porte cet identifiant."""


class ComparisonService:
    """Crée, traite, liste et supprime les comparaisons ; seul accès à la table comparisons.

    Reprend les contrôles d'import, le pool de threads et le contexte de calcul des analyses.
    """

    def __init__(self, analysis_service: AnalysisService) -> None:
        self.analyses = analysis_service
        self.settings = analysis_service.settings
        self.session_factory = analysis_service.session_factory
        self._fail_interrupted_comparisons()

    def create_comparison(self, upload: FileStorage, tasks: list[str]) -> ComparisonRecord:
        """Contrôle le fichier comme pour une analyse, l'enregistre au statut pending et lance
        la comparaison en arrière-plan ; lève AnalysisRejectedError si un contrôle échoue."""
        # Étape 1 : extension et nom nettoyé (S6), puis copie et contrôle de l'audio (D6).
        sent_name = upload.filename or ""
        extension = self.analyses.check_extension(sent_name)
        filename = clean_filename(sent_name, extension)
        comparison_id = str(uuid.uuid4())
        folder = self.comparison_dir(comparison_id)
        folder.mkdir(parents=True)
        original = folder / f"original.{extension}"
        upload.save(original)
        try:
            self.analyses.check_audio(original)
        except AnalysisRejectedError:
            shutil.rmtree(folder)
            raise
        # Étape 2 : enregistrement au statut pending, puis calcul en arrière-plan (S2).
        record = ComparisonRecord(
            id=comparison_id,
            original_filename=filename,
            status=AnalysisStatus.PENDING,
            tasks=tasks,
        )
        with self.session_factory() as session:
            session.add(record)
            session.commit()
        self._submit(comparison_id)
        return self.get_comparison(comparison_id)

    def get_comparison(self, comparison_id: str) -> ComparisonRecord:
        """Renvoie une comparaison, ou lève ComparisonNotFoundError."""
        with self.session_factory() as session:
            record = session.get(ComparisonRecord, comparison_id)
        if record is None:
            raise ComparisonNotFoundError(
                f"Aucune comparaison ne porte l'identifiant {comparison_id}."
            )
        return record

    def list_comparisons(self, limit: int, offset: int) -> list[ComparisonRecord]:
        """Comparaisons les plus récentes d'abord."""
        query = select(ComparisonRecord).order_by(ComparisonRecord.created_at.desc())
        query = query.limit(limit).offset(offset)
        with self.session_factory() as session:
            return list(session.scalars(query).all())

    def delete_comparison(self, comparison_id: str) -> None:
        """Supprime la comparaison et son audio ; lève ComparisonNotFoundError."""
        with self.session_factory() as session:
            record = session.get(ComparisonRecord, comparison_id)
            if record is None:
                raise ComparisonNotFoundError(
                    f"Aucune comparaison ne porte l'identifiant {comparison_id}."
                )
            session.delete(record)
            session.commit()
        shutil.rmtree(self.comparison_dir(comparison_id), ignore_errors=True)

    def comparison_dir(self, comparison_id: str) -> Path:
        """Dossier de l'audio d'une comparaison."""
        return self.settings.data_dir / "comparisons" / comparison_id

    def converted_audio_path(self, comparison_id: str) -> Path:
        """Audio converti (WAV mono 16 kHz), écrit au début du traitement."""
        return self.comparison_dir(comparison_id) / CONVERTED_AUDIO_NAME

    def _submit(self, comparison_id: str) -> None:
        if self.settings.run_jobs_synchronously:
            self._process(comparison_id)
            return
        self.analyses.executor.submit(self._process, comparison_id)

    def _process(self, comparison_id: str) -> None:
        self._update(comparison_id, status=AnalysisStatus.PROCESSING)
        try:
            signal = self._convert_audio(comparison_id)
            record = self.get_comparison(comparison_id)
            context = self.analyses.result_context
            results = compare_models(signal, record.tasks, context)
        except Exception as error:
            # Frontière du thread : toute erreur finit en statut failed, comme une analyse.
            message = f"Échec de la comparaison : {error}"
            self._update(comparison_id, status=AnalysisStatus.FAILED, error_message=message)
            return
        duration_s = len(signal) / TARGET_SAMPLE_RATE
        self._update(
            comparison_id, status=AnalysisStatus.DONE, duration_s=duration_s, results=results
        )

    def _convert_audio(self, comparison_id: str) -> FloatArray:
        # Mono 16 kHz (D1, D2), gardé en WAV PCM 16 bits pour la réécoute.
        folder = self.comparison_dir(comparison_id)
        original = sorted(folder.glob("original.*"))[0]
        signal = load_audio(original, max_seconds=self.settings.max_audio_seconds)
        clipped = np.clip(signal, -1.0, 1.0)
        destination = self.converted_audio_path(comparison_id)
        sf.write(destination, clipped, TARGET_SAMPLE_RATE, subtype=CONVERTED_AUDIO_SUBTYPE)
        return signal

    def _update(
        self,
        comparison_id: str,
        status: AnalysisStatus,
        error_message: str | None = None,
        duration_s: float | None = None,
        results: dict[str, Any] | None = None,
    ) -> None:
        with self.session_factory() as session:
            record = session.get(ComparisonRecord, comparison_id)
            # Supprimée pendant son calcul : rien à mettre à jour.
            if record is None:
                return
            record.status = status
            record.error_message = error_message
            if duration_s is not None:
                record.duration_s = duration_s
            if results is not None:
                record.results = results
            session.commit()

    def _fail_interrupted_comparisons(self) -> None:
        # Comme pour les analyses : un calcul en cours au redémarrage ne finira jamais.
        unfinished = [AnalysisStatus.PENDING, AnalysisStatus.PROCESSING]
        statement = update(ComparisonRecord).where(ComparisonRecord.status.in_(unfinished))
        statement = statement.values(
            status=AnalysisStatus.FAILED, error_message=INTERRUPTED_MESSAGE
        )
        with self.session_factory() as session:
            session.execute(statement)
            session.commit()


def compare_models(
    signal: FloatArray, tasks: list[str], context: ResultContext
) -> dict[str, list[dict[str, Any]]]:
    """Pour chaque tâche demandée, la liste des modèles qui ont tourné et leurs résultats."""
    requested = [Task(task_name) for task_name in tasks]
    # Étape 1 : zones de parole, une seule fois, hors du temps de calcul des modèles (D5).
    speech_segments: list[Segment] = []
    if needs_speech_segments(requested):
        speech_segments = context.speech_detector.detect(signal)
    # Étape 2 : chaque modèle de chaque tâche, sur le même audio.
    comparisons: dict[str, list[dict[str, Any]]] = {}
    for task in requested:
        comparisons[task.value] = task_comparison(signal, speech_segments, task, context)
    return comparisons


def task_comparison(
    signal: FloatArray, speech_segments: list[Segment], task: Task, context: ResultContext
) -> list[dict[str, Any]]:
    """Un passage par modèle de la tâche : identité, profils, temps de calcul, résultat.

    Un modèle utilisé par les deux profils ne tourne qu'une fois ; on note ses deux profils.
    """
    runs: list[dict[str, Any]] = []
    for profile in PROFILES:
        if not context.predictor.supports(task, profile):
            continue
        info = context.predictor.model_info(task, profile)
        already = _run_of(runs, info.model_id)
        if already is not None:
            already["profiles"].append(profile.value)
            continue
        # Temps mesuré autour du seul calcul du modèle (fenêtres, inférence, global) : le
        # modèle est chargé avant, sinon le premier passage paierait son chargement.
        context.predictor.prepare(task, profile)
        started = time.perf_counter()
        # Aucune voix : le locuteur ne fait pas partie des tâches comparables.
        result = task_result(signal, speech_segments, task, profile, context, [])
        compute_s = time.perf_counter() - started
        run = {
            "model_id": info.model_id,
            "model_version": info.model_version,
            "profiles": [profile.value],
            "compute_s": compute_s,
            "result": result,
        }
        runs.append(run)
    return runs


def _run_of(runs: list[dict[str, Any]], model_id: str) -> dict[str, Any] | None:
    for run in runs:
        if run["model_id"] == model_id:
            return run
    return None
