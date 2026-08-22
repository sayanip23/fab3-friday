"""Lane A smoke test — runs detect -> attribute -> causal end to end
against the generated data and checks the engine recovers the planted
scenario without ever being told what it is.

Usage: python tests/test_lane_a.py
"""
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from friday.contracts import load_contract
from friday.detect import detect_all_regions, check_history_sufficiency
from friday.attribute import attribute_region_movement
from friday.causal import screen_account_effect

COMPARISON_PERIOD = (pd.Timestamp("2026-06-26"), pd.Timestamp("2026-07-23"))
CURRENT_PERIOD = (pd.Timestamp("2026-07-24"), pd.Timestamp("2026-08-20"))


def main():
    contract = load_contract("contracts/kpis.yaml")
    sales = pd.read_csv("data/raw/sales_transactions.csv")
    events = pd.read_csv("data/raw/service_events.csv")

    checks = []

    # 1. Detection: does the engine find West on its own, ranked first?
    movements = detect_all_regions(sales, contract, COMPARISON_PERIOD, CURRENT_PERIOD)
    top = movements[0]
    checks.append(("Top-ranked material movement is West",
                    top.grain_key["region"] == "West" and top.is_material,
                    f"top={top.grain_key}, is_material={top.is_material}, "
                    f"z={top.z_score:.2f}, pct={top.pct_change:.1f}%"))

    # 2. Attribution: does the engine independently find Acme Corp as the dominant driver?
    attribution = attribute_region_movement(sales, "West", COMPARISON_PERIOD, CURRENT_PERIOD)
    dom = attribution.dominant_segment
    checks.append(("Attribution finds a dominant account segment",
                    dom is not None and dom.segment == "Acme Corp",
                    f"dominant={dom.segment if dom else None}, "
                    f"share={dom.contribution_share if dom else None}"))
    checks.append(("PVM decomposition of the remainder reconciles exactly",
                    attribution.pvm.reconciles_exactly,
                    f"pvm={attribution.pvm}"))

    # 3. Causal screen: does evidence justify calling this a *cause*, not just a correlation?
    screen = screen_account_effect(events, "Acme Corp", CURRENT_PERIOD[0])
    checks.append(("Causal screen passes for Acme Corp with real evidence",
                    screen.passed and screen.confidence == "high",
                    screen.reason))

    # 4. Sparse history: does the engine flag Nova without being told it's new?
    hist = check_history_sufficiency(sales, contract, "Nova", pd.Timestamp("2026-08-20"))
    checks.append(("Nova correctly flagged as insufficient history",
                    not hist.is_sufficient,
                    hist.reason))

    # 5. Negative control: an account with no real evidence should NOT pass the causal screen.
    #    Pick a long-tail West account that still has orders (i.e. wasn't cut off) as a control.
    west_accounts = sales[sales["region"] == "West"]["account_name"].unique()
    control_account = next(a for a in west_accounts if a not in ("Acme Corp",) and not a.startswith("SMB-"))
    control_screen = screen_account_effect(events, control_account, CURRENT_PERIOD[0])
    checks.append((f"Negative control ({control_account}) does not falsely pass",
                    not control_screen.passed,
                    control_screen.reason))

    width = max(len(name) for name, _, _ in checks)
    passed = 0
    for i, (name, ok, detail) in enumerate(checks, 1):
        mark = "✓" if ok else "✗"
        print(f"{i}. [{mark}] {name.ljust(width)}  {detail}")
        passed += ok
    print(f"\n{passed}/{len(checks)} Lane A checks passed.")
    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
