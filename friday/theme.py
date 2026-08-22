"""
Presentation layer only. No engine logic lives here.

Derived from the ui-ux-pro-max "Data-Dense Dashboard" profile, with the palette
kept on Accenture purple for brand continuity with the deck. Tokens are declared
in three layers as the profile specifies: primitive values, semantic roles, then
component usage. Nothing outside this file hardcodes a colour.

Accessibility is treated as priority 1 and 2 from the skill's rule table, so the
non-negotiables here are 4.5:1 body contrast, a visible focus ring on every
interactive control, 44px touch targets, and a reduced-motion escape hatch.
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------- primitives
PURPLE = "#A000FF"
PURPLE_DEEP = "#450073"
PURPLE_MID = "#7400C0"
LILAC = "#C1A3FF"
WASH = "#F7F4FC"
AMBER = "#D97706"          # accent, from the recommended profile
GREEN = "#1E8449"
RED = "#C0392B"
INK = "#1A1A1A"
MUTED = "#5A5A5A"
BORDER = "#E6DCF5"

# density 8/10 -> 8-32px scale, per the design dials
CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600&family=Fira+Sans:wght@300;400;500;600;700&display=swap');

:root {{
  --c-primary: {PURPLE};
  --c-primary-deep: {PURPLE_DEEP};
  --c-primary-mid: {PURPLE_MID};
  --c-accent: {AMBER};
  --c-ok: {GREEN};
  --c-bad: {RED};
  --c-ink: {INK};
  --c-muted: {MUTED};
  --c-border: {BORDER};
  --c-wash: {WASH};

  --space-1: 8px;  --space-2: 12px; --space-3: 16px;
  --space-4: 20px; --space-5: 24px; --space-6: 32px;

  --radius: 8px;
  --t-fast: 150ms;
  --t-base: 220ms;
  --ease: cubic-bezier(.4,0,.2,1);
}}

/* Deliberately narrow. A blanket [class*="st-"], span, div rule also captures
   Streamlit's Material Symbols spans, and the icon ligature then renders as the
   literal string "keyboard_arrow_right" instead of a glyph. */
html, body, .stMarkdown, p, li, h1, h2, h3, h4, h5, h6,
[data-testid="stMetricLabel"], [data-testid="stMarkdownContainer"],
[data-testid="stCaptionContainer"], .stButton button,
[data-testid="stTabs"] [role="tab"] {{
  font-family: 'Fira Sans', -apple-system, 'Segoe UI', sans-serif;
}}
code, pre, [data-testid="stJson"] {{ font-family: 'Fira Code', monospace; }}

/* belt and braces: never let the icon font be overridden */
[data-testid="stIconMaterial"], .material-icons, .material-symbols-rounded {{
  font-family: 'Material Symbols Rounded' !important;
}}

/* ---- headings ------------------------------------------------------- */
h1, h2, h3 {{ font-family: 'Fira Sans', sans-serif; letter-spacing: -.015em; }}
[data-testid="stMain"] h3 {{
  color: var(--c-primary-deep);
  font-weight: 600;
  border-bottom: 1px solid var(--c-border);
  padding-bottom: var(--space-2);
  margin-bottom: var(--space-4);
}}
[data-testid="stMain"] h4 {{
  color: var(--c-primary-mid); font-weight: 600; font-size: 1.02rem;
  margin-top: var(--space-2);
}}

/* ---- metric cards ---------------------------------------------------- */
[data-testid="stMetric"] {{
  background: var(--c-wash);
  border: 1px solid var(--c-border);
  border-radius: var(--radius);
  padding: var(--space-3) var(--space-4);
  transition: border-color var(--t-base) var(--ease),
              transform var(--t-base) var(--ease);
}}
[data-testid="stMetric"]:hover {{
  border-color: var(--c-primary);
  transform: translateY(-1px);
}}
[data-testid="stMetricLabel"] p {{
  font-size: .74rem !important;
  text-transform: uppercase;
  letter-spacing: .07em;
  color: var(--c-muted) !important;
  font-weight: 600;
}}
[data-testid="stMetricValue"] {{
  font-family: 'Fira Code', monospace !important;
  color: var(--c-primary-deep) !important;
  font-size: 1.7rem !important;
  font-weight: 600 !important;
}}

/* ---- tabs ------------------------------------------------------------ */
[data-testid="stTabs"] [role="tablist"] {{
  gap: 2px; border-bottom: 1px solid var(--c-border);
}}
[data-testid="stTabs"] [role="tab"] {{
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius) var(--radius) 0 0;
  font-size: .9rem; font-weight: 500; color: var(--c-muted);
  transition: background var(--t-fast) var(--ease), color var(--t-fast) var(--ease);
  min-height: 44px;                      /* touch target, priority 2 */
}}
[data-testid="stTabs"] [role="tab"]:hover {{
  background: var(--c-wash); color: var(--c-primary-deep);
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
  color: var(--c-primary); font-weight: 600; background: var(--c-wash);
}}

/* ---- tables: row highlighting on hover, a key effect in the profile --- */
[data-testid="stDataFrame"] {{
  border: 1px solid var(--c-border); border-radius: var(--radius); overflow: hidden;
}}
[data-testid="stDataFrame"] [role="row"]:hover {{ background: var(--c-wash) !important; }}

/* ---- sidebar --------------------------------------------------------- */
[data-testid="stSidebar"] {{
  background: var(--c-wash); border-right: 1px solid var(--c-border);
}}
[data-testid="stSidebar"] h1 {{
  font-size: 1.5rem; font-weight: 700; color: var(--c-primary-deep);
  letter-spacing: -.02em;
}}
[data-testid="stSidebar"] [role="radiogroup"] label {{
  padding: var(--space-1) var(--space-2); border-radius: 6px;
  transition: background var(--t-fast) var(--ease);
}}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {{ background: #EFE7FA; }}

/* ---- alerts ---------------------------------------------------------- */
[data-testid="stAlert"] {{ border-radius: var(--radius); border-left-width: 3px; }}

/* ---- expander -------------------------------------------------------- */
[data-testid="stExpander"] details {{
  border: 1px solid var(--c-border); border-radius: var(--radius);
}}
[data-testid="stExpander"] summary:hover {{ color: var(--c-primary); }}

/* ---- buttons: cursor + real hover, from the pre-delivery checklist ---- */
.stButton button {{
  border-radius: var(--radius); font-weight: 500; min-height: 44px;
  transition: all var(--t-fast) var(--ease); cursor: pointer;
}}
.stButton button:hover {{
  border-color: var(--c-primary); color: var(--c-primary);
  transform: translateY(-1px);
}}

/* ---- accessibility priority 1: focus must always be visible ---------- */
*:focus-visible {{
  outline: 2px solid var(--c-primary) !important;
  outline-offset: 2px !important;
  border-radius: 4px;
}}

/* ---- reduced motion -------------------------------------------------- */
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation-duration: .01ms !important;
    transition-duration: .01ms !important;
    scroll-behavior: auto !important;
  }}
  [data-testid="stMetric"]:hover, .stButton button:hover {{ transform: none; }}
}}

/* ---- FRIDAY specific components -------------------------------------- */
.fr-pill {{
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: .72rem; font-weight: 600; letter-spacing: .05em;
  text-transform: uppercase; font-family: 'Fira Sans', sans-serif;
}}
.fr-pill-high {{ background: #E6F4EA; color: {GREEN}; border: 1px solid #A8D5B5; }}
.fr-pill-medium {{ background: #FEF3E2; color: {AMBER}; border: 1px solid #F3C98B; }}
.fr-pill-low {{ background: #FEF3E2; color: {AMBER}; border: 1px solid #F3C98B; }}
.fr-pill-none {{ background: #FDECEA; color: {RED}; border: 1px solid #F0B7B2; }}
.fr-pill-pass {{ background: #E6F4EA; color: {GREEN}; border: 1px solid #A8D5B5; }}
.fr-pill-fail {{ background: #F2F2F2; color: {MUTED}; border: 1px solid #DDD; }}

.fr-chain {{
  display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap;
  background: var(--c-wash); border: 1px solid var(--c-border);
  border-radius: var(--radius); padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-4);
}}
.fr-chain-node {{
  font-family: 'Fira Code', monospace; font-size: .82rem; font-weight: 500;
  color: var(--c-primary-deep); background: #fff;
  border: 1px solid var(--c-border); border-radius: 6px;
  padding: 5px 10px;
}}
.fr-chain-arrow {{ color: var(--c-primary); font-weight: 700; }}
.fr-chain-label {{
  font-size: .72rem; text-transform: uppercase; letter-spacing: .07em;
  color: var(--c-muted); font-weight: 600; margin-right: var(--space-1);
}}

.fr-foot {{
  font-family: 'Fira Code', monospace; font-size: .74rem;
  color: var(--c-muted); border-top: 1px solid var(--c-border);
  padding-top: var(--space-2); margin-top: var(--space-4);
}}
</style>
"""


def apply() -> None:
    """Inject the stylesheet. Call once, immediately after set_page_config."""
    st.markdown(CSS, unsafe_allow_html=True)


def pill(text: str, kind: str) -> str:
    """
    Status pill. `kind` is a semantic role, never a colour, so the palette can
    change in one place without touching call sites.
    """
    return f'<span class="fr-pill fr-pill-{kind}">{text}</span>'


def chain(label: str, nodes: list[str]) -> str:
    """The causal chain as a scannable strip: root cause -> lever -> KPI."""
    inner = f' <span class="fr-chain-arrow">&rsaquo;</span> '.join(
        f'<span class="fr-chain-node">{n}</span>' for n in nodes)
    return (f'<div class="fr-chain"><span class="fr-chain-label">{label}</span>'
            f'{inner}</div>')
