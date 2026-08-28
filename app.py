"""
FRIDAY, demo shell.

Deliberately thin. Every number, decision and sentence on this page comes from
`friday.engine`; nothing is computed here. If the UI could produce a figure the
engine cannot, the audit record would be a fiction.

Run:  streamlit run app.py
"""
from __future__ import annotations

import json
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from friday import contracts, narrate, theme
from friday.access import EntitlementError, Principal
from friday.engine import Engine
from friday.feedback import FeedbackStore
from friday.kpi import Period

st.set_page_config(page_title="FRIDAY", page_icon="F", layout="wide")
theme.apply()

PERIOD = Period(date(2026, 7, 24), date(2026, 8, 20))
# Chart colours come from the theme so the palette is defined once. The
# down/up pair is blue vs orange, not green vs red: red-green is the most
# common colour vision deficiency and this chart is the attribution story.
PURPLE, GREY = theme.PURPLE, "#CBCBCB"
DOWN, UP = theme.CHART_DOWN, theme.CHART_UP

USERS = {
    "sales_director": ("R. Mehta", "Regional Sales Director, West"),
    "cfo": ("S. Iyer", "Chief Financial Officer"),
    "analyst": ("A. Rao", "Junior Analyst"),
}


# --------------------------------------------------------------------- engine
@st.cache_resource(show_spinner="Loading contract, sources and evidence index...")
def get_engine(use_llm: bool) -> Engine:
    c = contracts.load()
    client = None
    if use_llm:
        # Scripted stand in. A hosted model drops in here unchanged: the guard,
        # the fact pack and the prompt do not know or care which model replies.
        client = narrate.ScriptedClient(
            lambda s, p: "Revenue fell sharply, driven almost entirely by one "
                         "account, and we expect a further 41.5% decline.",
            name="scripted-narrator")
    return Engine(c, client=client, store=FeedbackStore())


st.sidebar.title("FRIDAY")
st.sidebar.caption("KPI intelligence to action engine")

role = st.sidebar.selectbox(
    "Signed in as", list(USERS), format_func=lambda r: USERS[r][1])
name, label = USERS[role]

use_llm = st.sidebar.toggle(
    "Route narrative through a model", value=False,
    help="Off: deterministic template. On: a scripted model that invents a figure, "
         "so you can watch the numeric guard reject it.")

engine = get_engine(use_llm)
principal = Principal(name, role, engine.contract)

st.sidebar.divider()

visible = engine.contract.visible_kpis(role)
withheld = [n for n in engine.contract.kpis if n not in visible]


def kpi_labels(names: list[str]) -> str:
    return ", ".join(engine.contract.kpis[n].label for n in names)


st.sidebar.caption(
    f"**Scope** · {principal.region_scope}",
    help=(
        f"Row level security. This role is scoped to {principal.region_scope}, so "
        f"every figure on the page is computed from {principal.region_scope} rows "
        f"only. The filter is applied to the data before anything is calculated, "
        f"not stripped out of the answer afterwards, and a request for another "
        f"region is refused."
        if principal.region_scope != "all" else
        "This role sees every region. The contract sets no row level filter for it, "
        "so figures are computed across all four regions."
    ))

st.sidebar.caption(
    f"**KPIs** · {len(visible)} of {len(engine.contract.kpis)} visible",
    help=(
        f"Visible to this role: {kpi_labels(visible)}."
        + (f"\n\nWithheld: {kpi_labels(withheld)}. The contract does not grant "
           f"these to this role, and asking for one raises an entitlement error "
           f"rather than returning a blanked out number." if withheld else
           " This role is granted every KPI in the contract.")
    ))

# joining words stay lowercase, so escalate_to_logistics reads as a phrase
# rather than as a header: "Escalate to Logistics", not "Escalate To Logistics".
SMALL_WORDS = {"to", "of", "for", "and", "the", "a", "an", "in", "on"}


def humanise(right: str) -> str:
    """contact_customer -> Contact Customer."""
    return " ".join(w if i and w in SMALL_WORDS else w.capitalize()
                    for i, w in enumerate(right.split("_")))


rights = principal.decision_rights
if rights:
    # two trailing spaces before the newline is a markdown hard break, so each
    # right lands on its own line instead of reflowing into one paragraph
    st.sidebar.caption(
        "**Decision rights**  \n"
        + "  \n".join(f"{i}) {humanise(r)}" for i, r in enumerate(rights, 1)))
else:
    st.sidebar.caption("**Decision rights** · none")

# --------------------------------------------------------------------- alerts
alerts = engine.alerts(principal, PERIOD)
if not alerts:
    st.info("No material movements for this role in the current period.")
    st.stop()

def movement_facts(m, suffix: str = "") -> list[str]:
    """
    The three facts of a movement, each labelled: which KPI, which slice, how
    far it moved.

    One function for both surfaces on purpose. The sidebar joins these into a
    single line and the header stacks them into three boxes, so the row you pick
    and the header you land on say the same thing in the same words.
    """
    # a movement with no filters is the national total, not a missing region
    scope = " | ".join(f"{k.replace('_', ' ').title()}={v}"
                       for k, v in m.filters.items()) or "Region=All"
    return [f"KPI={m.label}", scope, f"Net Output={m.pct:+.1f}%{suffix}"]


options = {" | ".join(movement_facts(m)): m for m in alerts}
st.sidebar.divider()
choice = st.sidebar.selectbox(
    f"Material movements ({len(alerts)})", list(options),
    help="Ranked by business impact weighted by certainty. "
         "Movements inside normal variance never appear here.")
movement = options[choice]

try:
    result = engine.explain(principal, movement.kpi, PERIOD, movement.filters)
except EntitlementError as e:
    st.error(f"Access denied: {e}")
    st.stop()

ins, run, pvm, assess = result.insight, result.run, result.pvm, result.assessment

# ------------------------------------------------------------------- headline
# Built from the movement rather than by splitting the engine's headline string:
# the labels then match the sidebar exactly, and a change to the engine's
# phrasing cannot quietly desync the two.
_parts = movement_facts(movement, " against the prior period")


def fmt(v: float) -> str:
    """Ratios and percentages need decimals; a ratio of 2.46 shown as '2' is wrong."""
    if v != v:
        return "n/a"
    return f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}"


head_col, metrics_col = st.columns([1, 2], gap="medium")

with head_col:
    st.markdown(theme.headline(_parts, stacked=True), unsafe_allow_html=True)

with metrics_col:
    # Two rows of two, not one row of four. Beside a stacked headline each card
    # would otherwise get about a third of its readable width, and the metric
    # values are the one thing on this page that must survive a glance.
    c1, c2 = st.columns(2)
    c3, c4 = st.columns(2)

    c1.metric("Current", fmt(movement.current), f"{movement.pct:+.1f}%")
    c2.metric("Prior period", fmt(movement.prior))
    c3.metric("Signal strength", f"{movement.z_score:.2f} sigma",
              help="Robust z against this slice's own history. "
                   "Threshold from the contract.")
    c4.metric("Confidence", assess.confidence.upper(),
              delta="abstained" if assess.abstain else "cause established",
              delta_color="inverse" if assess.abstain else "normal")

if ins.masked:
    st.caption("Account names are masked for this role. Pseudonyms are stable, so "
               "attribution still works without revealing the customer.")

# the whole finding as one scannable strip, so the chain reads before the prose
_root = next((v.driver.replace("_", " ") for v in assess.causes
              if v.kind == "evidential"), None)
_lever = next((v.driver for v in assess.causes if v.kind == "arithmetic"), None)
if _root and _lever:
    _share = next(v.share for v in assess.verdicts if v.driver == _lever)
    st.markdown(theme.chain("causal chain", [
        _root, f"{_lever} ({_share:.0%})", f"{movement.label} {movement.pct:+.1f}%"
    ]), unsafe_allow_html=True)
elif assess.abstain:
    st.markdown(theme.chain("outcome", [
        f"{movement.label} {movement.pct:+.1f}%", "no cause established",
        "abstained"]), unsafe_allow_html=True)

tabs = st.tabs(["Explanation", "Attribution", "Causal gates", "Evidence",
                "Actions", "Method and cost", "Contract", "Audit"])

# ------------------------------------------------------------------ narrative
with tabs[0]:
    st.markdown(f"#### {ins.persona}")
    st.write(ins.narrative.text)

    if ins.narrative.violations:
        st.error(f"**Numeric guard fired.** The model wrote "
                 f"{', '.join(ins.narrative.violations)}, which no stage computed. "
                 f"The generated text was discarded and the deterministic narrative "
                 f"shown instead.")
    elif ins.narrative.renderer == "llm":
        st.success("Narrative generated by a model. Every number in it was checked "
                   "against the fact pack before display.")
    else:
        st.caption("Deterministic narrative. No model involved.")

    if assess.abstain:
        st.warning("**No cause asserted.** " + "; ".join(assess.abstain_reasons))
        if ins.next_check:
            st.info(f"Check that would settle it: {ins.next_check}")

    with st.expander("The fact pack: every number this narrative was allowed to use"):
        st.dataframe(pd.DataFrame(ins.facts.lineage()), hide_index=True,
                     width="stretch")

# ----------------------------------------------------------------- attribution
with tabs[1]:
    st.markdown("#### Price, volume and mix")
    df = pvm.as_frame()
    # stack=False is load bearing: with one row per effect Vega still computes stack
    # offsets, which renders three separate contributions as one merged staircase
    # Step() sizes the band, not the whole plot. With a fixed total height the three
    # bands collapse to ~25px each and the bars touch, reading as one solid shape.
    chart = alt.Chart(df).mark_bar(size=22, cornerRadiusEnd=2).encode(
        y=alt.Y("effect:N", title=None, sort="-x"),
        x=alt.X("value:Q", title=f"contribution ({movement.unit})", stack=False),
        color=alt.condition(alt.datum.value < 0, alt.value(DOWN), alt.value(UP)),
        tooltip=[alt.Tooltip("effect:N"),
                 alt.Tooltip("value:Q", format=",.0f"),
                 alt.Tooltip("share_of_movement:Q", format="+.1%")],
    ).properties(height=alt.Step(46))
    st.altair_chart(chart, width="stretch")

    a, b = st.columns([2, 1])
    shown = df[["effect", "value", "share_of_movement"]].copy()
    shown["value"] = shown.value.map(lambda v: f"{v:,.0f}")
    shown["share_of_movement"] = shown.share_of_movement.map(lambda v: f"{v:+.1%}")
    shown.columns = ["effect", f"contribution ({movement.unit})", "share of movement"]
    a.dataframe(shown, hide_index=True, width="stretch")
    b.metric("Reconciliation residual", f"{abs(pvm.residual):.6f}",
             help="Contributions are an identity, not an approximation. This is "
                  "zero or the decomposition is not published.")
    if pvm.reconciled:
        b.success("Sums exactly to the movement")
    else:
        b.error("Does not reconcile, withheld")

    if result.by_account is not pvm:
        st.markdown("#### Largest contributors by account")
        acc = result.by_account.as_frame().head(6).copy()
        acc["value"] = acc.value.map(lambda v: f"{v:,.0f}")
        acc["share_of_movement"] = acc.share_of_movement.map(lambda v: f"{v:+.1%}")
        acc.columns = ["account", "dimension", f"contribution ({movement.unit})",
                       "share of movement"]
        st.dataframe(acc, hide_index=True, width="stretch")

# ---------------------------------------------------------------- causal gates
with tabs[2]:
    st.markdown("#### Three gates, all must pass before anything is called a cause")
    rows = []
    for v in assess.verdicts:
        rows.append({
            "driver": v.driver,
            "kind": v.kind,
            "share of movement": f"{v.share:.0%}" if v.kind == "arithmetic"
                                 else f"{v.strength:.1f}x rate",
            "sequence": "pass" if v.sequence_ok else "fail",
            "magnitude": "pass" if v.magnitude_ok else "fail",
            "mechanism": "pass" if v.mechanism_ok else "fail",
            "verdict": v.status.upper(),
            "why not": "; ".join(v.reasons) or "-",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption("Arithmetic drivers come from the decomposition and are the movement "
               "restated. Evidential drivers sit upstream and must be dated and "
               "corroborated. Screening them the same way would be a category error.")

# -------------------------------------------------------------------- evidence
with tabs[3]:
    if not result.evidence:
        st.info("No supporting passages retrieved for this slice.")
    for p in result.evidence:
        st.markdown(f"> {p.text}")
        st.caption(" · ".join(f"{k}: {v}" for k, v in p.provenance().items()))
        st.divider()
    st.markdown("#### Source freshness at the moment this ran")
    st.dataframe(pd.DataFrame(result.freshness), hide_index=True,
                 width="stretch")

# --------------------------------------------------------------------- actions
with tabs[4]:
    if assess.abstain:
        st.warning("No actions proposed: the engine did not establish a cause.")
    elif not ins.actions:
        st.info(f"No actions for {ins.persona}. This role holds no decision rights, "
                f"so recommending one would be meaningless.")
    else:
        for a in ins.actions:
            st.markdown(f"**{a.action}**")
            st.dataframe(pd.DataFrame([a.as_dict()]).T.rename(columns={0: ""}),
                         width="stretch")
    st.divider()

    st.markdown("#### Was this explanation right?")
    st.caption("Corrections adjust driver priors and materiality thresholds. They "
               "never rewrite a contribution, because contributions are arithmetic.")
    f1, f2, f3, f4 = st.columns(4)
    fb = None
    if f1.button("Correct", width="stretch"):
        fb = "correct"
    if f2.button("Wrong driver", width="stretch"):
        fb = "incorrect"
    if f3.button("Incomplete", width="stretch"):
        fb = "incomplete"
    if f4.button("Not material", width="stretch"):
        fb = "not_material"
    if fb:
        engine.record_feedback(result, fb, principal)
        st.success(f"Recorded '{fb}'. Priors now: "
                   f"{engine.store.driver_priors(movement.kpi) or 'neutral'} · "
                   f"threshold multiplier for this slice: "
                   f"{engine.store.materiality_nudge(movement.kpi, movement.slice_label)}")
        st.caption(engine.store.summary(movement.kpi))

# -------------------------------------------------------------- method & cost
with tabs[5]:
    st.markdown("#### Where the work actually happened")
    split = pd.DataFrame([
        {"method": k, "stages": v["stages"], "ms": v["ms"],
         "model calls": v["calls"], "share of latency": v["share_of_latency"]}
        for k, v in run.method_split().items()
    ]).sort_values("ms", ascending=False)

    ch = alt.Chart(split).mark_bar().encode(
        y=alt.Y("method:N", sort="-x", title=None),
        x=alt.X("ms:Q", title="milliseconds"),
        color=alt.condition(alt.datum.method == "llm",
                            alt.value(PURPLE), alt.value(GREY)),
        tooltip=list(split.columns),
    ).properties(height=alt.Step(34))
    st.altair_chart(ch, width="stretch")
    split_show = split.copy()
    split_show["share of latency"] = split_show["share of latency"].map(
        lambda v: f"{v:.1%}")
    st.dataframe(split_show, hide_index=True, width="stretch")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total latency", f"{run.total_ms:.0f} ms")
    m2.metric("Deterministic", f"{100 * run.deterministic_ms / run.total_ms:.0f}%"
              if run.total_ms else "n/a")
    m3.metric("Tokens", f"{run.tokens_in + run.tokens_out:,}")
    m4.metric("Estimated cost", f"INR {run.cost_inr:.3f}")
    st.success("Verified: no stage declared deterministic issued a model call. "
               "This is enforced at runtime, not asserted on a slide.")

# -------------------------------------------------------------------- contract
with tabs[6]:
    spec = engine.contract.kpis[movement.kpi]
    st.markdown(f"#### {spec.label}")
    st.code(spec.spec.get("formula", ""), language="sql")
    st.write(spec.spec.get("definition", ""))
    a, b = st.columns(2)
    a.markdown("**Materiality**")
    a.json(spec.spec["materiality"], expanded=True)
    b.markdown("**Access**")
    b.json(spec.spec["access"], expanded=True)
    st.markdown("**Lineage**")
    for step in spec.spec.get("lineage", []):
        st.markdown(f"- {step}")
    st.caption("No module hardcodes any of this. If it is not in contracts/kpis.yaml, "
               "the engine does not know it.")

# ----------------------------------------------------------------------- audit
with tabs[7]:
    st.markdown("#### Access decisions for this session")
    for line in principal.audit_trail():
        st.code(line, language=None)
    st.markdown("#### Full audit record for this insight")
    st.download_button("Download audit record (JSON)",
                       json.dumps(result.audit_record(), indent=2, default=str),
                       file_name=f"{result.insight_id}_audit.json",
                       mime="application/json")
    st.json(result.audit_record(), expanded=False)
