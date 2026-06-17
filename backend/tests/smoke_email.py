"""Smoke test: digest HTML rendering (no SMTP credentials required)."""
from types import SimpleNamespace

from app.notify.email import render_digest

posts = [
    SimpleNamespace(
        headline="That 'free World Cup stream' is a trap",
        body="Heads up: scammers are flooding search results with fake free "
             "streaming sites.\n\nHere's how to spot them and what to do instead.",
        format_type="psa_alert", source_name="Malwarebytes Labs",
        image_url="https://upload.wikimedia.org/x.jpg",
        image_recommended=True, is_pivotal=False,
    ),
    SimpleNamespace(
        headline="144 npm packages hijacked — why it matters to you",
        body="A popular code library was poisoned. Even if you've never heard "
             "of npm, the apps you use rely on it.",
        format_type="explainer", source_name="The Hacker News",
        image_url=None, image_recommended=False, is_pivotal=True,
    ),
]

html = render_digest(posts, run_date="Wednesday, 17 June 2026")

with open("tests/_digest_preview.html", "w", encoding="utf-8") as f:
    f.write(html)

assert "QuantrixLabs" in html
assert "2 ready-to-edit drafts" in html
assert "Public Safety Alert" in html
assert "Pivotal" in html                      # pivotal badge rendered
assert "AI suggests no image" in html          # shown for post 2
assert "Open the editor" in html
print("[OK] digest rendered -> tests/_digest_preview.html "
      f"({len(html)} bytes, {html.count('border-radius:12px')} cards)")
