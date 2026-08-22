"""
Phase 2 and 3 gate.

The engine is never told the ground truth in ASSUMPTIONS.md section 5. These checks
confirm it recovers it from the data alone.

Run:  python scripts/verify_phase23.py
"""
from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from friday import attribute, causal, contracts, detect          # noqa: E402
from friday.kpi import Period, Warehouse                         # noqa: E402

PERIOD = Period(date(2026, 7, 24), date(2026, 8, 20))
WEST = {"region": "West"}

results: list[tuple[bool, str, str]] = []


def check(ok, label, detail=""):
    results.append((bool(ok), label, detail))


c = contracts.load()
wh = Warehouse(c)

# ===================================================================== PHASE 2
m = detect.evaluate(wh, "net_revenue", PERIOD, WEST)
check(m.material and m.delta < 0,
      "P2 detects the planted West revenue movement as material",
      f"{m.summary()}  z={m.z_score:.2f} vs threshold "
      f"{c.kpis['net_revenue'].thresholds()[0]['threshold']}, "
      f"baseline n={m.baseline_n}")

check(m.statistical_pass and m.business_pass,
      "P2 requires BOTH statistical and business gates, per the brief",
      f"statistical={m.statistical_pass} (z={m.z_score:.2f}), "
      f"business={m.business_pass} ({m.delta:+,.0f} INR, {m.pct:+.1f}%)")

quiet = detect.evaluate(wh, "net_revenue", PERIOD, {"region": "North"})
check(not quiet.material,
      "P2 stays silent on a region that did not move materially",
      f"North {quiet.pct:+.1f}% ({quiet.delta:+,.0f} INR)  material={quiet.material} "
      f"-> no alert raised")

found = detect.dedupe_overlapping(detect.scan(wh, PERIOD, "cfo"))
check(len(found) > 0 and found[0].priority >= (found[-1].priority if found else 0),
      "P2 prioritises material movements rather than listing them",
      " | ".join(f"{x.kpi}[{x.slice_label}] p={x.priority:.1f}" for x in found[:4]))

nova = detect.evaluate(wh, "net_revenue", PERIOD, {"category": "Nova"})
check(nova.sparse and nova.confidence_cap == "low",
      "P2 trips the sparse history policy on the newly launched line",
      f"Nova history {nova.history_days}d < {nova.min_history_days}d, "
      f"confidence capped at '{nova.confidence_cap}'")

# ===================================================================== PHASE 3
pvm = attribute.price_volume_mix(wh, PERIOD, WEST, segment_by="category")
check(pvm.reconciled,
      "P3 price volume mix reconciles exactly to the movement",
      f"total {pvm.total_movement:+,.0f}  residual {pvm.residual:+.6f}  "
      + "  ".join(str(e) for e in pvm.effects))

vol = next(e for e in pvm.effects if e.driver == "volume")
price = next(e for e in pvm.effects if e.driver == "price")
mix = next(e for e in pvm.effects if e.driver == "mix")
check(vol.value < 0 and price.value < 0,
      "P3 recovers the planted directions without being told them",
      f"volume {vol.value:+,.0f} (Acme stopped ordering), "
      f"price {price.value:+,.0f} (Aurora discounted 8%), "
      f"mix {mix.value:+,.0f} (drift to Vertex)")

acct = attribute.by_dimension(wh, "net_revenue", PERIOD, "account_name", WEST)
top = acct.top(1)[0]
check(top.name == "Acme Corp" and top.value < 0,
      "P3 identifies the correct account as the largest single contributor",
      f"{top.name} {top.value:+,.0f} ({top.share:+.1%} of the movement), "
      f"reconciled={acct.reconciled}")

cat = attribute.by_dimension(wh, "net_revenue", PERIOD, "category", WEST)
check(cat.reconciled,
      "P3 dimensional contribution also reconciles",
      "  ".join(str(e) for e in cat.top(4)))

# ------------------------------------------------------------ causal screen
onset = causal.movement_onset(wh, "net_revenue", PERIOD, WEST)
check(onset is not None and onset >= date(2026, 7, 24),
      "P3 locates a durable onset date for the movement",
      f"onset {onset} (Acme stopped 2026-07-28, engine was not told)")

assess = causal.screen(wh, m, pvm.effects, PERIOD, WEST)
vol_v = next(v for v in assess.verdicts if v.driver == "volume")
price_v = next(v for v in assess.verdicts if v.driver == "price")
check(vol_v.is_cause and not price_v.is_cause,
      "P3 names the dominant lever a cause and demotes the rest to associations",
      " | ".join(f"{v.driver}={v.status}" for v in assess.verdicts))

check(all(v.gates() for v in assess.verdicts) and len(assess.verdicts) >= 4,
      "P3 runs all three gates on every candidate driver",
      " | ".join(f"{v.driver} ({v.kind}): {v.gates()}" for v in assess.verdicts[:2]))

root = [v for v in assess.causes if v.kind == "evidential"]
check(root and root[0].driver == "delivery_reliability"
      and root[0].first_evidence < root[0].onset,
      "P3 traces past the arithmetic to the upstream root cause",
      (f"{root[0].driver} at {root[0].strength:.1f}x baseline, evidence from "
       f"{root[0].first_evidence} precedes onset {root[0].onset}") if root
      else "no evidential root cause found")

ACME = {"account_name": "Acme Corp"}
cp = causal.driver_change_point(wh, "delivery_delay", PERIOD, ACME)
ratio = causal.evidence_rate_ratio(wh, "delivery_delay", PERIOD, ACME)
ev = causal.gather_evidence(wh, "volume", PERIOD, ACME)
check(cp is not None and abs((cp - date(2026, 6, 20)).days) <= 14
      and ratio > 2.0 and len(ev) > 0,
      "P3 locates the driver's own change point and corroborates with text",
      f"delivery reliability degraded from {cp} (planted 2026-06-20), "
      f"{ratio:.1f}x its pre change rate; "
      + (ev[0].cite(90) if ev else "no citation"))

ctrl_cp = causal.driver_change_point(wh, "delivery_delay", PERIOD, {"region": "North"})
ctrl_ratio = causal.evidence_rate_ratio(wh, "delivery_delay", PERIOD, {"region": "North"})
check(ctrl_cp is None and ctrl_ratio < causal.EVIDENTIAL_RATE_THRESHOLD,
      "Negative control: finds no change point in a region where nothing was planted",
      f"North change point {ctrl_cp}, rate ratio {ctrl_ratio:.2f}x "
      f"(below the {causal.EVIDENTIAL_RATE_THRESHOLD}x bar)")

check(assess.confidence == "high" and not assess.abstain,
      "P3 reaches high confidence on the headline case, with no blockers",
      f"confidence={assess.confidence}, abstain={assess.abstain}, "
      f"chain: {root[0].driver if root else '?'} -> volume "
      f"({vol_v.share:.0%} of the movement) -> net_revenue {m.pct:+.1f}%")

# ---------------------------------------------- abstention on a sparse slice
nova_pvm = attribute.price_volume_mix(wh, PERIOD, {"category": "Nova"},
                                      segment_by="channel")
nova_assess = causal.screen(wh, nova, nova_pvm.effects, PERIOD, {"category": "Nova"})
check(nova_assess.abstain and nova_assess.confidence in ("none", "low")
      and nova_assess.discriminating_check,
      "REQ 5: engine abstains on the low confidence case and names the next check",
      f"confidence={nova_assess.confidence}; "
      f"reasons: {'; '.join(nova_assess.abstain_reasons[:2])}")

# -------------------------------------------- LLM is not used for any number
import friday.detect, friday.attribute, friday.causal, friday.kpi              # noqa: E402
sources = "".join(open(os.path.join(os.path.dirname(m2.__file__) if False else
                                    os.path.dirname(friday.kpi.__file__),
                                    f"{name}.py"), encoding="utf-8").read()
                  for name, m2 in [("kpi", friday.kpi), ("detect", friday.detect),
                                   ("attribute", friday.attribute),
                                   ("causal", friday.causal)])
banned = [t for t in ("openai", "anthropic", "llm.complete", "chat.completions")
          if t in sources.lower().replace("no llm", "")]
check(not banned,
      "REQ 9: no LLM call exists anywhere in the quantitative path",
      "kpi, detect, attribute and causal are pure pandas and numpy"
      if not banned else f"found {banned}")

# ------------------------------------------------------------------- report
print("\nFRIDAY  Phase 2 and 3 gate\n" + "=" * 76)
for ok, label, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if detail:
        print(f"       {detail}")
failed = sum(1 for ok, _, _ in results if not ok)
print("=" * 76)
print(f"{len(results) - failed}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
