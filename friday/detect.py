"""
Phase 2. Materiality detection and prioritisation.

Answers Round 2 objective 1: "Detects and prioritises material KPI movements."

A movement is material only when it clears BOTH gates declared in the contract:

  statistical  the change is unusual against this slice's own history
  business     the change is large enough that somebody should act

The contract sets require_both: true, matching the brief's insistence that
materiality rests on "both statistical significance and business impact".

Method: robust z score. Median and MAD, not mean and standard deviation, because a
handful of past shocks would otherwise inflate the baseline and hide real movements.
Deterministic. No LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from .contracts import Contract
from .kpi import Filters, Period, Warehouse

MAD_TO_SIGMA = 1.4826


@dataclass
class Movement:
    kpi: str
    label: str
    filters: dict
    current: float
    prior: float
    delta: float
    pct: float
    unit: str

    z_score: float
    baseline_median_pct: float
    baseline_n: int

    statistical_pass: bool
    business_pass: bool
    material: bool

    sparse: bool
    history_days: int
    min_history_days: int
    confidence_cap: str | None

    priority: float = 0.0
    notes: list[str] = field(default_factory=list)

    @property
    def slice_label(self) -> str:
        if not self.filters:
            return "all"
        return ", ".join(f"{k}={v}" for k, v in self.filters.items())

    def summary(self) -> str:
        arrow = "down" if self.delta < 0 else "up"
        return (f"{self.label} [{self.slice_label}] {arrow} {abs(self.pct):.1f}% "
                f"({self.delta:+,.0f} {self.unit})")


def _robust_z(current: float, history: np.ndarray) -> tuple[float, float, int]:
    """Robust z of `current` against a history of comparable period changes."""
    clean = history[np.isfinite(history)]
    if len(clean) < 8:
        return float("nan"), float("nan"), len(clean)
    med = float(np.median(clean))
    mad = float(np.median(np.abs(clean - med)))
    sigma = mad * MAD_TO_SIGMA
    if sigma <= 1e-12:
        sigma = float(np.std(clean)) or 1e-12
    return (current - med) / sigma, med, len(clean)


def _baseline_changes(wh: Warehouse, kpi: str, period: Period, filters: Filters,
                      window_days: int) -> np.ndarray:
    """
    Distribution of historical period over period percentage changes for this slice.

    We roll the same comparison the user is making (N days against the preceding N
    days) backwards through history, so the current movement is judged against
    like for like rather than against daily noise.
    """
    hist_end = period.start - timedelta(days=1)
    hist_start = hist_end - timedelta(days=window_days + 2 * period.days)

    series, grain = wh.series(kpi, hist_start, hist_end, filters)
    # compare like for like: the same span the user is comparing, in the KPI's own grain
    n = max(1, period.days // 7) if grain == "weekly" else period.days

    if series.empty or len(series) < 2 * n + 4:
        return np.array([])

    ratio_kpis = {"avg_selling_price", "gross_margin_pct", "marketing_efficiency"}
    if kpi in ratio_kpis:
        block = series.rolling(n, min_periods=max(3, n // 2)).mean()
    else:
        block = series.rolling(n, min_periods=max(3, n // 2)).sum()

    cur = block.iloc[n:].to_numpy(dtype=float)
    pre = block.iloc[:-n].to_numpy(dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = 100.0 * (cur - pre) / np.where(pre == 0, np.nan, pre)
    return pct[np.isfinite(pct)]


def evaluate(wh: Warehouse, kpi: str, period: Period,
             filters: Filters = None, threshold_multiplier: float = 1.0) -> Movement:
    """
    Evaluate one KPI on one slice against the contract's materiality gates.

    `threshold_multiplier` carries the learned nudge from the feedback store, so a
    slice an analyst has repeatedly marked immaterial gets a higher bar. Default 1.0
    leaves contract behaviour untouched.
    """
    c: Contract = wh.c
    spec = c.kpis[kpi]
    stat_cfg, biz_cfg, require_both = spec.thresholds()

    prior_period = period.shifted(period.days)
    cur = wh.value(kpi, period, filters)
    pri = wh.value(kpi, prior_period, filters)

    delta = cur - pri
    pct = 100.0 * delta / pri if pri not in (0, None) and np.isfinite(pri) else float("nan")

    window = stat_cfg.get("baseline_window_days", 90)
    if stat_cfg.get("baseline_unit") == "weeks":
        window *= 7
    hist = _baseline_changes(wh, kpi, period, filters, window)
    z, med, n_obs = _robust_z(pct, hist)

    # sparse history policy, straight from the contract
    hist_days = wh.history_days(kpi, filters)
    min_days = spec.min_history_days
    sparse = hist_days < min_days
    cap = None
    notes: list[str] = []
    if sparse:
        policy = c.sparse_policy
        cap = next((a["cap_confidence_at"] for a in policy["actions"]
                    if "cap_confidence_at" in a), "low")
        notes.append(policy["disclaimer"].strip().format(
            observed_history_days=hist_days, min_history_days=min_days))

    stat_threshold = stat_cfg.get("threshold", 3.0) * threshold_multiplier
    if abs(threshold_multiplier - 1.0) > 1e-9:
        notes.append(f"threshold adjusted x{threshold_multiplier:.2f} by analyst feedback")
    if sparse:
        widen = next((a["widen_prediction_interval_by"] for a in c.sparse_policy["actions"]
                      if "widen_prediction_interval_by" in a), 1.0)
        stat_threshold *= widen
        notes.append(f"statistical threshold widened to {stat_threshold:.1f} "
                     f"by the sparse history policy")

    statistical_pass = bool(np.isfinite(z) and abs(z) >= stat_threshold)
    business_pass = bool(
        abs(delta) >= biz_cfg.get("min_abs_change", 0)
        and np.isfinite(pct) and abs(pct) >= biz_cfg.get("min_pct_change", 0)
    )

    material = (statistical_pass and business_pass) if require_both \
        else (statistical_pass or business_pass)

    if not np.isfinite(z):
        notes.append(f"insufficient baseline: only {n_obs} comparable periods")

    return Movement(
        kpi=kpi, label=spec.label, filters=dict(filters or {}),
        current=cur, prior=pri, delta=delta, pct=pct, unit=spec.unit,
        z_score=z, baseline_median_pct=med, baseline_n=n_obs,
        statistical_pass=statistical_pass, business_pass=business_pass,
        material=material, sparse=sparse, history_days=hist_days,
        min_history_days=min_days, confidence_cap=cap, notes=notes,
    )


def scan(wh: Warehouse, period: Period, role: str,
         dimension: str = "region") -> list[Movement]:
    """
    Sweep every KPI the role may see, across every value of one dimension plus the
    unfiltered total, and return material movements ordered by priority.

    Prioritisation is by absolute business impact, normalised per KPI so that a
    revenue movement in rupees and a margin movement in points can be ranked
    against each other.
    """
    c = wh.c
    found: list[Movement] = []
    values = c.dimensions[dimension]["values"]

    for kpi in c.visible_kpis(role):
        row_filter = c.row_filter(kpi, role)
        scope = values
        if row_filter == "own_region" and dimension == "region":
            scope = [c.roles[role]["region_scope"]]

        candidates: list[Filters] = [None] + [{dimension: v} for v in scope]
        for filters in candidates:
            if row_filter == "own_region" and filters is None:
                continue                      # role may not see the national total
            m = evaluate(wh, kpi, period, filters)
            if m.material:
                found.append(m)

    for m in found:
        biz = c.kpis[m.kpi].spec["materiality"]["business"]
        floor = max(biz.get("min_abs_change", 1), 1e-9)
        impact = abs(m.delta) / floor
        certainty = min(abs(m.z_score) / 3.0, 3.0) if np.isfinite(m.z_score) else 0.5
        m.priority = round(float(impact * certainty), 3)

    found.sort(key=lambda m: m.priority, reverse=True)
    return found


def dedupe_overlapping(movements: list[Movement]) -> list[Movement]:
    """
    Drop a national total when a single region already explains most of it, so the
    user is not alerted twice about the same underlying event.
    """
    keep: list[Movement] = []
    for m in movements:
        if m.filters:
            keep.append(m)
            continue
        same_kpi = [o for o in movements if o.kpi == m.kpi and o.filters]
        if same_kpi and max(abs(o.delta) for o in same_kpi) >= 0.7 * abs(m.delta):
            continue
        keep.append(m)
    return keep
