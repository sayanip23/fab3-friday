"""Lane A — attribution.

Decomposes a material KPI movement into ranked, reconciling drivers, using
only raw sales_transactions — this module has no knowledge of what was
planted. It must independently discover that one account explains most of
the West net_revenue drop, and separate that from the smaller price/mix
effect riding on top of it.

Method: an account-level split (does one account's departure explain the
move?) combined with a price/volume/mix decomposition of everyone else, by
product line. This mirrors standard PVM analysis, generalized to rank
*any* segment (account, product, channel) by contribution share rather
than assuming in advance which dimension matters.
"""
from __future__ import annotations

import dataclasses

import pandas as pd

COMPARISON_PERIOD = None  # set by caller; kept here only for type clarity


@dataclasses.dataclass(frozen=True)
class SegmentContribution:
    dimension: str          # "account", "product_line", "channel"
    segment: str
    revenue_comparison: float
    revenue_current: float
    contribution_inr: float
    contribution_share: float   # of total |change|


@dataclasses.dataclass(frozen=True)
class PriceVolumeMix:
    revenue_comparison: float
    revenue_current: float
    total_change_inr: float
    volume_effect_inr: float
    mix_effect_inr: float
    price_effect_inr: float
    reconciled_sum_inr: float
    reconciles_exactly: bool


@dataclasses.dataclass(frozen=True)
class AttributionResult:
    region: str
    total_change_inr: float
    top_segments: list[SegmentContribution]
    pvm: PriceVolumeMix
    dominant_segment: SegmentContribution | None


def _slice(sales: pd.DataFrame, region: str) -> pd.DataFrame:
    df = sales[sales["region"] == region].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["revenue"] = df["units"] * df["unit_price"]
    return df


def _period_revenue(df: pd.DataFrame, col: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    p = df[(df["date"] >= start) & (df["date"] <= end)]
    return p.groupby(col)["revenue"].sum()


def rank_segments(sales: pd.DataFrame, region: str, dimension: str,
                   comparison_period: tuple[pd.Timestamp, pd.Timestamp],
                   current_period: tuple[pd.Timestamp, pd.Timestamp]) -> list[SegmentContribution]:
    """Rank every value of `dimension` (e.g. account_name) by how much of
    the total revenue change it accounts for. This is a generic driver
    search — it doesn't know in advance that 'account_name' will be the
    answer for this scenario; the caller tries multiple dimensions and lets
    the ranking speak for itself.
    """
    df = _slice(sales, region)
    rev0 = _period_revenue(df, dimension, *comparison_period)
    rev1 = _period_revenue(df, dimension, *current_period)
    all_segments = sorted(set(rev0.index) | set(rev1.index))
    rev0 = rev0.reindex(all_segments, fill_value=0.0)
    rev1 = rev1.reindex(all_segments, fill_value=0.0)

    # Share is relative to the *net* total change (what we're actually
    # trying to explain), not the gross sum of |changes| across every
    # segment — with many small accounts, gross churn can dwarf the net
    # movement even when one segment clearly dominates the real story.
    total_net_change = float((rev1 - rev0).sum())
    out = []
    for seg in all_segments:
        change = float(rev1[seg] - rev0[seg])
        share = (change / total_net_change) if total_net_change else 0.0
        out.append(SegmentContribution(
            dimension=dimension, segment=seg,
            revenue_comparison=round(float(rev0[seg]), 2),
            revenue_current=round(float(rev1[seg]), 2),
            contribution_inr=round(change, 2),
            contribution_share=round(share, 4),
        ))
    return sorted(out, key=lambda s: abs(s.contribution_inr), reverse=True)


def _pvm_by_product(df: pd.DataFrame, comparison_period, current_period) -> PriceVolumeMix:
    g0 = df[(df["date"] >= comparison_period[0]) & (df["date"] <= comparison_period[1])] \
        .groupby("product_line").agg(units=("units", "sum"), revenue=("revenue", "sum"))
    g1 = df[(df["date"] >= current_period[0]) & (df["date"] <= current_period[1])] \
        .groupby("product_line").agg(units=("units", "sum"), revenue=("revenue", "sum"))
    g0["price"] = g0["revenue"] / g0["units"]
    g1["price"] = g1["revenue"] / g1["units"]
    all_products = sorted(set(g0.index) | set(g1.index))
    g0 = g0.reindex(all_products, fill_value=0.0)
    g1 = g1.reindex(all_products, fill_value=0.0)

    total_units0, total_units1 = g0["units"].sum(), g1["units"].sum()
    avg_price0 = (g0["revenue"].sum() / total_units0) if total_units0 else 0.0
    rev0, rev1 = g0["revenue"].sum(), g1["revenue"].sum()
    share0 = (g0["units"] / total_units0) if total_units0 else g0["units"] * 0
    share1 = (g1["units"] / total_units1) if total_units1 else g1["units"] * 0

    volume_effect = (total_units1 - total_units0) * avg_price0
    mix_effect = ((share1 - share0) * g0["price"].fillna(0)).sum() * total_units1
    price_effect = (g1["units"] * (g1["price"].fillna(0) - g0["price"].fillna(0))).sum()
    total_change = rev1 - rev0
    reconciled = volume_effect + mix_effect + price_effect

    return PriceVolumeMix(
        revenue_comparison=round(float(rev0), 2),
        revenue_current=round(float(rev1), 2),
        total_change_inr=round(float(total_change), 2),
        volume_effect_inr=round(float(volume_effect), 2),
        mix_effect_inr=round(float(mix_effect), 2),
        price_effect_inr=round(float(price_effect), 2),
        reconciled_sum_inr=round(float(reconciled), 2),
        reconciles_exactly=bool(abs(reconciled - total_change) < 1.0),
    )


def attribute_region_movement(sales: pd.DataFrame, region: str,
                               comparison_period: tuple[pd.Timestamp, pd.Timestamp],
                               current_period: tuple[pd.Timestamp, pd.Timestamp],
                               dominant_share_threshold: float = 0.5) -> AttributionResult:
    """Full attribution for one region's net_revenue movement.

    Strategy: rank accounts by contribution share first. If one account
    explains more than `dominant_share_threshold` of the total change, it
    is treated as a distinct driver and excluded before running the
    product-level price/volume/mix split on the remainder — otherwise a
    single account's departure gets smeared across every product it used
    to buy, hiding the real story. If no account dominates, run PVM on the
    full region instead.
    """
    df = _slice(sales, region)
    account_ranking = rank_segments(sales, region, "account_name", comparison_period, current_period)

    total_rev0 = float(df[(df["date"] >= comparison_period[0]) & (df["date"] <= comparison_period[1])]["revenue"].sum())
    total_rev1 = float(df[(df["date"] >= current_period[0]) & (df["date"] <= current_period[1])]["revenue"].sum())
    total_change = total_rev1 - total_rev0

    dominant = account_ranking[0] if account_ranking else None
    if dominant and abs(dominant.contribution_share) >= dominant_share_threshold:
        remainder = df[df["account_name"] != dominant.segment]
        pvm = _pvm_by_product(remainder, comparison_period, current_period)
    else:
        dominant = None
        pvm = _pvm_by_product(df, comparison_period, current_period)

    return AttributionResult(
        region=region,
        total_change_inr=round(total_change, 2),
        top_segments=account_ranking[:5],
        pvm=pvm,
        dominant_segment=dominant,
    )
