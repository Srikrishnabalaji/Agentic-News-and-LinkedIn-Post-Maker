"""Database engine and session management.

Works with both SQLite (local dev/testing) and PostgreSQL (Railway).
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _normalize_url(url: str) -> str:
    # Railway sometimes provides the legacy "postgres://" scheme which
    # SQLAlchemy 2.x no longer accepts.
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


_url = _normalize_url(settings.database_url)
_connect_args = {"check_same_thread": False} if _url.startswith("sqlite") else {}

engine = create_engine(_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if they do not exist (used for local/dev + first boot)."""
    from . import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
