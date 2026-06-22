"""Story ranking.

Deterministic, dependency-free scoring so it is fully testable offline.
Each candidate is scored on four axes, blended into a single 0-1 score:

    recency       - how fresh the story is (last 24h weighted highest)
    public_impact - how much it affects ordinary people (QuantrixLabs' mission)
    authority     - editorial trust of the source
    novelty       - NOT recently *posted* (penalized unless pivotal)

A story matching a topic posted within `novelty_window_days` is heavily
demoted -- unless it is flagged pivotal, in which case it is boosted so
genuinely major news is covered regardless.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from ..utils import TFIDFVectorizer, cosine_sim, same_story

# Words signalling direct relevance to everyday people (security stories).
_PUBLIC_IMPACT_TERMS = {
    "password", "passwords", "phishing", "scam", "scams", "fraud", "bank",
    "banking", "credit card", "identity theft", "breach", "data breach",
    "leaked", "leak", "stolen", "exposed", "ransomware", "hospital",
    "healthcare", "patients", "school", "students", "consumer", "consumers",
    "iphone", "android", "google", "apple", "microsoft", "windows", "chrome",
    "gmail", "outlook", "facebook", "instagram", "whatsapp", "tiktok",
    "social media", "wifi", "router", "smart home", "2fa", "two-factor",
    "mfa", "vpn", "patch", "update", "millions", "billions", "personal data",
    "personal information", "ssn", "social security", "tax", "romance scam",
    "deepfake", "voice clone", "child", "children", "elderly", "shopping",
    "paypal", "venmo", "crypto", "wallet", "email", "text message", "sms",
    "qr code", "subscription", "refund",
}

# Finance-specific terms signalling relevance to everyday people's money.
_FINANCE_IMPACT_TERMS = {
    "inflation", "interest rate", "interest rates", "fed", "federal reserve",
    "recession", "mortgage", "rent", "housing", "savings", "retirement",
    "401k", "ira", "pension", "social security", "tax", "taxes", "refund",
    "debt", "student loan", "credit score", "credit card", "bank", "banks",
    "layoffs", "job", "jobs", "unemployment", "wages", "salary", "raise",
    "cost of living", "grocery", "groceries", "gas prices", "energy",
    "stock market", "stocks", "investing", "etf", "index fund", "dividend",
    "crypto", "bitcoin", "earnings", "gdp", "budget", "spending",
    "consumer", "consumers", "millions", "billions", "economy", "economic",
    "tariff", "tariffs", "trade", "dollar", "exchange rate",
}

# Signals that a story is pivotal enough to cover even if recently posted.
_PIVOTAL_TERMS = {
    "actively exploited", "zero-day", "zero day", "0-day", "in the wild",
    "mass exploitation", "emergency directive", "known exploited",
    "critical vulnerability", "patch now", "patch immediately",
    "millions of users", "billions of", "nationwide", "worldwide outage",
    "supply chain attack", "global",
}

_STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with",
    "as", "by", "at", "from", "is", "are", "was", "were", "be", "been",
    "new", "now", "via", "how", "what", "why", "this", "that", "into",
    "after", "over", "amid", "its", "their", "your", "you",
}


def topic_key(title: str) -> str:
    """Normalized key for grouping the same story across days/sources."""
    tokens = re.findall(r"[a-z0-9]+", title.lower())
    significant = sorted({t for t in tokens if len(t) > 3 and t not in _STOPWORDS})
    return " ".join(significant[:8])


def is_pivotal(text: str) -> bool:
    low = text.lower()
    return any(term in low for term in _PIVOTAL_TERMS)


def _recency_score(published_at: datetime | None, now: datetime) -> float:
    if published_at is None:
        return 0.4  # unknown date -> neutral-low
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = (now - published_at).total_seconds() / 3600.0
    if age_hours < 0:
        age_hours = 0
    if age_hours <= 24:
        return 1.0
    if age_hours <= 48:
        return 0.75
    if age_hours <= 72:
        return 0.5
    if age_hours <= 168:  # one week
        return 0.25
    return 0.1


def _public_impact_score(text: str, category: str = "security") -> float:
    low = text.lower()
    terms = _FINANCE_IMPACT_TERMS if category == "finance" else _PUBLIC_IMPACT_TERMS
    hits = sum(1 for term in terms if term in low)
    return min(1.0, hits / 5.0)


def _novelty_penalty(
    title: str,
    recent_posted_keys: list[str],
    threshold: float = 0.25,
) -> bool:
    """True if this story closely matches a topic posted in the last N days.

    Uses the same two-signal hybrid as the RSS deduplicator: TF-IDF cosine
    for stories with overlapping vocabulary, plus a shared-rare-entity check
    for stories that share only a specific entity name (e.g. "Rokarolla")
    but have completely different headline wording.
    """
    if not recent_posted_keys:
        return False
    key = topic_key(title)
    corpus = [key] + recent_posted_keys
    vect = TFIDFVectorizer(corpus)
    vec = vect.vectorize(key)
    for posted_key in recent_posted_keys:
        if same_story(vec, vect.vectorize(posted_key), key, posted_key, vect, threshold):
            return True
    return False


def score_candidate(
    cand,
    now: datetime,
    recent_posted_keys: list[str],
) -> None:
    """Compute and attach `.score`, `.score_breakdown` to a Candidate."""
    text = f"{cand.title} {cand.summary} {cand.full_text}"
    recency = _recency_score(cand.published_at, now)
    impact = _public_impact_score(text, getattr(cand, "category", "security"))
    authority = cand.authority
    # Consumer-facing sources get a small mission-fit nudge.
    if cand.audience == "consumer":
        impact = min(1.0, impact + 0.1)

    pivotal = is_pivotal(text)
    recently_posted = _novelty_penalty(cand.title, recent_posted_keys)
    novelty = 0.2 if recently_posted else 1.0

    base = 0.35 * recency + 0.30 * impact + 0.20 * authority + 0.15 * novelty

    if recently_posted and not pivotal:
        base *= 0.2          # strong demotion for repeats
    elif pivotal:
        base = min(1.0, base + 0.15)  # ensure major news surfaces

    cand.score = round(base, 4)
    cand.score_breakdown = {
        "recency": round(recency, 3),
        "public_impact": round(impact, 3),
        "authority": round(authority, 3),
        "novelty": round(novelty, 3),
        "pivotal": pivotal,
        "recently_posted": recently_posted,
    }


def rank(
    candidates: list,
    recent_posted_keys: list[str],
    top_n: int,
    now: datetime | None = None,
    diversity_threshold: float = 0.20,
) -> list:
    """Score all candidates and return the top N, ensuring topic diversity.

    Diversity is enforced by greedy TF-IDF cosine selection: the highest-
    scoring story is picked first, then any remaining candidate whose
    TF-IDF cosine similarity to an already-selected story exceeds
    `diversity_threshold` is skipped. This is the within-batch safety net
    after RSS-level dedup — it catches any same-story candidates that
    slipped through because the headlines were too different in wording.

    TF-IDF is computed across the scored candidates so rare story-specific
    terms (entity names, CVE IDs) receive high weight and reliably link
    stories about the same subject even across differently angled headlines.
    """
    now = now or datetime.now(timezone.utc)
    for cand in candidates:
        score_candidate(cand, now, recent_posted_keys)
    ranked = sorted(candidates, key=lambda c: c.score, reverse=True)

    # Build TF-IDF over all topic keys in this batch.
    keys = [topic_key(c.title) for c in ranked]
    vectorizer = TFIDFVectorizer(keys)
    vectors = {i: vectorizer.vectorize(k) for i, k in enumerate(keys)}

    selected: list = []
    selected_vecs: list[dict[str, float]] = []
    selected_keys: list[str] = []

    for i, cand in enumerate(ranked):
        if len(selected) >= top_n:
            break
        vec = vectors[i]
        key_i = keys[i]
        if any(
            same_story(vec, sv, key_i, sk, vectorizer, diversity_threshold)
            for sv, sk in zip(selected_vecs, selected_keys)
        ):
            continue
        selected.append(cand)
        selected_vecs.append(vec)
        selected_keys.append(key_i)

    return selected
