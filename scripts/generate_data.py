"""
Generate the three simulated source systems for FRIDAY.

Deliberately mismatched grains and refresh cadences, per the Round 2 brief:
  sales_transactions  order line, daily
  marketing_spend     campaign,   weekly
  service_events      event,      continuous, free text

Ground truth planted here is documented in ASSUMPTIONS.md section 5. The engine is
never told any of it and must recover it from the data.

Run:  python scripts/generate_data.py
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

SEED = 20260821
RNG = np.random.default_rng(SEED)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "raw")

HISTORY_START = date(2025, 9, 1)
HISTORY_END = date(2026, 8, 20)

CURRENT_START, CURRENT_END = date(2026, 7, 24), date(2026, 8, 20)
PRIOR_START, PRIOR_END = date(2026, 6, 26), date(2026, 7, 23)

# planted events
LOGISTICS_CHANGE = date(2026, 6, 14)
COMPLAINTS_RISE = date(2026, 6, 20)
CRM_WARNING = date(2026, 7, 22)
ACME_STOPS = date(2026, 7, 28)
AURORA_DISCOUNT = date(2026, 8, 1)
NOVA_LAUNCH = date(2026, 7, 31)

REGIONS = ["North", "South", "East", "West"]
CHANNELS = ["Direct", "Partner", "Online"]

# category -> (list price, unit cost, base daily units per region)
CATEGORIES = {
    "Aurora":  (2400.0, 1500.0, 46),
    "Vertex":  (1150.0,  790.0, 62),
    "Halcyon": (3900.0, 2600.0, 18),
    "Nova":    (1750.0, 1180.0, 10),   # launches 2026-07-31, sparse history
}

REGION_SCALE = {"North": 1.00, "South": 0.86, "East": 0.72, "West": 1.18}
CHANNEL_SHARE = {"Direct": 0.46, "Partner": 0.34, "Online": 0.20}

ACCOUNTS = {
    "West":  ["Acme Corp", "Sterling Industries", "Vayu Logistics", "Orbit Retail"],
    "North": ["Meridian Group", "Kalpana Traders"],
    "South": ["Deccan Supply", "Bluewater Co"],
    "East":  ["Ganges Distributors", "Ironwood Ltd"],
}
# Acme is deliberately large: it must be able to move the West number on its own.
ACCOUNT_SHARE = {
    "Acme Corp": 0.18, "Sterling Industries": 0.29, "Vayu Logistics": 0.28, "Orbit Retail": 0.25,
    "Meridian Group": 0.58, "Kalpana Traders": 0.42,
    "Deccan Supply": 0.55, "Bluewater Co": 0.45,
    "Ganges Distributors": 0.61, "Ironwood Ltd": 0.39,
}


def daterange(a: date, b: date):
    for i in range((b - a).days + 1):
        yield a + timedelta(days=i)


def seasonal(d: date) -> float:
    """Mild annual seasonality plus a weekday effect."""
    doy = d.timetuple().tm_yday
    annual = 1.0 + 0.07 * np.sin(2 * np.pi * (doy - 60) / 365.0)
    weekday = {0: 1.06, 1: 1.08, 2: 1.05, 3: 1.03, 4: 0.98, 5: 0.72, 6: 0.55}[d.weekday()]
    return annual * weekday


def mix_pull(d: date) -> float:
    """Demand drifts toward the cheaper Vertex line through August (mix effect)."""
    if d < CURRENT_START:
        return 0.0
    progress = (d - CURRENT_START).days / max((CURRENT_END - CURRENT_START).days, 1)
    return 0.05 * progress


# ---------------------------------------------------------------- sales
def build_sales() -> pd.DataFrame:
    rows = []
    order_seq = 100000

    for d in daterange(HISTORY_START, HISTORY_END):
        s = seasonal(d)
        pull = mix_pull(d)

        for region in REGIONS:
            for category, (list_price, unit_cost, base_units) in CATEGORIES.items():
                if category == "Nova" and d < NOVA_LAUNCH:
                    continue

                shift = 1.0
                if category == "Vertex":
                    shift += pull
                elif category in ("Aurora", "Halcyon"):
                    shift -= pull * 0.6

                price = list_price
                if category == "Aurora" and region == "West" and d >= AURORA_DISCOUNT:
                    price = list_price * 0.86          # planted price effect, 14% cut

                if category == "Nova":
                    ramp = min(1.0, 0.35 + 0.05 * (d - NOVA_LAUNCH).days)
                    shift *= ramp

                for channel in CHANNELS:
                    expected = (base_units * REGION_SCALE[region] * CHANNEL_SHARE[channel]
                                * s * shift)
                    if expected <= 0:
                        continue

                    for account in ACCOUNTS[region]:
                        share = ACCOUNT_SHARE[account]

                        # planted volume effect: Acme stops ordering entirely
                        if account == "Acme Corp" and d >= ACME_STOPS:
                            continue

                        # mild pre-churn softening once complaints begin
                        soften = 1.0
                        if account == "Acme Corp" and d >= COMPLAINTS_RISE:
                            soften = 0.90

                        units = RNG.poisson(max(expected * share * soften, 0.01))
                        if units == 0:
                            continue

                        realised = price * RNG.normal(1.0, 0.012)
                        order_seq += 1
                        rows.append((
                            d.isoformat(), f"SO{order_seq}", account, region, channel,
                            category, f"{category[:3].upper()}-{RNG.integers(100, 999)}",
                            int(units), round(realised, 2), round(unit_cost, 2),
                        ))

    df = pd.DataFrame(rows, columns=[
        "date", "order_id", "account_name", "region", "channel",
        "category", "product_id", "units", "unit_price", "unit_cost",
    ])
    df["revenue"] = (df["units"] * df["unit_price"]).round(2)
    df["cost"] = (df["units"] * df["unit_cost"]).round(2)
    return df


# ------------------------------------------------------------ marketing
def build_marketing() -> pd.DataFrame:
    rows = []
    week = HISTORY_START - timedelta(days=HISTORY_START.weekday())
    while week <= HISTORY_END:
        for region in REGIONS:
            for channel in CHANNELS:
                base = 420000 * REGION_SCALE[region] * CHANNEL_SHARE[channel]
                campaign = "AlwaysOn"
                spend = base * RNG.normal(1.0, 0.09)

                # discount push behind the Aurora price cut
                if region == "West" and week >= AURORA_DISCOUNT - timedelta(days=7):
                    spend *= 1.35
                    campaign = "AuroraValue"

                rows.append((
                    week.isoformat(), region, channel, campaign,
                    round(max(spend, 0), 2), int(max(spend, 0) / RNG.uniform(1.6, 2.4)),
                ))
        week += timedelta(days=7)

    return pd.DataFrame(rows, columns=[
        "week_start", "region", "channel", "campaign", "spend", "impressions",
    ])


# --------------------------------------------------------- service events
TICKET_TEXT = {
    "delivery_delay": [
        "Consignment {ref} was promised on {d} and has still not arrived at our depot.",
        "Third late delivery this month against order {ref}. This is becoming a problem.",
        "Delivery for {ref} slipped again. Our production line was held up waiting for it.",
        "We were not notified that {ref} would be late. Please escalate.",
    ],
    "quality": [
        "Two cartons in {ref} arrived damaged. Requesting replacement.",
        "Packaging on {ref} was torn on arrival.",
    ],
    "billing": [
        "Invoice against {ref} shows the old rate. Please issue a correction.",
        "Purchase order number missing from the invoice for {ref}.",
    ],
}

CRM_TEXT = {
    "risk": [
        "Spoke with procurement. They are evaluating alternative suppliers after the "
        "recent delivery problems. Renewal is at risk.",
        "Account is unhappy about reliability. Asked for a written service improvement plan.",
    ],
    "routine": [
        "Quarterly catch up. No issues raised.",
        "Discussed upcoming volumes. Outlook broadly stable.",
        "Reviewed the product roadmap with the account team.",
    ],
}


def build_service_events() -> pd.DataFrame:
    rows = []
    seq = 500000

    for d in daterange(HISTORY_START, HISTORY_END):
        for region in REGIONS:
            for account in ACCOUNTS[region]:

                rate = 0.16
                if (region == "West" and account == "Acme Corp"
                        and d >= COMPLAINTS_RISE):
                    rate = 0.85                       # ~4x baseline, planted
                elif region == "West" and d >= LOGISTICS_CHANGE:
                    rate = 0.30                       # provider change hits region wide

                n = RNG.poisson(rate)
                for _ in range(n):
                    if d >= LOGISTICS_CHANGE and region == "West":
                        kind = RNG.choice(["delivery_delay", "quality", "billing"],
                                          p=[0.74, 0.14, 0.12])
                    else:
                        kind = RNG.choice(["delivery_delay", "quality", "billing"],
                                          p=[0.34, 0.30, 0.36])
                    seq += 1
                    tmpl = RNG.choice(TICKET_TEXT[kind])
                    rows.append((
                        f"{d.isoformat()}T{RNG.integers(8, 19):02d}:{RNG.integers(0, 59):02d}:00",
                        f"EV{seq}", "support_ticket", account, region, kind,
                        int(RNG.integers(1, 4)),
                        tmpl.format(ref=f"SO{RNG.integers(100000, 199999)}",
                                    d=(d - timedelta(days=int(RNG.integers(2, 9)))).isoformat()),
                    ))

        # CRM notes, roughly weekly per account
        if d.weekday() == 2:
            for region in REGIONS:
                for account in ACCOUNTS[region]:
                    risky = (account == "Acme Corp" and d >= CRM_WARNING)
                    # a risk note is deterministic: an account review that raises
                    # supplier risk is always logged, routine ones are sampled
                    if not risky and RNG.random() > 0.55:
                        continue
                    text = RNG.choice(CRM_TEXT["risk" if risky else "routine"])
                    seq += 1
                    rows.append((
                        f"{d.isoformat()}T11:00:00", f"EV{seq}", "crm_note",
                        account, region, "account_review", 2, text,
                    ))

    return pd.DataFrame(rows, columns=[
        "event_ts", "event_id", "event_type", "account_name",
        "region", "kind", "severity", "text",
    ])


def main() -> None:
    os.makedirs(OUT, exist_ok=True)

    sales = build_sales()
    marketing = build_marketing()
    events = build_service_events()

    sales.to_csv(os.path.join(OUT, "sales_transactions.csv"), index=False)
    marketing.to_csv(os.path.join(OUT, "marketing_spend.csv"), index=False)
    events.to_csv(os.path.join(OUT, "service_events.csv"), index=False)

    print(f"sales_transactions  {len(sales):>7,} rows  "
          f"{sales.date.min()} to {sales.date.max()}")
    print(f"marketing_spend     {len(marketing):>7,} rows  weekly")
    print(f"service_events      {len(events):>7,} rows  event level")

    # quick read of the planted movement, for our own verification only
    s = sales.copy()
    s["date"] = pd.to_datetime(s["date"]).dt.date
    cur = s[(s.date >= CURRENT_START) & (s.date <= CURRENT_END) & (s.region == "West")]
    pri = s[(s.date >= PRIOR_START) & (s.date <= PRIOR_END) & (s.region == "West")]
    cr, pr = cur.revenue.sum(), pri.revenue.sum()
    print(f"\nWest net_revenue  prior {pr:,.0f}  current {cr:,.0f}  "
          f"movement {100 * (cr - pr) / pr:+.1f}%")
    print(f"West units        prior {pri.units.sum():,}  current {cur.units.sum():,}")
    print(f"West ASP          prior {pr / pri.units.sum():,.0f}  "
          f"current {cr / cur.units.sum():,.0f}")
    print(f"Nova history days {(HISTORY_END - NOVA_LAUNCH).days}")


if __name__ == "__main__":
    main()
