"""Shared helper to turn a scraped Candidate into a persisted draft Post.

Used by the on-demand flows (story-candidate generation and live search)
so they produce posts identically to the daily pipeline.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Post, PostStatus, Source
from ..ranking.scorer import is_pivotal, topic_key
from ..scraper.article import enrich
from ..scraper.rss import Candidate
from .images import find_images
from .post import generate_post


def build_draft(
    db: Session,
    cand: Candidate,
    category: str,
    *,
    score: float = 0.0,
    run_id: int | None = None,
) -> Post:
    """Enrich, generate, find an image, and persist a draft Post (+ its Source).

    Caller is responsible for the surrounding commit/refresh.
    """
    if not cand.full_text:
        enrich([cand], limit=1)

    gen = generate_post(cand, category=category)

    options: list = []
    image_url = None
    image_attribution = None
    if gen.image_recommended:
        options = find_images(gen.image_query, cand.lead_image_url, cand.source_name)
        stock = [o for o in options if o["source"] != "Article"]
        chosen = stock[0] if stock else (options[0] if options else None)
        if chosen:
            image_url = chosen["url"]
            image_attribution = chosen["attribution"]

    source = Source(
        run_id=run_id, url=cand.url, title=cand.title,
        source_name=cand.source_name, summary=cand.summary,
        full_text=cand.full_text, lead_image_url=cand.lead_image_url,
        published_at=(cand.published_at.replace(tzinfo=None)
                      if cand.published_at else None),
        topic_key=topic_key(cand.title), score=score, category=category,
    )
    db.add(source)
    db.flush()

    pivotal = is_pivotal(f"{cand.title} {cand.summary} {cand.full_text}")
    post = Post(
        run_id=run_id, source_id=source.id,
        headline=gen.headline, body=gen.body,
        format_type=gen.format_type, hashtags=gen.hashtags,
        char_count=len(gen.body),
        image_recommended=gen.image_recommended,
        image_reason=gen.image_reason, image_url=image_url,
        image_attribution=image_attribution, image_options=options,
        source_url=cand.url, source_name=cand.source_name,
        topic_key=topic_key(cand.title), is_pivotal=pivotal, is_update=False,
        status=PostStatus.draft, category=category,
    )
    db.add(post)
    return post
