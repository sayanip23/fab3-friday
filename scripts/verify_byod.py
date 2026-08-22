"""
Bring-your-own-data gate.

Proves the engine works on files it has never seen, with a schema it was not
built for. Three fixtures, each generated here so nothing is tuned to them:

  1. a planted movement in an unfamiliar schema  -> must be found and attributed
  2. pure noise                                  -> must raise nothing
  3. a broken file                               -> must refuse, not crash

Run:  python scripts/verify_byod.py
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from friday import byod, profile as prof                       # noqa: E402

RNG = np.random.default_rng(7)
results: list[tuple[bool, str, str]] = []


def check(ok, label, detail=""):
    results.append((bool(ok), label, detail))


# ── fixture 1: deliberately alien schema ────────────────────────────────────
# Different column names, different domain, different scale to the demo data.
def clinic_bookings(days=180):
    start = date(2026, 1, 1)
    rows = []
    for i in range(days):
        d = start + timedelta(days=i)
        for site in ["Andheri", "Bandra", "Colaba", "Dadar"]:
            for svc in ["Dental", "Physio", "Optical"]:
                base = {"Andheri": 34, "Bandra": 28, "Colaba": 19, "Dadar": 25}[site]
                base *= {"Dental": 1.0, "Physio": 0.7, "Optical": 0.45}[svc]
                # planted: Bandra Physio collapses in the final 28 days
                if site == "Bandra" and svc == "Physio" and i >= days - 28:
                    base *= 0.18
                rows.append({
                    "booking_date": d.isoformat(),
                    "clinic_site": site,
                    "service_line": svc,
                    "appointments": int(RNG.poisson(max(base, 0.1))),
                    "revenue_inr": 0.0,
                    "booking_ref": f"BK{i:04d}{site[:2]}{svc[:2]}",
                })
    df = pd.DataFrame(rows)
    df["revenue_inr"] = (df.appointments * RNG.normal(820, 40, len(df))).round(2)
    return df


def flat_noise(days=180):
    start = date(2026, 1, 1)
    rows = []
    for i in range(days):
        d = start + timedelta(days=i)
        for region in ["North", "South"]:
            rows.append({
                "day": d.isoformat(),
                "region": region,
                "widgets_shipped": int(RNG.normal(500, 22)),
            })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════ 1. profiling
book = clinic_bookings()
p = prof.profile_frame(book)

check(p.date_column == "booking_date",
      "Finds the date column in an unfamiliar schema",
      f"chose '{p.date_column}' from {list(book.columns)}")

check("appointments" in p.measures and "revenue_inr" in p.measures,
      "Identifies numeric measures",
      f"measures: {p.measures}")

check("booking_ref" not in p.measures and "booking_ref" not in p.dimensions,
      "Rejects the identifier column instead of treating it as a dimension",
      "'booking_ref' is near-unique, so grouping by it would explain nothing")

check(set(p.dimensions) == {"clinic_site", "service_line"},
      "Identifies the categorical dimensions",
      f"dimensions: {p.dimensions}")

check(not p.supports_pvm,
      "Correctly reports that price/volume/mix is unavailable here",
      "no unit-price column, so the engine must not claim a price effect")

# ═══════════════════════════════════════════════════ 2. the planted movement
a = byod.analyse(book)
check(not a.errors, "Analysis runs end to end on the uploaded frame",
      f"{len(a.findings)} KPI(s) analysed; errors: {a.errors or 'none'}")

appt = next((f for f in a.findings if f.kpi == "appointments"), None)
check(appt is not None and appt.movement.material and appt.movement.delta < 0,
      "Detects the planted decline in a file it has never seen",
      f"{appt.movement.summary()}  z={appt.movement.z_score:.2f}" if appt else "not found")

check(appt and appt.contribution and appt.contribution.reconciled,
      "Contribution reconciles exactly on uploaded data",
      f"residual {appt.contribution.residual:+.6f}, dimension "
      f"'{appt.dimension}'" if appt and appt.contribution else "no contribution")

top = appt.contribution.top(1)[0] if appt and appt.contribution else None
check(top and top.name in ("Bandra", "Physio"),
      "Attributes the movement to the correct segment",
      f"top contributor '{top.name}' at {top.share:+.1%} "
      f"(planted: Bandra Physio)" if top else "none")

check(appt and appt.notes and any("unit-price" in n for n in appt.notes),
      "States plainly that price/volume/mix could not be run",
      appt.notes[0][:96] + "..." if appt and appt.notes else "no note")

# ═══════════════════════════════════════════════════ 3. negative control
noise = byod.analyse(flat_noise())
noisy = next((f for f in noise.findings if f.kpi == "widgets_shipped"), None)
check(noisy is not None and not noisy.movement.material,
      "Raises nothing on a file with no real signal",
      f"widgets_shipped {noisy.movement.pct:+.1f}% -> material="
      f"{noisy.movement.material}" if noisy else "not analysed")

# ═══════════════════════════════════════════════════ 4. refuses bad input
bad = byod.analyse(pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]}))
check(bad.errors and not bad.findings,
      "Refuses a file with no date column instead of crashing",
      bad.errors[0] if bad.errors else "no error raised")

short = pd.DataFrame({
    "when": [(date(2026, 8, 1) + timedelta(days=i)).isoformat() for i in range(40)],
    "sales": RNG.normal(100, 5, 40).round(2),
    "team": ["A", "B"] * 20,
})
short_a = byod.analyse(short)
check(any("history" in w.lower() or "days" in w.lower() for w in short_a.profile.warnings),
      "Warns when there is too little history to be confident",
      short_a.profile.warnings[0][:96] if short_a.profile.warnings else "no warning")

# ═══════════════════════════════════════════════════ 5. same pipeline, honestly
check(appt and appt.run.total_ms > 0 and not appt.run.verify(),
      "Uploaded data runs through the identical instrumented pipeline",
      appt.run.footer() if appt else "no telemetry")

check(appt and appt.assessment.abstain,
      "Abstains without a text corpus, rather than inventing a cause",
      f"confidence={appt.assessment.confidence}; "
      f"{appt.assessment.abstain_reasons[0][:70]}" if appt else "n/a")

# ───────────────────────────────────────────────────────────── report
print("\nFRIDAY  Bring-your-own-data gate\n" + "=" * 78)
for ok, label, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if detail:
        print(f"       {detail}")
failed = sum(1 for ok, _, _ in results if not ok)
print("=" * 78)
print(f"{len(results) - failed}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
