"""Post CRUD, regeneration, and status transitions."""
from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..generator.images import find_images
from ..generator.post import generate_post, rephrase_body
from ..models import DailyRun, Post, PostMetrics, PostStatus, RunStatus, Source
from ..ranking.scorer import is_pivotal, topic_key
from ..schemas import MetricsOut, MetricsUpdate, PostOut, PostUpdate, StatusUpdate
from ..scraper.rss import Candidate

router = APIRouter(prefix="/posts", tags=["posts"])


def _get_post(db: Session, post_id: int) -> Post:
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    return post


@router.get("/today", response_model=list[PostOut])
def posts_today(db: Session = Depends(get_db)):
    """Posts from the most recent completed run."""
    run = db.execute(
        select(DailyRun)
        .where(DailyRun.status == RunStatus.completed)
        .order_by(DailyRun.id.desc())
    ).scalars().first()
    if not run:
        return []
    return db.execute(
        select(Post).where(Post.run_id == run.id).order_by(Post.id)
    ).scalars().all()


@router.get("/history", response_model=list[PostOut])
def posts_history(
    db: Session = Depends(get_db),
    limit: int = Query(50, le=200),
    offset: int = 0,
    status: PostStatus | None = None,
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = None,
    sort_by: str = Query("date", pattern="^(date|date_asc|engagement)$"),
):
    """History with filtering (category/date/text), sorting, and pagination.

    `sort_by=engagement` ranks by reactions + comments*2 + reposts*3 using a
    LEFT JOIN onto post_metrics, so posts without metrics sort last (score 0).
    """
    stmt = select(Post)

    if status:
        stmt = stmt.where(Post.status == status)
    if category:
        stmt = stmt.where(Post.category == category)
    if date_from:
        stmt = stmt.where(Post.created_at >= datetime.combine(date_from, time.min))
    if date_to:
        # Inclusive of the whole end day.
        stmt = stmt.where(Post.created_at <= datetime.combine(date_to, time.max))
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Post.headline.ilike(like), Post.body.ilike(like)))

    if sort_by == "engagement":
        engagement = (
            func.coalesce(PostMetrics.reactions, 0)
            + func.coalesce(PostMetrics.comments, 0) * 2
            + func.coalesce(PostMetrics.reposts, 0) * 3
        )
        stmt = stmt.outerjoin(PostMetrics, PostMetrics.post_id == Post.id).order_by(
            engagement.desc(), Post.created_at.desc()
        )
    elif sort_by == "date_asc":
        stmt = stmt.order_by(Post.created_at.asc())
    else:
        stmt = stmt.order_by(Post.created_at.desc())

    return db.execute(stmt.limit(limit).offset(offset)).scalars().all()


@router.get("/{post_id}", response_model=PostOut)
def get_post(post_id: int, db: Session = Depends(get_db)):
    return _get_post(db, post_id)


@router.put("/{post_id}", response_model=PostOut)
def update_post(post_id: int, payload: PostUpdate, db: Session = Depends(get_db)):
    post = _get_post(db, post_id)
    data = payload.model_dump(exclude_unset=True)
    if "body" in data and data["body"] is not None:
        post.body = data["body"]
        post.char_count = len(data["body"])
    for field in ("headline", "hashtags", "image_url", "image_attribution"):
        if field in data:
            setattr(post, field, data[field])
    db.commit()
    db.refresh(post)
    return post


@router.post("/{post_id}/status", response_model=PostOut)
def set_status(post_id: int, payload: StatusUpdate, db: Session = Depends(get_db)):
    post = _get_post(db, post_id)
    post.status = payload.status
    if payload.status == PostStatus.posted and not post.posted_at:
        post.posted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(post)
    return post


@router.get("/{post_id}/metrics", response_model=MetricsOut)
def get_metrics(post_id: int, db: Session = Depends(get_db)):
    """Return manually-recorded LinkedIn performance for a post."""
    post = _get_post(db, post_id)
    if not post.metrics:
        raise HTTPException(404, "No metrics recorded for this post")
    return post.metrics


@router.put("/{post_id}/metrics", response_model=MetricsOut)
def upsert_metrics(
    post_id: int, payload: MetricsUpdate, db: Session = Depends(get_db)
):
    """Create or update performance metrics for a post (upsert)."""
    post = _get_post(db, post_id)
    metrics = post.metrics
    if metrics is None:
        metrics = PostMetrics(post_id=post.id)
        db.add(metrics)
    data = payload.model_dump(exclude_unset=True)
    for field in ("impressions", "reactions", "comments", "reposts"):
        if data.get(field) is not None:
            setattr(metrics, field, max(0, int(data[field])))
    db.commit()
    db.refresh(metrics)
    return metrics


@router.post("/{post_id}/rephrase", response_model=PostOut)
def rephrase_post(
    post_id: int,
    tone: str = Query("punchy", pattern="^(punchy|formal|shorter)$"),
    db: Session = Depends(get_db),
):
    """Rephrase the post body in a chosen tone (AI suggestion)."""
    post = _get_post(db, post_id)
    post.body = rephrase_body(post.body, tone)
    post.char_count = len(post.body)
    db.commit()
    db.refresh(post)
    return post


@router.post("/{post_id}/regenerate", response_model=PostOut)
def regenerate_post(post_id: int, db: Session = Depends(get_db)):
    """Re-run Claude on the post's original source article."""
    post = _get_post(db, post_id)
    source = db.get(Source, post.source_id) if post.source_id else None
    if not source:
        raise HTTPException(400, "Original source unavailable for regeneration")

    cand = Candidate(
        source_name=source.source_name, authority=0.8, audience="consumer",
        title=source.title, url=source.url, summary=source.summary or "",
        published_at=source.published_at, lead_image_url=source.lead_image_url,
        full_text=source.full_text or "",
    )
    gen = generate_post(cand, category=post.category)

    post.headline = gen.headline
    post.body = gen.body
    post.format_type = gen.format_type
    post.hashtags = gen.hashtags
    post.char_count = len(gen.body)
    post.image_recommended = gen.image_recommended
    post.image_reason = gen.image_reason
    post.is_pivotal = is_pivotal(f"{source.title} {source.full_text}")
    post.topic_key = topic_key(source.title)

    if gen.image_recommended:
        options = find_images(gen.image_query, source.lead_image_url,
                              source.source_name)
        post.image_options = options
        stock = [o for o in options if o["source"] != "Article"]
        chosen = stock[0] if stock else (options[0] if options else None)
        post.image_url = chosen["url"] if chosen else None
        post.image_attribution = chosen["attribution"] if chosen else None

    post.status = PostStatus.draft
    db.commit()
    db.refresh(post)
    return post
