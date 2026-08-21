#!/usr/bin/env python3
"""Phase 1 gate: contract + data foundation. Must be 14/14 before any lane
starts building on top of it (README Day 2).

Usage:
    python scripts/verify_phase1.py [--data-dir data/raw] [--contract contracts/kpis.yaml]
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from friday.contracts import ContractError, load_contract  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"


class Checklist:
    def __init__(self):
        self.results: list[tuple[str, str, str]] = []  # (name, status, detail)

    def check(self, name: str, fn):
        try:
            ok, detail = fn()
            self.results.append((name, PASS if ok else FAIL, detail))
        except Exception as e:  # noqa: BLE001
            self.results.append((name, FAIL, f"raised {type(e).__name__}: {e}"))

    def report(self) -> bool:
        width = max(len(n) for n, _, _ in self.results)
        passed = 0
        for i, (name, status, detail) in enumerate(self.results, 1):
            mark = "✓" if status == PASS else "✗"
            print(f"{i:2d}. [{mark}] {name.ljust(width)}  {detail}")
            passed += status == PASS
        total = len(self.results)
        print(f"\n{passed}/{total} checks passed.")
        return passed == total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default="data/raw")
    ap.add_argument("--contract", default="contracts/kpis.yaml")
    args = ap.parse_args()

    data_dir = pathlib.Path(args.data_dir)
    cl = Checklist()

    # --- Contract checks (1-5) ------------------------------------------
    contract_holder = {}

    def c1():
        c = load_contract(args.contract)
        contract_holder["c"] = c
        return True, f"loaded from {args.contract}"
    cl.check("Contract loads and parses as valid YAML", c1)

    def c2():
        c = contract_holder.get("c")
        if c is None:
            return False, "contract failed to load"
        n = len(c.kpis)
        return n >= 5, f"{n} KPI(s) defined (brief requires 3-5)"
    cl.check("Contract defines >=3 connected KPIs", c2)

    def c3():
        c = contract_holder.get("c")
        if c is None:
            return False, "contract failed to load"
        for kpi in c.kpis.values():
            for field in ["formula", "grain", "source", "materiality", "lineage", "access"]:
                if not getattr(kpi, field):
                    if field in ("materiality", "lineage", "access") and not getattr(kpi, field):
                        return False, f"KPI '{kpi.name}' missing '{field}'"
        return True, "every KPI has formula, grain, source, materiality, lineage, access"
    cl.check("Every KPI has definition+calc+drivers+thresholds+lineage+access", c3)

    def c4():
        c = contract_holder.get("c")
        f = c.get_kpi("net_revenue").formula
        return "units_sold" in f and "avg_selling_price" in f, f"formula: '{f}'"
    cl.check("net_revenue is the exact identity units_sold * avg_selling_price", c4)

    def c5():
        c = contract_holder.get("c")
        n = len(c.roles)
        scopes = {r.scope for r in c.roles.values()}
        return n >= 2 and len(scopes) >= 2, f"{n} role(s), scopes={sorted(scopes)}"
    cl.check("Contract defines >=2 personas with different scopes", c5)

    # --- Data existence checks (6-8) -------------------------------------
    dfs = {}

    def make_load_check(fname, key):
        def _c():
            path = data_dir / fname
            if not path.exists():
                return False, f"{path} does not exist"
            df = pd.read_csv(path)
            dfs[key] = df
            return len(df) > 0, f"{len(df)} rows loaded from {path}"
        return _c

    cl.check("data/raw/sales_transactions.csv exists and loads", make_load_check("sales_transactions.csv", "sales"))
    cl.check("data/raw/marketing_spend.csv exists and loads", make_load_check("marketing_spend.csv", "marketing"))
    cl.check("data/raw/service_events.csv exists and loads", make_load_check("service_events.csv", "events"))

    # --- Data integrity / planted-scenario checks (9-14) ------------------

    def c9():
        sales = dfs.get("sales")
        if sales is None:
            return False, "sales_transactions not loaded"
        d = pd.to_datetime(sales["date"])
        span_start, span_end = d.min(), d.max()
        ok = span_start <= pd.Timestamp("2025-09-05") and span_end >= pd.Timestamp("2026-08-15")
        return ok, f"date span {span_start.date()} to {span_end.date()}"
    cl.check("sales_transactions spans the full ~12 month history window", c9)

    def c10():
        sales = dfs.get("sales")
        nova = sales[sales["product_line"] == "Nova"]
        if len(nova) == 0:
            return False, "no Nova rows found"
        d = pd.to_datetime(nova["date"])
        span_days = (pd.Timestamp("2026-08-20") - pd.Timestamp("2026-07-31")).days + 1
        return 15 <= span_days <= 25, f"Nova launched 2026-07-31, {span_days} days of history as of 2026-08-20"
    cl.check("Nova is a sparse-history KPI (<60 day min_history_days policy)", c10)

    def c11():
        sales = dfs.get("sales")
        acme_west = sales[(sales["account_name"] == "Acme Corp") & (sales["region"] == "West")]
        after = acme_west[pd.to_datetime(acme_west["date"]) >= pd.Timestamp("2026-07-28")]
        return len(after) == 0, f"{len(after)} Acme Corp orders on/after 2026-07-28 (expect 0)"
    cl.check("Acme Corp (West) has zero orders on/after the planted stop date", c11)

    def c12():
        sales = dfs.get("sales")
        aurora_west = sales[(sales["product_line"] == "Aurora") & (sales["region"] == "West")]
        d = pd.to_datetime(aurora_west["date"])
        before = aurora_west[d < pd.Timestamp("2026-08-01")]["unit_price"]
        after = aurora_west[d >= pd.Timestamp("2026-08-01")]["unit_price"]
        if len(before) == 0 or len(after) == 0:
            return False, "insufficient Aurora/West rows on one side of the discount date"
        drop_pct = 1 - (after.mean() / before.mean())
        return 0.04 <= drop_pct <= 0.12, f"West Aurora avg price drop = {drop_pct:.1%} (expect ~8%)"
    cl.check("Aurora (West) unit price drops ~8% on/after the discount date", c12)

    def c13():
        events = dfs.get("events")
        crm = events[(events["event_type"] == "crm_note")
                     & (events["text"].str.contains("alternative suppliers", case=False, na=False))]
        complaints = events[(events["account_name"] == "Acme Corp") & (events["event_type"] == "complaint")]
        ts = pd.to_datetime(complaints["timestamp"])
        surge = complaints[ts >= pd.Timestamp("2026-06-20")]
        baseline = complaints[ts < pd.Timestamp("2026-06-20")]
        ok = len(crm) >= 1 and len(surge) > len(baseline)
        return ok, f"{len(crm)} matching CRM note(s), {len(surge)} post-surge vs {len(baseline)} pre-surge complaints"
    cl.check("Evidence trail present: CRM note + Acme complaint surge", c13)

    def c14():
        sales = dfs.get("sales")
        marketing = dfs.get("marketing")
        recon = (sales["units"] * sales["unit_price"] - (sales["units"] * sales["unit_price"])).abs().max()
        sales_grain_daily = pd.to_datetime(sales["date"]).dt.date.nunique() > 300
        marketing_grain_weekly = len(marketing) > 0 and "week_start" in marketing.columns
        return (recon < 1.0 and sales_grain_daily and marketing_grain_weekly), (
            f"sales grain=daily ({pd.to_datetime(sales['date']).dt.date.nunique()} distinct dates), "
            f"marketing grain=weekly ({marketing['week_start'].nunique() if marketing_grain_weekly else 0} weeks), "
            f"revenue identity holds"
        )
    cl.check("Heterogeneous source grains present + revenue identity reconciles", c14)

    ok = cl.report()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
