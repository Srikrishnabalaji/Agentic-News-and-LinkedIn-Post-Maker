"""Trusted cybersecurity news sources.

Curated for authority and relevance to QuantrixLabs' mission: educating
the general public on how cybersecurity stories affect everyday people.
Each source has an `authority` weight (0-1) used by the ranker.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewsSource:
    name: str
    feed_url: str
    authority: float  # 0-1, editorial trust / signal quality
    audience: str     # "consumer" | "enterprise" | "government"


SOURCES: list[NewsSource] = [
    NewsSource(
        "The Hacker News",
        "https://feeds.feedburner.com/TheHackersNews",
        0.85,
        "enterprise",
    ),
    NewsSource(
        "Krebs on Security",
        "https://krebsonsecurity.com/feed/",
        0.95,
        "consumer",
    ),
    NewsSource(
        "BleepingComputer",
        "https://www.bleepingcomputer.com/feed/",
        0.88,
        "consumer",
    ),
    NewsSource(
        "CISA Advisories",
        "https://www.cisa.gov/cybersecurity-advisories/all.xml",
        0.97,
        "government",
    ),
    NewsSource(
        "Dark Reading",
        "https://www.darkreading.com/rss.xml",
        0.82,
        "enterprise",
    ),
    NewsSource(
        "Malwarebytes Labs",
        "https://www.malwarebytes.com/blog/feed/index.xml",
        0.84,
        "consumer",
    ),
    NewsSource(
        "Help Net Security",
        "https://www.helpnetsecurity.com/feed/",
        0.78,
        "enterprise",
    ),
    NewsSource(
        "SecurityWeek",
        "https://www.securityweek.com/feed/",
        0.83,
        "enterprise",
    ),
    NewsSource(
        "Google Online Security Blog",
        "https://security.googleblog.com/feeds/posts/default",
        0.9,
        "consumer",
    ),
    NewsSource(
        "WeLiveSecurity (ESET)",
        "https://www.welivesecurity.com/en/rss/feed/",
        0.8,
        "consumer",
    ),
]
