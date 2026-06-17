"""Smoke test: verify image provider sources return results."""
from app.generator.images import _from_openverse, _from_wikimedia, find_images

QUERY = "person looking at phone worried"

print("=== Openverse ===")
results = _from_openverse(QUERY, 5)
for r in results[:3]:
    print("  " + r["source"] + ": " + r["attribution"][:55] + " | " + r["license"][:35])
assert len(results) > 0, "Openverse returned 0 results"
print("  Total:", len(results))

print()
print("=== Wikimedia ===")
results2 = _from_wikimedia(QUERY, 5)
for r in results2[:3]:
    print("  " + r["source"] + ": " + r["attribution"][:55])
assert len(results2) > 0, "Wikimedia returned 0 results"
print("  Total:", len(results2))

print()
print("=== find_images (search mode, 20 options) ===")
combined = find_images(QUERY, None, "TestSource", max_options=20)
sources = set(r["source"] for r in combined)
print("  Sources found:", sources)
print("  Total options:", len(combined))
assert len(combined) >= 2, "Expected multiple results from find_images"

print("\nAll image source tests passed.")
