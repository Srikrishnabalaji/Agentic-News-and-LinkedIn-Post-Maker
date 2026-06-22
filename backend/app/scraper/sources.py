"""News sources for QuantrixLabs — cybersecurity and finance feeds.

Each source has an `authority` weight (0-1) and a `category` that routes it
to the correct feed section (security or finance).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewsSource:
    name: str
    feed_url: str
    authority: float  # 0-1, editorial trust / signal quality
    audience: str     # "consumer" | "enterprise" | "government"
    category: str = "security"  # "security" | "finance"


SOURCES: list[NewsSource] = [
    # ── Cybersecurity ────────────────────────────────────────────────────
    NewsSource(
        "The Hacker News",
        "https://feeds.feedburner.com/TheHackersNews",
        0.85, "enterprise", "security",
    ),
    NewsSource(
        "Krebs on Security",
        "https://krebsonsecurity.com/feed/",
        0.95, "consumer", "security",
    ),
    NewsSource(
        "BleepingComputer",
        "https://www.bleepingcomputer.com/feed/",
        0.88, "consumer", "security",
    ),
    NewsSource(
        "CyberScoop",
        "https://cyberscoop.com/feed/",
        0.86, "enterprise", "security",
    ),
    NewsSource(
        "Dark Reading",
        "https://www.darkreading.com/rss.xml",
        0.82, "enterprise", "security",
    ),
    NewsSource(
        "Malwarebytes Labs",
        "https://www.malwarebytes.com/blog/feed/index.xml",
        0.84, "consumer", "security",
    ),
    NewsSource(
        "Help Net Security",
        "https://www.helpnetsecurity.com/feed/",
        0.78, "enterprise", "security",
    ),
    NewsSource(
        "SecurityWeek",
        "https://www.securityweek.com/feed/",
        0.83, "enterprise", "security",
    ),
    NewsSource(
        "Google Online Security Blog",
        "https://security.googleblog.com/feeds/posts/default",
        0.9, "consumer", "security",
    ),
    NewsSource(
        "WeLiveSecurity (ESET)",
        "https://www.welivesecurity.com/en/rss/feed/",
        0.8, "consumer", "security",
    ),

    # ── Security (additional) ─────────────────────────────────────────────
    NewsSource(
        "Ars Technica Security",
        "https://feeds.arstechnica.com/arstechnica/technology-lab",
        0.88, "consumer", "security",
    ),
    NewsSource(
        "The Register Security",
        "https://www.theregister.com/security/headlines.atom",
        0.85, "enterprise", "security",
    ),
    NewsSource(
        "Wired Security",
        "https://www.wired.com/category/security/feed/",
        0.86, "consumer", "security",
    ),
    NewsSource(
        "Infosecurity Magazine",
        "https://www.infosecurity-magazine.com/rss/news/",
        0.80, "enterprise", "security",
    ),

    # ── Finance ──────────────────────────────────────────────────────────
    NewsSource(
        "Bloomberg Markets",
        "https://feeds.bloomberg.com/markets/news.rss",
        0.92, "enterprise", "finance",
    ),
    NewsSource(
        "MarketWatch",
        "https://feeds.marketwatch.com/marketwatch/topstories/",
        0.86, "consumer", "finance",
    ),
    NewsSource(
        "BBC Business",
        "https://feeds.bbci.co.uk/news/business/rss.xml",
        0.90, "consumer", "finance",
    ),
    NewsSource(
        "Yahoo Finance",
        "https://finance.yahoo.com/news/rssindex",
        0.82, "consumer", "finance",
    ),
    NewsSource(
        "CNBC Finance",
        "https://www.cnbc.com/id/10000664/device/rss/rss.html",
        0.85, "consumer", "finance",
    ),
    NewsSource(
        "CNBC Economy",
        "https://www.cnbc.com/id/20910258/device/rss/rss.html",
        0.86, "consumer", "finance",
    ),
    NewsSource(
        "Finextra",
        "https://www.finextra.com/rss/headlines.aspx",
        0.85, "enterprise", "finance",
    ),
    NewsSource(
        "CoinDesk",
        "https://www.coindesk.com/arc/outboundfeeds/rss/",
        0.80, "consumer", "finance",
    ),
    NewsSource(
        "TechCrunch Fintech",
        "https://techcrunch.com/tag/fintech/feed/",
        0.82, "enterprise", "finance",
    ),
]
