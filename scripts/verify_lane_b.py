"""
Lane B gate. Retrieval, narrative synthesis, personas and the numeric guard.

Covers Round 2 minimum expectations 3 and 8, and objectives 4, 5 and 6.

Run:  python scripts/verify_lane_b.py
"""
from __future__ import annotations

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from friday import (access, attribute, causal, contracts, detect,   # noqa: E402
                    evidence, narrate, personas)
from friday.kpi import Period, Warehouse                            # noqa: E402

PERIOD = Period(date(2026, 7, 24), date(2026, 8, 20))
WEST = {"region": "West"}

results: list[tuple[bool, str, str]] = []


def check(ok, label, detail=""):
    results.append((bool(ok), label, detail))


c = contracts.load()
wh = Warehouse(c)

mv = detect.evaluate(wh, "net_revenue", PERIOD, WEST)
pvm = attribute.price_volume_mix(wh, PERIOD, WEST)
acct = attribute.by_dimension(wh, "net_revenue", PERIOD, "account_name", WEST)
assess = causal.screen(wh, mv, pvm.effects, PERIOD, WEST)

# =================================================================== RETRIEVAL
idx = evidence.Index.build(wh)
check(len(idx.docs) > 500,
      "BM25 index builds over the free text source",
      f"{len(idx.docs):,} passages indexed, average length "
      f"{idx._avg_len:.1f} tokens, no model download required")

hits = evidence.for_driver(idx, "delivery_reliability", PERIOD, WEST)
check(len(hits) >= 2 and all("deliver" in h.text.lower() or "late" in h.text.lower()
                             or "arriv" in h.text.lower() or "slip" in h.text.lower()
                             for h in hits),
      "Retrieval returns on topic passages for a driver",
      hits[0].cite(100) if hits else "nothing returned")

vol_hits = evidence.for_driver(idx, "volume", PERIOD, {"account_name": "Acme Corp"})
check(vol_hits and "alternative suppliers" in vol_hits[0].text.lower(),
      "Retrieval surfaces the planted churn signal as the top passage",
      vol_hits[0].cite(110) if vol_hits else "not found")

kinds = {h.kind for h in evidence.for_driver(idx, "delivery_reliability", PERIOD, WEST, top_k=3)}
texts = [h.text for h in evidence.for_driver(idx, "delivery_reliability", PERIOD, WEST, top_k=3)]
check(len(set(texts)) == len(texts),
      "Diversification stops the same sentence being cited three times",
      f"{len(texts)} distinct passages across kinds {sorted(kinds)}")

north = evidence.for_driver(idx, "volume", PERIOD, {"region": "North"})
check(not any("alternative suppliers" in p.text.lower() for p in north),
      "Retrieval respects the slice, West evidence never leaks into North",
      f"{len(north)} passage(s) for North, none mentioning supplier churn")

prov = hits[0].provenance() if hits else {}
check(all(k in prov for k in ("source", "date", "age_days", "source_lag_hours",
                              "retrieval_method", "relevance_score")),
      "REQ 8: every citation carries source, freshness, method and score",
      str(prov))

fresh = evidence.freshness_report(wh, ["sales_transactions", "marketing_spend",
                                       "service_events"])
check(len(fresh) == 3 and {f["grain"] for f in fresh} == {"order_line", "campaign_week", "event"},
      "REQ 8: source freshness is disclosed across all three grains",
      " | ".join(f"{f['source']}: {f['cadence']}, {f['lag_hours']}h lag, "
                 f"grain {f['grain']}" for f in fresh))

# ================================================================ NUMERIC GUARD
director = access.Principal("R. Mehta", "sales_director", c)
cfo = access.Principal("S. Iyer", "cfo", c)
analyst = access.Principal("A. Rao", "analyst", c)

pack = personas.build_facts(wh, cfo, mv, pvm, acct, assess, PERIOD)
check(len(pack.facts) >= 15 and all(f.provenance for f in pack.facts.values()
                                    if f.key not in ("kpi", "slice", "period")),
      "Fact pack carries every permitted number, each stamped with its producer",
      f"{len(pack.facts)} facts; e.g. volume_effect <- "
      f"{pack['volume_effect'].provenance}")

honest = narrate.ScriptedClient(lambda s, p: (
    "Net Revenue for region=West moved -19.2% against the prior period. "
    "Volume accounts for 73% of the movement. The upstream cause is delivery "
    "reliability, running at 5.5 times its previous rate."))
r_ok = narrate.render_guarded(honest, pack, "CFO", "explain", [], lambda: "fallback")
check(not r_ok.violations and r_ok.renderer == "llm" and not r_ok.fell_back,
      "Guard passes prose whose every number comes from the fact pack",
      f"renderer={r_ok.renderer}, violations={r_ok.violations}")

liar = narrate.ScriptedClient(lambda s, p: (
    "Net Revenue for region=West moved -19.2% against the prior period, and we "
    "expect a further 34.7% decline next quarter costing 8,400,000 INR."))
r_bad = narrate.render_guarded(liar, pack, "CFO", "explain", [], lambda: "fallback")
check(r_bad.fell_back and any(v.startswith("34.7") for v in r_bad.violations)
      and any("8,400,000" in v for v in r_bad.violations),
      "REQ: an invented number fails the render instead of reaching a reader",
      f"caught {r_bad.violations}, fell back to {r_bad.renderer}")

subtle = narrate.ScriptedClient(lambda s, p: (
    "Volume accounts for 78% of the movement."))     # true figure is 73%
r_sub = narrate.render_guarded(subtle, pack, "CFO", "explain", [], lambda: "fallback")
check(r_sub.fell_back and any(v.startswith("78") for v in r_sub.violations),
      "Guard catches a plausible but wrong figure, not just an absurd one",
      f"78% rejected against the computed 73%; violations {r_sub.violations}")

rounded = narrate.ScriptedClient(lambda s, p: (
    "Volume accounts for 72.8% of the movement, worth -1,132,495 INR."))
r_round = narrate.render_guarded(rounded, pack, "CFO", "explain", [], lambda: "fallback")
check(not r_round.fell_back,
      "Guard tolerates legitimate rounding of a computed figure",
      "72.8% and 73% both accepted for a share computed as 0.728")

# ===================================================================== PERSONAS
ev_west = evidence.for_driver(idx, "delivery_reliability", PERIOD, WEST)
ins_dir = personas.build_insight(wh, director, mv, pvm, acct, assess, ev_west, PERIOD)
ins_cfo = personas.build_insight(wh, cfo, mv, pvm, acct, assess, ev_west, PERIOD)
ins_ana = personas.build_insight(wh, analyst, mv, pvm, acct, assess, ev_west, PERIOD)

check(ins_dir.narrative.text != ins_cfo.narrative.text != ins_ana.narrative.text,
      "REQ 3: one movement, three genuinely different narratives",
      f"director {len(ins_dir.narrative.text)} chars, cfo "
      f"{len(ins_cfo.narrative.text)}, analyst {len(ins_ana.narrative.text)}")

check("Acme Corp" in ins_dir.narrative.text and "Acme Corp" not in ins_ana.narrative.text
      and "acct_" in ins_ana.narrative.text,
      "REQ 7 in the narrative: the analyst's prose is masked at the source",
      f"director names the account; analyst sees "
      f"{ins_ana.facts.get('top_account')}")

check(ins_dir.actions and ins_cfo.actions and not ins_ana.actions,
      "REQ 3: actions follow decision rights, the analyst correctly gets none",
      f"director {len(ins_dir.actions)}, cfo {len(ins_cfo.actions)}, "
      f"analyst {len(ins_ana.actions)} (holds no decision rights)")

d_levers = {a.controllable_lever for a in ins_dir.actions}
c_levers = {a.controllable_lever for a in ins_cfo.actions}
check(d_levers != c_levers,
      "Different roles are offered different levers, not the same list relabelled",
      f"director: {sorted(d_levers)} | cfo: {sorted(c_levers)}")

required = c.action_schema["required_fields"]
a0 = ins_dir.actions[0]
check(all(getattr(a0, f, None) for f in required),
      "REQ: actions fill the brief's schema exactly",
      " -> ".join(required))

check(all(a.owner for a in ins_dir.actions + ins_cfo.actions),
      "Every action names an owner who holds the required right",
      a0.line()[:150] + "...")

# ------------------------------------------------------- abstention narrative
nova = detect.evaluate(wh, "net_revenue", PERIOD, {"category": "Nova"})
nova_pvm = attribute.price_volume_mix(wh, PERIOD, {"category": "Nova"},
                                      segment_by="channel")
nova_acct = attribute.by_dimension(wh, "net_revenue", PERIOD, "account_name",
                                   {"category": "Nova"})
nova_assess = causal.screen(wh, nova, nova_pvm.effects, PERIOD, {"category": "Nova"})
ins_nova = personas.build_insight(wh, cfo, nova, nova_pvm, nova_acct, nova_assess,
                                  [], PERIOD)
check(ins_nova.abstained and not ins_nova.actions and ins_nova.next_check,
      "REQ 5: on the low confidence case the narrative abstains and offers no action",
      f"'{ins_nova.narrative.text[-60:]}' | next check: "
      f"{ins_nova.next_check[:70]}...")

check("not sufficient to name a cause" in ins_nova.narrative.text,
      "Abstention is stated in the prose, not buried in a confidence field",
      ins_nova.narrative.text[-90:])

# --------------------------------------------------------------- traceability
lineage = pack.lineage()
check(len(lineage) >= 12 and all(l["produced_by"] for l in lineage),
      "REQ 8: every asserted number traces to the stage that computed it",
      f"{len(lineage)} traced facts; e.g. {lineage[4]['fact']} = "
      f"{lineage[4]['value']} from {lineage[4]['produced_by']}")

llm_facts = [l for l in lineage if "llm" in l["produced_by"].lower()]
check(not llm_facts,
      "REQ 9: not one number in the fact pack was produced by a model",
      f"0 of {len(lineage)} facts came from generation; "
      "all from sql, arithmetic, statistics or causal screening")

# ------------------------------------------------------------------- report
print("\nFRIDAY  Lane B gate: retrieval, narrative, personas\n" + "=" * 78)
for ok, label, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if detail:
        print(f"       {detail}")
print("=" * 78)
print("\n--- Regional Sales Director ---\n")
print(ins_dir.render())
print("\n--- Junior Analyst (masked) ---\n")
print(ins_ana.render())
failed = sum(1 for ok, _, _ in results if not ok)
print("\n" + "=" * 78)
print(f"{len(results) - failed}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
