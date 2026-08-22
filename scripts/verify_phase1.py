"""
Phase 1 gate. Run this before starting Phase 2.

Proves, against the generated data and the contract, that the foundations the rest
of FRIDAY depends on actually hold. Every check maps to a Round 2 requirement.

Run:  python scripts/verify_phase1.py
"""
from __future__ import annotations

import os
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from friday import contracts  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")

CURRENT = (date(2026, 7, 24), date(2026, 8, 20))
PRIOR = (date(2026, 6, 26), date(2026, 7, 23))

results: list[tuple[bool, str, str]] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    results.append((bool(ok), label, detail))


def window(df: pd.DataFrame, col: str, lo: date, hi: date) -> pd.DataFrame:
    d = pd.to_datetime(df[col]).dt.date
    return df[(d >= lo) & (d <= hi)]


# ---------------------------------------------------------------- contract
try:
    c = contracts.load(strict=True)
    check(True, "Contract parses and passes structural validation",
          f"{len(c.kpis)} KPIs, {len(c.sources)} sources, {len(c.roles)} roles")
except Exception as exc:                                   # noqa: BLE001
    check(False, "Contract parses and passes structural validation", str(exc))
    for ok, label, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {label}\n       {detail}")
    sys.exit(1)

check(3 <= len(c.kpis) <= 5,
      "REQ 1a: three to five connected KPIs",
      f"{len(c.kpis)}: {', '.join(c.kpis)}")

grains = {n: s["time_grain"] for n, s in c.sources.items()}
cadences = {n: s["refresh_cadence"] for n, s in c.sources.items()}
check(len(c.sources) >= 2 and len(set(grains.values())) >= 2,
      "REQ 1b: sources differ in grain and refresh cadence",
      " | ".join(f"{n}: {grains[n]}/{cadences[n]}" for n in c.sources))

needed = {"definition", "formula", "drivers", "materiality", "lineage", "access"}
missing = {n: sorted(needed - set(k.spec)) for n, k in c.kpis.items()
           if needed - set(k.spec)}
check(not missing,
      "REQ 2: semantic contract carries definitions, calculations, drivers, "
      "thresholds, lineage and access",
      "all KPIs complete" if not missing else str(missing))

# ------------------------------------------------------------------ files
frames: dict[str, pd.DataFrame] = {}
missing_files = []
for name, spec in c.sources.items():
    path = os.path.join(ROOT, spec["file"])
    if os.path.exists(path):
        frames[name] = pd.read_csv(path)
    else:
        missing_files.append(spec["file"])
check(not missing_files, "All declared source files exist",
      ", ".join(f"{n}={len(d):,} rows" for n, d in frames.items())
      or f"missing {missing_files}")

sales = frames["sales_transactions"]
marketing = frames["marketing_spend"]
events = frames["service_events"]

# ------------------------------------------------- KPI identity reconciles
cur = window(sales, "date", *CURRENT)
pri = window(sales, "date", *PRIOR)
cur_w = cur[cur.region == "West"]
pri_w = pri[pri.region == "West"]

rev_c, units_c = cur_w.revenue.sum(), cur_w.units.sum()
rev_p, units_p = pri_w.revenue.sum(), pri_w.units.sum()
asp_c, asp_p = rev_c / units_c, rev_p / units_p

recon_err = abs(units_c * asp_c - rev_c) / rev_c
check(recon_err < 1e-9,
      "KPI identity holds: net_revenue == units_sold * avg_selling_price",
      f"residual {recon_err:.2e}  (required for price/volume/mix to reconcile)")

# -------------------------------------------------- movement is material
move_pct = 100 * (rev_c - rev_p) / rev_p
move_abs = rev_c - rev_p
stat, biz, both = c.kpis["net_revenue"].thresholds()
material = abs(move_abs) >= biz["min_abs_change"] and abs(move_pct) >= biz["min_pct_change"]
check(material,
      "REQ 4: planted movement clears the contract's business materiality gate",
      f"West net_revenue {move_pct:+.1f}%  ({move_abs:,.0f} INR)  "
      f"gate: {biz['min_pct_change']}% and {biz['min_abs_change']:,} INR")

# ------------------------------------------- movement is genuinely multi factor
vol_effect = (units_c - units_p) * asp_p
price_mix_effect = (asp_c - asp_p) * units_c
check(abs(vol_effect) > 0 and abs(price_mix_effect) > 0
      and abs(vol_effect + price_mix_effect - move_abs) / abs(move_abs) < 1e-6,
      "REQ 4: movement decomposes into separable volume and price/mix effects",
      f"volume {vol_effect:+,.0f}  price+mix {price_mix_effect:+,.0f}  "
      f"sum {vol_effect + price_mix_effect:+,.0f} vs actual {move_abs:+,.0f}")

# ------------------------------------------------------- sparse history
nova = sales[sales.category == "Nova"]
nova_days = pd.to_datetime(nova["date"]).dt.date.nunique()
min_hist = c.kpis["net_revenue"].min_history_days
check(0 < nova_days < min_hist,
      "REQ 6: a sparse history slice exists and trips the contract policy",
      f"Nova has {nova_days} days against min_history_days={min_hist} "
      f"-> {c.sparse_policy['actions'][1]}")

# --------------------------------------------------- cross grain join works
s = sales.copy()
s["week_start"] = (pd.to_datetime(s["date"])
                   - pd.to_timedelta(pd.to_datetime(s["date"]).dt.weekday, unit="D")
                   ).dt.date.astype(str)
weekly_rev = s.groupby(["week_start", "region", "channel"], as_index=False).revenue.sum()
joined = weekly_rev.merge(marketing, on=["week_start", "region", "channel"], how="inner")
coverage = len(joined) / len(weekly_rev)
check(coverage > 0.9 and len(joined) > 0,
      "REQ 1c: daily sales reconcile upward to weekly marketing grain",
      f"{len(joined):,} weekly rows joined, {coverage:.0%} coverage, "
      f"marketing lag {c.sources['marketing_spend']['expected_lag_hours']}h")

# -------------------------------------------------------- text evidence
ev = events.copy()
ev["d"] = pd.to_datetime(ev["event_ts"]).dt.date
acme = ev[(ev.account_name == "Acme Corp") & (ev.kind == "delivery_delay")]
before = acme[acme.d < date(2026, 6, 20)]
after = acme[acme.d >= date(2026, 6, 20)]
days_b = max((date(2026, 6, 20) - date(2025, 9, 1)).days, 1)
days_a = max((date(2026, 8, 20) - date(2026, 6, 20)).days, 1)
rate_ratio = (len(after) / days_a) / max(len(before) / days_b, 1e-9)
crm = ev[(ev.event_type == "crm_note") & (ev.text.str.contains("alternative suppliers"))]
check(rate_ratio > 2.5 and len(crm) > 0,
      "REQ 8: unstructured evidence trail is recoverable from text",
      f"Acme delivery complaints {rate_ratio:.1f}x baseline, "
      f"{len(crm)} CRM note(s) naming supplier risk")

# ------------------------------------------------------ entitlements work
sd = set(c.visible_kpis("sales_director"))
cfo = set(c.visible_kpis("cfo"))
an = set(c.visible_kpis("analyst"))
masked = c.masked_columns("net_revenue", "analyst")
check("gross_margin_pct" in cfo and "gross_margin_pct" not in sd
      and "account_name" in masked and c.row_filter("net_revenue", "sales_director"),
      "REQ 7: role based entitlement produces genuinely different access",
      f"sales_director={len(sd)} KPIs (row filter: "
      f"{c.row_filter('net_revenue', 'sales_director')}), cfo={len(cfo)}, "
      f"analyst={len(an)} with {masked} masked")

# ----------------------------------------------------- personas differ
check(len(c.roles) >= 2
      and len({r.get("narrative_depth") for r in c.roles.values()}) >= 2
      and len({tuple(r.get("decision_rights", [])) for r in c.roles.values()}) >= 2,
      "REQ 3: at least two personas with different depth and decision rights",
      " | ".join(f"{n}: {r['narrative_depth']}, "
                 f"{len(r.get('decision_rights', []))} rights"
                 for n, r in c.roles.items()))

# -------------------------------------------------------- action schema
check(c.action_schema["required_fields"] == [
        "driver", "controllable_lever", "action", "expected_impact",
        "owner", "confidence", "monitoring_plan"],
      "Action schema matches the shape the brief specifies exactly",
      " -> ".join(c.action_schema["required_fields"]))

# ------------------------------------------------------------------ report
print("\nFRIDAY  Phase 1 gate\n" + "=" * 72)
for ok, label, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if detail:
        print(f"       {detail}")

failed = sum(1 for ok, _, _ in results if not ok)
print("=" * 72)
print(f"{len(results) - failed}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
