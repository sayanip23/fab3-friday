"""Lane B — evidence retrieval.

Retrieval, not generation: given a claim to support (an account, a region,
a time window), find the service_events text that's actually relevant, and
attach freshness and a similarity score to every result so the narrative
layer can cite *why* it trusts a piece of evidence, not just assert it.

Method: TF-IDF + cosine similarity rather than a neural embedding model.
This is a deliberate, stated scope choice (see ASSUMPTIONS.md) — it needs
no downloaded model and no network call, so the retrieval step is fast,
fully reproducible, and doesn't add a multi-GB dependency to a hackathon
judge's machine. Swapping in sentence-transformers or a hosted embedding
endpoint is a drop-in replacement for `EvidenceIndex.search` if the team
wants denser semantic matching later.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _light_stem_tokenizer(text: str) -> list[str]:
    """Crude suffix-stripping so 'supplier'/'suppliers', 'complaint'/
    'complaints' etc. match as the same token, without pulling in a full
    stemming dependency. Good enough for short operational text; a real
    embedding model would do this more robustly (see module docstring)."""
    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    stemmed = []
    for t in tokens:
        if len(t) > 4 and t.endswith("ies"):
            t = t[:-3] + "y"
        elif len(t) > 4 and t.endswith("es"):
            t = t[:-2]
        elif len(t) > 4 and t.endswith("s") and not t.endswith("ss"):
            t = t[:-1]
        stemmed.append(t)
    return stemmed


@dataclasses.dataclass(frozen=True)
class EvidenceRecord:
    event_id: str
    timestamp: pd.Timestamp
    region: str | None
    account_id: str | None
    account_name: str | None
    event_type: str
    text: str
    relevance_score: float
    freshness_hours: float
    method: str = "tfidf_cosine_similarity"


class EvidenceIndex:
    """A fitted TF-IDF index over one service_events table. Build once,
    search many times — rebuilding per query would be wasteful and would
    make freshness/relevance non-comparable across calls."""

    def __init__(self, events: pd.DataFrame):
        self.events = events.reset_index(drop=True).copy()
        self.events["timestamp"] = pd.to_datetime(self.events["timestamp"])
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
        stemmed_stop_words = {_light_stem_tokenizer(w)[0] for w in ENGLISH_STOP_WORDS if _light_stem_tokenizer(w)}
        self.vectorizer = TfidfVectorizer(tokenizer=_light_stem_tokenizer, stop_words=list(stemmed_stop_words),
                                          min_df=1, token_pattern=None)
        self.matrix = self.vectorizer.fit_transform(self.events["text"].fillna(""))

    def search(self, query: str, as_of: pd.Timestamp, top_k: int = 5,
               account_name: str | None = None, region: str | None = None,
               event_types: list[str] | None = None,
               max_age_days: int | None = None) -> list[EvidenceRecord]:
        """Rank service_events by text relevance to `query`, after applying
        structural filters (account/region/type/recency) — filter first,
        then rank, so a highly-relevant record about the wrong account
        can't leak into someone else's evidence trail.
        """
        mask = pd.Series(True, index=self.events.index)
        if account_name is not None:
            mask &= self.events["account_name"] == account_name
        if region is not None:
            mask &= self.events["region"] == region
        if event_types is not None:
            mask &= self.events["event_type"].isin(event_types)
        mask &= self.events["timestamp"] <= as_of
        if max_age_days is not None:
            mask &= self.events["timestamp"] >= (as_of - pd.Timedelta(days=max_age_days))

        candidates = self.events[mask]
        if len(candidates) == 0:
            return []

        query_vec = self.vectorizer.transform([query])
        cand_matrix = self.matrix[candidates.index]
        sims = cosine_similarity(query_vec, cand_matrix).ravel()

        # Rank by (relevance, recency) and drop exact-duplicate text before
        # truncating to top_k — otherwise a handful of boilerplate
        # complaint templates can occupy the entire result set and crowd
        # out a single, more informative record like a CRM note.
        ranked_positions = sorted(
            range(len(sims)),
            key=lambda i: (sims[i], candidates.iloc[i]["timestamp"]),
            reverse=True,
        )
        results = []
        seen_text = set()
        for pos in ranked_positions:
            row = candidates.iloc[pos]
            if row["text"] in seen_text:
                continue
            seen_text.add(row["text"])
            age_hours = (as_of - row["timestamp"]).total_seconds() / 3600
            results.append(EvidenceRecord(
                event_id=row["event_id"],
                timestamp=row["timestamp"],
                region=row.get("region"),
                account_id=row.get("account_id"),
                account_name=row.get("account_name"),
                event_type=row["event_type"],
                text=row["text"],
                relevance_score=round(float(sims[pos]), 4),
                freshness_hours=round(float(age_hours), 1),
            ))
            if len(results) >= top_k:
                break
        return results
