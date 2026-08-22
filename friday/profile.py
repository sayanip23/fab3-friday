"""
Bring your own data.

Profiles an arbitrary CSV and synthesises a KPI contract for it, so the same
detection / attribution / causal / abstention pipeline can run against data the
engine has never seen.

This is the honest answer to "does it only work on your example?". Everything
downstream reads the contract, so if we can write a correct contract for an
uploaded file, every stage works unchanged.

What it cannot do, stated plainly rather than faked:

  price/volume/mix  needs a unit-count column and a unit-price column. Most
                    CSVs have neither, so uploaded data gets dimensional
                    attribution instead and the UI says so.
  evidence          needs a free-text corpus. Without one the causal screen
                    runs on the arithmetic path only, and confidence is capped
                    because no upstream cause can be corroborated.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# A column with more distinct values than this is an identifier, not a
# dimension. Grouping revenue by order_id produces one row per order and
# explains nothing.
MAX_DIMENSION_CARDINALITY = 60
MAX_DIMENSION_RATIO = 0.5

# Columns whose names alone disqualify them as measures.
ID_HINTS = ("id", "key", "code", "number", "no", "ref", "uuid", "guid", "index")

UNIT_HINTS = ("unit", "units", "qty", "quantity", "volume", "count")
PRICE_HINTS = ("price", "rate", "unit_price", "unitprice", "asp")


@dataclass
class Profile:
    """What we found in the file, and what we can therefore compute."""
    rows: int
    date_column: str | None
    measures: list[str] = field(default_factory=list)
    dimensions: list[str] = field(default_factory=list)
    unit_column: str | None = None
    price_column: str | None = None
    date_min: str | None = None
    date_max: str | None = None
    span_days: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return bool(self.date_column and self.measures and self.rows >= 30)

    @property
    def supports_pvm(self) -> bool:
        """Price/volume/mix needs both a unit count and a per-unit price."""
        return bool(self.unit_column and self.price_column)


def _looks_like_id(name: str, series: pd.Series, rows: int) -> bool:
    low = name.lower()
    if any(low == h or low.endswith("_" + h) for h in ID_HINTS):
        return True
    # Near-unique integers are almost always keys.
    if pd.api.types.is_integer_dtype(series) and series.nunique() > 0.9 * rows:
        return True
    return False


def _detect_date(df: pd.DataFrame) -> tuple[str | None, list[str]]:
    """
    Pick the column that parses as dates most reliably.

    Scored on parse rate rather than the first success: a product code like
    "2024-A" can parse partially, and choosing it would silently wreck every
    downstream period comparison.
    """
    notes: list[str] = []
    best, best_rate = None, 0.0

    for col in df.columns:
        s = df[col]
        if pd.api.types.is_numeric_dtype(s):
            continue
        sample = s.dropna().astype(str).head(400)
        if sample.empty:
            continue
        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        rate = parsed.notna().mean()
        if rate > best_rate:
            best, best_rate = col, rate

    if best is None or best_rate < 0.8:
        notes.append(
            "No column parsed reliably as a date. A date column is required: "
            "every comparison in the engine is period against period."
        )
        return None, notes

    if best_rate < 0.98:
        notes.append(
            f"'{best}' parsed as a date for {best_rate:.0%} of rows; "
            f"unparseable rows are dropped."
        )
    return best, notes


def _match(cols: list[str], hints: tuple[str, ...]) -> str | None:
    for c in cols:
        low = c.lower().replace(" ", "_")
        if any(h == low or h in low.split("_") for h in hints):
            return c
    return None


def profile_frame(df: pd.DataFrame) -> Profile:
    """Inspect a DataFrame and report what the engine can do with it."""
    rows = len(df)
    warnings: list[str] = []

    date_col, notes = _detect_date(df)
    warnings += notes

    measures, dimensions = [], []
    for col in df.columns:
        if col == date_col:
            continue
        s = df[col]
        if pd.api.types.is_numeric_dtype(s):
            if _looks_like_id(col, s, rows):
                continue
            if s.notna().sum() < rows * 0.5:
                warnings.append(f"'{col}' is more than half empty and was skipped.")
                continue
            measures.append(col)
        else:
            n = s.nunique(dropna=True)
            if 2 <= n <= MAX_DIMENSION_CARDINALITY and n <= rows * MAX_DIMENSION_RATIO:
                dimensions.append(col)

    if not measures:
        warnings.append("No numeric measure column found. There is nothing to track.")
    if not dimensions:
        warnings.append(
            "No categorical column found, so the engine can detect a movement "
            "but cannot say which segment caused it."
        )

    unit_col = _match(measures, UNIT_HINTS)
    price_col = _match(measures, PRICE_HINTS)

    d_min = d_max = None
    span = 0
    if date_col:
        d = pd.to_datetime(df[date_col], errors="coerce", format="mixed").dropna()
        if not d.empty:
            d_min, d_max = str(d.min().date()), str(d.max().date())
            span = int((d.max() - d.min()).days)
            if span < 56:
                warnings.append(
                    f"Only {span} days of history. The engine needs two equal "
                    f"periods plus a baseline; expect low confidence and abstention."
                )

    return Profile(
        rows=rows, date_column=date_col, measures=measures, dimensions=dimensions,
        unit_column=unit_col, price_column=price_col,
        date_min=d_min, date_max=d_max, span_days=span, warnings=warnings,
    )


def normalise(df: pd.DataFrame, profile: Profile) -> pd.DataFrame:
    """Coerce to the shape the Warehouse expects: a parsed `_d` date column."""
    out = df.copy()
    out["_d"] = pd.to_datetime(out[profile.date_column], errors="coerce",
                               format="mixed").dt.date
    out = out.dropna(subset=["_d"])
    for m in profile.measures:
        out[m] = pd.to_numeric(out[m], errors="coerce")
    return out


def build_contract(profile: Profile, df: pd.DataFrame,
                   source_name: str = "uploaded") -> dict:
    """
    Synthesise a contract dict for the uploaded data.

    Thresholds are derived from the file's own behaviour rather than copied
    from the demo contract. A materiality floor that suits crores of rupees
    would never fire on a dataset counting support tickets.
    """
    kpis: dict = {}

    for m in profile.measures:
        series = pd.to_numeric(df[m], errors="coerce").dropna()
        daily = df.groupby("_d")[m].sum() if "_d" in df else series

        # Business floor: half the median day, so an ordinary day's worth of
        # movement is not treated as an event.
        typical_day = float(np.nanmedian(daily)) if len(daily) else float(series.mean() or 1)
        min_abs = max(abs(typical_day) * 0.5, 1e-9)

        kpis[m] = {
            "label": m.replace("_", " ").title(),
            "definition": f"Sum of '{m}' from the uploaded file.",
            "formula": f"sum({m})",
            "calculation_method": "deterministic_sql",
            # generic computation contract — read by Warehouse.value()
            "column": m,
            "agg": "sum",
            "source": source_name,
            "sources": [source_name],
            "time_grain": "daily",
            "unit": "",
            "direction": "higher_is_better",
            "decomposable_by": list(profile.dimensions),
            "drivers": [
                {"name": d, "type": "internal", "controllable": True, "lever": "review"}
                for d in profile.dimensions
            ],
            "materiality": {
                "statistical": {
                    "method": "robust_z_score",
                    "baseline_window_days": 90,
                    "threshold": 2.0,
                },
                "business": {"min_abs_change": min_abs, "min_pct_change": 3.0},
                "require_both": True,
            },
            "min_history_days": 60,
            "lineage": [
                f"uploaded file, column '{m}'",
                f"dates parsed from '{profile.date_column}'",
                "summed by day, then by the requested period",
            ],
            "access": {"roles_allowed": ["owner"]},
        }

    dimensions = {
        d: {"values": sorted(map(str, df[d].dropna().unique()))[:MAX_DIMENSION_CARDINALITY]}
        for d in profile.dimensions
    }

    return {
        "contract_version": 1,
        "steward": "uploaded at runtime",
        "sources": {
            source_name: {
                "label": "Uploaded file",
                "system": "user upload",
                "grain": "row",
                "time_grain": "daily",
                "refresh_cadence": "on upload",
                "expected_lag_hours": 0,
                "staleness_warning_hours": 1e9,
                "file": None,           # injected as a frame, never read from disk
                "keys": [],
                "contains_free_text": False,
            }
        },
        "dimensions": dimensions,
        "kpis": kpis,
        "sparse_history_policy": {
            "trigger": "observed_history_days < min_history_days",
            "actions": [
                {"widen_prediction_interval_by": 1.8},
                {"cap_confidence_at": "low"},
                {"suppress_causal_claims": True},
            ],
            "disclaimer": (
                "This slice has {observed_history_days} days of history against a "
                "{min_history_days} day requirement. Movement is reported, but no "
                "cause is asserted."
            ),
        },
        "roles": {
            "owner": {
                "label": "Data owner",
                "region_scope": "all",
                "can_see_account_names": True,
                "kpis": list(kpis),
                "narrative_depth": "detailed",
                "decision_rights": ["review_finding"],
            }
        },
        "action_schema": {
            "required_fields": [
                "driver", "controllable_lever", "action", "expected_impact",
                "owner", "confidence", "monitoring_plan",
            ],
            "rule": "Actions only for controllable drivers.",
            "lever_rights": {"review": "review_finding"},
            "lever_actions": {
                "review": "Review the {segment} segment, which accounts for most of the movement.",
            },
        },
        "abstention": {
            "abstain_when": [
                "evidence_sources_agreeing < 2",
                "top_driver_contribution_share < 0.35",
                "sparse_history_triggered: true",
            ],
            "behaviour": "State the movement, present competing slices, assert no cause.",
        },
    }
