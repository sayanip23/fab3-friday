"""
Presentation layer only. No engine logic lives here.

Accenture brand alignment: primary purple is #A100FF, the exact, documented
Accenture brand purple used in the official Round 1 template (verified
against Accenture's own PPTX — not an approximation; the prior value here,
#A000FF, was a one-digit typo off-brand). Typography uses Arial, per the
official template's own stated rule ("use standard Arial font"), so the
app and the deck are visually one submission, not two. Numbers use a
monospace system stack so figures align in columns without depending on a
Google Fonts CDN call the demo can't afford to fail on.

Tokens are declared in three layers: primitive values, semantic roles, then
component usage. Nothing outside this file hardcodes a colour.

Accessibility is treated as priority 1 and 2 from the skill's rule table, so
the non-negotiables here are 4.5:1 body contrast, a visible focus ring on
every interactive control, 44px touch targets, and a reduced-motion escape
hatch.
"""
from __future__ import annotations

import streamlit as st

# ---------------------------------------------------------------- primitives
# #A100FF is Accenture's documented brand purple (PMS 7442 C) — the exact
# value used in the official Round 1 PPTX template, not a rounded guess.
PURPLE = "#A100FF"
PURPLE_DEEP = "#3D0066"
PURPLE_MID = "#7500C0"
LILAC = "#C1A3FF"
WASH = "#F7F2FF"
BLACK = "#000000"          # Accenture's brand palette is purple/black/white.
WHITE = "#FFFFFF"
SIDE_BG = "#F1E7FE"        # sidebar: a light purple wash, one step deeper than
SIDE_HOVER = "#E3D2FB"     # the main-content wash so the rail still separates.
# Status colours use the blue / orange / neutral axis rather than red / green.
# Red-green is invisible to roughly 1 in 12 men (deuteran and protan CVD), and
# a judge or a CFO who cannot tell "cause established" from "no cause" is the
# whole product failing. Blue and orange stay distinguishable under every
# common CVD type, and the neutral is far enough apart in luminance to survive
# full monochromacy. Values are darkened from the Okabe-Ito safe palette so
# every one clears 4.5:1 as text on its own pill.
OK = "#0072B2"             # Okabe-Ito blue   - established / pass / high
CAUTION = "#9E5C00"        # dark amber       - medium / low confidence
NEUTRAL = "#3A3A3A"        # dark neutral     - abstained / refused / fail

# Chart fills are a separate token from text colours on purpose. Text needs
# 4.5:1 so it has to be dark, and a dark orange starts to read as red, which
# defeats the point. A large filled bar only needs 3:1, so it can sit at a
# brighter, unmistakably amber value that no one will mistake for red.
CHART_UP = "#0072B2"
CHART_DOWN = "#CC7A00"

# Legacy aliases: some call sites still import these names.
AMBER = CAUTION
GREEN = OK
RED = CAUTION
INK = "#141414"
MUTED = "#5A5A5A"
BORDER = "#E4D9F7"
HEAD_BG = "#E3D0FA"        # headline chips: a step darker than the page wash
HEAD_BORDER = "#C39BF0"    # so the three facts read as objects, not as text

FONT_SANS = "Arial, 'Helvetica Neue', Helvetica, sans-serif"
FONT_MONO = "Consolas, 'Courier New', ui-monospace, monospace"

# density 8/10 -> 8-32px scale, per the design dials
CSS = f"""
<style>
:root {{
  --c-primary: {PURPLE};
  --c-primary-deep: {PURPLE_DEEP};
  --c-primary-mid: {PURPLE_MID};
  --c-black: {BLACK};
  --c-white: {WHITE};
  --c-ok: {OK};
  --c-caution: {CAUTION};
  --c-neutral: {NEUTRAL};
  --c-accent: {CAUTION};
  --c-ink: {INK};
  --c-muted: {MUTED};
  --c-border: {BORDER};
  --c-wash: {WASH};
  --c-side-bg: {SIDE_BG};
  --c-side-hover: {SIDE_HOVER};

  --space-1: 8px;  --space-2: 12px; --space-3: 16px;
  --space-4: 20px; --space-5: 24px; --space-6: 32px;

  --radius: 8px;
  --t-fast: 150ms;
  --t-base: 220ms;
  --ease: cubic-bezier(.4,0,.2,1);
}}

/* ---- hide Streamlit's own chrome: this is an internal tool, not a --------
   Streamlit Cloud demo, so the hamburger menu, Deploy button and "Made
   with Streamlit" footer read as unfinished rather than as a product. The
   header bar itself stays (it still hosts the sidebar-collapse control). */
#MainMenu {{ visibility: hidden; }}
footer {{ visibility: hidden; }}
[data-testid="stToolbar"] {{ visibility: hidden; }}
[data-testid="stDecoration"] {{ display: none; }}
[data-testid="stHeader"] {{ background: transparent; }}

/* The control that re-opens a collapsed sidebar lives in the header. Hiding
   the toolbar must never take it with it, or the sidebar becomes a one-way
   door. Force it visible and give it brand styling so it reads as a button. */
[data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"] {{
  visibility: visible !important;
  opacity: 1 !important;
  display: flex !important;
  z-index: 1000;
}}
[data-testid="stSidebarCollapsedControl"] button,
[data-testid="stExpandSidebarButton"] {{
  background: var(--c-primary) !important;
  border: 1px solid var(--c-primary) !important;
  border-radius: 6px !important;
  box-shadow: 0 2px 10px rgba(0,0,0,.22);
}}
[data-testid="stSidebarCollapsedControl"] button *,
[data-testid="stExpandSidebarButton"] * {{
  color: var(--c-white) !important;
  fill: var(--c-white) !important;
}}

/* ---- page rhythm: Streamlit ships ~6rem of dead space above the first
   heading. Pull it in, but leave enough room for the re-open control. */
[data-testid="stMainBlockContainer"], .block-container {{
  padding-top: 2.6rem !important;
}}

/* Deliberately narrow. A blanket [class*="st-"], span, div rule also captures
   Streamlit's Material Symbols spans, and the icon ligature then renders as the
   literal string "keyboard_arrow_right" instead of a glyph. */
html, body, .stMarkdown, p, li, h1, h2, h3, h4, h5, h6,
[data-testid="stMetricLabel"], [data-testid="stMarkdownContainer"],
[data-testid="stCaptionContainer"], .stButton button,
[data-testid="stTabs"] [role="tab"] {{
  font-family: {FONT_SANS};
}}
code, pre, [data-testid="stJson"] {{ font-family: {FONT_MONO}; }}

/* belt and braces: never let the icon font be overridden */
[data-testid="stIconMaterial"], .material-icons, .material-symbols-rounded {{
  font-family: 'Material Symbols Rounded' !important;
}}

/* ---- headings ------------------------------------------------------- */
h1, h2, h3 {{ font-family: {FONT_SANS}; letter-spacing: -.01em; }}
/* The headline is the single most important line on the page, so it gets
   treated as a banner rather than as text with a rule under it, and real
   space beneath so it does not crowd the KPI row. */
[data-testid="stMain"] h3 {{
  color: var(--c-primary-deep);
  font-weight: 700;
  font-size: 1.5rem;
  background: var(--c-wash);
  border: 1px solid var(--c-border);
  border-left: 5px solid var(--c-primary);
  border-radius: var(--radius);
  padding: var(--space-4) var(--space-5);
  margin: 0 0 var(--space-6) 0;
}}
[data-testid="stMain"] h4 {{
  color: var(--c-primary-mid); font-weight: 700; font-size: 1.02rem;
  margin-top: var(--space-2);
}}

/* ---- metric cards ---------------------------------------------------- */
/* Columns stretch, cards fill them. Without this the card shrink-wraps its
   text, so four KPIs render as four different-sized boxes. */
[data-testid="stHorizontalBlock"] {{ align-items: stretch; }}
[data-testid="stColumn"] {{ display: flex; flex-direction: column; }}
/* the height has to be handed down through every wrapper Streamlit inserts,
   or the card shrink-wraps its own text again */
[data-testid="stColumn"] > div,
[data-testid="stColumn"] [data-testid="stVerticalBlockBorderWrapper"],
[data-testid="stColumn"] [data-testid="stVerticalBlock"],
[data-testid="stColumn"] [data-testid="stElementContainer"] {{
  width: 100%;
  height: 100%;
}}
[data-testid="stMetric"] {{
  width: 100%;
  height: 100%;
  min-height: 118px;                     /* tallest card sets the floor */
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  /* top-aligned, NOT centred: a card with no delta row would otherwise sit
     its label lower than its neighbours' */
  justify-content: flex-start;
  gap: 2px;
  background: var(--c-wash);
  border: 1px solid var(--c-border);
  border-top: 3px solid var(--c-primary);
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
  font-weight: 700;
}}
[data-testid="stMetricValue"] {{
  font-family: {FONT_MONO} !important;
  color: var(--c-black) !important;
  font-size: 1.7rem !important;
  font-weight: 700 !important;
}}

/* ---- tabs ------------------------------------------------------------ */
[data-testid="stTabs"] [role="tablist"] {{
  gap: 2px; border-bottom: 1px solid var(--c-border);
}}
[data-testid="stTabs"] [role="tab"] {{
  padding: var(--space-2) var(--space-4);
  /* a light outline on every tab, so the unselected ones read as targets
     you can click rather than as loose text next to a purple block */
  border: 1px solid var(--c-border);
  border-bottom: none;
  background: var(--c-white);
  border-radius: var(--radius) var(--radius) 0 0;
  font-size: .9rem; font-weight: 600; color: var(--c-muted);
  transition: background var(--t-fast) var(--ease),
              color var(--t-fast) var(--ease),
              border-color var(--t-fast) var(--ease);
  min-height: 44px;                      /* touch target, priority 2 */
}}
[data-testid="stTabs"] [role="tab"]:hover {{
  background: var(--c-wash); color: var(--c-primary-deep);
  border-color: {HEAD_BORDER};
}}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
  color: var(--c-white); font-weight: 700;
  background: var(--c-primary); border-color: var(--c-primary);
}}

/* ---- tables: row highlighting on hover, a key effect in the profile --- */
[data-testid="stDataFrame"] {{
  border: 1px solid var(--c-border); border-radius: var(--radius); overflow: hidden;
}}
[data-testid="stDataFrame"] [role="row"]:hover {{ background: var(--c-wash) !important; }}

/* ---- sidebar --------------------------------------------------------- */
/* Light purple rail rather than a black one: black next to a white canvas
   reads as two separate applications bolted together. */
[data-testid="stSidebar"] {{
  background: var(--c-side-bg);
  border-right: 1px solid var(--c-border);
}}
[data-testid="stSidebar"] * {{ color: var(--c-ink); }}
[data-testid="stSidebar"] h1 {{
  font-size: 1.6rem; font-weight: 700; color: var(--c-primary-deep) !important;
  letter-spacing: -.01em; display: flex; align-items: center; gap: 6px;
}}
[data-testid="stSidebar"] h1::before {{
  content: '>'; color: var(--c-primary); font-weight: 900;
}}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
  color: var(--c-primary-mid) !important;
}}
[data-testid="stSidebar"] [role="radiogroup"] label {{
  padding: var(--space-1) var(--space-2); border-radius: 6px;
  transition: background var(--t-fast) var(--ease);
}}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {{
  background: var(--c-side-hover);
}}
[data-testid="stSidebar"] hr {{ border-color: var(--c-border) !important; }}
[data-testid="stSidebar"] [data-baseweb="select"] > div {{
  background: var(--c-white); border-color: var(--c-border);
}}
/* Streamlit's automatic multipage nav labels the entry point "app", after
   the filename, which reads as an unfinished project rather than a product.
   Hidden here; app.py adds a properly labelled link instead. */
[data-testid="stSidebarNav"] {{ display: none; }}

/* Hiding the nav leaves Streamlit's reserved space behind, so the sidebar
   opens with a large void above the title. Pull the content back up to sit
   just under the collapse control. */
[data-testid="stSidebarUserContent"] {{
  padding-top: .5rem !important;
}}
[data-testid="stSidebarHeader"] {{
  padding-top: .5rem !important;
  padding-bottom: 0 !important;
  height: auto !important;
  min-height: 0 !important;
}}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div:first-child {{
  margin-top: 0 !important;
}}
[data-testid="stSidebar"] h1 {{ margin-top: 0 !important; padding-top: 0 !important; }}

/* the hand-placed page link that replaces it */
[data-testid="stSidebar"] [data-testid="stPageLink"] a {{
  border-radius: 6px; padding: 6px 10px;
  border: 1px solid var(--c-border); background: var(--c-white);
}}
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover {{
  border-color: var(--c-primary); background: var(--c-side-hover);
}}
[data-testid="stSidebar"] [data-testid="stPageLink"] a * {{
  color: var(--c-primary-deep) !important; font-weight: 600;
}}

/* ---- alerts ---------------------------------------------------------- */
[data-testid="stAlert"] {{ border-radius: var(--radius); border-left-width: 3px; }}

/* ---- expander -------------------------------------------------------- */
[data-testid="stExpander"] details {{
  border: 1px solid var(--c-border); border-radius: var(--radius);
}}
[data-testid="stExpander"] summary:hover {{ color: var(--c-primary); }}

/* ---- buttons: cursor + real hover, from the pre-delivery checklist ---- */
.stButton button {{
  border-radius: var(--radius); font-weight: 600; min-height: 44px;
  transition: all var(--t-fast) var(--ease); cursor: pointer;
}}
.stButton button:hover {{
  border-color: var(--c-primary); color: var(--c-primary);
  transform: translateY(-1px);
}}
.stButton button[kind="primary"] {{
  background: var(--c-primary); border-color: var(--c-primary);
}}
.stButton button[kind="primary"]:hover {{
  background: var(--c-primary-deep); border-color: var(--c-primary-deep);
  color: var(--c-white);
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
  font-size: .72rem; font-weight: 700; letter-spacing: .05em;
  text-transform: uppercase; font-family: {FONT_SANS};
}}
/* WCAG 1.4.1: colour must never be the only carrier of meaning. Each pill
   also gets a glyph, so the state survives greyscale printing and every
   form of colour vision deficiency. */
.fr-pill::before {{ font-weight: 900; margin-right: 5px; }}

.fr-pill-high {{ background: #EDF6FB; color: {OK}; border: 1px solid #9CC9E2; }}
.fr-pill-high::before {{ content: '✓'; }}          /* check */
.fr-pill-pass {{ background: #EDF6FB; color: {OK}; border: 1px solid #9CC9E2; }}
.fr-pill-pass::before {{ content: '✓'; }}

.fr-pill-medium {{ background: #FDF3E9; color: {CAUTION}; border: 1px solid #E5B98C; }}
.fr-pill-medium::before {{ content: '▲'; }}        /* triangle */
.fr-pill-low {{ background: #FDF3E9; color: {CAUTION}; border: 1px solid #E5B98C; }}
.fr-pill-low::before {{ content: '▲'; }}

.fr-pill-none {{ background: #EDEDED; color: {NEUTRAL}; border: 1px solid #C4C4C4; }}
.fr-pill-none::before {{ content: '✕'; }}          /* cross */
.fr-pill-fail {{ background: #EDEDED; color: {NEUTRAL}; border: 1px solid #C4C4C4; }}
.fr-pill-fail::before {{ content: '✕'; }}

/* ---- metric deltas ---------------------------------------------------
   st.metric ships its own red/green, which is exactly the pair we are
   trying to remove, and it is applied through generated emotion classes
   rather than anything we control. Override it here, keyed on the arrow
   Streamlit already renders, so the shape channel carries the meaning and
   the colour only reinforces it.
   Note: this keys on arrow DIRECTION, so a metric declared with
   delta_color="inverse" is coloured by direction rather than by sentiment.
   Down always reads as caution, which is the honest reading for this app. */
[data-testid="stMetricDelta"] {{
  color: var(--c-ok) !important;
  background: #EDF6FB !important;
  border-radius: 999px;
  padding: 1px 9px;
  font-weight: 700;
  width: fit-content;
}}
[data-testid="stMetricDelta"] * {{ color: inherit !important; }}
[data-testid="stMetricDelta"] svg {{ fill: currentColor !important; }}
[data-testid="stMetricDelta"]:has([data-testid="stMetricDeltaIcon-Down"]) {{
  color: var(--c-caution) !important;
  background: #FDF3E9 !important;
}}

/* ---- headline chips ---------------------------------------------------
   The headline is three separate facts glued together with middots: which
   KPI, which slice, how much it moved. Splitting them into their own boxes
   lets the eye pick out the one it wants instead of reading a sentence. */
.fr-head {{
  display: flex;
  gap: var(--space-3);            /* matches Streamlit's column gutter, so the
                                     row lines up with the KPI cards below */
  width: 100%;
  margin: 0 0 var(--space-5) 0;
  align-items: stretch;           /* equal heights, whatever the text length */
}}
.fr-head-part {{
  flex: 1 1 0;                    /* equal widths, full row */
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-family: {FONT_SANS};
  font-size: 1.12rem; font-weight: 700; letter-spacing: -.01em;
  color: var(--c-primary-deep);
  background: {HEAD_BG};
  border: 1px solid {HEAD_BORDER};
  border-radius: var(--radius);
  padding: var(--space-3) var(--space-4);
}}
.fr-head-part:first-child {{ border-left: 5px solid var(--c-primary); }}

/* Stacked variant: the three facts run down the page instead of across it, so
   the metric grid can sit beside them. height:100% lets the three blocks share
   the column's full height, which is what keeps the stack level with the 2x2
   grid on the right rather than ending short of it. Text goes left aligned:
   centred text reads fine in a wide chip and badly in a tall narrow one. */
.fr-head-col {{
  flex-direction: column;
  flex: 1 1 auto;
  height: 100%;
  margin-bottom: 0;
}}
/* flex-basis 0 with grow 1 is what makes the three boxes equal height rather
   than each sizing to its own text: "Net Revenue" and "-19.2% against the
   prior period" are very different lengths and would otherwise differ. */
.fr-head-col .fr-head-part {{
  flex: 1 1 0;
  min-height: 0;
  border-left: 5px solid var(--c-primary);
  justify-content: flex-start;
  text-align: left;
}}

/* Make the stack reach the full height of the metric grid beside it.
   height:100% cannot do this: it only resolves when EVERY ancestor has a
   definite height, and Streamlit inserts several wrappers between the column
   and the markdown, some with no test id to target. Naming them individually
   is guesswork that breaks whenever Streamlit changes its DOM.
   So: select every div that CONTAINS the headline — that is exactly its
   ancestor chain, whatever Streamlit calls them — and make each a flex column
   that grows. flex:1 propagates through auto-height parents, which is the
   thing height:100% cannot do.
   The [data-testid="stColumn"]:has(...) prefix is load bearing. Without it
   "div:has(.fr-head-col)" would match every ancestor up to the page root and
   turn the whole app into a flex column. */
[data-testid="stColumn"]:has(.fr-head-col) div:has(.fr-head-col) {{
  display: flex;
  flex-direction: column;
  flex: 1 1 auto;
  min-height: 0;
  height: 100%;
  /* Streamlit puts margin-bottom:-16px on stMarkdownContainer to swallow the
     trailing margin of a markdown paragraph. On a flex item that is not
     cosmetic: the line is filled by OUTER size, so the box grows to 268px for
     its outer size to reach the column's 252px, and the stack inside inherits
     the 268 and hangs 16px below the metric grid. Zeroing it is what actually
     levels the two columns. */
  margin-bottom: 0;
}}

/* ---- narrative -------------------------------------------------------
   The explanation is the one paragraph a reader actually reads, and it was
   set at body size across the full page width. A line that long is hard to
   track back from at the wrap, so the measure is capped near 75 characters,
   which is the range typography research settles on. Size and leading go up
   because this is prose, not a data label. */
.fr-narrative {{
  font-family: {FONT_SANS};
  font-size: 1.05rem;
  line-height: 1.75;
  color: var(--c-ink);
  max-width: 76ch;
  margin: var(--space-2) 0 var(--space-3) 0;
}}
/* Figures carry the argument, so they get weight and the brand colour. The
   surrounding words stay at normal weight or nothing stands out. */
.fr-narrative strong {{
  font-weight: 700;
  color: var(--c-primary-deep);
  white-space: nowrap;      /* never break "-1,556,566" across two lines */
}}

.fr-chain {{
  display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap;
  /* deep brand purple rather than black: black was the only pure-black
     element left on the page and read as a different application */
  background: var(--c-primary-deep);
  border: 1px solid var(--c-primary-deep);
  border-radius: var(--radius); padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-4);
}}
.fr-chain-node {{
  font-family: {FONT_MONO}; font-size: .82rem; font-weight: 600;
  color: var(--c-primary-deep); background: var(--c-white);
  border: 1px solid {HEAD_BORDER}; border-radius: 6px;
  padding: 5px 10px;
}}
.fr-chain-arrow {{ color: var(--c-primary); font-weight: 900; }}
.fr-chain-label {{
  font-size: .72rem; text-transform: uppercase; letter-spacing: .07em;
  color: {LILAC}; font-weight: 700; margin-right: var(--space-1);
}}

.fr-foot {{
  font-family: {FONT_MONO}; font-size: .74rem;
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


def headline(parts: list[str], stacked: bool = False) -> str:
    """
    The headline as separate boxes rather than one middot-joined sentence:
    KPI, slice, movement. Callers pass the parts, so this never has to guess
    where the boundaries are.

    `stacked` runs the boxes down a column instead of across a row, for the
    layout where the metric cards sit beside them rather than beneath.
    """
    cls = "fr-head fr-head-col" if stacked else "fr-head"
    inner = "".join(f'<span class="fr-head-part">{p}</span>' for p in parts)
    return f'<div class="{cls}">{inner}</div>'
