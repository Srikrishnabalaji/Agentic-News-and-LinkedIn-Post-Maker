"""SQLAlchemy ORM models.

Three tables:
  - daily_runs : one row per pipeline execution (the 11 AM cron run)
  - sources    : scraped news articles considered as candidates
  - posts      : Claude-generated LinkedIn drafts surfaced to the reviewer
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class PostStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    posted = "posted"


class DailyRun(Base):
    __tablename__ = "daily_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.running
    )
    num_candidates: Mapped[int] = mapped_column(Integer, default=0)
    num_posts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    posts: Mapped[list["Post"]] = relationship(back_populates="run")
    sources: Mapped[list["Source"]] = relationship(back_populates="run")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("daily_runs.id"), nullable=True)

    url: Mapped[str] = mapped_column(String(1024), index=True)
    title: Mapped[str] = mapped_column(String(512))
    source_name: Mapped[str] = mapped_column(String(128))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    lead_image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    topic_key: Mapped[str | None] = mapped_column(String(256), index=True, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    run: Mapped["DailyRun"] = relationship(back_populates="sources")
    post: Mapped["Post"] = relationship(back_populates="source", uselist=False)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("daily_runs.id"), nullable=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), nullable=True)

    # --- Generated content ---
    headline: Mapped[str] = mapped_column(String(512))
    body: Mapped[str] = mapped_column(Text)
    format_type: Mapped[str] = mapped_column(String(64), default="explainer")
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    char_count: Mapped[int] = mapped_column(Integer, default=0)

    # --- Imagery ---
    image_recommended: Mapped[bool] = mapped_column(Boolean, default=False)
    image_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    image_attribution: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # List of {url, thumb, attribution, source, license} dicts.
    image_options: Mapped[list] = mapped_column(JSON, default=list)

    # --- Provenance / dedup ---
    source_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    topic_key: Mapped[str | None] = mapped_column(String(256), index=True, nullable=True)
    is_pivotal: Mapped[bool] = mapped_column(Boolean, default=False)

    # --- Review lifecycle ---
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus), default=PostStatus.draft, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Reserved for the future LinkedIn API integration (no schema change needed).
    linkedin_post_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    run: Mapped["DailyRun"] = relationship(back_populates="posts")
    source: Mapped["Source"] = relationship(back_populates="post")
