"""Story discovery & replacement: browse candidate stories, generate posts
from them on demand, request more (re-scrape), and dismiss/recover them."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..generator.build import build_draft
from ..models import (
    CandidateStatus,
    DailyRun,
    Post,
    RunStatus,
    StoryCandidate,
)
from ..ranking.freshness import check_freshness_batch
from ..ranking.scorer import rank, topic_key
from ..scraper.rss import Candidate, fetch_all
from ..schemas import (
    CandidateGenerateRequest,
    CandidateListOut,
    CandidateOut,
    PostOut,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/candidates", tags=["candidates"])

_VALID = ("security", "finance")


def _check_category(category: str) -> str:
    if category not in _VALID:
        raise HTTPException(400, f"category must be one of {_VALID}")
    return category


def _promote_pending(db: Session, category: str, limit: int) -> None:
    """Move the next `limit` highest-scoring pending candidates to 'shown'."""
    pending = db.execute(
        select(StoryCandidate)
        .where(StoryCandidate.category == category)
        .where(StoryCandidate.status == CandidateStatus.pending)
        .order_by(StoryCandidate.score.desc())
        .limit(limit)
    ).scalars().all()
    for c in pending:
        c.status = CandidateStatus.shown
    if pending:
        db.commit()


def _build_list(db: Session, category: str) -> CandidateListOut:
    shown = db.execute(
        select(StoryCandidate)
        .where(StoryCandidate.category == category)
        .where(StoryCandidate.status == CandidateStatus.shown)
        .order_by(StoryCandidate.score.desc())
    ).scalars().all()
    dismissed = db.execute(
        select(func.count(StoryCandidate.id))
        .where(StoryCandidate.category == category)
        .where(StoryCandidate.status == CandidateStatus.dismissed)
    ).scalar() or 0
    remaining = db.execute(
        select(func.count(StoryCandidate.id))
        .where(StoryCandidate.category == category)
        .where(StoryCandidate.status == CandidateStatus.pending)
    ).scalar() or 0
    return CandidateListOut(
        candidates=shown, dismissed_count=dismissed, has_more=remaining > 0
    )


def _rescrape(db: Session, category: str) -> int:
    """Fetch fresh stories for a category, keep novel+relevant ones not already
    stored, and insert them as pending. Returns the number inserted."""
    data = fetch_all(db)
    cands = data.get(category, [])
    existing = {
        u for (u,) in db.execute(
            select(StoryCandidate.url).where(StoryCandidate.category == category)
        ).all()
    }
    fresh = [c for c in cands if c.url not in existing]
    if not fresh:
        return 0

    ranked = rank(fresh, recent_posted_keys=[], top_n=15)
    verdicts = check_freshness_batch(ranked, category=category)
    inserted = 0
    for cand in ranked:
        v = verdicts.get(cand.url, {"is_novel": True, "is_relevant": True})
        if not (v.get("is_novel", True) and v.get("is_relevant", True)):
            continue
        db.add(StoryCandidate(
            run_id=None, url=cand.url, title=cand.title,
            source_name=cand.source_name, summary=cand.summary, full_text=None,
            lead_image_url=cand.lead_image_url,
            published_at=(cand.published_at.replace(tzinfo=None)
                          if cand.published_at else None),
            category=category, score=cand.score,
            topic_key=topic_key(cand.title),
            authority=cand.authority, audience=cand.audience,
            status=CandidateStatus.pending,
        ))
        inserted += 1
    if inserted:
        db.commit()
    return inserted


def _latest_run_id(db: Session) -> int | None:
    return db.execute(
        select(DailyRun.id)
        .where(DailyRun.status == RunStatus.completed)
        .order_by(DailyRun.id.desc())
    ).scalars().first()


def _generate_from_candidate(db: Session, c: StoryCandidate, run_id: int | None) -> Post:
    """Run the generation pipeline for one stored candidate and persist a draft."""
    cand = Candidate(
        source_name=c.source_name, authority=c.authority, audience=c.audience,
        title=c.title, url=c.url, summary=c.summary or "",
        published_at=c.published_at, lead_image_url=c.lead_image_url,
        full_text=c.full_text or "",
    )
    post = build_draft(db, cand, c.category, score=c.score, run_id=run_id)
    c.status = CandidateStatus.generated
    return post


@router.get("", response_model=CandidateListOut)
def list_candidates(
    category: str = Query(...),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Promote the next batch of pending candidates to shown and return all
    currently-shown candidates for the category (so previously-seen ones can
    be revisited)."""
    _check_category(category)
    _promote_pending(db, category, limit)
    return _build_list(db, category)


@router.post("/more", response_model=CandidateListOut)
def more_candidates(
    category: str = Query(...),
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """Show the next batch; if the pending pool is empty, re-scrape first."""
    _check_category(category)
    remaining = db.execute(
        select(func.count(StoryCandidate.id))
        .where(StoryCandidate.category == category)
        .where(StoryCandidate.status == CandidateStatus.pending)
    ).scalar() or 0
    if remaining == 0:
        added = _rescrape(db, category)
        log.info("[candidates] re-scrape for %s added %d", category, added)
    _promote_pending(db, category, limit)
    return _build_list(db, category)


@router.get("/dismissed", response_model=list[CandidateOut])
def dismissed_candidates(
    category: str = Query(...),
    db: Session = Depends(get_db),
):
    """All dismissed candidates for a category, for the recovery panel."""
    _check_category(category)
    return db.execute(
        select(StoryCandidate)
        .where(StoryCandidate.category == category)
        .where(StoryCandidate.status == CandidateStatus.dismissed)
        .order_by(StoryCandidate.score.desc())
    ).scalars().all()


@router.post("/generate", response_model=list[PostOut])
def generate_from_candidates(
    payload: CandidateGenerateRequest, db: Session = Depends(get_db)
):
    """Generate a draft post for each selected candidate."""
    if not payload.candidate_ids:
        raise HTTPException(400, "No candidates selected")

    run_id = _latest_run_id(db)
    created: list[Post] = []
    for cid in payload.candidate_ids:
        c = db.get(StoryCandidate, cid)
        if not c or c.status == CandidateStatus.generated:
            continue
        try:
            created.append(_generate_from_candidate(db, c, run_id))
        except Exception:
            log.exception("Failed to generate post from candidate %s", cid)

    if not created:
        raise HTTPException(502, "Could not generate posts from the selection")

    db.commit()
    for p in created:
        db.refresh(p)
    return created


@router.patch("/{candidate_id}/dismiss", response_model=CandidateOut)
def dismiss_candidate(candidate_id: int, db: Session = Depends(get_db)):
    c = db.get(StoryCandidate, candidate_id)
    if not c:
        raise HTTPException(404, "Candidate not found")
    c.status = CandidateStatus.dismissed
    db.commit()
    db.refresh(c)
    return c


@router.patch("/{candidate_id}/undismiss", response_model=CandidateOut)
def undismiss_candidate(candidate_id: int, db: Session = Depends(get_db)):
    c = db.get(StoryCandidate, candidate_id)
    if not c:
        raise HTTPException(404, "Candidate not found")
    c.status = CandidateStatus.shown
    db.commit()
    db.refresh(c)
    return c
