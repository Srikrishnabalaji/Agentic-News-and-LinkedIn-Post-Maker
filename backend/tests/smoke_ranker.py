"""Smoke test for ranking logic: synthetic assertions + live ranking."""
from datetime import datetime, timedelta, timezone

from app.ranking.scorer import rank, topic_key, is_pivotal, score_candidate
from app.scraper.rss import Candidate

NOW = datetime(2026, 6, 17, 11, 0, tzinfo=timezone.utc)


def mk(title, hours_ago, authority=0.8, audience="enterprise", summary=""):
    return Candidate(
        source_name="t", authority=authority, audience=audience,
        title=title, url="http://x/" + title.replace(" ", "-"),
        summary=summary,
        published_at=NOW - timedelta(hours=hours_ago),
    )


# 1. Fresh consumer-impact story should outrank stale enterprise jargon.
fresh_breach = mk("Major bank data breach exposes millions of customer passwords",
                  2, 0.9, "consumer")
stale_jargon = mk("Vendor announces new SIEM dashboard integration", 100, 0.7)
ranked = rank([stale_jargon, fresh_breach], [], top_n=2, now=NOW)
assert ranked[0] is fresh_breach, "fresh consumer story should rank first"
print(f"[OK] recency+impact: {fresh_breach.score} > {stale_jargon.score}")

# 2. Recently-posted topic should be demoted...
repeat = mk("Bank data breach exposes millions of customer passwords", 2, 0.9, "consumer")
posted_keys = [topic_key("Bank data breach exposes millions of customer passwords")]
score_candidate(repeat, NOW, posted_keys)
assert repeat.score_breakdown["recently_posted"] is True
print(f"[OK] repeat demoted: score={repeat.score} breakdown={repeat.score_breakdown}")

# 3. ...UNLESS pivotal (actively exploited zero-day) -> covered anyway.
pivotal = mk("Actively exploited zero-day in Windows hits millions of users", 2,
             0.9, "consumer")
score_candidate(pivotal, NOW, [topic_key(pivotal.title)])
assert pivotal.score_breakdown["pivotal"] is True
assert pivotal.score > repeat.score, "pivotal repeat should beat normal repeat"
print(f"[OK] pivotal override: score={pivotal.score}")

assert is_pivotal("This is actively exploited in the wild")
assert not is_pivotal("A routine quarterly patch was released")
print("[OK] pivotal detection")

print("\nAll ranker assertions passed.")
