"""Image sourcing for posts.

Aggregates free, watermark-free image options from multiple providers:

  1. Unsplash       (free license, no watermark)   -- needs free API key
  2. Pexels         (free license, no watermark)   -- needs free API key
  3. Pixabay        (royalty-free)                 -- needs free API key
  4. Openverse      (Creative Commons search)      -- no key required
  5. Wikimedia      (freely licensed)              -- no key required
  6. Article image  (og:image)                     -- license UNKNOWN, flagged

Every option carries attribution + a license note so the human reviewer can
respect reuse terms. The article image is included but clearly marked as
needing verification, per QuantrixLabs' "properly cited and allowed" rule.

For initial post generation, a small budget (max_options=4) is used.
For user-triggered searches, the endpoint passes max_options=20 to fill the
expanded modal grid with meaningful variety.
"""
from __future__ import annotations

import logging

import httpx

from ..config import settings

log = logging.getLogger(__name__)

_TIMEOUT = 12.0


def _image_option(url, thumb, attribution, source, license_note, source_url=""):
    return {
        "url": url,
        "thumb": thumb or url,
        "attribution": attribution,
        "source": source,
        "license": license_note,
        "source_url": source_url,
    }


def _from_unsplash(query: str, n: int, page: int = 1) -> list[dict]:
    if not settings.unsplash_access_key:
        return []
    try:
        r = httpx.get(
            "https://api.unsplash.com/search/photos",
            params={"query": query, "per_page": min(n, 30), "page": page, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {settings.unsplash_access_key}"},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        out = []
        for p in r.json().get("results", []):
            name = p.get("user", {}).get("name", "Unknown")
            out.append(_image_option(
                p["urls"]["regular"], p["urls"]["small"],
                f"Photo by {name} on Unsplash", "Unsplash",
                "Unsplash License (free, no attribution required)",
                p.get("links", {}).get("html", ""),
            ))
        return out
    except Exception as exc:
        log.warning("Unsplash search failed: %s", exc)
        return []


def _from_pexels(query: str, n: int, page: int = 1) -> list[dict]:
    if not settings.pexels_api_key:
        return []
    try:
        r = httpx.get(
            "https://api.pexels.com/v1/search",
            params={"query": query, "per_page": min(n, 80), "page": page, "orientation": "landscape"},
            headers={"Authorization": settings.pexels_api_key},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        out = []
        for p in r.json().get("photos", []):
            out.append(_image_option(
                p["src"]["large"], p["src"]["medium"],
                f"Photo by {p.get('photographer', 'Unknown')} on Pexels", "Pexels",
                "Pexels License (free, no attribution required)",
                p.get("url", ""),
            ))
        return out
    except Exception as exc:
        log.warning("Pexels search failed: %s", exc)
        return []


def _from_pixabay(query: str, n: int, page: int = 1) -> list[dict]:
    if not settings.pixabay_api_key:
        return []
    try:
        r = httpx.get(
            "https://pixabay.com/api/",
            params={
                "key": settings.pixabay_api_key,
                "q": query,
                "image_type": "photo",
                "per_page": max(3, min(n, 200)),  # Pixabay: valid range 3-200
                "page": page,
                "safesearch": "true",
                "orientation": "horizontal",
            },
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        out = []
        for p in r.json().get("hits", []):
            out.append(_image_option(
                p.get("webformatURL", p.get("largeImageURL", "")),
                p.get("previewURL", ""),
                f"Photo by {p.get('user', 'Unknown')} on Pixabay",
                "Pixabay",
                "Pixabay License (free, no attribution required)",
                p.get("pageURL", ""),
            ))
        return out
    except Exception as exc:
        log.warning("Pixabay search failed: %s", exc)
        return []


def _from_openverse(query: str, n: int, page: int = 1) -> list[dict]:
    """Creative Commons image search via Openverse (no API key needed).

    Uses open CC licenses (CC0, CC BY, CC BY-SA) — all allow reuse with
    attribution. No `license_type` restriction so results are plentiful.
    """
    try:
        r = httpx.get(
            "https://api.openverse.org/v1/images/",
            params={
                "q": query,
                "page_size": min(n, 20),
                "page": page,
                "license": "cc0,by,by-sa",
            },
            headers={"User-Agent": "QuantrixLabsBot/1.0 (quantrixlabs@gmail.com)"},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        out = []
        for p in r.json().get("results", []):
            url = p.get("url", "")
            thumb = p.get("thumbnail") or url
            if not url:
                continue
            creator = p.get("creator") or "Unknown"
            lic = (p.get("license") or "cc").upper()
            ver = p.get("license_version", "")
            lic_str = "CC0 (Public Domain)" if lic == "CC0" else f"CC {lic} {ver}".strip()
            out.append(_image_option(
                url, thumb,
                f"Photo by {creator} via Openverse",
                "Openverse",
                f"{lic_str} — attribution required",
                p.get("foreign_landing_url", ""),
            ))
        return out
    except Exception as exc:
        log.warning("Openverse search failed: %s", exc)
        return []


def _from_wikimedia(query: str, n: int, page: int = 1) -> list[dict]:
    # Request 4× more than needed because Commons returns PDFs and SVGs that
    # get filtered out — bitmap images are a subset of all File: namespace hits.
    fetch = min(n * 4, 50)
    offset = (page - 1) * fetch
    try:
        r = httpx.get(
            "https://commons.wikimedia.org/w/api.php",
            params={
                "action": "query", "format": "json", "generator": "search",
                "gsrsearch": f"filetype:bitmap {query}",
                "gsrnamespace": 6, "gsrlimit": fetch,
                "gsroffset": offset,
                "prop": "imageinfo", "iiprop": "url|extmetadata",
                "iiurlwidth": 800,
            },
            headers={"User-Agent": "QuantrixLabsBot/1.0 (quantrixlabs@gmail.com)"},
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        out = []
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            url = info.get("url")
            if not url or not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                continue
            meta = info.get("extmetadata", {})
            artist = meta.get("Artist", {}).get("value", "Wikimedia Commons")
            from bs4 import BeautifulSoup
            artist = BeautifulSoup(artist, "html.parser").get_text(" ", strip=True)
            lic = meta.get("LicenseShortName", {}).get("value", "See Commons page")
            out.append(_image_option(
                url, info.get("thumburl", url),
                f"{artist} via Wikimedia Commons", "Wikimedia Commons",
                f"{lic} (attribution may be required)",
                page.get("title", ""),
            ))
            if len(out) >= n:
                break
        return out
    except Exception as exc:
        log.warning("Wikimedia search failed: %s", exc)
        return []


def find_images(query: str, article_image: str | None, source_name: str,
                max_options: int = 4, page: int = 1) -> list[dict]:
    """Return up to `max_options` image choices for a post.

    When max_options is small (initial pipeline generation), we stop as soon
    as each source fills the budget. When max_options is large (user search),
    we pull from every provider and aggregate for maximum variety.
    `page` is passed to each provider for Load More pagination (1-based).
    Article image is only included on page 1 (it doesn't paginate).
    """
    include_article = article_image and page == 1
    stock_budget = max_options - (1 if include_article else 0)
    is_large_search = max_options >= 10

    stock: list[dict] = []

    if query and stock_budget > 0:
        if is_large_search:
            # For expanded modal: pull generously from every source.
            per_source = max(5, stock_budget // 4)
            for fetcher in (
                _from_unsplash,
                _from_pexels,
                _from_pixabay,
                _from_openverse,
                _from_wikimedia,
            ):
                stock.extend(fetcher(query, per_source, page))
        else:
            # For initial generation: stop early once the small budget is met.
            stock.extend(_from_unsplash(query, stock_budget, page))
            if len(stock) < stock_budget:
                stock.extend(_from_pexels(query, stock_budget - len(stock), page))
            if len(stock) < stock_budget:
                stock.extend(_from_pixabay(query, stock_budget - len(stock), page))
            if len(stock) < stock_budget:
                stock.extend(_from_openverse(query, stock_budget - len(stock), page))
            if len(stock) < stock_budget:
                stock.extend(_from_wikimedia(query, stock_budget - len(stock), page))

    # De-dupe by URL and trim.
    seen, options = set(), []
    for opt in stock:
        if opt["url"] and opt["url"] not in seen:
            seen.add(opt["url"])
            options.append(opt)
    options = options[:stock_budget]

    if include_article and article_image not in seen:
        options.append(_image_option(
            article_image, article_image,
            f"Lead image from {source_name}", "Article",
            "UNKNOWN — verify reuse rights before publishing",
            "",
        ))

    return options[:max_options]
