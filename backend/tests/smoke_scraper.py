"""Manual smoke test: DB init + live RSS fetch across a few sources."""
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

from app.db import init_db
from app.scraper.rss import fetch_all, fetch_source
from app.scraper.sources import SOURCES

init_db()
print("DB init OK\n")

ok = 0
for s in SOURCES:
    items = fetch_source(s, max_items=3)
    status = "OK " if items else "EMPTY"
    if items:
        ok += 1
    print(f"[{status}] {s.name}: {len(items)} items")
    if items:
        print(f"        e.g. {items[0].title[:70]!r}  ({items[0].published_at})")

print(f"\n{ok}/{len(SOURCES)} feeds returned items")
sys.exit(0 if ok >= len(SOURCES) // 2 else 1)
