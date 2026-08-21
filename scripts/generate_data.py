#!/usr/bin/env python3
"""Generate the three simulated FRIDAY source systems.

Reproducible from SEED. Plants a known, recoverable scenario in the West
region so the prototype's output can be checked against a ground truth the
engine itself is never shown. See ASSUMPTIONS.md section 5 for the narrative
and scripts/verify_phase1.py for the automated checks against this data.

Usage:
    python scripts/generate_data.py [--seed 42] [--out-dir data/raw]
"""
from __future__ import annotations

import argparse
import json
import pathlib
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration — every planted event lives here, nowhere else.
# ---------------------------------------------------------------------------

HISTORY_START = pd.Timestamp("2025-09-01")
HISTORY_END = pd.Timestamp("2026-08-20")
COMPARISON_START = pd.Timestamp("2026-06-26")
COMPARISON_END = pd.Timestamp("2026-07-23")
CURRENT_START = pd.Timestamp("2026-07-24")
CURRENT_END = pd.Timestamp("2026-08-20")

REGIONS = ["North", "South", "East", "West"]
CHANNELS = ["Direct", "Distributor", "Online"]
PRODUCT_LINES = ["Aurora", "Vertex", "Nova", "Orion"]

BASE_PRICE = {"Aurora": 1200.0, "Vertex": 800.0, "Nova": 950.0, "Orion": 650.0}
BASE_COST_RATIO = {"Aurora": 0.68, "Vertex": 0.70, "Nova": 0.72, "Orion": 0.66}
NOVA_LAUNCH = pd.Timestamp("2026-07-31")
ORDER_PROB_SCALE = 6.0  # scales all order frequencies uniformly to reduce Poisson noise around the planted effect

# Planted events (all dates fixed, all magnitudes stated here and only here)
WEST_LOGISTICS_CHANGE = pd.Timestamp("2026-06-14")
ACME_COMPLAINT_SURGE_START = pd.Timestamp("2026-06-20")
ACME_CRM_NOTE_DATE = pd.Timestamp("2026-07-22")
ACME_STOPS_ORDERING = pd.Timestamp("2026-07-28")
AURORA_WEST_DISCOUNT_START = pd.Timestamp("2026-08-01")
AURORA_WEST_DISCOUNT_PCT = 0.08
MIX_SHIFT_REDIRECT_PROB = 0.35  # share of would-be West Aurora orders that go to Vertex instead, from discount date

NAMED_ACCOUNTS = {
    "West": ["Acme Corp", "Meridian Foods", "Silverline Retail"],
    "North": ["Highland Traders", "Zenith Textiles", "Northgate Supplies"],
    "South": ["Coastal Distributors", "Deccan Mercantile", "Palmgrove Retail"],
    "East": ["Ganges Traders", "Emberton Wholesale", "Riverside Mercantile"],
}
LONG_TAIL_PER_REGION = 14


@dataclass
class Account:
    account_id: str
    account_name: str
    region: str
    tier: str  # "named" or "long_tail"
    order_prob_per_day: float
    units_mean: float
    channel_weights: dict = field(default_factory=dict)
    product_weights: dict = field(default_factory=dict)


def build_accounts(rng: np.random.Generator) -> list[Account]:
    accounts: list[Account] = []
    for region in REGIONS:
        for i, name in enumerate(NAMED_ACCOUNTS[region]):
            acct_id = f"{region[:1]}N{i+1:02d}"
            # Acme gets a deliberately larger, regular order pattern —
            # calibrated below in calibrate_acme() to land near 12% of
            # West regional revenue, consistent with the Round 1 pitch.
            is_acme = (region == "West" and name == "Acme Corp")
            accounts.append(Account(
                account_id=acct_id,
                account_name=name,
                region=region,
                tier="named",
                order_prob_per_day=(0.12 if is_acme else rng.uniform(0.18, 0.30)) * ORDER_PROB_SCALE,
                units_mean=12.0 if is_acme else rng.uniform(8, 16),
                channel_weights={"Direct": 0.55, "Distributor": 0.35, "Online": 0.10},
                product_weights=_product_weights(rng),
            ))
        for i in range(LONG_TAIL_PER_REGION):
            acct_id = f"{region[:1]}T{i+1:03d}"
            accounts.append(Account(
                account_id=acct_id,
                account_name=f"SMB-{region}-{i+1:03d}",
                region=region,
                tier="long_tail",
                order_prob_per_day=rng.uniform(0.03, 0.09) * ORDER_PROB_SCALE,
                units_mean=rng.uniform(2, 6),
                channel_weights={"Direct": 0.20, "Distributor": 0.30, "Online": 0.50},
                product_weights=_product_weights(rng),
            ))
    return accounts


def _product_weights(rng: np.random.Generator) -> dict:
    w = rng.dirichlet([3, 2, 0.5, 2])  # Nova starts underweighted, it launches late
    return dict(zip(PRODUCT_LINES, w))


def _available_products(as_of: pd.Timestamp) -> list[str]:
    return PRODUCT_LINES if as_of >= NOVA_LAUNCH else [p for p in PRODUCT_LINES if p != "Nova"]


def generate_sales_transactions(accounts: list[Account], rng: np.random.Generator) -> pd.DataFrame:
    dates = pd.date_range(HISTORY_START, HISTORY_END, freq="D")
    rows = []
    order_seq = 0
    for acct in accounts:
        for d in dates:
            if acct.account_name == "Acme Corp" and d >= ACME_STOPS_ORDERING:
                continue  # planted: Acme stops ordering entirely
            if rng.random() > acct.order_prob_per_day:
                continue

            avail = _available_products(d)
            weights = np.array([acct.product_weights[p] for p in avail])
            weights = weights / weights.sum()
            product = rng.choice(avail, p=weights)

            # Planted mix shift: some West Aurora demand redirects to Vertex
            # once the discount starts.
            if (acct.region == "West" and product == "Aurora"
                    and d >= AURORA_WEST_DISCOUNT_START
                    and rng.random() < MIX_SHIFT_REDIRECT_PROB):
                product = "Vertex"

            channel = rng.choice(list(acct.channel_weights.keys()),
                                  p=list(acct.channel_weights.values()))
            units = max(1, int(round(rng.normal(acct.units_mean, acct.units_mean * 0.25))))

            price = BASE_PRICE[product] * rng.uniform(0.985, 1.015)
            if acct.region == "West" and product == "Aurora" and d >= AURORA_WEST_DISCOUNT_START:
                price *= (1 - AURORA_WEST_DISCOUNT_PCT)  # planted: 8% West Aurora discount
            cost = price * BASE_COST_RATIO[product] * rng.uniform(0.98, 1.02)

            order_seq += 1
            rows.append({
                "order_id": f"ORD{order_seq:07d}",
                "date": d.date().isoformat(),
                "region": acct.region,
                "product_line": product,
                "channel": channel,
                "account_id": acct.account_id,
                "account_name": acct.account_name,
                "account_tier": acct.tier,
                "units": units,
                "unit_price": round(float(price), 2),
                "unit_cost": round(float(cost), 2),
            })
    return pd.DataFrame(rows)


def generate_marketing_spend(rng: np.random.Generator) -> pd.DataFrame:
    weeks = pd.date_range(HISTORY_START, HISTORY_END, freq="W-MON")
    rows = []
    base_weekly = {"Aurora": 42000, "Vertex": 30000, "Nova": 15000, "Orion": 24000}
    for wk in weeks:
        for region in REGIONS:
            for product in PRODUCT_LINES:
                if product == "Nova" and wk < (NOVA_LAUNCH - pd.Timedelta(days=7)):
                    continue
                for channel in CHANNELS:
                    spend = base_weekly[product] / len(REGIONS) / len(CHANNELS)
                    spend *= rng.uniform(0.7, 1.3)
                    rows.append({
                        "week_start": wk.date().isoformat(),
                        "region": region,
                        "product_line": product,
                        "channel": channel,
                        "campaign_id": f"CMP-{region[:1]}{product[:2].upper()}-{wk.strftime('%y%W')}",
                        "spend_inr": round(float(spend), 2),
                    })
    return pd.DataFrame(rows)


def generate_service_events(accounts: list[Account], rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    seq = 0
    complaint_texts = [
        "Delivery arrived {n} days late, second time this month.",
        "Shipment damaged on arrival, requesting replacement.",
        "Delivery window missed again, please advise.",
        "Order delayed at the West warehouse, no update given.",
        "Consistently late deliveries since the logistics change.",
    ]
    inquiry_texts = [
        "Requesting updated pricing for next quarter.",
        "Asking about bulk discount thresholds.",
        "Wants to know Nova availability timeline.",
    ]

    for acct in accounts:
        base_rate_per_week = 0.3
        acme = (acct.account_name == "Acme Corp")
        for wk_start in pd.date_range(HISTORY_START, HISTORY_END, freq="W-MON"):
            rate = base_rate_per_week
            if acme and wk_start >= ACME_COMPLAINT_SURGE_START:
                rate = base_rate_per_week * 11.4  # planted: 11.4x baseline
            n_complaints = rng.poisson(rate)
            for _ in range(n_complaints):
                seq += 1
                day_offset = int(rng.integers(0, 7))
                ts = wk_start + pd.Timedelta(days=day_offset, hours=int(rng.integers(8, 18)))
                if ts < HISTORY_START or ts > HISTORY_END:
                    continue
                rows.append({
                    "event_id": f"EVT{seq:07d}",
                    "timestamp": ts.isoformat(),
                    "region": acct.region,
                    "account_id": acct.account_id,
                    "account_name": acct.account_name,
                    "channel": None,
                    "event_type": "complaint",
                    "text": rng.choice(complaint_texts).format(n=int(rng.integers(2, 6))),
                })
            if rng.random() < 0.05:
                seq += 1
                ts = wk_start + pd.Timedelta(days=int(rng.integers(0, 7)), hours=10)
                rows.append({
                    "event_id": f"EVT{seq:07d}",
                    "timestamp": ts.isoformat(),
                    "region": acct.region,
                    "account_id": acct.account_id,
                    "account_name": acct.account_name,
                    "channel": None,
                    "event_type": "inquiry",
                    "text": rng.choice(inquiry_texts),
                })

    # Planted: single CRM note, the leading indicator
    seq += 1
    rows.append({
        "event_id": f"EVT{seq:07d}",
        "timestamp": ACME_CRM_NOTE_DATE.isoformat(),
        "region": "West",
        "account_id": "WN01",
        "account_name": "Acme Corp",
        "channel": None,
        "event_type": "crm_note",
        "text": "Account team notes: client is evaluating alternative suppliers "
                "following repeated delivery issues.",
    })

    # Planted: single ops note, the upstream root cause
    seq += 1
    rows.append({
        "event_id": f"EVT{seq:07d}",
        "timestamp": WEST_LOGISTICS_CHANGE.isoformat(),
        "region": "West",
        "account_id": None,
        "account_name": None,
        "channel": None,
        "event_type": "ops_note",
        "text": "West warehouse switched third-party logistics provider "
                "effective today, from RegionalFreight Co. to QuickHaul Logistics.",
    })

    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    return df


def _period_agg(df: pd.DataFrame, start, end) -> pd.DataFrame:
    p = df[(df["date"] >= start) & (df["date"] <= end)]
    g = p.groupby("product_line").agg(units=("units", "sum"), revenue=("revenue", "sum"))
    g["price"] = g["revenue"] / g["units"]
    return g


def _pvm_by_product(df: pd.DataFrame) -> dict:
    """Price/volume/mix decomposition by product_line for a given slice of
    sales, comparison period vs current period. Reconciles exactly."""
    g0 = _period_agg(df, COMPARISON_START, COMPARISON_END)
    g1 = _period_agg(df, CURRENT_START, CURRENT_END)
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

    return {
        "revenue_comparison": round(float(rev0), 2),
        "revenue_current": round(float(rev1), 2),
        "total_change_inr": round(float(rev1 - rev0), 2),
        "volume_effect_inr": round(float(volume_effect), 2),
        "mix_effect_inr": round(float(mix_effect), 2),
        "price_effect_inr": round(float(price_effect), 2),
    }


def west_movement_decomposition(sales: pd.DataFrame, focus_account: str = "Acme Corp") -> dict:
    """Two-level decomposition of West net_revenue movement, matching the
    planted causal structure exactly:

      total_change = account_effect(focus_account) + product_pvm(everyone_else)

    This isolates the account-level volume loss (Acme stopping) from the
    product-level price/mix effects (Aurora discount, mix shift to Vertex)
    that ride on top of it — a single product-line-only PVM split blends
    the two and hides the account-specific cause. FRIDAY's own
    friday/attribute.py must reach this same structure independently from
    raw data; this function exists only to state what the generator planted.
    """
    df = sales[sales["region"] == "West"].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["revenue"] = df["units"] * df["unit_price"]

    focus = df[df["account_name"] == focus_account]
    rest = df[df["account_name"] != focus_account]

    def rev_in(d, start, end):
        return float(d[(d["date"] >= start) & (d["date"] <= end)]["revenue"].sum())

    focus_rev0 = rev_in(focus, COMPARISON_START, COMPARISON_END)
    focus_rev1 = rev_in(focus, CURRENT_START, CURRENT_END)
    focus_effect = focus_rev1 - focus_rev0

    rest_pvm = _pvm_by_product(rest)

    total_rev0 = rev_in(df, COMPARISON_START, COMPARISON_END)
    total_rev1 = rev_in(df, CURRENT_START, CURRENT_END)
    total_change = total_rev1 - total_rev0

    reconciled = focus_effect + rest_pvm["total_change_inr"]

    return {
        "region": "West",
        "comparison_period": [COMPARISON_START.date().isoformat(), COMPARISON_END.date().isoformat()],
        "current_period": [CURRENT_START.date().isoformat(), CURRENT_END.date().isoformat()],
        "revenue_comparison": round(total_rev0, 2),
        "revenue_current": round(total_rev1, 2),
        "total_change_inr": round(total_change, 2),
        "total_change_pct": round(total_change / total_rev0 * 100, 2) if total_rev0 else None,
        f"{focus_account.lower().replace(' ', '_')}_account_effect_inr": round(focus_effect, 2),
        "remaining_accounts_volume_effect_inr": rest_pvm["volume_effect_inr"],
        "remaining_accounts_mix_effect_inr": rest_pvm["mix_effect_inr"],
        "remaining_accounts_price_effect_inr": rest_pvm["price_effect_inr"],
        "reconciled_sum_inr": round(reconciled, 2),
        "reconciles_exactly": bool(abs(reconciled - total_change) < 1.0),
    }

def calibrate_acme_share(sales: pd.DataFrame) -> float:
    df = sales[sales["region"] == "West"].copy()
    df["date"] = pd.to_datetime(df["date"])
    df["revenue"] = df["units"] * df["unit_price"]
    window = df[(df["date"] >= COMPARISON_START) & (df["date"] <= COMPARISON_END)]
    total = window["revenue"].sum()
    acme = window[window["account_name"] == "Acme Corp"]["revenue"].sum()
    return float(acme / total) if total else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", type=str, default="data/raw")
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    accounts = build_accounts(rng)
    sales = generate_sales_transactions(accounts, rng)
    marketing = generate_marketing_spend(rng)
    events = generate_service_events(accounts, rng)

    sales.to_csv(out_dir / "sales_transactions.csv", index=False)
    marketing.to_csv(out_dir / "marketing_spend.csv", index=False)
    events.to_csv(out_dir / "service_events.csv", index=False)

    acme_share = calibrate_acme_share(sales)
    west_pvm = west_movement_decomposition(sales, focus_account="Acme Corp")

    nova_orders = int((sales["product_line"] == "Nova").sum())
    nova_history_days = int((HISTORY_END - NOVA_LAUNCH).days) + 1  # fixed by launch date, not by when orders happened to land

    ground_truth = {
        "seed": args.seed,
        "note": "For offline validation only. FRIDAY's engine must never read this file.",
        "acme_share_of_west_revenue_comparison_period": round(acme_share, 4),
        "west_net_revenue_decomposition": west_pvm,
        "nova_history_days_as_of_2026_08_20": nova_history_days,
        "nova_order_count": nova_orders,
        "planted_events": {
            "west_logistics_provider_change": WEST_LOGISTICS_CHANGE.date().isoformat(),
            "acme_complaint_surge_start": ACME_COMPLAINT_SURGE_START.date().isoformat(),
            "acme_crm_note_date": ACME_CRM_NOTE_DATE.date().isoformat(),
            "acme_stops_ordering": ACME_STOPS_ORDERING.date().isoformat(),
            "aurora_west_discount_start": AURORA_WEST_DISCOUNT_START.date().isoformat(),
            "aurora_west_discount_pct": AURORA_WEST_DISCOUNT_PCT,
            "nova_launch_date": NOVA_LAUNCH.date().isoformat(),
        },
        "row_counts": {
            "sales_transactions": len(sales),
            "marketing_spend": len(marketing),
            "service_events": len(events),
        },
    }
    with open(out_dir / "ground_truth.json", "w") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"Wrote {len(sales)} sales rows, {len(marketing)} marketing rows, "
          f"{len(events)} service event rows to {out_dir}/")
    print(f"Acme share of West revenue (comparison period): {acme_share:.1%}")
    print(f"West net_revenue movement: {west_pvm['total_change_pct']}% "
          f"({west_pvm['total_change_inr']:,.0f} INR)")
    print(f"  Acme Corp account effect:        {west_pvm['acme_corp_account_effect_inr']:,.0f} INR")
    print(f"  remaining accounts, volume:      {west_pvm['remaining_accounts_volume_effect_inr']:,.0f} INR")
    print(f"  remaining accounts, mix:         {west_pvm['remaining_accounts_mix_effect_inr']:,.0f} INR")
    print(f"  remaining accounts, price:       {west_pvm['remaining_accounts_price_effect_inr']:,.0f} INR")
    print(f"  reconciles exactly: {west_pvm['reconciles_exactly']}")
    print(f"Nova history as of 2026-08-20: {nova_history_days} days ({nova_orders} orders)")


if __name__ == "__main__":
    main()
