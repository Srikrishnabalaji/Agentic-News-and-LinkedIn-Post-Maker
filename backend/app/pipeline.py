"""The daily pipeline: scrape → rank → generate → image → persist → notify.

Invoked by the Railway cron job (via the secured /run/pipeline endpoint)
every morning, and runnable manually for testing.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .generator.images import find_images
from .generator.post import generate_post
from .models import DailyRun, Post, PostStatus, RunStatus, Source
from .notify.email import send_digest
from .ranking.scorer import is_pivotal, rank, topic_key
from .scraper.article import enrich
from .scraper.rss import fetch_all
from .schemas import PipelineResult

log = logging.getLogger(__name__)


def _recent_posted_keys(db: Session, window_days: int) -> list[str]:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=window_days)
    rows = db.execute(
        select(Post.topic_key)
        .where(Post.status == PostStatus.posted)
        .where(Post.created_at >= cutoff)
        .where(Post.topic_key.is_not(None))
    ).scalars().all()
    return [k for k in rows if k]


def _prune_history(db: Session, retention_days: int) -> int:
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)
    old_posts = db.execute(
        select(Post).where(Post.created_at < cutoff)
    ).scalars().all()
    for p in old_posts:
        db.delete(p)
    old_sources = db.execute(
        select(Source).where(Source.scraped_at < cutoff)
    ).scalars().all()
    for s in old_sources:
        db.delete(s)
    db.commit()
    return len(old_posts)


def run_pipeline(db: Session) -> PipelineResult:
    run = DailyRun(status=RunStatus.running)
    db.add(run)
    db.commit()
    db.refresh(run)
    log.info("=== Pipeline run #%d started ===", run.id)

    try:
        recent_keys = _recent_posted_keys(db, settings.novelty_window_days)
        log.info("%d topics posted in last %d days (novelty filter)",
                 len(recent_keys), settings.novelty_window_days)

        candidates = fetch_all()
        run.num_candidates = len(candidates)

        selected = rank(candidates, recent_keys, top_n=settings.posts_per_run)
        log.info("Selected %d stories for generation", len(selected))

        # Fetch full article text for the chosen stories (better drafts).
        enrich(selected, limit=len(selected))

        created_posts: list[Post] = []
        for cand in selected:
            source = Source(
                run_id=run.id, url=cand.url, title=cand.title,
                source_name=cand.source_name, summary=cand.summary,
                full_text=cand.full_text, lead_image_url=cand.lead_image_url,
                published_at=(cand.published_at.replace(tzinfo=None)
                              if cand.published_at else None),
                topic_key=topic_key(cand.title), score=cand.score,
            )
            db.add(source)
            db.flush()

            gen = generate_post(cand)

            options = []
            image_url = None
            image_attribution = None
            if gen.image_recommended:
                options = find_images(
                    gen.image_query, cand.lead_image_url, cand.source_name
                )
                # Default to the first free/stock option (skip the flagged
                # article image as the auto-pick).
                stock = [o for o in options if o["source"] != "Article"]
                chosen = stock[0] if stock else (options[0] if options else None)
                if chosen:
                    image_url = chosen["url"]
                    image_attribution = chosen["attribution"]

            pivotal = is_pivotal(f"{cand.title} {cand.summary} {cand.full_text}")
            post = Post(
                run_id=run.id, source_id=source.id,
                headline=gen.headline, body=gen.body,
                format_type=gen.format_type, hashtags=gen.hashtags,
                char_count=len(gen.body),
                image_recommended=gen.image_recommended,
                image_reason=gen.image_reason, image_url=image_url,
                image_attribution=image_attribution, image_options=options,
                source_url=cand.url, source_name=cand.source_name,
                topic_key=topic_key(cand.title), is_pivotal=pivotal,
                status=PostStatus.draft,
            )
            db.add(post)
            created_posts.append(post)

        run.num_posts = len(created_posts)
        run.status = RunStatus.completed
        run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        for p in created_posts:
            db.refresh(p)

        pruned = _prune_history(db, settings.history_retention_days)
        if pruned:
            log.info("Pruned %d posts older than %d days",
                     pruned, settings.history_retention_days)

        email_sent = send_digest(created_posts)
        log.info("=== Pipeline run #%d complete: %d posts, email_sent=%s ===",
                 run.id, len(created_posts), email_sent)
        return PipelineResult(run_id=run.id, num_posts=len(created_posts),
                              email_sent=email_sent)

    except Exception as exc:
        log.exception("Pipeline run #%d failed", run.id)
        run.status = RunStatus.failed
        run.error = str(exc)[:1000]
        run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        raise
