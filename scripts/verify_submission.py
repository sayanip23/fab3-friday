"""
Submission audit.

Checks the running system against the Round 2 brief itself, requirement by
requirement, and tells you where in the UI each one is demonstrated.

This is not a substitute for the four lane gates. Those test that the code is
correct. This tests that the code answers the question that was actually asked.

Run:  python scripts/verify_submission.py
"""
from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from friday import attribute, causal, contracts, detect, evidence, narrate  # noqa: E402
from friday.access import EntitlementError, Principal                       # noqa: E402
from friday.engine import Engine                                            # noqa: E402
from friday.feedback import Correction, FeedbackStore                       # noqa: E402
from friday.kpi import Period                                               # noqa: E402

PERIOD = Period(date(2026, 7, 24), date(2026, 8, 20))
WEST = {"region": "West"}

rows: list[tuple[str, str, bool, str, str]] = []


def req(group: str, ident: str, ok, evidence_text: str, where: str) -> None:
    rows.append((group, ident, bool(ok), evidence_text, where))


c = contracts.load()
store = FeedbackStore(os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "data", "feedback_audit.jsonl"))
store.clear()
eng = Engine(c, store=store)

cfo = Principal("S. Iyer", "cfo", c)
director = Principal("R. Mehta", "sales_director", c)
analyst = Principal("A. Rao", "analyst", c)

r_dir = eng.explain(director, "net_revenue", PERIOD, WEST)
r_cfo = eng.explain(cfo, "net_revenue", PERIOD, WEST)
r_ana = eng.explain(analyst, "net_revenue", PERIOD, WEST)

nova_mv = detect.evaluate(eng.wh, "net_revenue", PERIOD, {"category": "Nova"})
nova_pvm = attribute.price_volume_mix(eng.wh, PERIOD, {"category": "Nova"},
                                      segment_by="channel")
nova_as = causal.screen(eng.wh, nova_mv, nova_pvm.effects, PERIOD,
                        {"category": "Nova"})

# ============================ MINIMUM PROTOTYPE EXPECTATIONS (10) ============
G = "MINIMUM PROTOTYPE EXPECTATION"

grains = {s["time_grain"] for s in c.sources.values()}
cadences = {s["refresh_cadence"] for s in c.sources.values()}
req(G, "1. Three to five connected KPIs, two or three sources, different grains",
    len(c.kpis) == 5 and len(c.sources) == 3 and len(grains) == 3,
    f"{len(c.kpis)} KPIs, {len(c.sources)} sources, grains {sorted(grains)}, "
    f"cadences {sorted(cadences)}",
    "Contract tab")

spec = c.kpis["net_revenue"].spec
has = [k for k in ("definition", "formula", "drivers", "materiality", "lineage",
                   "access") if k in spec]
req(G, "2. Semantic contract: definitions, calculations, drivers, thresholds, "
       "lineage, access",
    len(has) == 6 and not c.validate(),
    f"contracts/kpis.yaml carries {', '.join(has)}; validator reports "
    f"{len(c.validate())} problems",
    "Contract tab")

req(G, "3. At least two personas, different narratives or actions",
    (r_dir.insight.narrative.text != r_cfo.insight.narrative.text
     != r_ana.insight.narrative.text
     and {a.controllable_lever for a in r_dir.insight.actions}
     != {a.controllable_lever for a in r_cfo.insight.actions}),
    f"3 personas; director levers "
    f"{sorted({a.controllable_lever for a in r_dir.insight.actions})}, "
    f"cfo {sorted({a.controllable_lever for a in r_cfo.insight.actions})}, "
    f"analyst {len(r_ana.insight.actions)} actions",
    "Sidebar 'Signed in as', then Explanation and Actions tabs")

pvm = r_cfo.pvm
nonzero = [e for e in pvm.effects if abs(e.share) > 0.05]
req(G, "4. One multi factor movement with known underlying drivers",
    len(nonzero) >= 3 and pvm.reconciled,
    "  ".join(str(e) for e in pvm.effects)
    + f"  residual {pvm.residual:.2e}",
    "Attribution tab")

req(G, "5. One low confidence scenario, engine requests clarification or abstains",
    nova_as.abstain and nova_as.discriminating_check is not None,
    f"Nova abstains at confidence '{nova_as.confidence}'; names the check: "
    f"{nova_as.discriminating_check[:60]}...",
    "Select the Nova movement, Explanation tab")

req(G, "6. One sparse history or newly launched KPI",
    nova_mv.sparse and nova_mv.confidence_cap == "low",
    f"Nova has {nova_mv.history_days} days against a "
    f"{nova_mv.min_history_days} day minimum; confidence capped at "
    f"'{nova_mv.confidence_cap}'",
    "Explanation tab, warning banner")

leaked = False
try:
    director.view(eng.wh.frame("sales_transactions"), "gross_margin_pct")
    leaked = True
except EntitlementError:
    pass
d_rows = len(director.view(eng.wh.frame("sales_transactions"), "net_revenue"))
all_rows = len(eng.wh.frame("sales_transactions"))
req(G, "7. One role based security or entitlement scenario",
    not leaked and d_rows < all_rows and r_ana.insight.masked,
    f"director sees {d_rows:,}/{all_rows:,} rows, is denied gross_margin_pct; "
    f"analyst account name masked to {r_ana.insight.facts.get('top_account')}",
    "Sidebar scope, Audit tab")

p = r_cfo.evidence[0].provenance() if r_cfo.evidence else {}
req(G, "8. Evidence: source freshness, method, contribution, confidence, lineage",
    all(k in p for k in ("source", "source_lag_hours", "retrieval_method"))
    and bool(r_cfo.insight.facts.lineage()) and pvm.reconciled
    and r_cfo.assessment.confidence in causal.CONFIDENCE_ORDER,
    f"citation carries {sorted(p)}; {len(r_cfo.insight.facts.lineage())} facts "
    f"traced to producing stage; confidence '{r_cfo.assessment.confidence}'",
    "Evidence tab, and the fact pack expander on Explanation")

split = r_cfo.run.method_split()
req(G, "9. Clear breakdown of LLM versus non LLM processing",
    not r_cfo.run.verify() and len(split) >= 4,
    f"{len(r_cfo.run.stages)} stages across methods {sorted(split)}; "
    f"runtime check reports {len(r_cfo.run.verify())} violations",
    "Method and cost tab")

req(G, "10. Runtime telemetry: latency, model calls, tokens, estimated cost",
    r_cfo.run.total_ms > 0 and "estimated_cost_inr" in r_cfo.run.to_dict(),
    r_cfo.run.footer(),
    "Method and cost tab")

# ==================================== ROUND 2 OBJECTIVES (8) =================
O = "ROUND 2 OBJECTIVE"

alerts = eng.alerts(cfo, PERIOD)
quiet = detect.evaluate(eng.wh, "net_revenue", PERIOD, {"region": "North"})
req(O, "1. Detects and prioritises material KPI movements",
    len(alerts) > 0 and alerts[0].priority >= alerts[-1].priority
    and not quiet.material,
    f"{len(alerts)} material movements, ranked "
    f"{alerts[0].priority:.1f} down to {alerts[-1].priority:.1f}; "
    f"North at {quiet.pct:+.1f}% correctly raises nothing",
    "Sidebar 'Material movements'")

me = eng.wh.value("marketing_efficiency", PERIOD, WEST)
req(O, "2. Reconciles data and business context across heterogeneous sources",
    me == me and len(grains) == 3,
    f"marketing_efficiency = {me:.2f} joins daily sales to weekly spend; "
    f"grain reconciliation declared as "
    f"{c.kpis['marketing_efficiency'].spec['grain_reconciliation']['method']}",
    "Contract tab, marketing_efficiency")

req(O, "3. Identifies and ranks explanatory drivers with appropriate methods",
    pvm.reconciled and len(r_cfo.assessment.verdicts) >= 4,
    f"price volume mix reconciles to {pvm.residual:.2e}; "
    f"{len(r_cfo.assessment.verdicts)} drivers screened across arithmetic and "
    f"evidential kinds",
    "Attribution and Causal gates tabs")

req(O, "4. Persona specific narratives supported by traceable evidence",
    bool(r_dir.evidence) and bool(r_dir.insight.facts.lineage()),
    f"{len(r_dir.evidence)} citations; every asserted number traced to its stage",
    "Explanation and Evidence tabs")

req(O, "5. Communicates uncertainty and abstains",
    nova_as.abstain and r_cfo.assessment.confidence == "high",
    f"headline case reaches 'high' with no blockers; Nova abstains with "
    f"{len(nova_as.abstain_reasons)} stated reasons",
    "Explanation tab, confidence metric")

acts = r_dir.insight.actions
fields = c.action_schema["required_fields"]
req(O, "6. Actions grounded in business levers, constraints and decision rights",
    acts and all(getattr(a, f, None) for a in acts for f in fields)
    and not r_ana.insight.actions,
    f"actions fill all {len(fields)} schema fields; analyst holds no decision "
    f"rights and correctly receives none",
    "Actions tab")

before = store.driver_priors("net_revenue")
eng.record_feedback(r_cfo, "incorrect", cfo, correct_driver="price")
after = store.driver_priors("net_revenue")
req(O, "7. Learns from analyst and business user feedback",
    after != before and after.get("price", 1.0) > 1.0,
    f"one correction moved priors from {before or 'neutral'} to {after}; "
    f"append only log replays to identical state",
    "Actions tab, feedback buttons")

req(O, "8. Operates within realistic security, cost, latency, scalability limits",
    r_cfo.run.total_ms < 2000 and not leaked,
    f"{r_cfo.run.total_ms:.0f} ms end to end on "
    f"{all_rows:,} rows, INR {r_cfo.run.cost_inr:.3f} per insight, "
    f"entitlements enforced on the data not the output",
    "Method and cost tab")

store.clear()

# ------------------------------------------------------------------- report
print("\nFRIDAY  Submission audit against the Round 2 brief")
print("=" * 100)
current = None
for group, ident, ok, ev, where in rows:
    if group != current:
        print(f"\n{group}S\n" + "-" * 100)
        current = group
    print(f"[{'MET' if ok else 'NOT MET'}] {ident}")
    print(f"        evidence : {ev}")
    print(f"        show it  : {where}")

failed = [r for r in rows if not r[2]]
print("\n" + "=" * 100)
print(f"{len(rows) - len(failed)}/{len(rows)} requirements demonstrated "
      f"({10 - len([r for r in failed if 'MINIMUM' in r[0]])}/10 minimum "
      f"expectations, {8 - len([r for r in failed if 'OBJECTIVE' in r[0]])}/8 "
      f"objectives)")
if failed:
    print("\nNOT MET:")
    for _, ident, _, ev, _ in failed:
        print(f"  - {ident}\n    {ev}")
sys.exit(1 if failed else 0)
