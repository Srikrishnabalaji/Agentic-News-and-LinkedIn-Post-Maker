"""RSS source management: CRUD + curated/AI feed suggestions."""
from __future__ import annotations

import json
import logging
import re

import feedparser
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import RSSSource
from ..schemas import (
    AISuggestRequest,
    RSSSourceCreate,
    RSSSourceOut,
    RSSSourceUpdate,
    SourceSuggestion,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/sources", tags=["sources"])

_UA = "Mozilla/5.0 (compatible; QuantrixLabsBot/1.0; +https://quantrixlabs.com)"

# Pre-vetted feeds offered as one-click suggestions (not in the default seed).
_CURATED: list[dict] = [
    # Security
    {"name": "Schneier on Security", "url": "https://www.schneier.com/feed/atom/", "authority": 0.92, "category": "security"},
    {"name": "Graham Cluley", "url": "https://grahamcluley.com/feed/", "authority": 0.82, "category": "security"},
    {"name": "SANS Internet Storm Center", "url": "https://isc.sans.edu/rssfeed.xml", "authority": 0.88, "category": "security"},
    {"name": "Troy Hunt", "url": "https://www.troyhunt.com/rss/", "authority": 0.86, "category": "security"},
    {"name": "The Record", "url": "https://therecord.media/feed/", "authority": 0.85, "category": "security"},
    {"name": "Securelist (Kaspersky)", "url": "https://securelist.com/feed/", "authority": 0.84, "category": "security"},
    {"name": "Sophos News", "url": "https://news.sophos.com/en-us/feed/", "authority": 0.83, "category": "security"},
    {"name": "CISA Advisories", "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml", "authority": 0.9, "category": "security"},
    # Finance
    {"name": "WSJ Markets", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml", "authority": 0.9, "category": "finance"},
    {"name": "Investing.com", "url": "https://www.investing.com/rss/news.rss", "authority": 0.78, "category": "finance"},
    {"name": "Seeking Alpha", "url": "https://seekingalpha.com/feed.xml", "authority": 0.79, "category": "finance"},
    {"name": "Forbes Money", "url": "https://www.forbes.com/money/feed/", "authority": 0.8, "category": "finance"},
    {"name": "Kiplinger", "url": "https://www.kiplinger.com/feeds/all.rss", "authority": 0.8, "category": "finance"},
    {"name": "NerdWallet", "url": "https://www.nerdwallet.com/blog/feed/", "authority": 0.77, "category": "finance"},
    {"name": "Federal Reserve Press", "url": "https://www.federalreserve.gov/feeds/press_all.xml", "authority": 0.93, "category": "finance"},
]


def _validate_feed(url: str) -> str | None:
    """Return a feed title if the URL parses to a usable feed, else None."""
    try:
        parsed = feedparser.parse(url, agent=_UA)
    except Exception as exc:  # pragma: no cover - network variance
        log.warning("Feed validation error for %s: %s", url, exc)
        return None
    if parsed.entries:
        return (parsed.feed.get("title") if parsed.feed else None) or url
    # Some valid feeds momentarily return no entries; accept if it has a title.
    if parsed.feed and parsed.feed.get("title"):
        return parsed.feed.get("title")
    return None


@router.get("", response_model=list[RSSSourceOut])
def list_sources(db: Session = Depends(get_db)):
    return db.execute(
        select(RSSSource).order_by(RSSSource.category, RSSSource.name)
    ).scalars().all()


@router.get("/suggestions/curated", response_model=list[SourceSuggestion])
def curated_suggestions(
    category: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Vetted feeds not already in the DB (optionally filtered by category)."""
    existing = {
        u for (u,) in db.execute(select(RSSSource.url)).all()
    }
    out = []
    for c in _CURATED:
        if c["url"] in existing:
            continue
        if category and c["category"] != category:
            continue
        out.append(SourceSuggestion(**c))
    return out


@router.post("/suggestions/ai", response_model=list[SourceSuggestion])
def ai_suggestions(payload: AISuggestRequest, db: Session = Depends(get_db)):
    """Ask Gemini for 5 quality RSS feeds for the given category."""
    if not settings.has_gemini:
        raise HTTPException(503, "AI suggestions require a Gemini API key")

    category = payload.category if payload.category in ("security", "finance") else "security"
    existing_rows = db.execute(
        select(RSSSource.name, RSSSource.url).where(RSSSource.category == category)
    ).all()
    existing_names = ", ".join(n for n, _ in existing_rows) or "none"
    existing_urls = {u for _, u in existing_rows}

    prompt = f"""Suggest 5 high-quality, currently-active RSS feed URLs for {category} news \
suitable for a professional LinkedIn account covering {category} topics for a general audience.

We already use these, so suggest DIFFERENT ones: {existing_names}

Return ONLY a JSON array, no prose:
[{{"name": "Source Name", "url": "https://.../feed", "authority": 0.85, "category": "{category}"}}]
authority is a 0-1 editorial-trust estimate."""

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=800, temperature=0.4),
        )
        text = resp.text or ""
        match = re.search(r"\[.*\]", text, re.DOTALL)
        items = json.loads(match.group(0)) if match else []
    except Exception as exc:
        log.warning("AI source suggestion failed: %s", exc)
        raise HTTPException(502, "AI suggestion failed, try again")

    out = []
    seen = set()
    for it in items:
        url = str(it.get("url", "")).strip()
        if not url or url in existing_urls or url in seen:
            continue
        seen.add(url)
        try:
            authority = float(it.get("authority", 0.8))
        except (TypeError, ValueError):
            authority = 0.8
        out.append(SourceSuggestion(
            name=str(it.get("name", "Unknown")).strip(),
            url=url,
            authority=max(0.0, min(1.0, authority)),
            category=category,
        ))
    return out


@router.post("", response_model=RSSSourceOut, status_code=201)
def add_source(payload: RSSSourceCreate, db: Session = Depends(get_db)):
    url = payload.url.strip()
    if not url.startswith(("http://", "https://")):
        raise HTTPException(400, "URL must start with http:// or https://")

    existing = db.execute(
        select(RSSSource).where(RSSSource.url == url)
    ).scalars().first()
    if existing:
        raise HTTPException(409, "That feed URL is already in your sources")

    title = _validate_feed(url)
    if not title:
        raise HTTPException(400, "Could not read a valid RSS feed at that URL")

    category = payload.category if payload.category in ("security", "finance") else "security"
    source = RSSSource(
        name=payload.name.strip() or title,
        url=url,
        category=category,
        authority=max(0.0, min(1.0, payload.authority)),
        audience=payload.audience or "consumer",
        enabled=True,
        is_custom=True,
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.patch("/{source_id}", response_model=RSSSourceOut)
def update_source(
    source_id: int, payload: RSSSourceUpdate, db: Session = Depends(get_db)
):
    source = db.get(RSSSource, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    data = payload.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        source.name = data["name"].strip() or source.name
    if "authority" in data and data["authority"] is not None:
        source.authority = max(0.0, min(1.0, float(data["authority"])))
    if "enabled" in data and data["enabled"] is not None:
        source.enabled = bool(data["enabled"])
    db.commit()
    db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: int, db: Session = Depends(get_db)):
    source = db.get(RSSSource, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    if not source.is_custom:
        raise HTTPException(403, "Built-in sources can be disabled but not deleted")
    db.delete(source)
    db.commit()
