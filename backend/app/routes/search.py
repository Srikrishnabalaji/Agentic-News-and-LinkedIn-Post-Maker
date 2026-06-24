"""Search: stored posts (DB) and live web stories (Tavily) with on-demand
post generation from a live result."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..generator.build import build_draft
from ..models import DailyRun, Post, RunStatus
from ..scraper.rss import Candidate
from ..schemas import (
    LiveSearchResult,
    PostOut,
    SearchGenerateRequest,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/search", tags=["search"])


def _domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


@router.get("/stored", response_model=list[PostOut])
def search_stored(
    q: str = Query(..., min_length=1),
    category: str | None = None,
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    """Full-text-ish search over stored posts (headline + body)."""
    like = f"%{q.strip()}%"
    stmt = select(Post).where(
        or_(Post.headline.ilike(like), Post.body.ilike(like))
    )
    if category:
        stmt = stmt.where(Post.category == category)
    stmt = stmt.order_by(Post.created_at.desc()).limit(limit)
    return db.execute(stmt).scalars().all()


@router.get("/live", response_model=list[LiveSearchResult])
def search_live(q: str = Query(..., min_length=1)):
    """Live web search via Tavily. 503 if no API key is configured."""
    if not settings.has_tavily:
        raise HTTPException(503, "Live search is not configured (no Tavily API key)")

    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": settings.tavily_api_key,
                "query": q,
                "search_depth": "basic",
                "topic": "news",
                "max_results": 10,
            },
            timeout=20.0,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        log.warning("Tavily search failed: %s", exc)
        raise HTTPException(502, "Live search is temporarily unavailable")

    out: list[LiveSearchResult] = []
    for r in data.get("results", []):
        url = r.get("url", "")
        if not url:
            continue
        out.append(LiveSearchResult(
            title=r.get("title", "Untitled"),
            url=url,
            content=(r.get("content") or "")[:500],
            published_date=r.get("published_date"),
            source=_domain(url),
        ))
    return out


@router.post("/generate", response_model=PostOut)
def generate_from_search(
    payload: SearchGenerateRequest, db: Session = Depends(get_db)
):
    """Scrape a live result and generate a draft post from it."""
    url = payload.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "A valid article URL is required")

    category = payload.category if payload.category in ("security", "finance") else "security"
    cand = Candidate(
        source_name=_domain(url) or "Web",
        authority=0.8, audience="consumer",
        title=payload.title.strip() or url,
        url=url, summary=payload.summary or "",
        published_at=None, lead_image_url=None, full_text="",
    )

    run_id = db.execute(
        select(DailyRun.id)
        .where(DailyRun.status == RunStatus.completed)
        .order_by(DailyRun.id.desc())
    ).scalars().first()

    try:
        post = build_draft(db, cand, category, run_id=run_id)
    except Exception:
        log.exception("Search-to-post generation failed for %s", url)
        raise HTTPException(502, "Could not generate a post from that article")

    db.commit()
    db.refresh(post)
    return post
