"""Gemini-powered freshness + cross-reference check for news candidates.

Evaluates all candidates in a single batched Gemini call.  The model judges
from the article's own content and timeline — looking for temporal cues that
indicate the core event is older than it appears (e.g. "following last month's
breach", "in the attack disclosed in April", etc.).

Web-search cross-referencing is intended for a future phase; skipping it here
avoids parallel DNS floods that break subsequent API calls.

Falls back to all-novel if Gemini is unavailable or the call fails.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_FALLBACK = {"is_novel": True, "is_update": False, "is_relevant": True, "reason": "skipped"}


def _extract_json_array(text: str) -> list[dict]:
    """Extract the last JSON array from text (handles extra prose before/after)."""
    arrays = re.findall(r'\[\s*\{.*?\}\s*\]', text, re.DOTALL)
    if arrays:
        return json.loads(arrays[-1])
    cleaned = text.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1].lstrip("json").strip() if len(parts) >= 2 else cleaned
    return json.loads(cleaned)


def check_freshness_batch(
    candidates: list,
    category: str = "security",
    now: datetime | None = None,
) -> dict[str, dict]:
    """Return {url: {is_novel, is_update, reason}} for each candidate.

    Sends all candidates in a single batched Gemini call.  The model uses the
    article's own text — publication date, internal references to when the
    event occurred, summary language — to determine whether the core event is
    genuinely new or just now being written about.

    Padding rule enforced by the caller: only Gemini-novel + within-72h
    candidates are ever used for padding slots.  Stale stories never appear.
    """
    if not candidates:
        return {}

    from ..config import settings

    if not settings.has_gemini:
        log.info("[freshness] Gemini unavailable — skipping freshness check")
        return {c.url: dict(_FALLBACK) for c in candidates}

    now = now or datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    articles = []
    for i, cand in enumerate(candidates):
        pub_str = cand.published_at.strftime("%Y-%m-%d") if cand.published_at else "unknown"
        if cand.published_at:
            pub = cand.published_at
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            age_h = round((now - pub).total_seconds() / 3600, 1)
        else:
            age_h = None
        articles.append({
            "id": i,
            "pub_date": pub_str,
            "age_hours": age_h,  # explicit age so Gemini doesn't need to calculate
            "headline": cand.title[:200],
            "summary": (cand.summary or "")[:400],
        })

    relevance_rule = ""
    if category == "finance":
        relevance_rule = """
is_relevant = false if the article is primarily about any of these off-topic areas:
  • Consumer entertainment: movies, box office results, streaming, gaming, music, sports
  • Celebrity, lifestyle, or personal-interest human-interest stories
  • Retail consumer products, brand marketing, or PR incidents (e.g. company apology emails)
  • Political/diplomatic events with no direct financial or economic dimension
  is_relevant = true for: markets & investing, stocks, M&A, IPOs, earnings, banking, payments,
  fintech, crypto/blockchain, DeFi, macro economy (GDP, inflation, interest rates, central banks,
  trade policy), and AI/technology applied to financial services.
"""
    else:
        relevance_rule = "\nis_relevant = true for all security, threat, vulnerability, and privacy topics.\n"

    prompt = f"""Today is {today_str}. You are a rigorous news editor evaluating {category} stories for a professional LinkedIn account focused on cybersecurity and finance.

For each article, determine whether the CORE EVENT (the thing that actually happened) is genuinely new.
An article's own publication date is NOT reliable — an article published today can describe an event from weeks ago.
Read the headline and summary carefully for temporal signals.

is_novel = true ONLY if the CORE EVENT occurred within the past 48 hours.
  Exception: if today's article contains a genuinely new development on an older event
  (arrest made, patch released, new victim count, company statement, regulatory action,
  lawsuit filed), set is_novel = true AND is_update = true.

is_novel = false in ALL of these cases:
  • Attribution reports or "who did it" articles about an attack/incident that originally
    occurred more than 48 hours ago — even if published today.
    Example: "Microsoft links [attack name] to North Korea" = attribution article about
    a past attack = stale, unless today's article reveals new victims or new damage.
  • Articles describing events in past tense anchored to a date more than 48 hours ago:
    "in the attack that occurred in April", "following last month's breach", "after May 2026".
  • Evergreen advice, how-to, trend analysis, or opinion pieces with no specific breaking
    news anchor from the past 48 hours.
  • Webinar announcements, promotional content, or product launches.

is_update = true only when is_novel is true AND the article is a follow-up to prior coverage.
{relevance_rule}
reason = one sentence citing the key signal (e.g. "Attribution article about an attack from early June 2026").

Articles:
{json.dumps(articles, indent=2)}

Reply with ONLY a JSON array, one object per article in the same order as input:
[{{"id": 0, "is_novel": true, "is_update": false, "is_relevant": true, "reason": "..."}}]"""

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=1500,
                temperature=0.1,
            ),
        )
        verdicts_list = _extract_json_array(resp.text or "")
    except Exception as exc:
        log.warning("[freshness][%s] batch check failed (%s) — treating all as novel", category, exc)
        return {c.url: dict(_FALLBACK) for c in candidates}

    result: dict[str, dict] = {}
    for verdict in verdicts_list:
        idx = verdict.get("id")
        if idx is None or not (0 <= idx < len(candidates)):
            continue
        cand = candidates[idx]
        entry = {
            "is_novel": bool(verdict.get("is_novel", True)),
            "is_update": bool(verdict.get("is_update", False)),
            "is_relevant": bool(verdict.get("is_relevant", True)),
            "reason": str(verdict.get("reason", "")),
        }
        result[cand.url] = entry
        log.info(
            "[freshness][%s] novel=%-5s update=%-5s relevant=%-5s | %s — %s",
            category,
            entry["is_novel"],
            entry["is_update"],
            entry["is_relevant"],
            cand.title[:60],
            entry["reason"],
        )

    for cand in candidates:
        if cand.url not in result:
            result[cand.url] = dict(_FALLBACK)

    return result
