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


class CandidateStatus(str, enum.Enum):
    pending = "pending"      # discovered, not yet shown to the user
    shown = "shown"          # surfaced in the candidate drawer
    generated = "generated"  # a post was created from it
    dismissed = "dismissed"  # user hid it (recoverable)


class RSSSource(Base):
    """A configurable RSS feed the scraper pulls from.

    Replaces the hardcoded sources.py list. Seeded from that list on first
    boot (is_custom=False). Built-ins can be toggled/edited but not deleted;
    user-added feeds (is_custom=True) can be deleted.
    """
    __tablename__ = "rss_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    url: Mapped[str] = mapped_column(String(1024), unique=True)
    category: Mapped[str] = mapped_column(String(32), default="security", index=True)
    authority: Mapped[float] = mapped_column(Float, default=0.8)
    audience: Mapped[str] = mapped_column(String(32), default="consumer")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


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
    category: Mapped[str] = mapped_column(String(32), default="security")

    run: Mapped["DailyRun"] = relationship(back_populates="sources")
    post: Mapped["Post"] = relationship(back_populates="source", uselist=False)


class StoryCandidate(Base):
    """A discovered-but-not-necessarily-used story, for the replacement pool.

    Every pipeline run stores its viable (fresh, relevant) candidates here so
    the user can browse alternatives, generate posts on demand, dismiss ones
    they don't want (recoverable), or request a fresh scrape for more.
    """
    __tablename__ = "story_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey("daily_runs.id"), nullable=True
    )

    url: Mapped[str] = mapped_column(String(1024), index=True)
    title: Mapped[str] = mapped_column(String(512))
    source_name: Mapped[str] = mapped_column(String(128))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    lead_image_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    category: Mapped[str] = mapped_column(String(32), default="security", index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    topic_key: Mapped[str | None] = mapped_column(String(256), nullable=True)
    authority: Mapped[float] = mapped_column(Float, default=0.8)
    audience: Mapped[str] = mapped_column(String(32), default="consumer")

    status: Mapped[CandidateStatus] = mapped_column(
        Enum(CandidateStatus), default=CandidateStatus.pending, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


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
    is_update: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str] = mapped_column(String(32), default="security", index=True)

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
    metrics: Mapped["PostMetrics | None"] = relationship(
        back_populates="post", uselist=False, cascade="all, delete-orphan"
    )


class PostMetrics(Base):
    """Manually-entered LinkedIn performance for a posted draft.

    Kept in a separate table so the future LinkedIn API integration can
    populate it (linkedin_post_id / last_fetched_at) without touching the
    posts schema. One row per post (post_id is unique).
    """
    __tablename__ = "post_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id"), unique=True, index=True
    )

    impressions: Mapped[int] = mapped_column(Integer, default=0)
    reactions: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    reposts: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    # Reserved for the future LinkedIn API integration (no schema change needed).
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    post: Mapped["Post"] = relationship(back_populates="metrics")
