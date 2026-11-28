"""Persistance des analyses (décision S3) : SQLite via SQLAlchemy 2.

Les tables des segments et des prédictions viendront avec le MCD MERISE ; elles ne sont pas
anticipées ici : les résultats sont stockés en JSON dans la table analyses (C13). La table
analysis_summaries garde une copie calculée du premier choix de chaque tâche, pour que
l'historique n'ait jamais à lire results (EF-08). Les tables sont créées au démarrage, sans
outil de migration : une colonne manquante dans une table existante arrête le démarrage avec
un message clair.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, Engine, ForeignKey, String, create_engine, inspect, select
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

from echolens.services.results import summarize_results


def _utc_now() -> datetime:
    # Défini avant les tables : SQLAlchemy l'appelle à chaque insertion pour created_at.
    return datetime.now(UTC)


class AnalysisStatus(StrEnum):
    """Cycle de vie d'une analyse : pending → processing → done, ou failed."""

    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Base(DeclarativeBase):
    """Classe de base des tables SQLAlchemy d'EchoLens."""


class AnalysisRecord(Base):
    """Une analyse demandée par l'utilisateur : le fichier importé et son statut."""

    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    original_filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default=AnalysisStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(String, default=None)
    duration_s: Mapped[float | None] = mapped_column(default=None)
    # Liste des tâches demandées, stockée en texte JSON par SQLite (ex. ["emotion", "speaker"]).
    tasks: Mapped[list[str]] = mapped_column(JSON)
    profile: Mapped[str] = mapped_column(String(16))
    # Résultats, un objet par tâche demandée (JSON, contrat de l'API) ; null tant que
    # l'analyse n'est pas terminée.
    results: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    # Ligne de résumé (table analysis_summaries) ; absente tant que l'analyse n'est pas
    # terminée. cascade : supprimer l'analyse supprime aussi son résumé.
    summary_row: Mapped[AnalysisSummaryRecord | None] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    # Consentement donné avant l'enregistrement d'une session du flux micro (ENF-10) ; absent
    # pour un fichier importé. cascade : supprimer l'analyse supprime aussi le consentement.
    consent_row: Mapped[RecordingConsentRecord | None] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )

    @property
    def summary(self) -> dict[str, Any] | None:
        """Résumé de l'analyse pour l'historique, ou None s'il n'y en a pas encore."""
        if self.summary_row is None:
            return None
        return self.summary_row.summary


class AnalysisSummaryRecord(Base):
    """Résumé d'une analyse terminée : premier choix de chaque tâche, sans segments (EF-08).

    Copie calculée de results (services.results.summarize_results), voulue : la liste de
    l'historique la lit sans toucher à results. Une table à part plutôt qu'une colonne de
    analyses : SQLite range une ligne d'un seul bloc, et lire une colonne placée après results
    oblige à parcourir tout le JSON de results sur le disque.
    """

    __tablename__ = "analysis_summaries"

    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), primary_key=True)
    summary: Mapped[dict[str, Any]] = mapped_column(JSON)
    analysis: Mapped[AnalysisRecord] = relationship(back_populates="summary_row")


class RecordingConsentRecord(Base):
    """Consentement à l'enregistrement de sa voix, donné sur la page Direct (ENF-10, S6).

    Une ligne par analyse issue du flux micro : la version du texte accepté et la date. Sans
    cette ligne, le serveur n'enregistre pas la session. Une table à part : create_all la crée
    seule dans une base existante, sans toucher à la table analyses.
    """

    __tablename__ = "recording_consents"

    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id"), primary_key=True)
    consent_version: Mapped[str] = mapped_column(String(32))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    analysis: Mapped[AnalysisRecord] = relationship(back_populates="consent_row")


class ComparisonRecord(Base):
    """Une comparaison de modèles sur un même fichier (EF-15), gardée dans l'Historique.

    results : pour chaque tâche, la liste des modèles du registre qui ont tourné, chacun avec
    son temps de calcul et son résultat au format d'une analyse (JSON). Une table à part :
    create_all la crée seule dans une base existante, sans toucher à la table analyses.
    """

    __tablename__ = "comparisons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    original_filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default=AnalysisStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(String, default=None)
    duration_s: Mapped[float | None] = mapped_column(default=None)
    tasks: Mapped[list[str]] = mapped_column(JSON)
    results: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)


class SpeakerRecord(Base):
    """Un locuteur enregistré sur la page Locuteurs, avec son consentement (EF-11, S6).

    La voix est la moyenne normée des vecteurs de ses morceaux de parole (C15), stockée en JSON.
    Elle n'a de sens qu'avec le modèle qui l'a calculée : model_id et model_version sont gardés,
    et l'audio d'enregistrement est gardé sur disque pour pouvoir la recalculer avec un autre
    modèle (décision de Luciano, 27 nov. 2026). Supprimer le locuteur supprime les deux.
    """

    __tablename__ = "speakers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    voice: Mapped[list[float]] = mapped_column(JSON)
    model_id: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(32))
    # Parole réellement utilisée (morceaux gardés par la VAD) et nombre de morceaux.
    speech_s: Mapped[float]
    segment_count: Mapped[int]
    audio_count: Mapped[int]
    # Version du texte de consentement accepté (configs/inference.yaml, speaker).
    consent_version: Mapped[str] = mapped_column(String(32))
    # Consentement au clonage (C35), donné par une seconde case ; absent : la voix ne peut pas
    # être clonée. cascade : supprimer le locuteur supprime aussi ce consentement et ses
    # extraits synthétiques.
    # lazy="selectin" : lu avec le locuteur, car l'objet est utilisé après la session.
    cloning_consent_row: Mapped[CloningConsentRecord | None] = relationship(
        back_populates="speaker", cascade="all, delete-orphan", lazy="selectin"
    )
    syntheses: Mapped[list[SynthesisRecord]] = relationship(
        back_populates="speaker", cascade="all, delete-orphan"
    )

    @property
    def cloning_allowed(self) -> bool:
        """Vrai si la personne a accepté que sa voix soit clonée."""
        return self.cloning_consent_row is not None


class CloningConsentRecord(Base):
    """Consentement au clonage d'une voix enregistrée (EF-18, ENF-10, S6).

    Une table à part : create_all la crée seule dans une base existante, sans toucher à la
    table speakers.
    """

    __tablename__ = "cloning_consents"

    speaker_id: Mapped[str] = mapped_column(ForeignKey("speakers.id"), primary_key=True)
    consent_version: Mapped[str] = mapped_column(String(32))
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    speaker: Mapped[SpeakerRecord] = relationship(back_populates="cloning_consent_row")


class SynthesisRecord(Base):
    """Un extrait de voix synthétique produit par la page Cloner (EF-18).

    Le texte et le locuteur cloné sont gardés : on sait toujours quelle voix a dit quoi, et
    quand. L'audio (WAV marqué) est dans le dossier du locuteur : le supprimer efface tout.
    """

    __tablename__ = "syntheses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now)
    speaker_id: Mapped[str] = mapped_column(ForeignKey("speakers.id"))
    text: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String(16), default=AnalysisStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(String, default=None)
    model_id: Mapped[str] = mapped_column(String(64))
    model_version: Mapped[str] = mapped_column(String(32))
    duration_s: Mapped[float | None] = mapped_column(default=None)
    compute_s: Mapped[float | None] = mapped_column(default=None)
    # lazy="joined" : le nom du locuteur est lu avec l'extrait, utilisable après la session.
    speaker: Mapped[SpeakerRecord] = relationship(back_populates="syntheses", lazy="joined")

    @property
    def speaker_name(self) -> str:
        """Nom du locuteur dont la voix a été clonée."""
        return self.speaker.name


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    """Ouvre la base, crée les tables manquantes et renvoie une fabrique de sessions.

    expire_on_commit=False : les objets lus restent utilisables après la fermeture de la session,
    ce qui permet au service de les renvoyer aux routes.
    """
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    check_columns_are_current(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    fill_missing_summaries(session_factory)
    return session_factory


def check_columns_are_current(engine: Engine) -> None:
    """Refuse une base créée par une version plus ancienne, avec un message clair.

    create_all crée les tables absentes, mais n'ajoute pas de colonne à une table existante :
    sans ce contrôle, la première requête échouerait sur « no such column ».
    """
    inspector = inspect(engine)
    existing = {column["name"] for column in inspector.get_columns(AnalysisRecord.__tablename__)}
    expected = set(AnalysisRecord.__table__.columns.keys())
    missing = sorted(expected - existing)
    if missing:
        raise RuntimeError(
            f"La base de données ({engine.url}) a été créée par une version plus ancienne "
            f"d'EchoLens : colonnes manquantes {', '.join(missing)}. Supprimez le fichier de la "
            "base (var/echolens.db par défaut) : il sera recréé au prochain démarrage."
        )


def fill_missing_summaries(session_factory: sessionmaker[Session]) -> None:
    """Crée le résumé de chaque analyse terminée qui n'en a pas encore (EF-08).

    Cas d'une base créée avant la table analysis_summaries. Une analyse à la fois, chacune
    dans sa propre transaction : on peut relancer sans risque, et un arrêt en plein
    remplissage est repris au démarrage suivant.
    """
    # Étape 1 : analyses terminées sans ligne de résumé (jointure externe gauche).
    query = select(AnalysisRecord.id)
    query = query.outerjoin(AnalysisSummaryRecord)
    query = query.where(AnalysisRecord.status == AnalysisStatus.DONE)
    query = query.where(AnalysisSummaryRecord.analysis_id.is_(None))
    with session_factory() as session:
        analysis_ids = session.scalars(query).all()
    # Étape 2 : résumé calculé depuis results, un seul JSON complet en mémoire à la fois.
    for analysis_id in analysis_ids:
        add_summary(session_factory, analysis_id)


def add_summary(session_factory: sessionmaker[Session], analysis_id: str) -> None:
    """Calcule le résumé d'une analyse depuis results et l'enregistre."""
    with session_factory() as session:
        results_query = select(AnalysisRecord.results).where(AnalysisRecord.id == analysis_id)
        results = session.scalar(results_query)
        if results is None:
            return
        summary = summarize_results(results)
        session.add(AnalysisSummaryRecord(analysis_id=analysis_id, summary=summary))
        session.commit()
