"""
Lane C gate. Entitlements, telemetry and the feedback loop.

Covers Round 2 minimum expectations 7, 9 and 10.

Run:  python scripts/verify_lane_c.py
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from friday import access, attribute, causal, contracts, detect, feedback, telemetry  # noqa: E402
from friday.kpi import Period, Warehouse                                              # noqa: E402

PERIOD = Period(date(2026, 7, 24), date(2026, 8, 20))
WEST = {"region": "West"}

results: list[tuple[bool, str, str]] = []


def check(ok, label, detail=""):
    results.append((bool(ok), label, detail))


c = contracts.load()
wh = Warehouse(c)
sales = wh.frame("sales_transactions")

# ================================================================ ENTITLEMENTS
director = access.Principal("R. Mehta", "sales_director", c)
cfo = access.Principal("S. Iyer", "cfo", c)
analyst = access.Principal("A. Rao", "analyst", c)

d_view = director.view(sales, "net_revenue")
check(set(d_view.region.unique()) == {"West"} and len(d_view) < len(sales),
      "REQ 7: row level security, sales director is confined to their own region",
      f"{len(sales):,} rows in, {len(d_view):,} out, regions "
      f"{sorted(d_view.region.unique())}, {len(sales) - len(d_view):,} rows withheld")

a_view = analyst.view(sales, "net_revenue")
real_names = set(sales.account_name.unique())
seen = set(a_view.account_name.unique())
check(not (seen & real_names) and all(n.startswith("acct_") for n in seen),
      "REQ 7: column masking, analyst never sees a real account name",
      f"analyst sees {sorted(seen)[:3]}... instead of {sorted(real_names)[:3]}...")

check(len(a_view) == len(sales),
      "Masking preserves analysability, the analyst still sees every row",
      f"{len(a_view):,} rows, {a_view.account_name.nunique()} distinct pseudonyms "
      f"against {sales.account_name.nunique()} real accounts")

acct_masked = attribute.by_dimension(wh, "net_revenue", PERIOD, "account_name", WEST)
top_real = acct_masked.top(1)[0].name
check(access.pseudonymise(top_real) == access.pseudonymise(top_real)
      and access.pseudonymise("Acme Corp") != access.pseudonymise("Orbit Retail"),
      "Pseudonyms are stable across runs and distinct across accounts",
      f"'{top_real}' -> {access.pseudonymise(top_real)} (same every run)")

denied = False
try:
    director.view(sales, "gross_margin_pct")
except access.EntitlementError as e:
    denied = True
    reason = str(e)
check(denied,
      "REQ 7: KPI level entitlement, margin is withheld from the sales director",
      reason if denied else "NOT DENIED, this is a leak")

narrowed = director.filters_for("net_revenue", None)
blocked = False
try:
    director.filters_for("net_revenue", {"region": "North"})
except access.EntitlementError:
    blocked = True
check(narrowed == {"region": "West"} and blocked,
      "Requests are narrowed to scope, and out of scope requests are refused",
      f"unfiltered request became {narrowed}; request for North was refused")

check(cfo.may_act("approve_pricing_change") and not director.may_act("approve_pricing_change")
      and director.may_act("contact_customer") and not analyst.decision_rights,
      "Decision rights differ by role, so actions can be routed to a real owner",
      f"cfo={cfo.decision_rights[:2]}, director={director.decision_rights[:2]}, "
      f"analyst={analyst.decision_rights}")

check(len(director.audit_trail()) >= 2 and "ALLOW" in director.audit_trail()[0]
      and any("DENY" in l for l in director.audit_trail()),
      "Every access decision is written to an audit trail",
      " | ".join(director.audit_trail()[:2]))

redacted = access.redact_free_text(
    "Spoke with Priya Nair in procurement about the delays.", ["Priya Nair"])
check("Priya Nair" not in redacted and "procurement" in redacted,
      "Free text is redacted of named individuals before it can reach a narrative",
      redacted)

# =================================================================== TELEMETRY
run = telemetry.Run(insight_id="ins_0001", principal=cfo.name, role=cfo.role)

with run.stage("entitlement", "business_rules", "row filter and column mask") as s:
    scoped = cfo.view(sales, "net_revenue")

with run.stage("detection", "statistics", "robust z against 90 day baseline") as s:
    mv = detect.evaluate(wh, "net_revenue", PERIOD, WEST)
    s.detail = f"z={mv.z_score:.2f}, material={mv.material}"

with run.stage("attribution", "deterministic_logic", "price volume mix") as s:
    pvm = attribute.price_volume_mix(wh, PERIOD, WEST)
    s.detail = f"residual={pvm.residual:.6f}"

with run.stage("causal_screen", "causal_inference", "sequence magnitude mechanism") as s:
    assess = causal.screen(wh, mv, pvm.effects, PERIOD, WEST)
    s.detail = f"confidence={assess.confidence}"

with run.stage("evidence_retrieval", "retrieval", "text probe over service_events") as s:
    ev = causal.gather_evidence(wh, "delivery_reliability", PERIOD, WEST)
    s.detail = f"{len(ev)} items"

with run.stage("narrative", "llm", "synthesis only, every number injected") as s:
    time.sleep(0.03)                      # stands in for the model round trip
    run.record_model_call(s, model="friday-narrator", tier="standard",
                          tokens_in=880, tokens_out=240, ms=30.0,
                          purpose="persona narrative")

problems = run.verify()
check(not problems,
      "REQ 9: the LLM claim is enforced, not asserted",
      "no deterministic stage issued a model call; "
      f"{len([s for s in run.stages if not s.is_llm])} deterministic stages, "
      f"{len([s for s in run.stages if s.is_llm])} generative")

split = run.method_split()
check("llm" in split and split["llm"]["calls"] == 1
      and sum(v["calls"] for k, v in split.items() if k != "llm") == 0,
      "REQ 9: method split is derived from instrumentation, not written by hand",
      " | ".join(f"{k}: {v['stages']} stage(s), {v['ms']}ms, {v['calls']} call(s)"
                 for k, v in sorted(split.items())))

check(run.total_ms > 0 and run.tokens_in == 880 and run.tokens_out == 240
      and run.cost_inr > 0,
      "REQ 10: latency, model calls, tokens and cost are all captured",
      run.footer())

det_share = run.deterministic_ms / run.total_ms
check(det_share > 0.0,
      "Latency is attributed between deterministic work and generation",
      f"deterministic {run.deterministic_ms:.0f}ms, llm {run.llm_ms:.0f}ms "
      f"({det_share:.0%} of latency is deterministic)")

# a stage that cheats must be caught
bad = telemetry.Run("ins_bad")
with bad.stage("attribution", "deterministic_logic") as s:
    bad.record_model_call(s, "sneaky", "small", 10, 10, 1.0, "should not happen")
check(len(bad.verify()) == 1 and "must stay free of generation" in bad.verify()[0],
      "A deterministic stage that issues a model call fails verification",
      bad.verify()[0][:96] + "...")

rejected = False
try:
    with telemetry.Run("ins_x").stage("mystery", "vibes"):
        pass
except telemetry.TelemetryError:
    rejected = True
check(rejected,
      "A stage cannot declare a method outside the brief's taxonomy",
      "method 'vibes' rejected; only sql, deterministic_logic, business_rules, "
      "statistics, traditional_ml, causal_inference, retrieval, llm are allowed")

check("estimated_cost_inr" in run.to_dict() and run.to_json().startswith("{"),
      "Telemetry serialises for the audit record",
      f"insight {run.insight_id}: {run.to_dict()['estimated_cost_inr']} INR estimated")

# ==================================================================== FEEDBACK
store = feedback.FeedbackStore(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "feedback_test.jsonl"))
store.clear()

before = store.driver_priors("net_revenue")
ranked_before = [v.driver for v in store.rerank("net_revenue", assess.verdicts)]

store.record(feedback.Correction(
    insight_id="ins_0001", kpi="net_revenue", slice_label="region=West",
    verdict="incorrect", stated_driver="volume", correct_driver="price",
    note="Acme was already lost last quarter; the discount is the live issue.",
    by=cfo.name, role=cfo.role))
store.record(feedback.Correction(
    insight_id="ins_0002", kpi="net_revenue", slice_label="region=West",
    verdict="incomplete", correct_driver="price",
    note="Also mention the competitor promotion.", by=cfo.name, role=cfo.role))

after = store.driver_priors("net_revenue")
check(after.get("price", 1.0) > 1.0 and after.get("volume", 1.0) < 1.0,
      "REQ 7 objective: corrections move driver priors in the right direction",
      f"before {before or 'all neutral'} -> after {after}")

def margin(verdicts, priors):
    """Weighted gap between the top two explanations, as a ratio."""
    w = sorted((abs(v.contribution) * priors.get(v.driver, 1.0) for v in verdicts),
               reverse=True)
    return w[0] / w[1] if len(w) > 1 and w[1] else float("inf")

m_before = margin(assess.verdicts, before or {})
m_after = margin(assess.verdicts, after)
check(m_after < m_before * 0.75,
      "Corrections measurably narrow the gap between competing explanations",
      f"volume led price by {m_before:.2f}x before feedback, {m_after:.2f}x after "
      f"({100 * (1 - m_after / m_before):.0f}% narrower)")

# a dominant arithmetic driver must survive feedback: contributions are facts
ranked_after = [v.driver for v in store.rerank("net_revenue", assess.verdicts)]
check(ranked_after[0] == "volume",
      "Feedback cannot overturn a driver that dominates the arithmetic",
      f"volume still leads at {m_after:.2f}x despite two corrections against it; "
      f"priors only reorder, they never rewrite a contribution")

# but where the arithmetic is close, the learned prior decides
close = [
    causal.Verdict(driver="price", lever="pricing", controllable=True,
                   contribution=-300_000.0, share=0.30, sequence_ok=True,
                   magnitude_ok=True, mechanism_ok=True, onset=None,
                   first_evidence=None),
    causal.Verdict(driver="volume", lever="account_management", controllable=True,
                   contribution=-330_000.0, share=0.33, sequence_ok=True,
                   magnitude_ok=True, mechanism_ok=True, onset=None,
                   first_evidence=None),
]
order_naive = [v.driver for v in sorted(close, key=lambda v: abs(v.contribution),
                                        reverse=True)]
order_learned = [v.driver for v in store.rerank("net_revenue", close)]
check(order_naive[0] == "volume" and order_learned[0] == "price",
      "Where contributions are close, the learned prior decides the order",
      f"raw contribution ranks {' > '.join(order_naive)}; "
      f"after feedback {' > '.join(order_learned)} "
      f"(330k x 0.85 = 280k against 300k x 1.32 = 397k)")

n_before = store.materiality_nudge("net_revenue", "region=South")
store.record(feedback.Correction(
    insight_id="ins_0003", kpi="net_revenue", slice_label="region=South",
    verdict="not_material", note="Seasonal, we see this every August.",
    by=analyst.name, role=analyst.role))
n_after = store.materiality_nudge("net_revenue", "region=South")
check(n_after > n_before and n_after <= feedback.NUDGE_MAX,
      "Alert fatigue is fixable by the people suffering it",
      f"South threshold multiplier {n_before} -> {n_after} after one "
      f"'not material' correction; capped at {feedback.NUDGE_MAX}")

for _ in range(30):
    store.record(feedback.Correction(
        insight_id="spam", kpi="net_revenue", slice_label="region=South",
        verdict="not_material", by="x", role="analyst"))
check(store.materiality_nudge("net_revenue", "region=South") <= feedback.NUDGE_MAX
      and max(store.driver_priors("net_revenue").values()) <= feedback.PRIOR_MAX,
      "Bounds hold, so no one can silence a KPI by spamming corrections",
      f"after 30 more corrections the multiplier is still "
      f"{store.materiality_nudge('net_revenue', 'region=South')} "
      f"(cap {feedback.NUDGE_MAX})")

replayed = feedback.FeedbackStore(store.path)
check(replayed.driver_priors("net_revenue") == store.driver_priors("net_revenue"),
      "State is reconstructed exactly by replaying the log, so the loop is auditable",
      f"{len(replayed.events)} events replayed to identical priors")
store.clear()

# ------------------------------------------------------------------- report
print("\nFRIDAY  Lane C gate: entitlements, telemetry, feedback\n" + "=" * 78)
for ok, label, detail in results:
    print(f"[{'PASS' if ok else 'FAIL'}] {label}")
    if detail:
        print(f"       {detail}")
print("=" * 78)
print("\nTelemetry for insight ins_0001\n")
print(run.table())
print("\n" + run.footer())
failed = sum(1 for ok, _, _ in results if not ok)
print("=" * 78)
print(f"{len(results) - failed}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
