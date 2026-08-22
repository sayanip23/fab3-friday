"""
Lane B. Evidence retrieval.

Answers the brief's requirement for narratives "supported by traceable evidence",
and supplies the freshness, method and lineage fields of minimum expectation 8.

Ranking is BM25, implemented here rather than pulled in, for three reasons: it needs
no model download so the prototype runs offline and reproducibly, it is fully
explainable to a sceptical stakeholder, and its scores are stable across runs so a
citation shown in the video is the citation a judge gets when they run it. Swapping
in embeddings later means replacing `_score` and nothing else.

Note the division of labour with `causal.gather_evidence`. That function screens, so
it wants recall across a driver's whole vocabulary and returns everything matching.
This module cites, so it wants precision and returns the best few passages. Different
jobs, different tools.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta

from .kpi import Filters, Period, Warehouse

TOKEN = re.compile(r"[a-z0-9]+")
K1, B = 1.5, 0.75

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "is", "was",
    "we", "our", "us", "this", "that", "it", "has", "have", "been", "with",
    "at", "as", "be", "are", "not", "but", "from", "by",
}


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN.findall(str(text).lower()) if t not in STOPWORDS]


@dataclass
class Passage:
    """One citable piece of evidence, carrying everything a reader needs to check it."""
    event_id: str
    source: str
    when: date
    kind: str
    account: str
    region: str
    text: str
    score: float
    freshness_hours: float
    method: str = "bm25"

    @property
    def age_days(self) -> int:
        return (date(2026, 8, 20) - self.when).days

    def cite(self, max_len: int = 150) -> str:
        t = self.text if len(self.text) <= max_len else self.text[: max_len - 1] + "…"
        return f'[{self.source} · {self.when} · {self.kind}] "{t}"'

    def provenance(self) -> dict:
        """The lineage stamp required by minimum expectation 8."""
        return {
            "event_id": self.event_id,
            "source": self.source,
            "date": self.when.isoformat(),
            "age_days": self.age_days,
            "source_lag_hours": self.freshness_hours,
            "retrieval_method": self.method,
            "relevance_score": round(self.score, 3),
        }


@dataclass
class Index:
    """BM25 over the free text source. Built once, queried many times."""
    docs: list[dict] = field(default_factory=list)
    _df: Counter = field(default_factory=Counter)
    _tokens: list[list[str]] = field(default_factory=list)
    _avg_len: float = 0.0

    @classmethod
    def build(cls, wh: Warehouse) -> "Index":
        spec = wh.c.sources["service_events"]
        if spec.get("role") != "evidence_only":
            raise ValueError("service_events must be declared evidence_only")

        df = wh.frame("service_events")
        idx = cls()
        for _, r in df.iterrows():
            idx.docs.append({
                "event_id": r["event_id"], "when": r["_d"], "kind": r["kind"],
                "account": r["account_name"], "region": r["region"],
                "text": r["text"], "lag": spec["expected_lag_hours"],
            })
            toks = tokenize(r["text"])
            idx._tokens.append(toks)
            idx._df.update(set(toks))

        n = len(idx._tokens)
        idx._avg_len = sum(len(t) for t in idx._tokens) / n if n else 0.0
        return idx

    def _idf(self, term: str) -> float:
        n = len(self._tokens)
        df = self._df.get(term, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def _score(self, query: list[str], i: int) -> float:
        toks = self._tokens[i]
        if not toks:
            return 0.0
        tf = Counter(toks)
        norm = 1 - B + B * (len(toks) / self._avg_len) if self._avg_len else 1.0
        return sum(self._idf(q) * (tf[q] * (K1 + 1)) / (tf[q] + K1 * norm)
                   for q in query if tf[q])

    def search(self, query: str, period: Period, filters: Filters = None,
               lookback_days: int = 90, top_k: int = 3,
               recency_halflife_days: float = 45.0) -> list[Passage]:
        """
        Best passages for a query, within the window and the caller's slice.

        Score is BM25 with a gentle recency decay. Without the decay an eloquent
        complaint from last year outranks the terse one from last week that actually
        explains the movement.
        """
        q = tokenize(query)
        if not q:
            return []

        lo = period.start - timedelta(days=lookback_days)
        hits: list[Passage] = []

        for i, d in enumerate(self.docs):
            if not (lo <= d["when"] <= period.end):
                continue
            if filters:
                if filters.get("region") and d["region"] != filters["region"]:
                    continue
                if filters.get("account_name") and d["account"] != filters["account_name"]:
                    continue

            raw = self._score(q, i)
            if raw <= 0:
                continue
            age = (period.end - d["when"]).days
            decayed = raw * (0.5 ** (age / recency_halflife_days))

            hits.append(Passage(
                event_id=d["event_id"], source="service_events", when=d["when"],
                kind=d["kind"], account=d["account"], region=d["region"],
                text=d["text"], score=decayed, freshness_hours=d["lag"],
            ))

        hits.sort(key=lambda p: (-p.score, p.when))
        return _diversify(hits, top_k)


def _diversify(hits: list[Passage], top_k: int) -> list[Passage]:
    """
    Prefer distinct kinds and dates.

    The generated corpus repeats phrasings, and unfiltered BM25 will happily return
    the same sentence three times from three tickets. Three identical citations look
    like three pieces of evidence and are one.
    """
    out: list[Passage] = []
    seen_kind: Counter = Counter()
    seen_text: set[str] = set()

    for p in hits:
        sig = " ".join(tokenize(p.text)[:8])
        if sig in seen_text:
            continue
        if seen_kind[p.kind] >= 2:
            continue
        out.append(p)
        seen_text.add(sig)
        seen_kind[p.kind] += 1
        if len(out) >= top_k:
            break
    return out


# queries per driver, kept declarative so they read as configuration
DRIVER_QUERIES = {
    "delivery_reliability": "late delivery delayed not arrived escalate consignment slipped",
    "volume": "evaluating alternative suppliers renewal at risk unhappy reliability",
    "price": "invoice rate correction discount price",
    "quality": "damaged torn packaging replacement",
}


def for_driver(index: Index, driver: str, period: Period,
               filters: Filters = None, top_k: int = 3) -> list[Passage]:
    q = DRIVER_QUERIES.get(driver)
    return index.search(q, period, filters, top_k=top_k) if q else []


def freshness_report(wh: Warehouse, sources: list[str]) -> list[dict]:
    """Per source freshness, so a narrative can disclose what it was working from."""
    out = []
    for name in sources:
        spec = wh.c.sources[name]
        lag = spec["expected_lag_hours"]
        warn = spec.get("staleness_warning_hours", float("inf"))
        out.append({
            "source": name,
            "cadence": spec["refresh_cadence"],
            "lag_hours": lag,
            "stale": lag > warn,
            "grain": spec["grain"],
        })
    return out
