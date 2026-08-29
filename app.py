"""
FRIDAY, demo shell.

Deliberately thin. Every number, decision and sentence on this page comes from
`friday.engine`; nothing is computed here. If the UI could produce a figure the
engine cannot, the audit record would be a fiction.

Run:  streamlit run app.py
"""
from __future__ import annotations

import html
import json
import re
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

# Price/volume/mix decomposes revenue whatever KPI is selected, so its figures
# are in revenue's unit, not the selected movement's. Labelling them with the
# movement's unit read as "contribution (ratio)" against values in lakhs on any
# KPI that is not revenue. Taken from the contract rather than written in.
PVM_UNIT = engine.contract.kpis["net_revenue"].unit

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

def movement_pairs(m, suffix: str = "") -> list[tuple[str, str]]:
    """
    The facts of a movement as label/value pairs: which KPI, which slice, how
    far it moved.

    One source for both surfaces on purpose. The sidebar joins them into a
    single "Label=value" line and the header card sets each label over its
    value, so the row you pick and the header you land on say the same thing in
    the same words.
    """
    # a movement with no filters is the national total, not a missing region
    scope = [(k.replace("_", " ").title(), v) for k, v in m.filters.items()]
    return [("KPI", m.label), *(scope or [("Region", "All")]),
            ("Movement", f"{m.pct:+.1f}%{suffix}")]


def movement_facts(m, suffix: str = "") -> list[str]:
    """The same facts, values only, for one-line surfaces."""
    return [v for _, v in movement_pairs(m, suffix)]


# Values only, joined with a middot. The labelled form is roughly twice the
# width of the sidebar, so the selectbox clipped it mid-number and showed the
# tail -- "| Region=West | Movement=-19.2" -- which reads as a broken control
# rather than a choice. The header card still carries the labels.
options = {" · ".join(movement_facts(m)): m for m in alerts}
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
_parts = movement_pairs(movement)


def fmt(v: float) -> str:
    """Ratios and percentages need decimals; a ratio of 2.46 shown as '2' is wrong."""
    if v != v:
        return "n/a"
    return f"{v:,.2f}" if abs(v) < 1000 else f"{v:,.0f}"


# ISO dates first, so 2026-06-16 is emphasised whole rather than shattered into
# three separate numbers.
_FIGURE = re.compile(r"(\d{4}-\d{2}-\d{2}|-?\d[\d,]*(?:\.\d+)?%?)")


def emphasise(text: str) -> str:
    """
    Bold the figures in a narrative, for display only.

    Done here rather than in the engine on purpose. The narrative string is also
    served by the REST layer and rendered by the React console, and markup baked
    into it there would reach those callers as literal characters. Presentation
    belongs in the presentation layer.
    """
    return _FIGURE.sub(r"<strong>\1</strong>", html.escape(str(text)))


# Full names for the fact pack. Underscored keys are how the engine addresses
# these internally; a reader should not have to decode them.
FACT_LABELS = {
    "kpi": "KPI",
    "slice": "Slice",
    "period": "Period compared",
    "current_value": "Current value",
    "prior_value": "Prior period value",
    "change_abs": "Change, absolute",
    "change_pct": "Change, percent",
    "z_score": "Signal strength (robust z score)",
    "normal_swing": "Normal swing for this slice",
    "top_account": "Largest contributing account",
    "top_account_effect": "That account's contribution",
    "root_cause": "Upstream root cause",
    "root_cause_strength": "Root cause rate against its own baseline",
    "root_cause_from": "Root cause began",
    "onset": "Movement onset",
    "confidence": "Confidence",
}


# The action schema the brief specifies, in the order the contract lists it.
ACTION_FIELD_LABELS = {
    "driver": "Driver",
    "controllable_lever": "Controllable lever",
    "action": "Action",
    "expected_impact": "Expected impact",
    "owner": "Owner",
    "confidence": "Confidence",
    "monitoring_plan": "Monitoring plan",
}


def fact_label(key: str) -> str:
    """Human readable name for a fact key: volume_effect -> Volume effect."""
    if key in FACT_LABELS:
        return FACT_LABELS[key]
    # driver derived keys are generated from the contract, so they are handled
    # by shape rather than enumerated: volume_share -> Volume share
    head, *rest = key.split("_")
    return " ".join([head.capitalize(), *rest])


_span = f"{PERIOD.start:%d %b} - {PERIOD.end:%d %b %Y}"
st.markdown(theme.topbar(
    "KPI overview",
    f"{len(alerts)} material movement{'' if len(alerts) == 1 else 's'} "
    f"for {label}", _span), unsafe_allow_html=True)

# Direction, once, in one place. Down is amber and up is blue rather than the
# usual red/green, for the reason set out in the theme: red-green is the most
# common colour vision deficiency and this is the number the page turns on.
_down = movement.pct < 0

# the materiality gate this movement had to clear to be on the page at all
_z_gate = engine.contract.kpis[movement.kpi].thresholds()[0].get("threshold")

# The four numbers, each with the colour its own reading calls for. Bars may use
# the brighter chart tokens because a 4px block only needs 3:1; the small text
# beneath uses the darker status tokens, which clear 4.5:1.
_stats = [
    {"value": fmt(movement.current), "label": "Current", "color": theme.PURPLE,
     "icon": "level",
     "note": f"{movement.pct:+.1f}% vs prior",
     "note_color": theme.CAUTION if _down else theme.OK},
    {"value": fmt(movement.prior), "label": "Prior period",
     "color": theme.LILAC, "icon": "clock",
     "note": "the baseline", "note_color": theme.MUTED},
    # the unit lives in the note, not the label: a label long enough to wrap
    # strands the help marker alone on a second line
    {"value": f"{movement.z_score:.2f}", "label": "Signal strength",
     "color": theme.CHART_DOWN if movement.z_score < 0 else theme.CHART_UP,
     "icon": "pulse",
     # the threshold is read off the contract, never typed here, so a
     # recalibration moves this line without anyone remembering to
     "note": f"sigma · alerts beyond {_z_gate:.2f}" if _z_gate else "sigma",
     "note_color": theme.MUTED,
     "help": "Robust z against this slice's own history. "
             "Threshold from the contract."},
    {"value": assess.confidence.upper(), "label": "Confidence",
     "color": theme.NEUTRAL if assess.abstain else theme.OK,
     "icon": "shield",
     "note": "abstained" if assess.abstain else "cause established",
     "note_color": theme.NEUTRAL if assess.abstain else theme.OK},
]

# The chain is worked out before the row is drawn, because whether there is one
# decides how wide the other two cards get.
_root = next((v.driver.replace("_", " ") for v in assess.causes
              if v.kind == "evidential"), None)
_lever = next((v.driver for v in assess.causes if v.kind == "arithmetic"), None)
if _root and _lever:
    _share = next(v.share for v in assess.verdicts if v.driver == _lever)
    _chain = ("Causal chain", "root cause to outcome",
              [_root, f"{_lever} ({_share:.0%})",
               f"{movement.label} {movement.pct:+.1f}%"])
elif assess.abstain:
    # an abstention is a finding too, and it gets the same box rather than
    # being quietly dropped: the reader should see that the engine stopped
    _chain = ("Outcome", "no cause established",
              [f"{movement.label} {movement.pct:+.1f}%", "no cause established",
               "abstained"])
else:
    _chain = None

# Three cards, not two and a banner: what moved, the numbers, and the chain that
# explains them are three parts of one finding and belong on one line. The
# chain used to run full width underneath, where it read as a footer.
# Not equal thirds. The facts card holds three short strings and had width to
# spare; the summary holds four numbers two-by-two and was the one that felt
# tight, so the width moves from the first card to the middle one.
_cols = st.columns([0.85, 1.35, 1.05] if _chain else [1, 2], gap="medium")

with _cols[0]:
    st.markdown(theme.fact_card("Movement", "vs prior period", _parts),
                unsafe_allow_html=True)

with _cols[1]:
    # two by two once the card is a third of the page rather than two thirds
    st.markdown(theme.stat_card("Summary", _span, _stats, grid=bool(_chain)),
                unsafe_allow_html=True)

if _chain:
    with _cols[2]:
        st.markdown(theme.chain_card(*_chain), unsafe_allow_html=True)

if ins.masked:
    st.caption("Account names are masked for this role. Pseudonyms are stable, so "
               "attribution still works without revealing the customer.")

tabs = st.tabs(["Explanation", "Attribution", "Causal gates", "Evidence",
                "Actions", "Method and cost", "Contract", "Audit"])

# ------------------------------------------------------------------ narrative
with tabs[0]:
    st.markdown(f"#### {ins.persona}")
    st.markdown(f'<div class="fr-narrative">{emphasise(ins.narrative.text)}</div>',
                unsafe_allow_html=True)

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
        st.caption(
            "Read the right hand column. Every figure above was computed by one "
            "of these methods before the sentence was written, which is what lets "
            "us say the model is not the source of any number here — and mean it.")
        _facts = pd.DataFrame(ins.facts.lineage())
        _facts["fact"] = _facts["fact"].map(fact_label)
        st.dataframe(
            _facts, hide_index=True, width="stretch",
            # size to the content: an inner scrollbar on a short reference table
            # makes the reader hunt, and this already sits inside an expander
            height=(len(_facts) + 1) * 35 + 3,
            column_config={
                "fact": st.column_config.TextColumn(
                    "Fact", width="medium",
                    help="One quantity the narrative was permitted to state. If a "
                         "number is not on this list, the guard rejects the text "
                         "rather than letting it reach you."),
                "value": st.column_config.TextColumn(
                    "Value", width="small",
                    help="The figure as computed, in the unit the contract declares "
                         "for it. This is what the prose must match."),
                "produced_by": st.column_config.TextColumn(
                    "Produced by", width="large",
                    help="The method that produced the figure. Deterministic SQL, "
                         "arithmetic, a statistical test or the causal screen — "
                         "never generation. This column is the evidence for that "
                         "claim, and a gate fails the build if any row here ever "
                         "names a model."),
            })

# ----------------------------------------------------------------- attribution
with tabs[1]:
    st.markdown("#### Price, volume and mix")
    df = pvm.as_frame()
    # stack=False is load bearing: with one row per effect Vega still computes stack
    # offsets, which renders three separate contributions as one merged staircase
    # Step() sizes the band, not the whole plot. With a fixed total height the three
    # bands collapse to ~25px each and the bars touch, reading as one solid shape.
    chart = alt.Chart(df).mark_bar(size=22, cornerRadiusEnd=4).encode(
        y=alt.Y("effect:N", title=None, sort="-x"),
        x=alt.X("value:Q", title=f"contribution ({PVM_UNIT})", stack=False),
        # colour identifies the lever, not the sign: all three effects are
        # negative here, so a diverging encoding would paint them identically
        # and carry no information. Direction is already in the bar's geometry.
        color=alt.Color("effect:N", legend=None, scale=alt.Scale(
            domain=list(theme.LEVER_COLORS), range=list(theme.LEVER_COLORS.values()))),
        tooltip=[alt.Tooltip("effect:N"),
                 alt.Tooltip("value:Q", format=",.0f"),
                 alt.Tooltip("share_of_movement:Q", format="+.1%")],
    ).properties(height=alt.Step(46))
    st.altair_chart(chart, width="stretch")

    a, b = st.columns([2, 1])
    shown = df[["effect", "value", "share_of_movement"]].copy()
    shown["value"] = shown.value.map(lambda v: f"{v:,.0f}")
    shown["share_of_movement"] = shown.share_of_movement.map(lambda v: f"{v:+.1%}")
    a.dataframe(
        shown, hide_index=True, width="stretch",
        column_config={
            "effect": st.column_config.TextColumn(
                "Effect", width="small",
                help="The lever the movement is being restated in. Volume is the "
                     "change in units at last period's prices, price is the change "
                     "in realised price on this period's units, and mix is what "
                     "moved because demand shifted between product lines."),
            "value": st.column_config.TextColumn(
                f"Contribution ({PVM_UNIT})", width="small",
                help=f"How much of the movement this lever accounts for, in "
                     f"{PVM_UNIT}. This decomposition always splits revenue, so it "
                     f"is stated in {PVM_UNIT} even when the selected KPI is "
                     f"measured in something else."),
            "share_of_movement": st.column_config.TextColumn(
                "Share of movement", width="small",
                help="This lever as a proportion of the total movement, signed by "
                     "the direction it pushed. A negative share pushed the KPI "
                     "down; a lever that offset the movement would show positive. "
                     "The narrative quotes the same figures without the sign, "
                     "because that is how they are said aloud: volume at -72.8% "
                     "here is 'volume explains 73% of the drop' there. The three "
                     "shares sum to 100% because the decomposition is an identity, "
                     "not an estimate."),
        })
    a.caption("Shares are signed by direction: negative pushed the KPI down. The "
              "narrative states the same shares without the sign.")
    b.metric("Reconciliation residual", f"{abs(pvm.residual):.6f}",
             help="Contributions are an identity, not an approximation. This is "
                  "zero or the decomposition is not published.")
    if pvm.reconciled:
        b.success("Sums exactly to the movement")
    else:
        b.error("Does not reconcile, withheld")

    if result.by_account is not pvm:
        st.markdown("#### Largest contributors by account")

        # The table below says the same thing, but a reader has to compare nine
        # digit numbers across rows to see that one account carries most of the
        # movement. Length is the one encoding that needs no arithmetic.
        top = result.by_account.as_frame().head(5)
        # Contributions to a fall are negative, so the bars run left and their
        # labels have to sit on the left end. Decided here from the data rather
        # than in a Vega expression, because the whole frame shares a sign.
        _neg = bool((top.value <= 0).all())
        _bars = alt.Chart(top).mark_bar(size=18, cornerRadiusEnd=4).encode(
            y=alt.Y("effect:N", title=None, sort="x" if _neg else "-x"),
            x=alt.X("value:Q", title=f"contribution ({PVM_UNIT})"),
            # one measure, not several entities: magnitude is the whole job here,
            # so it is one hue. Colouring the biggest bar differently would tie
            # colour to rank, and the ranking already has the y axis.
            color=alt.value(theme.PURPLE_MID),
            tooltip=[alt.Tooltip("effect:N", title="account"),
                     alt.Tooltip("value:Q", format=",.0f"),
                     alt.Tooltip("share_of_movement:Q", format="+.1%")],
        )
        _labels = _bars.mark_text(
            align="right" if _neg else "left", dx=-6 if _neg else 6,
            fontWeight=600, color=theme.INK,
        ).encode(text=alt.Text("value:Q", format=",.0f"), color=alt.value(theme.INK))
        st.altair_chart((_bars + _labels).properties(height=alt.Step(34)),
                        width="stretch")

        acc = result.by_account.as_frame().head(6).copy()
        acc["driver"] = acc.driver.map(lambda d: str(d).replace("_", " ").title())
        acc["value"] = acc.value.map(lambda v: f"{v:,.0f}")
        acc["share_of_movement"] = acc.share_of_movement.map(lambda v: f"{v:+.1%}")
        st.dataframe(
            acc, hide_index=True, width="stretch",
            column_config={
                "effect": st.column_config.TextColumn(
                    "Account", width="medium",
                    help="The account this share of the movement sits with. Masked "
                         "to a stable pseudonym for roles that may not see customer "
                         "names, so the attribution still works without revealing "
                         "who it is."),
                "driver": st.column_config.TextColumn(
                    "Split by", width="small",
                    help="The dimension the movement was broken down across."),
                "value": st.column_config.TextColumn(
                    f"Contribution ({PVM_UNIT})", width="small",
                    help="How much of the movement came from this account. Where it "
                         "sits, which is a different question from why it happened."),
                "share_of_movement": st.column_config.TextColumn(
                    "Share of movement", width="small",
                    help="This account as a proportion of the total movement. A "
                         "large share names where to look; it is not on its own a "
                         "cause, which is what the causal gates are for."),
            })

# ---------------------------------------------------------------- causal gates
with tabs[2]:
    st.markdown("#### Three gates, all must pass before anything is called a cause")

    # Three gates times every declared driver is a wall of the words "pass" and
    # "fail", and this is the table a reader spends longest on. A dot in front
    # of each gives the column a shape, so a row that failed is visible before
    # it is read. The word stays beside it: the dot is a second channel, never
    # the only one.
    #
    # The dots are characters that carry their own colour rather than a pandas
    # Styler, because st.dataframe drops a Styler's font colour: measured in
    # 1.62 on a two-row frame, with and without column_config, every cell came
    # back at the default ink. CSS would not have reached them either, since
    # the grid is drawn on a canvas and has no cell to select.
    #
    # Blue for a gate that held, amber for one that did not. Same axis the theme
    # uses everywhere and for the same reason: red-green is the most common
    # colour vision deficiency, and this is the table where a reader must not
    # lose the answer.
    #
    # The three gate columns get dots and the verdict does not. The dots earn
    # their place where every cell reads "pass" or "fail" and the eye has
    # nothing to catch on; CAUSE and ASSOCIATION are already distinct words,
    # and a dot in front of them only costs the "why not" column the width it
    # needs to finish its sentence.
    _PASS, _FAIL = "\U0001F535", "\U0001F7E0"

    def _gate(ok: bool) -> str:
        return f"{_PASS} pass" if ok else f"{_FAIL} fail"

    rows = []
    for v in assess.verdicts:
        rows.append({
            # Same drivers appear as "Volume" in Attribution and the causal
            # chain card renders "delivery reliability" with a space. Printing
            # the raw contract key here made one concept look like three.
            "driver": v.driver.replace("_", " ").title(),
            "kind": v.kind,
            "share of movement": f"{v.share:.0%}" if v.kind == "arithmetic"
                                 else f"{v.strength:.1f}x rate",
            "sequence": _gate(v.sequence_ok),
            "magnitude": _gate(v.magnitude_ok),
            "mechanism": _gate(v.mechanism_ok),
            "verdict": v.status.upper(),
            "why not": "; ".join(v.reasons) or "-",
        })
    _gate_help = ("Deterministic rule over dates and numbers. No judgement, and "
                  "nothing a model can talk its way past.")
    st.dataframe(
        pd.DataFrame(rows), hide_index=True, width="stretch",
        column_config={
            "driver": st.column_config.TextColumn(
                # no width hint: a fixed small column cut "delivery_reliability"
                # and a medium one stole the width "why not" needs to finish its
                # sentence. Letting the grid size this column to its own content
                # is the only setting that fits both.
                "Driver",
                help="The candidate explanation being tested. Every declared driver "
                     "of this KPI is screened, not only the ones that look good."),
            "kind": st.column_config.TextColumn(
                "Kind", width="small",
                help="Arithmetic drivers fall out of the decomposition: they are the "
                     "movement restated, so the arithmetic is their mechanism. "
                     "Evidential drivers are candidate root causes upstream of it, "
                     "which never appear in the decomposition and must instead be "
                     "dated and corroborated from text."),
            "share of movement": st.column_config.TextColumn(
                "Weight", width="small",
                help="For an arithmetic driver, the share of the movement it "
                     "accounts for. For an evidential driver, how much more often "
                     "its events occur now than before its own change point."),
            "sequence": st.column_config.TextColumn(
                "Sequence", width="small",
                help="Is the candidate cause observable BEFORE the movement began? "
                     "A cause cannot follow its effect. " + _gate_help),
            "magnitude": st.column_config.TextColumn(
                "Magnitude", width="small",
                help="Is it big enough to matter? Arithmetic drivers must clear the "
                     "contribution share the contract sets; evidential drivers must "
                     "clear a rate multiple against their own baseline. "
                     + _gate_help),
            "mechanism": st.column_config.TextColumn(
                "Mechanism", width="small",
                help="Is there a route from cause to effect? It must be a declared "
                     "driver of this KPI, and something has to corroborate it. "
                     + _gate_help),
            "verdict": st.column_config.TextColumn(
                # auto-sized for the same reason as Driver: "ASSOCIATION" is one
                # character wider than a small column
                "Verdict",
                help="CAUSE only when all three gates pass. Anything less is "
                     "reported as an ASSOCIATION — a large contribution tells you "
                     "where a movement sits, never why it happened."),
            "why not": st.column_config.TextColumn(
                "Why not", width="large",
                help="Which gate failed, and by how much against which threshold. "
                     "Stated so you can disagree with the call rather than having "
                     "to take it on trust."),
        })
    st.caption("Arithmetic drivers come from the decomposition and are the movement "
               "restated. Evidential drivers sit upstream and must be dated and "
               "corroborated. Screening them the same way would be a category error.")

# -------------------------------------------------------------------- evidence
with tabs[3]:
    if not result.evidence:
        st.info("No supporting passages retrieved for this slice.")
    for p in result.evidence:
        st.markdown(f"> {p.text}")
        # provenance() returns the contract's own field names, which is right
        # for the audit record and wrong on screen: this tab is read by a sales
        # director, not by whoever wrote the schema. Relabel at the display
        # layer only, so the audit JSON keeps its stable keys.
        _PROV_LABELS = {
            "event_id": "Event", "source": "Source", "date": "Dated",
            "age_days": "Age (days)", "source_lag_hours": "Source lag (hours)",
            "retrieval_method": "Retrieved by", "relevance_score": "Relevance",
        }
        _prov = p.provenance()
        st.caption(" · ".join(
            f"{_PROV_LABELS.get(k, k.replace('_', ' ').capitalize())}: "
            f"{v.upper() if k == 'retrieval_method' else v}"
            for k, v in _prov.items()))
        st.divider()
    st.markdown("#### Source freshness at the moment this ran")
    # A CheckboxColumn renders False as an empty, clickable-looking box, which
    # reads as "no data" rather than "not stale" -- the wrong answer to the
    # only question this column is asked. Say it in words instead.
    _fresh = pd.DataFrame(result.freshness)
    if "stale" in _fresh.columns:
        _fresh["stale"] = _fresh.stale.map(lambda v: "Stale" if v else "Fresh")
    st.dataframe(
        _fresh, hide_index=True, width="stretch",
        column_config={
            "source": st.column_config.TextColumn(
                "Source", width="medium",
                help="The system these rows came from. Declared in the contract, "
                     "not discovered at run time."),
            "cadence": st.column_config.TextColumn(
                "Refresh cadence", width="small",
                help="How often that system publishes new data. The three sources "
                     "are deliberately mismatched — daily, weekly and continuous — "
                     "because reconciling that is the hard part of the problem."),
            "lag_hours": st.column_config.NumberColumn(
                "Expected lag (hours)", width="small",
                help="How far behind reality this source is expected to run. "
                     "Marketing spend lags sales by up to three days, which is why "
                     "a movement cannot be attributed to spend that has not landed."),
            "stale": st.column_config.TextColumn(
                "Freshness", width="small",
                help="True when the lag exceeds the staleness warning the contract "
                     "sets for this source. A stale source is a stated reason to "
                     "abstain rather than something the engine works around."),
            "grain": st.column_config.TextColumn(
                "Grain", width="small",
                help="What one row represents: an order line, a campaign week, a "
                     "single event. Two sources at different grains cannot be "
                     "joined without aggregating the finer one upward first."),
        })

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
            # A transposed frame left the value column with a blank header and
            # raw schema keys down the side. Field/value carries the same content
            # and can be labelled.
            # Values as well as field names: driver and lever are contract keys
            # ("delivery_reliability", "account_management") and the rest of the
            # app now renders them as words. Printing the raw key here made the
            # same driver look like a different thing from tab to tab.
            _KEYED = {"driver", "controllable_lever", "lever"}
            # "action" is the bold heading directly above this table, so the
            # row repeated it -- and being the longest value, it was the one
            # Streamlit truncated mid-word. Dropping it removes the duplicate
            # and the clipping in one go; the sentence is still shown in full.
            _rows = pd.DataFrame(
                [{"field": ACTION_FIELD_LABELS.get(k, fact_label(k)),
                  "value": (str(v).replace("_", " ").title()
                            if k in _KEYED else v)}
                 for k, v in a.as_dict().items() if k != "action"])
            st.dataframe(
                _rows, hide_index=True, width="stretch",
                height=(len(_rows) + 1) * 35 + 3,
                column_config={
                    "field": st.column_config.TextColumn(
                        "Field", width="small",
                        help="The action schema the brief specifies. All seven "
                             "fields must be filled: the engine raises rather than "
                             "publish a recommendation missing any of them."),
                    # the action and monitoring plan are full sentences and were
                    # being truncated mid-word at the column edge
                    "value": st.column_config.TextColumn("Value", width="large"),
                    "value": st.column_config.TextColumn(
                        "Value", width="large",
                        help="Filled from the contract and the computed facts, "
                             "never free text. An action is only offered where the "
                             "driver is marked controllable and this role holds the "
                             "decision right that lever requires."),
                })
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
        # driver_priors() returns a dict, and printing it put Python syntax on
        # screen. Same content, said in words.
        _priors = engine.store.driver_priors(movement.kpi)
        _priors_txt = (", ".join(f"{k.replace('_', ' ')} {v:.2f}"
                                 for k, v in _priors.items())
                       if _priors else "neutral")
        st.success(
            f"Recorded '{fb.replace('_', ' ')}'. Driver priors are now "
            f"{_priors_txt}, and the materiality threshold for this slice is "
            f"multiplied by "
            f"{engine.store.materiality_nudge(movement.kpi, movement.slice_label):.4g}.")
        # summary() counts corrections by their stored kind, which are the
        # enum names ("not_material"). The success line above already says
        # "not material"; two spellings of one word three lines apart reads
        # as two different things.
        st.caption(engine.store.summary(movement.kpi).replace("_", " "))

# -------------------------------------------------------------- method & cost
with tabs[5]:
    st.markdown("#### Where the work actually happened")
    split = pd.DataFrame([
        {"method": k, "stages": v["stages"], "ms": v["ms"],
         "model calls": v["calls"], "share of latency": v["share_of_latency"]}
        for k, v in run.method_split().items()
    ]).sort_values("ms", ascending=False)

    ch = alt.Chart(split).mark_bar(cornerRadiusEnd=4).encode(
        y=alt.Y("method:N", sort="-x", title=None),
        x=alt.X("ms:Q", title="milliseconds"),
        # keyed on the method name, so sorting the bars by latency can never
        # repaint them: colour follows the entity, never its rank
        color=alt.Color("method:N", legend=None, scale=alt.Scale(
            domain=list(theme.METHOD_COLORS), range=list(theme.METHOD_COLORS.values()))),
        tooltip=list(split.columns),
    ).properties(height=alt.Step(34))
    st.altair_chart(ch, width="stretch")
    split_show = split.copy()
    split_show["share of latency"] = split_show["share of latency"].map(
        lambda v: f"{v:.1%}")
    st.dataframe(
        split_show, hide_index=True, width="stretch",
        column_config={
            "method": st.column_config.TextColumn(
                "Method", width="medium",
                help="How the work was done. The vocabulary is fixed — sql, "
                     "deterministic_logic, business_rules, statistics, "
                     "traditional_ml, causal_inference, retrieval, llm — and a "
                     "stage declaring anything outside it is rejected outright."),
            "stages": st.column_config.NumberColumn(
                "Stages", width="small",
                help="How many pipeline stages declared this method. The split is "
                     "derived from that instrumentation, not written by hand."),
            "ms": st.column_config.NumberColumn(
                "Milliseconds", width="small",
                help="Wall clock time those stages took, measured on this run."),
            "model calls": st.column_config.NumberColumn(
                "Model calls", width="small",
                help="Model calls issued from stages of this method. Any non-zero "
                     "count on a row other than 'llm' fails the run at runtime — "
                     "that check is what makes the deterministic claim enforceable "
                     "rather than merely asserted."),
            "share of latency": st.column_config.TextColumn(
                "Share of latency", width="small",
                help="This method's portion of end to end time, which is how you "
                     "see at a glance how little of the answer generation touched."),
        })

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
