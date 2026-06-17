"""Smoke test for the post generator (mock mode when no API key)."""
from app.config import settings
from app.generator.post import generate_post, _normalize_hashtags
from app.scraper.rss import fetch_all
from app.scraper.article import enrich

print(f"has_anthropic={settings.has_anthropic} model={settings.anthropic_model}\n")

# Hashtag normalization edge cases.
tags = _normalize_hashtags(["#Phishing", "phishing", "online safety", ""])
assert "CyberSecurity" in tags and "QuantrixLabs" in tags
assert tags.count("Phishing") == 1 if "Phishing" in tags else True
print(f"[OK] hashtag normalize -> {tags}")

# Live: fetch one real story, enrich, generate.
cands = fetch_all(max_items_per_source=3)
assert cands, "no candidates fetched"
enrich(cands, limit=1)
top = cands[0]
post = generate_post(top)

print(f"\n--- Generated ({post.format_type}) ---")
print(f"Headline: {post.headline}")
print(f"Image recommended: {post.image_recommended} — {post.image_reason}")
print(f"Image query: {post.image_query!r}")
print(f"Hashtags: {post.hashtags}")
print(f"Char count: {len(post.body)}")
print("Body:\n" + post.body)

assert post.body and len(post.body) < 3000
assert post.format_type
assert post.hashtags
print("\n[OK] generator produced a valid draft")
