"""RSS feed fetching and normalization.

Uses feedparser (no API keys). Produces a flat list of candidate articles
with normalized fields, deduplicated by URL and TF-IDF cosine similarity
so that the same story covered by multiple sources appears only once
(highest-authority source is kept).
"""
from __future__ import annotations

import html
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import feedparser

from ..utils import TFIDFVectorizer, same_story
from .sources import SOURCES, NewsSource

log = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible; QuantrixLabsBot/1.0; +https://quantrixlabs.com)"


@dataclass
class Candidate:
    source_name: str
    authority: float
    audience: str
    title: str
    url: str
    summary: str = ""
    published_at: datetime | None = None
    lead_image_url: str | None = None
    full_text: str = ""
    score: float = 0.0
    score_breakdown: dict = field(default_factory=dict)


def _parse_date(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        val = getattr(entry, key, None) or entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    return None


def _extract_feed_image(entry) -> str | None:
    media = entry.get("media_content") or entry.get("media_thumbnail")
    if media and isinstance(media, list) and media:
        url = media[0].get("url")
        if url:
            return url
    for link in entry.get("links", []):
        if link.get("rel") == "enclosure" and "image" in link.get("type", ""):
            return link.get("href")
    return None


def _clean_summary(entry) -> str:
    raw = entry.get("summary", "") or entry.get("description", "")
    if not raw:
        return ""
    if "<" in raw:
        from bs4 import BeautifulSoup
        raw = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    return html.unescape(raw).strip()[:1000]


def _normalise_title(title: str) -> str:
    """Lowercase alphanumeric tokens only — used as TF-IDF input."""
    import re
    tokens = re.findall(r"[a-z0-9]+", title.lower())
    # Drop very short tokens that add noise but keep numbers (e.g. CVE years)
    return " ".join(t for t in tokens if len(t) > 2)


def fetch_source(source: NewsSource, max_items: int = 15) -> list[Candidate]:
    out: list[Candidate] = []
    try:
        parsed = feedparser.parse(source.feed_url, agent=_UA)
    except Exception as exc:  # pragma: no cover
        log.warning("Failed to parse %s: %s", source.name, exc)
        return out

    if getattr(parsed, "bozo", 0) and not parsed.entries:
        log.warning("Feed %s returned no entries (bozo=%s)", source.name, parsed.bozo)
        return out

    for entry in parsed.entries[:max_items]:
        url = entry.get("link")
        title = html.unescape((entry.get("title") or "").strip())
        if not url or not title:
            continue
        out.append(
            Candidate(
                source_name=source.name,
                authority=source.authority,
                audience=source.audience,
                title=title,
                url=url,
                summary=_clean_summary(entry),
                published_at=_parse_date(entry),
                lead_image_url=_extract_feed_image(entry),
            )
        )
    log.info("Fetched %d items from %s", len(out), source.name)
    return out


def deduplicate(
    candidates: list[Candidate],
    cosine_threshold: float = 0.20,
) -> list[Candidate]:
    """Remove URL duplicates and same-story cross-source duplicates.

    Same-story detection uses a two-signal hybrid (see `same_story()` in
    utils.py): TF-IDF cosine similarity catches stories with substantial
    vocabulary overlap, while a shared-rare-entity check catches stories
    linked only by an entity name when the headlines use completely different
    vocabulary (e.g. "Rokarolla steals PINs" vs "Rokarolla gains full device
    control" — same story, cosine < threshold, but "rokarolla" is rare in
    the corpus).

    When two candidates are judged the same story, the higher-authority
    source is kept so the strongest editorial voice represents the topic.
    """
    # --- Step 1: remove exact URL duplicates ---
    seen_urls: set[str] = set()
    url_deduped: list[Candidate] = []
    for c in candidates:
        norm = c.url.split("?")[0].rstrip("/")
        if norm not in seen_urls:
            seen_urls.add(norm)
            url_deduped.append(c)

    if len(url_deduped) <= 1:
        return url_deduped

    # --- Step 2: build TF-IDF on the full candidate set ---
    keys = [_normalise_title(c.title) for c in url_deduped]
    vectorizer = TFIDFVectorizer(keys)
    vectors = [vectorizer.vectorize(k) for k in keys]

    # --- Step 3: greedy dedup, preferring higher-authority sources ---
    # Sort highest authority first so the best source for each story wins.
    order = sorted(range(len(url_deduped)),
                   key=lambda i: url_deduped[i].authority, reverse=True)

    kept_indices: set[int] = set()
    kept_vecs: list[dict[str, float]] = []
    kept_keys: list[str] = []

    for i in order:
        vec = vectors[i]
        key_i = keys[i]
        if any(
            same_story(vec, kv, key_i, kk, vectorizer, cosine_threshold)
            for kv, kk in zip(kept_vecs, kept_keys)
        ):
            continue          # same story already represented by a better source
        kept_indices.add(i)
        kept_vecs.append(vec)
        kept_keys.append(key_i)

    # Return in the original fetch order (preserves recency sorting).
    return [c for i, c in enumerate(url_deduped) if i in kept_indices]


def fetch_all(max_items_per_source: int = 15) -> list[Candidate]:
    all_candidates: list[Candidate] = []
    for source in SOURCES:
        all_candidates.extend(fetch_source(source, max_items_per_source))
    deduped = deduplicate(all_candidates)
    log.info("Fetched %d candidates, %d after dedup", len(all_candidates), len(deduped))
    return deduped
