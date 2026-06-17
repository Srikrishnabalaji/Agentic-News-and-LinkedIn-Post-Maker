"""Shared text-similarity utilities.

Implements TF-IDF vector cosine similarity without any ML dependencies.
Used by the RSS deduplicator and ranker diversity filter to detect when
multiple candidates are covering the same story from different angles.

Why TF-IDF over plain bag-of-words or Jaccard:
  - Rare, story-specific terms (e.g. 'Rokarolla', 'ShinyHunters') get a
    high IDF weight and dominate the cosine score, exactly as intended.
  - Common terms ('android', 'malware', 'attack') get a lower IDF weight,
    so two unrelated stories that happen to share generic words don't
    incorrectly merge.
  - Cosine normalises for document length.

However, cosine alone can miss cases where two headlines describe the same
story from completely different angles (e.g. "Rokarolla steals banking PINs"
vs "Rokarolla achieves full device control"). They share only the entity
name and one generic tech word, keeping the cosine low despite being the
same story. The `same_story()` helper adds a secondary rare-entity check to
catch these: if two texts share any token that is both ≥5 chars and appears
in ≤3 documents in the current corpus, it is story-specific enough to
conclude they are the same story.
"""
from __future__ import annotations

import math
from collections import Counter


def cosine_sim(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity between two TF-IDF weight dicts."""
    if not vec_a or not vec_b:
        return 0.0
    dot = sum(vec_a[w] * vec_b[w] for w in vec_a if w in vec_b)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


class TFIDFVectorizer:
    """Lightweight TF-IDF vectorizer for a fixed corpus of short texts.

    Usage:
        v = TFIDFVectorizer(texts)
        vec = v.vectorize("some text")
        sim = cosine_sim(v.vectorize(a), v.vectorize(b))
    """

    def __init__(self, texts: list[str]) -> None:
        tokenised = [t.split() for t in texts]
        n = len(tokenised)

        df: Counter[str] = Counter()
        for tokens in tokenised:
            df.update(set(tokens))

        # Expose raw document-frequency counts for the rare-entity check.
        self.df: dict[str, int] = dict(df)
        self.n_docs: int = n

        # Smooth IDF: log((n+1)/(df+1)) + 1  (same as sklearn's default)
        self._idf: dict[str, float] = {
            word: math.log((n + 1) / (count + 1)) + 1.0
            for word, count in df.items()
        }

    def vectorize(self, text: str) -> dict[str, float]:
        """Return a TF-IDF weight dict for `text` (handles OOV tokens)."""
        tokens = text.split()
        if not tokens:
            return {}
        tf = Counter(tokens)
        max_tf = max(tf.values())
        return {
            word: (count / max_tf) * self._idf.get(word, 1.0)
            for word, count in tf.items()
        }


def same_story(
    vec_a: dict[str, float],
    vec_b: dict[str, float],
    text_a: str,
    text_b: str,
    vect: TFIDFVectorizer,
    cosine_threshold: float = 0.20,
    rare_df_cutoff: int = 3,
    min_term_len: int = 5,
) -> bool:
    """Return True when two topic-key texts describe the same news story.

    Two-signal hybrid:

    1. **TF-IDF cosine ≥ threshold** — catches stories with substantial
       vocabulary overlap (most same-story pairs).

    2. **Shared rare entity** — catches stories linked only by an entity
       name when the headlines are worded completely differently (e.g.
       "Rokarolla steals banking PINs" vs "Rokarolla achieves full device
       control").  A term qualifies as a rare entity when:
         - it appears in ≤ `rare_df_cutoff` documents in the corpus
           (default 3 — ≤ ~2% of a typical 130-story batch), AND
         - it is ≥ `min_term_len` characters long (filters out short
           abbreviations like 'cve', 'cisa', 'vpn').
    """
    if cosine_sim(vec_a, vec_b) >= cosine_threshold:
        return True
    tokens_a = set(text_a.split())
    tokens_b = set(text_b.split())
    for term in tokens_a & tokens_b:
        if len(term) >= min_term_len and vect.df.get(term, 999) <= rare_df_cutoff:
            return True
    return False
