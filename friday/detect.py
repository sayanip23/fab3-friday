"""Lane A — materiality detection.

Decides whether a KPI movement is worth anyone's attention at all, using
the method the contract specifies (robust_z_score) rather than a hardcoded
threshold. This module never sees the planted scenario — it only sees raw
sales_transactions and the contract, and has to notice the West net_revenue
drop on its own.
"""
from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from friday.contracts import Contract


@dataclasses.dataclass(frozen=True)
class MaterialityResult:
    kpi: str
    grain_key: dict          # e.g. {"region": "West"}
    baseline_median: float
    baseline_mad: float
    current_value: float
    comparison_value: float
    z_score: float
    pct_change: float | None
    abs_change: float
    is_statistically_material: bool
    is_business_material: bool
    is_material: bool         # both statistical AND business thresholds, per contract
    reason: str


def _robust_z(value: float, baseline: np.ndarray) -> tuple[float, float, float]:
    """Median/MAD-based z-score — robust to the outliers a plain mean/std
    would let a single freak day distort."""
    median = float(np.median(baseline))
    mad = float(np.median(np.abs(baseline - median)))
    # 1.4826 makes MAD a consistent estimator of std under normality.
    scaled_mad = mad * 1.4826
    if scaled_mad == 0:
        z = 0.0 if value == median else np.inf
    else:
        z = (value - median) / scaled_mad
    return z, median, mad


def _daily_series(sales: pd.DataFrame, region: str) -> pd.Series:
    df = sales[sales["region"] == region].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["revenue"] = df["units"] * df["unit_price"]
    return df.groupby("date")["revenue"].sum()


def _rolling_window_sums(daily: pd.Series, window_days: int, start: pd.Timestamp,
                          end: pd.Timestamp) -> np.ndarray:
    """Every overlapping `window_days`-day sum with an end date in
    [start, end] — the distribution of 'what a typical N-day total looks
    like' that the current period gets compared against."""
    idx = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    full = daily.reindex(idx, fill_value=0.0)
    sums = full.rolling(window_days).sum()
    return sums[(sums.index >= start) & (sums.index <= end)].dropna().to_numpy()


def detect_region_revenue_movement(sales: pd.DataFrame, contract: Contract, region: str,
                                    comparison_period: tuple[pd.Timestamp, pd.Timestamp],
                                    current_period: tuple[pd.Timestamp, pd.Timestamp]) -> MaterialityResult:
    """Materiality check for net_revenue in one region, current vs
    comparison window, against a rolling 90-day baseline distribution."""
    kpi = contract.get_kpi("net_revenue")
    window_days = (current_period[1] - current_period[0]).days + 1
    baseline_days = kpi.materiality["baseline_window_days"]
    threshold_z = kpi.materiality["threshold_z"]
    min_impact = kpi.materiality.get("min_business_impact_inr", 0)

    daily = _daily_series(sales, region)

    baseline_end = comparison_period[0] - pd.Timedelta(days=1)
    baseline_start = baseline_end - pd.Timedelta(days=baseline_days - 1)
    baseline = _rolling_window_sums(daily, window_days, baseline_start, baseline_end)

    comparison_value = float(daily[(daily.index >= comparison_period[0])
                                    & (daily.index <= comparison_period[1])].sum())
    current_value = float(daily[(daily.index >= current_period[0])
                                 & (daily.index <= current_period[1])].sum())

    if len(baseline) < 5:
        # Not enough history to judge — abstain rather than guess, per the
        # sparse_history policy.
        z = float("nan")
        stat_material = False
        reason = f"only {len(baseline)} baseline windows available (<5); insufficient history to judge materiality"
        median = mad = float("nan")
    else:
        z, median, mad = _robust_z(current_value, baseline)
        stat_material = abs(z) >= threshold_z
        reason = f"z={z:.2f} vs threshold {threshold_z}"

    abs_change = current_value - comparison_value
    pct_change = (abs_change / comparison_value * 100) if comparison_value else None
    business_material = abs(abs_change) >= min_impact

    return MaterialityResult(
        kpi="net_revenue",
        grain_key={"region": region},
        baseline_median=median,
        baseline_mad=mad,
        current_value=current_value,
        comparison_value=comparison_value,
        z_score=z,
        pct_change=pct_change,
        abs_change=abs_change,
        is_statistically_material=stat_material,
        is_business_material=business_material,
        is_material=bool(stat_material and business_material),
        reason=reason,
    )


def detect_all_regions(sales: pd.DataFrame, contract: Contract,
                        comparison_period: tuple[pd.Timestamp, pd.Timestamp],
                        current_period: tuple[pd.Timestamp, pd.Timestamp]) -> list[MaterialityResult]:
    """Scan every region and return only material movements, ranked by
    absolute rupee impact — this is the triage step: most enterprise
    dashboards fire far more alerts than are worth a human's attention."""
    results = [
        detect_region_revenue_movement(sales, contract, region, comparison_period, current_period)
        for region in contract.business["regions"]
    ]
    return sorted(results, key=lambda r: abs(r.abs_change), reverse=True)


@dataclasses.dataclass(frozen=True)
class HistorySufficiencyResult:
    product_line: str
    history_days: int
    min_required_days: int
    is_sufficient: bool
    reason: str


def check_history_sufficiency(sales: pd.DataFrame, contract: Contract, product_line: str,
                               as_of: pd.Timestamp) -> HistorySufficiencyResult:
    """Sparse-history guard, per contracts/kpis.yaml policies.sparse_history.
    A product with too little history gets flagged rather than fed into
    materiality/trend logic that assumes a stable baseline exists."""
    min_days = contract.policies["sparse_history"]["min_history_days"]
    rows = sales[sales["product_line"] == product_line]
    if len(rows) == 0:
        return HistorySufficiencyResult(product_line, 0, min_days, False, "no sales rows found at all")

    first_date = pd.to_datetime(rows["date"]).min()
    history_days = int((as_of - first_date).days) + 1
    sufficient = history_days >= min_days
    reason = (f"{history_days} days of history since first sale on {first_date.date()} "
              f"(policy requires >= {min_days})")
    return HistorySufficiencyResult(product_line, history_days, min_days, sufficient, reason)
