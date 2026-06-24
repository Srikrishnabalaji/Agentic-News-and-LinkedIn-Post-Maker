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
from .models import (
    CandidateStatus,
    DailyRun,
    Post,
    PostStatus,
    RunStatus,
    Source,
    StoryCandidate,
)
from .notify.email import send_digest
from .ranking.freshness import check_freshness_batch
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
    old_candidates = db.execute(
        select(StoryCandidate).where(StoryCandidate.created_at < cutoff)
    ).scalars().all()
    for c in old_candidates:
        db.delete(c)
    db.commit()
    return len(old_posts)


def run_pipeline(db: Session) -> PipelineResult:
    run = DailyRun(status=RunStatus.running)
    db.add(run)
    db.commit()
    db.refresh(run)
    log.info("=== Pipeline run #%d started ===", run.id)

    try:
        now = datetime.now(timezone.utc)
        recent_keys = _recent_posted_keys(db, settings.novelty_window_days)
        log.info("%d topics posted in last %d days (novelty filter)",
                 len(recent_keys), settings.novelty_window_days)

        candidates_by_category = fetch_all(db)
        total_candidates = sum(len(v) for v in candidates_by_category.values())
        run.num_candidates = total_candidates

        created_posts: list[Post] = []

        for category, candidates in candidates_by_category.items():
            # --- Stage 1: rank a larger pool so freshness filtering has room ---
            OVER_SELECT = max(15, settings.posts_per_run * 3)
            pool = rank(candidates, recent_keys, top_n=OVER_SELECT, now=now)
            log.info("[%s] Ranked %d diverse candidates for freshness check", category, len(pool))

            # --- Stage 2: batched Gemini freshness check on top 15 ---
            CHECK_N = min(15, len(pool))
            verdicts = check_freshness_batch(pool[:CHECK_N], category=category, now=now)

            # --- Stage 3: build selection — Gemini-stale stories never appear ---
            #
            # Primary pool: all Gemini-confirmed novel candidates (in ranked order).
            #   These are used first regardless of exact age — Gemini already
            #   verified the core event is genuinely new.
            #
            # Padding: if primary pool < posts_per_run, draw from unchecked
            #   candidates (pool[CHECK_N:]) but ONLY if pub_date <= 72 h ago.
            #   We have no Gemini verdict for these, so we use date as a proxy.
            #
            # Stale (is_novel=False) candidates are NEVER used, even for padding.

            _72h = timedelta(hours=72)

            def _age_hours(cand) -> float:
                if cand.published_at is None:
                    return float("inf")
                pub = cand.published_at
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                return (now - pub).total_seconds() / 3600.0

            # All novel + relevant candidates from the Gemini-checked pool, in ranked order.
            all_novel: list = []
            for i, cand in enumerate(pool[:CHECK_N]):
                v = verdicts.get(cand.url, {"is_novel": True, "is_update": False, "is_relevant": True})
                cand.is_update = v["is_update"]
                if v["is_novel"] and v.get("is_relevant", True):
                    all_novel.append(cand)

            # Unchecked candidates (beyond CHECK_N) — only within 72 h.
            unchecked_72h: list = []
            for cand in pool[CHECK_N:]:
                cand.is_update = False
                if _age_hours(cand) <= 72:
                    unchecked_72h.append(cand)

            # Primary selection: top posts_per_run from Gemini-confirmed pool.
            selected = all_novel[:settings.posts_per_run]

            # Padding: remaining Gemini-novel, then unchecked-within-72h.
            if len(selected) < settings.posts_per_run:
                needed = settings.posts_per_run - len(selected)
                padding_pool = all_novel[settings.posts_per_run:] + unchecked_72h
                selected += padding_pool[:needed]

            log.info(
                "[%s] Final selection: %d/%d posts (wanted %d, %d Gemini-novel, %d padded)",
                category, len(selected), len(pool),
                settings.posts_per_run, len(all_novel),
                max(0, len(selected) - len(all_novel[:settings.posts_per_run])),
            )
            if len(selected) < settings.posts_per_run:
                log.info("[%s] Thin news day — only %d fresh stories", category, len(selected))

            enrich(selected, limit=len(selected))

            for cand in selected:
                source = Source(
                    run_id=run.id, url=cand.url, title=cand.title,
                    source_name=cand.source_name, summary=cand.summary,
                    full_text=cand.full_text, lead_image_url=cand.lead_image_url,
                    published_at=(cand.published_at.replace(tzinfo=None)
                                  if cand.published_at else None),
                    topic_key=topic_key(cand.title), score=cand.score,
                    category=category,
                )
                db.add(source)
                db.flush()

                gen = generate_post(cand, category=category)

                options = []
                image_url = None
                image_attribution = None
                if gen.image_recommended:
                    options = find_images(
                        gen.image_query, cand.lead_image_url, cand.source_name
                    )
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
                    is_update=cand.is_update,
                    status=PostStatus.draft, category=category,
                )
                db.add(post)
                created_posts.append(post)

            # --- Persist the viable pool for the discovery/replacement feature ---
            # Selected stories become posts (generated); the rest stay pending
            # so the user can browse and generate from them on demand.
            selected_urls = {c.url for c in selected}
            for cand in all_novel + unchecked_72h:
                cstatus = (
                    CandidateStatus.generated
                    if cand.url in selected_urls
                    else CandidateStatus.pending
                )
                db.add(StoryCandidate(
                    run_id=run.id, url=cand.url, title=cand.title,
                    source_name=cand.source_name, summary=cand.summary,
                    full_text=cand.full_text or None,
                    lead_image_url=cand.lead_image_url,
                    published_at=(cand.published_at.replace(tzinfo=None)
                                  if cand.published_at else None),
                    category=category, score=cand.score,
                    topic_key=topic_key(cand.title),
                    authority=cand.authority, audience=cand.audience,
                    status=cstatus,
                ))

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
