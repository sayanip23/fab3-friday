"""
Bring your own data.

Upload a CSV and the engine analyses it with the same pipeline the demo uses:
profile the file, synthesise a contract, then run detection, attribution,
causal screening and abstention against it.

The page is deliberately blunt about what it cannot do. A tool that quietly
downgrades its analysis and says nothing is worse than one that refuses.
"""
from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from friday import byod, theme

st.set_page_config(page_title="FRIDAY · Your data", page_icon="F", layout="wide")
theme.apply()

st.title("Bring your own data")
st.caption(
    "Upload a CSV. The engine profiles it, writes a contract for it, and runs "
    "the identical pipeline it runs on the demo dataset."
)

# ─────────────────────────────────────────────────────────────── sample file
SAMPLE = pd.DataFrame({
    "booking_date": pd.date_range("2026-01-01", periods=120).astype(str).repeat(2),
    "clinic_site": ["Andheri", "Bandra"] * 120,
    "service_line": ["Dental", "Physio"] * 120,
    "appointments": [34, 28] * 120,
})

with st.expander("What the file needs"):
    st.markdown(
        """
        **Required**
        - one **date** column (any common format)
        - at least one **numeric** column to track

        **Strongly recommended**
        - one or more **categorical** columns (region, product, branch), so the
          engine can say *which segment* moved rather than only *that something* did
        - **at least 84 days** of history, so there are two equal periods plus a
          baseline to judge them against

        **What will not work on an upload**
        - *Price, volume and mix* needs a unit-count column **and** a unit-price
          column. Without both, you get contribution by segment instead.
        - *Root causes* need a free-text source (tickets, notes). Without one the
          engine reports associations and refuses to name a cause. That refusal
          is deliberate.
        """
    )
    st.download_button(
        "Download a sample CSV",
        SAMPLE.to_csv(index=False).encode(),
        file_name="friday_sample.csv",
        mime="text/csv",
    )

uploaded = st.file_uploader("CSV file", type=["csv"], label_visibility="collapsed")

if uploaded is None:
    st.info("Upload a CSV above to begin.")
    st.stop()

# ─────────────────────────────────────────────────────────────────── read it
try:
    raw = pd.read_csv(io.BytesIO(uploaded.getvalue()))
except Exception as exc:                                   # noqa: BLE001
    st.error(f"Could not read that file: {type(exc).__name__}: {exc}")
    st.stop()

st.success(f"Read **{len(raw):,} rows** and **{len(raw.columns)} columns** from `{uploaded.name}`.")
with st.expander("Preview the first rows"):
    st.dataframe(raw.head(12), width="stretch")

window = st.slider(
    "Comparison window (days)", 7, 90, 28, step=7,
    help="Two equal, adjacent windows ending at the last date in your file.",
)

with st.spinner("Profiling and analysing…"):
    analysis = byod.analyse(raw, window=window)

# ────────────────────────────────────────────────────────────── refusals
if analysis.errors and not analysis.findings:
    st.error("### The engine refused this file")
    for e in analysis.errors:
        st.markdown(f"- {e}")
    st.caption("Refusing is the correct behaviour here. Guessing would not be.")
    st.stop()

p = analysis.profile

# ─────────────────────────────────────────────────────────── what it found
st.markdown("### What the engine found in your file")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Rows", f"{p.rows:,}")
c2.metric("Date column", p.date_column or "none")
c3.metric("Measures", len(p.measures))
c4.metric("Dimensions", len(p.dimensions))

a, b = st.columns(2)
a.markdown("**Tracking these measures**")
a.write(", ".join(f"`{m}`" for m in p.measures) or "none")
b.markdown("**Splitting by these dimensions**")
b.write(", ".join(f"`{d}`" for d in p.dimensions) or "none found")

st.caption(
    f"History: {p.date_min} to {p.date_max} ({p.span_days} days) · "
    f"comparing {analysis.period} against {analysis.prior}"
)

for w in p.warnings:
    st.warning(w)

if not p.supports_pvm:
    st.info(
        "**Price, volume and mix is unavailable for this file.** It needs a "
        "unit-count column and a unit-price column. Contribution by segment is "
        "shown instead."
    )

st.divider()

# ───────────────────────────────────────────────────────────────── findings
material = analysis.material
if not material:
    st.markdown("### No material movement found")
    st.info(
        "Every measure stayed inside its own normal range for this window. "
        "**This is a result, not a failure** — a system that always finds "
        "something is a system nobody can trust."
    )
    with st.expander("See what was checked anyway"):
        st.dataframe(pd.DataFrame([{
            "measure": f.label,
            "change": f"{f.movement.pct:+.1f}%",
            "signal": f"{f.movement.z_score:.2f} sigma",
            "material": f.movement.material,
        } for f in analysis.findings]), hide_index=True, width="stretch")
    st.stop()

st.markdown(f"### {len(material)} material movement(s)")

for f in material:
    with st.container(border=True):
        st.markdown(f"#### {f.label}")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Current", f"{f.movement.current:,.2f}", f"{f.movement.pct:+.1f}%")
        m2.metric("Prior period", f"{f.movement.prior:,.2f}")
        m3.metric("Signal strength", f"{f.movement.z_score:.2f} sigma")
        m4.metric("Confidence", f.assessment.confidence.upper(),
                  delta="abstained" if f.assessment.abstain else None,
                  delta_color="inverse" if f.assessment.abstain else "off")

        if f.insight is not None:
            st.write(f.insight.narrative.text)

        if f.contribution and f.contribution.effects:
            st.markdown(f"**Where it sits, by `{f.dimension}`**")
            frame = f.contribution.as_frame()
            shown = frame[["effect", "value", "share_of_movement"]].copy()
            shown["value"] = shown.value.map(lambda v: f"{v:,.2f}")
            shown["share_of_movement"] = shown.share_of_movement.map(lambda v: f"{v:+.1%}")
            shown.columns = ["segment", "contribution", "share of movement"]

            cc1, cc2 = st.columns([3, 1])
            cc1.dataframe(shown, hide_index=True, width="stretch")
            cc2.metric("Reconciliation residual", f"{abs(f.contribution.residual):.6f}")
            if f.contribution.reconciled:
                cc2.success("Sums exactly to the movement")
            else:
                cc2.error("Does not reconcile, withheld")

        if f.assessment.abstain:
            st.warning("**No cause asserted.** " + "; ".join(f.assessment.abstain_reasons))

        for n in f.notes:
            st.caption(n)

        st.caption(f"`{f.run.insight_id}` · {f.run.footer()}")

if analysis.errors:
    with st.expander(f"{len(analysis.errors)} column(s) could not be analysed"):
        for e in analysis.errors:
            st.markdown(f"- `{e}`")
