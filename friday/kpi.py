"""
Contract driven KPI computation.

Every value returned here comes from deterministic pandas arithmetic against the
declared source, using the formula recorded in contracts/kpis.yaml. No LLM is
involved anywhere in this module, by design.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from .contracts import Contract, ContractError

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

Filters = dict[str, str] | None


@dataclass(frozen=True)
class Period:
    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def shifted(self, days: int) -> "Period":
        return Period(self.start - timedelta(days=days), self.end - timedelta(days=days))

    def __str__(self) -> str:
        return f"{self.start} to {self.end}"


def _dated(s: pd.Series) -> pd.Series:
    """
    Weekly series are keyed by week-start strings for joining. Callers compare the
    index against date objects, so normalise before returning: str <= date raises.
    """
    if len(s):
        s.index = pd.to_datetime(pd.Index(s.index)).date
    return s


def week_start(s: pd.Series) -> pd.Series:
    d = pd.to_datetime(s)
    return (d - pd.to_timedelta(d.dt.weekday, unit="D")).dt.date.astype(str)


class Warehouse:
    """Loads the declared sources and computes KPI values from the contract."""

    def __init__(self, contract: Contract, frames: dict[str, pd.DataFrame] | None = None):
        """
        `frames` injects already-loaded DataFrames instead of reading the paths
        in the contract. That is what lets an uploaded CSV run through the exact
        same pipeline as the bundled sources — the engine cannot tell the
        difference, which is the point.
        """
        self.c = contract
        self._frames: dict[str, pd.DataFrame] = {}
        for name, spec in contract.sources.items():
            if frames and name in frames:
                df = frames[name].copy()
                if "_d" not in df.columns:
                    raise ContractError(f"injected frame '{name}' has no parsed '_d' column")
                self._frames[name] = df
                continue
            path = os.path.join(ROOT, spec["file"])
            df = pd.read_csv(path)
            date_col = ("date" if "date" in df else
                        "week_start" if "week_start" in df else "event_ts")
            df["_d"] = pd.to_datetime(df[date_col]).dt.date
            self._frames[name] = df

    # ------------------------------------------------------------------ util
    def frame(self, source: str) -> pd.DataFrame:
        return self._frames[source]

    def _slice(self, source: str, period: Period | None, filters: Filters) -> pd.DataFrame:
        df = self._frames[source]
        if period is not None:
            df = df[(df["_d"] >= period.start) & (df["_d"] <= period.end)]
        for col, val in (filters or {}).items():
            if col in df.columns:
                df = df[df[col] == val]
        return df

    def freshness_hours(self, source: str, as_of: date) -> float:
        """How stale the source is, in hours, given its declared lag."""
        return float(self.c.sources[source]["expected_lag_hours"])

    def is_stale(self, source: str, as_of: date) -> bool:
        spec = self.c.sources[source]
        return spec["expected_lag_hours"] > spec.get("staleness_warning_hours", 1e9)

    def history_days(self, kpi: str, filters: Filters = None) -> int:
        """Observed history for this slice. Drives the sparse history policy."""
        spec = self.c.kpis[kpi].spec
        src = spec.get("source") or self.c.kpis[kpi].sources[0]
        df = self._slice(src, None, filters)
        return int(df["_d"].nunique())

    # ------------------------------------------------------------------ value
    def value(self, kpi: str, period: Period, filters: Filters = None) -> float:
        if kpi not in self.c.kpis:
            raise ContractError(f"unknown kpi '{kpi}'")

        spec = self.c.kpis[kpi].spec

        # Generic path: any KPI that declares a column and an aggregation is
        # computed without the engine knowing its name. Synthesised contracts
        # from uploaded files always take this route.
        if spec.get("column") and spec.get("agg"):
            return self._generic(kpi, spec, period, filters)

        if kpi == "marketing_efficiency":
            return self._marketing_efficiency(period, filters)

        df = self._slice("sales_transactions", period, filters)
        if df.empty:
            return float("nan")

        if kpi == "net_revenue":
            return float(df.revenue.sum())
        if kpi == "units_sold":
            return float(df.units.sum())
        if kpi == "avg_selling_price":
            u = df.units.sum()
            return float(df.revenue.sum() / u) if u else float("nan")
        if kpi == "gross_margin_pct":
            r = df.revenue.sum()
            return float(100.0 * (r - df.cost.sum()) / r) if r else float("nan")

        raise ContractError(f"no implementation for kpi '{kpi}'")

    def _generic(self, kpi: str, spec: dict, period: Period,
                 filters: Filters) -> float:
        """Aggregate one declared column over the period. No hardcoded names."""
        src = spec.get("source") or self.c.kpis[kpi].sources[0]
        df = self._slice(src, period, filters)
        if df.empty:
            return float("nan")
        col, agg = spec["column"], spec["agg"]
        if col not in df.columns:
            raise ContractError(f"column '{col}' not present in source '{src}'")
        series = pd.to_numeric(df[col], errors="coerce")
        return float(getattr(series, agg)())

    def _generic_series(self, kpi: str, spec: dict, start: date, end: date,
                        filters: Filters) -> pd.Series:
        src = spec.get("source") or self.c.kpis[kpi].sources[0]
        df = self._slice(src, Period(start, end), filters)
        if df.empty:
            return pd.Series(dtype=float)
        col, agg = spec["column"], spec["agg"]
        g = df.assign(**{col: pd.to_numeric(df[col], errors="coerce")}).groupby("_d")[col]
        s = getattr(g, agg)()
        idx = pd.date_range(start, end, freq="D").date
        return s.reindex(idx).astype(float)

    def _marketing_efficiency(self, period: Period, filters: Filters) -> float:
        """Crosses two grains. Sales aggregate upward to the weekly marketing grain."""
        sales = self._slice("sales_transactions", period, filters)
        mkt = self._slice("marketing_spend", period, filters)
        if sales.empty or mkt.empty:
            return float("nan")
        spend = mkt.spend.sum()
        return float(sales.revenue.sum() / spend) if spend else float("nan")

    # ----------------------------------------------------------------- series
    def daily_series(self, kpi: str, start: date, end: date,
                     filters: Filters = None) -> pd.Series:
        """Daily KPI values, used to build the materiality baseline."""
        spec = self.c.kpis[kpi].spec
        if spec.get("column") and spec.get("agg"):
            return self._generic_series(kpi, spec, start, end, filters)

        df = self._slice("sales_transactions", Period(start, end), filters)
        if df.empty:
            return pd.Series(dtype=float)

        g = df.groupby("_d")
        if kpi == "net_revenue":
            s = g.revenue.sum()
        elif kpi == "units_sold":
            s = g.units.sum().astype(float)
        elif kpi == "avg_selling_price":
            s = g.revenue.sum() / g.units.sum()
        elif kpi == "gross_margin_pct":
            r, c = g.revenue.sum(), g.cost.sum()
            s = 100.0 * (r - c) / r
        else:
            raise ContractError(f"no daily series for kpi '{kpi}'")

        idx = pd.date_range(start, end, freq="D").date
        return s.reindex(idx).astype(float)

    def weekly_series(self, kpi: str, start: date, end: date,
                      filters: Filters = None) -> pd.Series:
        """Weekly grain. Sales aggregate upward to meet the coarser marketing grain."""
        if kpi != "marketing_efficiency":
            daily = self.daily_series(kpi, start, end, filters)
            if daily.empty:
                return pd.Series(dtype=float)
            wk = pd.Series(daily.to_numpy(dtype=float),
                           index=week_start(pd.Series(list(daily.index))))
            wk = wk.groupby(level=0).sum()
            return _dated(wk)

        sales = self._slice("sales_transactions", Period(start, end), filters)
        mkt = self._slice("marketing_spend", Period(start, end), filters)
        if sales.empty or mkt.empty:
            return pd.Series(dtype=float)

        sales = sales.assign(_w=week_start(sales["date"]))
        mkt = mkt.assign(_w=mkt["week_start"].astype(str))
        rev = sales.groupby("_w").revenue.sum()
        spend = mkt.groupby("_w").spend.sum()
        joined = pd.concat([rev, spend], axis=1).dropna()
        joined = joined[joined.spend > 0]
        return _dated((joined.revenue / joined.spend).astype(float))

    def series(self, kpi: str, start: date, end: date,
               filters: Filters = None) -> tuple[pd.Series, str]:
        """Series at the KPI's declared time grain, plus that grain's name."""
        grain = self.c.kpis[kpi].time_grain
        if grain == "weekly":
            return self.weekly_series(kpi, start, end, filters), "weekly"
        return self.daily_series(kpi, start, end, filters), "daily"

    # ------------------------------------------------------- segment tables
    def generic_segments(self, source: str, column: str, agg: str, period: Period,
                         by: str, filters: Filters = None) -> pd.Series:
        """Aggregate one column per segment. Input to dimensional attribution."""
        df = self._slice(source, period, filters)
        if df.empty or by not in df.columns:
            return pd.Series(dtype=float)
        g = df.assign(**{column: pd.to_numeric(df[column], errors="coerce")}).groupby(by)[column]
        return getattr(g, agg)().astype(float)

    def segments(self, period: Period, by: str, filters: Filters = None) -> pd.DataFrame:
        """Units, revenue and realised price per segment. Input to price volume mix."""
        df = self._slice("sales_transactions", period, filters)
        if df.empty:
            return pd.DataFrame(columns=[by, "units", "revenue", "cost", "price"])
        out = df.groupby(by, as_index=False).agg(
            units=("units", "sum"), revenue=("revenue", "sum"), cost=("cost", "sum"))
        out["price"] = out.revenue / out.units
        return out
