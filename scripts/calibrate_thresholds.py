"""
Calibrate the statistical materiality threshold against a measured false positive rate.

The Round 2 brief asks how we would "define, measure, and report false positive and
negative rates to a skeptical stakeholder". A threshold picked by intuition cannot
answer that. This script measures it.

Method: walk the same period over period comparison backwards through history, on
slices where nothing was planted. Any alert raised there is a false positive by
construction, because that history is ordinary trading. Sweep the threshold and read
off the alert rate.

Run:  python scripts/calibrate_thresholds.py
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from friday import contracts, detect                       # noqa: E402
from friday.kpi import Period, Warehouse                   # noqa: E402

# Quiet history only: ends before the planted logistics change on 2026-06-14.
EVAL_END = date(2026, 6, 1)
N_PERIODS = 20
STEP_DAYS = 7
PERIOD_DAYS = 28

KPIS = ["net_revenue", "units_sold", "avg_selling_price", "gross_margin_pct"]
SLICES = [None, {"region": "West"}, {"region": "North"},
          {"region": "South"}, {"region": "East"}]
THRESHOLDS = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]


def main() -> None:
    c = contracts.load()
    wh = Warehouse(c)

    zs: dict[str, list[float]] = {k: [] for k in KPIS}
    business_pass: dict[str, list[bool]] = {k: [] for k in KPIS}

    for i in range(N_PERIODS):
        end = EVAL_END - timedelta(days=i * STEP_DAYS)
        period = Period(end - timedelta(days=PERIOD_DAYS - 1), end)
        for kpi in KPIS:
            for filters in SLICES:
                m = detect.evaluate(wh, kpi, period, filters)
                if np.isfinite(m.z_score):
                    zs[kpi].append(abs(m.z_score))
                    business_pass[kpi].append(m.business_pass)

    print("Calibration on quiet history "
          f"(periods ending on or before {EVAL_END}, nothing planted)\n")
    print(f"{'KPI':<20} {'n':>5}  " +
          "  ".join(f"z>={t}" for t in THRESHOLDS))
    print("-" * 78)

    recommended: dict[str, float] = {}
    for kpi in KPIS:
        arr = np.array(zs[kpi])
        biz = np.array(business_pass[kpi])
        if not len(arr):
            continue

        rates = []
        for t in THRESHOLDS:
            # a false positive requires BOTH gates, exactly as production does
            fired = (arr >= t) & biz
            rates.append(fired.mean())
        print(f"{kpi:<20} {len(arr):>5}  " +
              "  ".join(f"{r:>5.1%}" for r in rates))

        # tightest threshold holding the false positive rate at or below 5%
        pick = next((t for t, r in zip(THRESHOLDS, rates) if r <= 0.05), THRESHOLDS[-1])
        recommended[kpi] = pick

    print("\nRecommended thresholds at a 5% false positive budget")
    print("-" * 78)
    for kpi, t in recommended.items():
        current = c.kpis[kpi].thresholds()[0].get("threshold")
        flag = "" if abs(current - t) < 1e-9 else f"   <-- contract says {current}"
        print(f"  {kpi:<20} {t}{flag}")

    print("\nNote: the business gate is applied alongside the statistical gate here, "
          "\nbecause that is how production evaluates a movement. Reporting a "
          "\nstatistical rate alone would overstate the alert volume.")


if __name__ == "__main__":
    main()
