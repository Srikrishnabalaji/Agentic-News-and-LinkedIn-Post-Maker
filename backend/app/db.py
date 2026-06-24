"""Database engine and session management.

Works with both SQLite (local dev/testing) and PostgreSQL (Railway).
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
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


def _apply_migrations() -> None:
    """Idempotent column additions for existing databases."""
    migrations = [
        "ALTER TABLE posts ADD COLUMN category VARCHAR(32) NOT NULL DEFAULT 'security'",
        "ALTER TABLE sources ADD COLUMN category VARCHAR(32) NOT NULL DEFAULT 'security'",
        "ALTER TABLE posts ADD COLUMN is_update BOOLEAN NOT NULL DEFAULT 0",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # column already exists


def _seed_sources() -> None:
    """Populate rss_sources from the hardcoded list on first boot only."""
    from sqlalchemy import select

    from .models import RSSSource
    from .scraper.sources import SOURCES

    db = SessionLocal()
    try:
        already = db.execute(select(RSSSource.id).limit(1)).first()
        if already:
            return
        for s in SOURCES:
            db.add(RSSSource(
                name=s.name, url=s.feed_url, category=s.category,
                authority=s.authority, audience=s.audience,
                enabled=True, is_custom=False,
            ))
        db.commit()
    finally:
        db.close()


def init_db() -> None:
    """Create tables if they do not exist (used for local/dev + first boot)."""
    from . import models  # noqa: F401  (ensure models are registered)

    Base.metadata.create_all(bind=engine)
    _apply_migrations()
    _seed_sources()
