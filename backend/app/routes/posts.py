"""Post CRUD, regeneration, and status transitions."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..generator.images import find_images
from ..generator.post import generate_post, rephrase_body
from ..models import DailyRun, Post, PostStatus, RunStatus, Source
from ..ranking.scorer import is_pivotal, topic_key
from ..schemas import PostOut, PostUpdate, StatusUpdate
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
):
    stmt = select(Post).order_by(Post.created_at.desc())
    if status:
        stmt = stmt.where(Post.status == status)
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
