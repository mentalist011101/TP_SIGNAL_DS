"""Persistance des analyses (décision S3) : SQLite via SQLAlchemy 2, une seule table pour l'instant.

Les tables des segments et des prédictions viendront avec le MCD MERISE ; elles ne sont pas
anticipées ici. Les tables sont créées au démarrage, sans migrations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import JSON, DateTime, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


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


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    """Ouvre la base, crée les tables manquantes et renvoie une fabrique de sessions.

    expire_on_commit=False : les objets lus restent utilisables après la fermeture de la session,
    ce qui permet au service de les renvoyer aux routes.
    """
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
