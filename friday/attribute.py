"""
Phase 3a. Contribution analysis.

Answers Round 2 objective 3: "Identifies and ranks explanatory drivers using
appropriate analytical methods."

Two complementary decompositions, both pure arithmetic:

  price_volume_mix   why revenue moved, in terms of the levers a business pulls
  by_dimension       where it moved, in terms of accounts, categories, channels

Both reconcile to the total movement exactly. That exactness is the point: it is
what lets us say the LLM is not the source of quantitative truth and mean it. If a
decomposition does not sum to the movement, the engine refuses to publish it.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .kpi import Filters, Period, Warehouse

RECONCILE_TOLERANCE = 1e-6


@dataclass(frozen=True)
class Effect:
    name: str
    driver: str
    value: float
    share: float          # signed share of the total movement

    def __str__(self) -> str:
        return f"{self.name} {self.value:+,.0f} ({self.share:+.1%})"


@dataclass
class Decomposition:
    method: str
    total_movement: float
    effects: list[Effect]
    residual: float
    reconciled: bool
    segment_dimension: str | None = None

    def top(self, n: int = 3) -> list[Effect]:
        return sorted(self.effects, key=lambda e: abs(e.value), reverse=True)[:n]

    def as_frame(self) -> pd.DataFrame:
        return pd.DataFrame([{
            "effect": e.name, "driver": e.driver,
            "value": round(e.value, 2), "share_of_movement": round(e.share, 4),
        } for e in sorted(self.effects, key=lambda e: abs(e.value), reverse=True)])


def price_volume_mix(wh: Warehouse, period: Period, filters: Filters = None,
                     segment_by: str = "category") -> Decomposition:
    """
    Three way decomposition of a revenue movement.

        volume = (U1 - U0) * P0bar
        mix    = sum over segments of (u1_i - U1 * s0_i) * (p0_i - P0bar)
        price  = sum over segments of u1_i * (p1_i - p0_i)

    where U is total units, P0bar is the prior blended price, s0_i is the prior
    unit share of segment i. These three sum to (R1 - R0) identically, so the
    residual below is a guard against data problems, not an approximation error.
    """
    prior = period.shifted(period.days)
    cur = wh.segments(period, segment_by, filters).set_index(segment_by)
    pri = wh.segments(prior, segment_by, filters).set_index(segment_by)

    seg = sorted(set(cur.index) | set(pri.index))
    cur = cur.reindex(seg).fillna(0.0).astype(float)
    pri = pri.reindex(seg).fillna(0.0).astype(float)

    u1, u0 = cur.units, pri.units
    r1, r0 = float(cur.revenue.sum()), float(pri.revenue.sum())
    U1, U0 = float(u1.sum()), float(u0.sum())

    if U0 == 0 or U1 == 0:
        return Decomposition("price_volume_mix", r1 - r0, [], r1 - r0, False, segment_by)

    P0bar = r0 / U0
    # a segment with no prior units has no prior price; use the blended price so it
    # lands in volume and mix rather than creating a false price effect
    p0 = (pri.revenue / u0.replace(0.0, np.nan)).fillna(P0bar)
    p1 = (cur.revenue / u1.replace(0.0, np.nan)).fillna(p0)
    s0 = u0 / U0

    volume = (U1 - U0) * P0bar
    mix = float(((u1 - U1 * s0) * (p0 - P0bar)).sum())
    price = float((u1 * (p1 - p0)).sum())

    total = r1 - r0
    residual = total - (volume + mix + price)
    denom = abs(total) if abs(total) > 1e-9 else 1.0

    effects = [
        Effect("Volume", "volume", float(volume), volume / denom),
        Effect("Price", "price", price, price / denom),
        Effect("Mix", "mix", mix, mix / denom),
    ]
    return Decomposition(
        method="price_volume_mix", total_movement=total, effects=effects,
        residual=float(residual),
        reconciled=abs(residual) / denom < RECONCILE_TOLERANCE,
        segment_dimension=segment_by,
    )


def by_dimension(wh: Warehouse, kpi: str, period: Period, dimension: str,
                 filters: Filters = None, top_n: int = 6) -> Decomposition:
    """
    Where the movement came from. Additive KPIs only, since a ratio cannot be
    split across slices without a weighting convention the contract does not define.
    """
    additive = {"net_revenue": "revenue", "units_sold": "units"}
    if kpi not in additive:
        raise ValueError(f"'{kpi}' is not additive and cannot be split by {dimension}")

    col = additive[kpi]
    prior = period.shifted(period.days)
    cur = wh.segments(period, dimension, filters).set_index(dimension)
    pri = wh.segments(prior, dimension, filters).set_index(dimension)

    keys = sorted(set(cur.index) | set(pri.index))
    c = cur.reindex(keys).fillna(0.0)[col].astype(float)
    p = pri.reindex(keys).fillna(0.0)[col].astype(float)

    deltas = (c - p).sort_values(key=abs, ascending=False)
    total = float(c.sum() - p.sum())
    denom = abs(total) if abs(total) > 1e-9 else 1.0

    effects = [Effect(str(k), dimension, float(v), float(v) / denom)
               for k, v in deltas.items()]

    head = effects[:top_n]
    tail = effects[top_n:]
    if tail:
        rest = sum(e.value for e in tail)
        head.append(Effect(f"all other {dimension}s ({len(tail)})", dimension,
                           rest, rest / denom))

    residual = total - sum(e.value for e in head)
    return Decomposition(
        method=f"contribution_by_{dimension}", total_movement=total, effects=head,
        residual=float(residual),
        reconciled=abs(residual) / denom < RECONCILE_TOLERANCE,
        segment_dimension=dimension,
    )
