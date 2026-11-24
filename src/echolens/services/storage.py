"""Persistance des analyses (décision S3) : SQLite via SQLAlchemy 2, une seule table pour l'instant.

Les tables des segments et des prédictions viendront avec le MCD MERISE ; elles ne sont pas
anticipées ici : les résultats sont stockés en JSON dans la table analyses (C13). Les tables
sont créées au démarrage, sans outil de migration : une colonne ajoutée depuis (summary) est
créée et remplie au démarrage ; pour toute autre colonne manquante, le serveur refuse de
démarrer et demande de supprimer la base.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Engine,
    String,
    create_engine,
    inspect,
    select,
    text,
    update,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from echolens.services.results import summarize_results

# Seule colonne ajoutée après coup que le démarrage sait créer et remplir (voir upgrade_columns).
SUMMARY_COLUMN = "summary"


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
    # Résumé des résultats pour l'historique (premier choix de chaque tâche, sans segments),
    # écrit en même temps que results ; null tant que l'analyse n'est pas terminée.
    summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    """Ouvre la base, crée les tables manquantes et renvoie une fabrique de sessions.

    expire_on_commit=False : les objets lus restent utilisables après la fermeture de la session,
    ce qui permet au service de les renvoyer aux routes.
    """
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    upgrade_columns(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


def upgrade_columns(engine: Engine) -> None:
    """Met à niveau une base créée par une version plus ancienne, ou refuse de démarrer.

    create_all crée les tables absentes, mais n'ajoute pas de colonne à une table existante :
    sans ce contrôle, la première requête échouerait sur « no such column ». La colonne summary
    se déduit de results : elle est ajoutée et remplie ici. Toute autre colonne manquante
    arrête le démarrage avec un message clair.
    """
    missing = missing_columns(engine)
    # Étape 1 : refus si une colonne qu'on ne sait pas remplir manque.
    unknown_missing = [name for name in missing if name != SUMMARY_COLUMN]
    if unknown_missing:
        raise RuntimeError(
            f"La base de données ({engine.url}) a été créée par une version plus ancienne "
            f"d'EchoLens : colonnes manquantes {', '.join(unknown_missing)}. Supprimez le "
            "fichier de la base (var/echolens.db par défaut) : il sera recréé au prochain "
            "démarrage."
        )
    # Étape 2 : ajout et remplissage de summary, une seule fois (la colonne existe ensuite).
    if SUMMARY_COLUMN in missing:
        add_summary_column(engine)


def missing_columns(engine: Engine) -> list[str]:
    """Colonnes du modèle AnalysisRecord absentes de la table analyses en base."""
    inspector = inspect(engine)
    existing = {column["name"] for column in inspector.get_columns(AnalysisRecord.__tablename__)}
    expected = set(AnalysisRecord.__table__.columns.keys())
    return sorted(expected - existing)


def add_summary_column(engine: Engine) -> None:
    """Ajoute la colonne summary et la remplit à partir de results, pour chaque analyse.

    Personne n'a à supprimer sa base. Limite : le pilote sqlite3 valide l'ALTER TABLE tout de
    suite, hors transaction. Si le serveur est tué pendant le remplissage, la colonne existe
    au démarrage suivant et n'est pas remplie de nouveau : les analyses concernées s'affichent
    sans résultat dans l'historique, mais leur page Résultat reste complète.
    """
    with engine.begin() as connection:
        # Étape 1 : la colonne, vide (NULL) pour toutes les analyses existantes.
        connection.execute(text("ALTER TABLE analyses ADD COLUMN summary JSON"))
        # Étape 2 : les identifiants d'abord, puis les résultats un par un, pour ne garder
        # qu'un seul JSON complet en mémoire à la fois.
        analysis_ids = connection.scalars(select(AnalysisRecord.id)).all()
        for analysis_id in analysis_ids:
            results_query = select(AnalysisRecord.results).where(AnalysisRecord.id == analysis_id)
            results = connection.scalar(results_query)
            # Analyse en cours ou en échec : pas de résultats, donc pas de résumé.
            if results is None:
                continue
            summary = summarize_results(results)
            summary_update = update(AnalysisRecord).where(AnalysisRecord.id == analysis_id)
            connection.execute(summary_update.values(summary=summary))
