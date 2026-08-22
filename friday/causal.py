"""
Phase 3b. Causal screening and confidence.

Answers Round 2 objective 5: "Communicates uncertainty and abstains when evidence
is insufficient or contradictory."

A contribution tells you a segment moved. It does not tell you why, and a large
contribution is not a cause. Before FRIDAY will name anything as a cause, three
gates must all pass:

  SEQUENCE   the candidate cause is observable before the effect begins
  MAGNITUDE  it accounts for a meaningful share of the movement
  MECHANISM  it is a declared driver of this KPI and something corroborates it

Any gate failing means the finding is reported as an association, not a cause.
All three tests are deterministic rules over dates and numbers. No LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .contracts import Contract
from .detect import Movement
from .kpi import Filters, Period, Warehouse

CONFIDENCE_ORDER = ["none", "low", "medium", "high"]

# Two different kinds of driver, which must not be screened the same way.
#
# ARITHMETIC drivers fall out of the decomposition itself. Volume, price and mix
# are not causes of the movement, they are the movement, restated in the levers a
# business pulls. Their sequence and mechanism are established by the arithmetic,
# so asking a text corpus to corroborate them is a category error.
#
# EVIDENTIAL drivers are candidate root causes sitting upstream of the arithmetic.
# Delivery reliability does not appear in a revenue decomposition at all; it shows
# up as volume, one quarter later. These must be dated and corroborated.
ARITHMETIC_DRIVERS = {"volume", "price", "mix"}

# which event kind in the free text source measures an evidential driver
DRIVER_EVENT_KIND = {
    "delivery_reliability": "delivery_delay",
}

# a driver's underlying rate must move by at least this multiple to count
EVIDENTIAL_RATE_THRESHOLD = 2.0

# keyword probes for the mechanism test. Lane B replaces this with embedding
# retrieval; the keys stay the same so the interface does not change.
EVIDENCE_PROBES = {
    "delivery_reliability": ["late", "delay", "slipped", "not arrived", "escalate"],
    "volume": ["alternative suppliers", "renewal", "at risk", "unhappy"],
    "price": ["rate", "discount", "price"],
}


@dataclass
class EvidenceItem:
    source: str
    when: date
    kind: str
    text: str
    freshness_hours: float

    def cite(self, max_len: int = 110) -> str:
        t = self.text if len(self.text) <= max_len else self.text[: max_len - 1] + "…"
        return f"[{self.source} {self.when}] {t}"


@dataclass
class Verdict:
    driver: str
    lever: str
    controllable: bool
    contribution: float
    share: float

    sequence_ok: bool
    magnitude_ok: bool
    mechanism_ok: bool

    onset: date | None
    first_evidence: date | None
    kind: str = "arithmetic"          # arithmetic | evidential
    strength: float = 0.0             # evidential only: rate ratio against baseline
    evidence: list[EvidenceItem] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def is_cause(self) -> bool:
        return self.sequence_ok and self.magnitude_ok and self.mechanism_ok

    @property
    def status(self) -> str:
        return "cause" if self.is_cause else "association"

    def gates(self) -> str:
        mark = lambda ok: "pass" if ok else "fail"      # noqa: E731
        return (f"sequence {mark(self.sequence_ok)}, magnitude {mark(self.magnitude_ok)}, "
                f"mechanism {mark(self.mechanism_ok)}")


@dataclass
class Assessment:
    movement: Movement
    verdicts: list[Verdict]
    confidence: str
    abstain: bool
    abstain_reasons: list[str]
    competing: list[str] = field(default_factory=list)
    discriminating_check: str | None = None

    @property
    def causes(self) -> list[Verdict]:
        return [v for v in self.verdicts if v.is_cause]


# --------------------------------------------------------------------- onset
def movement_onset(wh: Warehouse, kpi: str, period: Period,
                   filters: Filters = None) -> date | None:
    """
    First day inside the period where the KPI departs durably from its prior level.
    Used by the sequence gate, so a cause must precede this date.
    """
    prior = period.shifted(period.days)

    # Daily revenue swings by a factor of two across the week (Sunday against
    # Wednesday), so a raw daily series cannot separate a business movement from
    # the weekday cycle. Smooth over a whole week first, centred so the onset is
    # dated to when the level actually shifted rather than a week later.
    # grain aware: a weekly KPI has no daily series, and asking for one raises.
    # This is the same fix already applied in detect._baseline_changes.
    full, grain = wh.series(kpi, prior.start, period.end, filters)
    if full.empty:
        return None
    # weekly data is already free of the weekday cycle, so it needs far less smoothing
    win = 7 if grain == "daily" else 3
    smooth = full.rolling(win, center=True, min_periods=max(2, win // 2)).mean()

    base = smooth[[d <= prior.end for d in smooth.index]].to_numpy(dtype=float)
    base = base[np.isfinite(base)]
    if len(base) < 7:
        return None

    med = float(np.median(base))
    mad = float(np.median(np.abs(base - med))) or 1.0
    threshold = med - 1.5 * 1.4826 * mad

    run, run_start = 0, None
    for d, v in smooth.items():
        if d < period.start:
            continue
        if np.isfinite(v) and v < threshold:
            run += 1
            run_start = run_start or d
            if run >= (3 if grain == "daily" else 2):
                return run_start
        else:
            run, run_start = 0, None
    return None


# ------------------------------------------------------------------ evidence
def gather_evidence(wh: Warehouse, driver: str, period: Period,
                    filters: Filters = None, lookback_days: int = 75) -> list[EvidenceItem]:
    """Keyword probe over the free text source. Evidence only, never a KPI input."""
    probes = EVIDENCE_PROBES.get(driver, [])
    if not probes:
        return []

    df = wh.frame("service_events").copy()
    lo = period.start - timedelta(days=lookback_days)
    df = df[(df["_d"] >= lo) & (df["_d"] <= period.end)]
    for col, val in (filters or {}).items():
        if col in df.columns:
            df = df[df[col] == val]
    if df.empty:
        return []

    pattern = "|".join(probes)
    hit = df[df.text.str.contains(pattern, case=False, na=False)]
    lag = wh.c.sources["service_events"]["expected_lag_hours"]

    return [EvidenceItem("service_events", r["_d"], r["kind"], r["text"], lag)
            for _, r in hit.sort_values("_d").iterrows()]


def _event_counts(wh: Warehouse, kind: str, lo: date, hi: date,
                  filters: Filters = None) -> pd.Series:
    df = wh.frame("service_events")
    for col, val in (filters or {}).items():
        if col in df.columns:
            df = df[df[col] == val]
    df = df[(df.kind == kind) & (df["_d"] >= lo) & (df["_d"] <= hi)]
    idx = pd.date_range(lo, hi, freq="D").date
    if df.empty:
        return pd.Series(0.0, index=idx)
    return df.groupby("_d").size().reindex(idx, fill_value=0).astype(float)


def driver_change_point(wh: Warehouse, kind: str, period: Period,
                        filters: Filters = None,
                        lookback_days: int = 320) -> date | None:
    """
    When this driver's own rate shifted, found the same way we find a KPI onset.

    This matters more than it looks. A fixed recent baseline window is contaminated
    by the driver's own elevated period, which suppresses the measured ratio and can
    hide a real root cause. Anchoring on the change point removes that bias and also
    gives the sequence gate a meaningful date: not merely when some matching text
    first appeared, but when the driver actually degraded.
    """
    lo = period.start - timedelta(days=lookback_days)
    counts = _event_counts(wh, kind, lo, period.end, filters)
    if counts.sum() < 10:
        return None

    # Event counts are sparse: most days are zero, so median and MAD both collapse
    # to zero and any threshold built from them fires on the first quiet cluster.
    # Compare rates instead, against a quiet head window.
    head_days = max(90, int(len(counts) * 0.40))
    if len(counts) < head_days + 60:
        return None

    head = counts.iloc[:head_days]
    if head.sum() < 5:
        return None
    base_rate = float(head.mean())

    win = 14
    smooth = counts.rolling(win, center=True, min_periods=7).mean()

    # A 14 day mean of a Poisson process with rate r has standard error sqrt(r/14).
    # At these rates that noise term dominates any fixed offset, so the threshold has
    # to scale with it or ordinary clusters of two or three tickets read as a shift.
    noise = float(np.sqrt(max(base_rate, 1e-6) / win))
    threshold = max(2.0 * base_rate, base_rate + 3.0 * noise)

    run, run_start = 0, None
    for d, v in smooth.iloc[head_days:].items():
        if np.isfinite(v) and v >= threshold:
            run += 1
            run_start = run_start or d
            if run >= 21:                    # sustained three weeks, not a spike
                return run_start
        else:
            run, run_start = 0, None
    return None


def evidence_rate_ratio(wh: Warehouse, kind: str, period: Period,
                        filters: Filters = None, baseline_days: int = 120) -> float:
    """
    How much more often an event kind occurs now than before it changed.

    If a change point is found, the baseline is everything before it, which keeps
    the driver's own elevated period out of its own comparison. Otherwise we fall
    back to a fixed window.
    """
    cp = driver_change_point(wh, kind, period, filters)
    lo = period.start - timedelta(days=baseline_days if cp is None else 320)
    counts = _event_counts(wh, kind, lo, period.end, filters)
    if counts.empty:
        return 0.0

    if cp is not None:
        base = counts[[d < cp for d in counts.index]]
        cur = counts[[d >= cp for d in counts.index]]
    else:
        base = counts[[d < period.start for d in counts.index]]
        cur = counts[[period.start <= d <= period.end for d in counts.index]]

    if len(base) == 0 or base.mean() == 0:
        return float("inf") if len(cur) and cur.mean() > 0 else 0.0
    return float(cur.mean() / base.mean())


# --------------------------------------------------------------------- gates
def screen(wh: Warehouse, movement: Movement, effects: list,
           period: Period, filters: Filters = None) -> Assessment:
    """Run the three gates over each candidate driver of a movement."""
    c: Contract = wh.c
    spec = c.kpis[movement.kpi]
    declared = {d["name"]: d for d in spec.spec["drivers"]}
    abst = c.abstention

    min_share = next((r for r in [0.35] ), 0.35)
    for rule in abst.get("abstain_when", []):
        if isinstance(rule, str) and "top_driver_contribution_share" in rule:
            try:
                min_share = float(rule.split("<")[-1].strip())
            except ValueError:
                pass

    onset = movement_onset(wh, movement.kpi, period, filters)
    verdicts: list[Verdict] = []

    # ---- arithmetic drivers, straight from the decomposition
    for eff in effects:
        driver = eff.driver
        decl = declared.get(driver)
        share = abs(eff.share)
        reasons: list[str] = []

        magnitude_ok = share >= min_share
        if not magnitude_ok:
            reasons.append(f"explains {share:.0%} of the movement, below the "
                           f"{min_share:.0%} threshold")

        if decl is None:
            mechanism_ok = False
            reasons.append(f"'{driver}' is not a declared driver of {movement.kpi}")
        else:
            mechanism_ok = True          # the decomposition is the mechanism

        sequence_ok = onset is not None
        if not sequence_ok:
            reasons.append("no durable onset detected, so ordering cannot be established")

        verdicts.append(Verdict(
            driver=driver, kind="arithmetic",
            lever=(decl or {}).get("lever", "unknown"),
            controllable=bool((decl or {}).get("controllable", False)),
            contribution=eff.value, share=share,
            sequence_ok=sequence_ok, magnitude_ok=magnitude_ok,
            mechanism_ok=mechanism_ok, onset=onset, first_evidence=None,
            evidence=gather_evidence(wh, driver, period, filters)[:2],
            reasons=reasons,
        ))

    # ---- evidential drivers, candidate root causes upstream of the arithmetic
    verdicts += _screen_evidential(wh, movement, declared, onset, period, filters)

    verdicts.sort(key=lambda v: (v.kind != "arithmetic", -abs(v.contribution)))
    return _finalise(wh, movement, verdicts, min_share)


def _screen_evidential(wh: Warehouse, movement: Movement, declared: dict,
                       onset: date | None, period: Period,
                       filters: Filters) -> list[Verdict]:
    """
    Screen declared drivers that cannot appear in the decomposition.

    These are the drivers that actually answer 'why'. A revenue decomposition can
    only ever tell you volume fell; it takes a dated, corroborated evidential
    driver to say the volume fell because deliveries stopped arriving on time.
    """
    out: list[Verdict] = []

    for name, decl in declared.items():
        if name in ARITHMETIC_DRIVERS or name not in DRIVER_EVENT_KIND:
            continue

        kind = DRIVER_EVENT_KIND[name]
        ratio = evidence_rate_ratio(wh, kind, period, filters)
        evidence = gather_evidence(wh, name, period, filters)
        change_point = driver_change_point(wh, kind, period, filters)
        # the driver's own change point is a stronger sequence anchor than the first
        # keyword match, which may just be an ordinary ticket that happens to match
        first_ev = change_point or (evidence[0].when if evidence else None)
        reasons: list[str] = []

        magnitude_ok = ratio >= EVIDENTIAL_RATE_THRESHOLD
        if not magnitude_ok:
            reasons.append(f"{kind} rate is {ratio:.1f}x baseline, below the "
                           f"{EVIDENTIAL_RATE_THRESHOLD:.1f}x threshold")

        mechanism_ok = bool(evidence)
        if not mechanism_ok:
            reasons.append("no corroborating text evidence found")

        if onset is None:
            sequence_ok = False
            reasons.append("no durable onset detected")
        elif first_ev is None:
            sequence_ok = False
            reasons.append("no dated evidence to order against the onset")
        else:
            sequence_ok = first_ev <= onset
            if not sequence_ok:
                reasons.append(f"evidence begins {first_ev}, after onset {onset}")

        out.append(Verdict(
            driver=name, kind="evidential", lever=decl.get("lever", "unknown"),
            controllable=bool(decl.get("controllable", False)),
            contribution=0.0, share=0.0, strength=ratio,
            sequence_ok=sequence_ok, magnitude_ok=magnitude_ok,
            mechanism_ok=mechanism_ok, onset=onset, first_evidence=first_ev,
            evidence=evidence[:3], reasons=reasons,
        ))

    return out


def _finalise(wh: Warehouse, movement: Movement, verdicts: list[Verdict],
              min_share: float) -> Assessment:
    """Apply the contract's abstention policy and score confidence."""
    reasons: list[str] = []
    causes = [v for v in verdicts if v.is_cause]
    arithmetic = [v for v in verdicts if v.kind == "arithmetic"]
    root_causes = [v for v in causes if v.kind == "evidential"]
    # only arithmetic drivers carry a share of the movement, so only they can
    # answer the question of whether any one driver explains enough of it
    top_share = max((v.share for v in arithmetic), default=0.0)

    if top_share < min_share:
        reasons.append(f"no single driver explains more than {min_share:.0%} "
                       f"of the movement (best is {top_share:.0%})")

    if movement.sparse:
        reasons.append(f"sparse history: {movement.history_days} days against a "
                       f"{movement.min_history_days} day minimum")

    ranked = sorted(arithmetic, key=lambda v: abs(v.share), reverse=True)
    competing: list[str] = []
    if len(ranked) >= 2 and abs(ranked[0].share - ranked[1].share) < 0.10:
        competing = [ranked[0].driver, ranked[1].driver]
        reasons.append(f"competing hypotheses within 10 points: "
                       f"{ranked[0].driver} and {ranked[1].driver}")

    for src, spec in wh.c.sources.items():
        if spec["expected_lag_hours"] > spec.get("staleness_warning_hours", 1e9):
            reasons.append(f"source '{src}' is stale")

    if not causes:
        reasons.append("no driver passed all three causal gates")

    abstain = bool(reasons)

    if abstain:
        confidence = "low" if causes else "none"
    elif top_share >= 0.6 and root_causes:
        # one lever explains most of the movement AND an upstream root cause is
        # dated, corroborated and precedes it
        confidence = "high"
    elif top_share >= 0.45:
        confidence = "medium"
    else:
        confidence = "low"

    if movement.confidence_cap:
        cap = movement.confidence_cap
        if CONFIDENCE_ORDER.index(confidence) > CONFIDENCE_ORDER.index(cap):
            confidence = cap

    check = None
    if competing:
        check = (f"Split the movement by {competing[0]} and {competing[1]} over the "
                 f"prior two periods. Whichever retains its share is the driver.")
    elif abstain and not causes:
        check = ("Re-run once the stale source lands, or widen the comparison window "
                 "so the slice clears its minimum history.")

    return Assessment(movement=movement, verdicts=verdicts, confidence=confidence,
                      abstain=abstain, abstain_reasons=reasons,
                      competing=competing, discriminating_check=check)
