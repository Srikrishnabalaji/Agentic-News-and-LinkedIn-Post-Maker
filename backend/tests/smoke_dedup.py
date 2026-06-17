"""Regression test: same-story multi-source dedup (the Rokarolla case).

Verifies that three differently-worded headlines about the same entity
('Rokarolla') are collapsed to one story by both layers of dedup:
  1. RSS-level TF-IDF cosine deduplicate()
  2. Within-batch ranker TF-IDF cosine diversity selection
"""
from datetime import datetime, timedelta, timezone

from app.scraper.rss import Candidate, deduplicate
from app.ranking.scorer import rank
from app.utils import TFIDFVectorizer, cosine_sim

NOW = datetime(2026, 6, 17, 11, 0, tzinfo=timezone.utc)


def mk(title, url, authority=0.8, hours_ago=2):
    return Candidate(
        source_name="t", authority=authority, audience="consumer",
        title=title, url=url,
        published_at=NOW - timedelta(hours=hours_ago),
    )


# --- 1. Cosine similarity utility ---
texts = [
    "rokarolla android malware steals crypto pins sms",
    "rokarolla android trojan control device persistence",
    "kodak breach shiny hunters extortion",
]
v = TFIDFVectorizer(texts)
sim_same = cosine_sim(v.vectorize(texts[0]), v.vectorize(texts[1]))
sim_diff = cosine_sim(v.vectorize(texts[0]), v.vectorize(texts[2]))
assert sim_same > sim_diff, f"Rokarolla pair ({sim_same:.3f}) should score higher than unrelated pair ({sim_diff:.3f})"
print(f"[OK] cosine: Rokarolla pair={sim_same:.3f} > unrelated pair={sim_diff:.3f}")


# --- 2. RSS deduplicate() collapses all 3 Rokarolla stories ---
stories = [
    mk("New Rokarolla Android Malware Steals PINs, SMS Codes, and Crypto",
       "https://thehackernews.com/rokarolla-1", authority=0.85),
    mk("Rokarolla Android Trojan Levels Up to Full Device Control, Persistence",
       "https://darkreading.com/rokarolla-2", authority=0.82),
    mk("New Rokarolla Android malware targets 217 banking crypto apps",
       "https://bleepingcomputer.com/rokarolla-3", authority=0.88),
    mk("Kodak confirms data breach claimed by ShinyHunters extortion gang",
       "https://bleepingcomputer.com/kodak-breach", authority=0.88),
    mk("CISA adds one known exploited vulnerability to catalog",
       "https://cisa.gov/vuln-1", authority=0.97),
]
deduped = deduplicate(stories)
titles = [c.title for c in deduped]
rokarolla_count = sum(1 for t in titles if "Rokarolla" in t)
assert rokarolla_count == 1, (
    f"expected 1 Rokarolla story after RSS dedup, got {rokarolla_count}: {titles}"
)
kept = next(c for c in deduped if "Rokarolla" in c.title)
assert kept.authority == 0.88, f"expected highest-authority kept (0.88), got {kept.authority}"
print(f"[OK] RSS dedup: {len(stories)} → {len(deduped)}, kept {kept.source_name} (authority={kept.authority})")


# --- 3. Ranker diversity selection as second safety net ---
# Even if dedup misses them, the ranker should still emit only one.
batch = [
    mk("New Rokarolla Android Malware Steals PINs, SMS Codes, and Crypto",
       "https://thehackernews.com/rokarolla-1", authority=0.85),
    mk("Rokarolla Android Trojan Levels Up to Full Device Control",
       "https://darkreading.com/rokarolla-2", authority=0.82),
    mk("Rokarolla Android malware targets 217 banking crypto apps",
       "https://bleepingcomputer.com/rokarolla-3", authority=0.88),
    mk("Kodak confirms data breach claimed by ShinyHunters extortion gang",
       "https://bleepingcomputer.com/kodak-breach", authority=0.88),
    mk("CISA adds one known exploited vulnerability to catalog",
       "https://cisa.gov/vuln-1", authority=0.97),
    mk("Phishing campaign targets Gmail and Outlook users with fake alerts",
       "https://helpnetsecurity.com/phishing-1", authority=0.78),
]
ranked = rank(batch, [], top_n=5, now=NOW)
ranked_titles = [c.title for c in ranked]
rokarolla_in_ranked = sum(1 for t in ranked_titles if "Rokarolla" in t)
assert rokarolla_in_ranked == 1, (
    f"ranker passed {rokarolla_in_ranked} Rokarolla stories: {ranked_titles}"
)
print(f"[OK] ranker diversity: {len(batch)} candidates → {len(ranked)} selected")
for c in ranked:
    print(f"     {c.title[:65]} (score={c.score})")

print("\nAll dedup regression tests passed.")
