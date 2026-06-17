"""Full-article fetcher.

Pulls the article HTML for the top-ranked candidates so Claude has real
substance to write from, and extracts a license-friendly lead image
(og:image) as a fallback image source.
"""
from __future__ import annotations

import logging

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible; QuantrixLabsBot/1.0; +https://quantrixlabs.com)"
_HEADERS = {"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"}

# Tags whose text we never want as article body.
_NOISE = {"script", "style", "nav", "footer", "header", "aside", "form", "noscript"}


def _extract_main_text(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(_NOISE):
        tag.decompose()

    # Prefer semantic <article>, else the densest <div> by paragraph count.
    article = soup.find("article")
    container = article
    if container is None:
        best, best_count = None, 0
        for div in soup.find_all(["div", "main", "section"]):
            count = len(div.find_all("p"))
            if count > best_count:
                best, best_count = div, count
        container = best or soup

    paragraphs = [p.get_text(" ", strip=True) for p in container.find_all("p")]
    text = "\n\n".join(p for p in paragraphs if len(p) > 40)
    return text[:8000]


def _extract_og_image(soup: BeautifulSoup) -> str | None:
    for prop in ("og:image", "twitter:image", "twitter:image:src"):
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            return tag["content"]
    return None


def fetch_article(url: str, timeout: float = 15.0) -> tuple[str, str | None]:
    """Return (full_text, lead_image_url). Empty text on failure."""
    try:
        with httpx.Client(
            headers=_HEADERS, timeout=timeout, follow_redirects=True
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
    except Exception as exc:  # pragma: no cover - network variance
        log.warning("Article fetch failed for %s: %s", url, exc)
        return "", None

    soup = BeautifulSoup(resp.text, "html.parser")
    return _extract_main_text(soup), _extract_og_image(soup)


def enrich(candidates: list, limit: int) -> None:
    """Fetch full text for the top `limit` candidates, in place."""
    for cand in candidates[:limit]:
        text, og_image = fetch_article(cand.url)
        if text:
            cand.full_text = text
        if og_image and not cand.lead_image_url:
            cand.lead_image_url = og_image
