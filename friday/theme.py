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

import html

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
# The page the cards sit on. White cards on a white page separate only by a
# hairline, which is why the app read as flat next to the dashboards it is
# modelled on: those tint the page and leave the cards near-white, so every
# card lifts. Lighter and less saturated than the sidebar, so the rail still
# reads as a different surface, and light enough that muted ink on it stays
# above 4.5:1.
PAGE = "#F4F1FA"
HEAD_BG = "#E3D0FA"        # headline chips: a step darker than the page wash
HEAD_BORDER = "#C39BF0"    # so the three facts read as objects, not as text

# ---------------------------------------------------------------- chart series
# Categorical palette for charts where the bars are separate ENTITIES rather
# than one measure — which lever, which method — so colour identifies rather
# than decorates. Values are the data-viz reference palette's light-mode steps,
# used unchanged and assigned in a fixed order per entity, never cycled and
# never by rank: a chart sorted by value must not repaint its bars.
#
# Validated, not eyeballed (OKLab deltaE x100, all-pairs, white surface):
#   the three lever hues    CVD 9.2, normal vision 24.0   -> clears both gates
#   the six method hues     CVD 6.2, normal vision 16.3   -> CVD sits in the
#     6-8 band, which is permitted only alongside a second, non-colour channel.
#     Both charts name every bar on the category axis, so identity is never
#     carried by colour alone and the condition holds.
# Yellow and magenta fall under 3:1 against white; the same axis labels satisfy
# the relief rule that obliges.
SERIES_BLUE = "#2a78d6"
SERIES_ORANGE = "#eb6834"
SERIES_AQUA = "#1baf7a"
SERIES_YELLOW = "#eda100"
SERIES_MAGENTA = "#e87ba4"
SERIES_GREEN = "#008300"
SERIES_VIOLET = "#4a3aa7"

# Price/volume/mix: three levers, three hues.
LEVER_COLORS = {
    "Volume": SERIES_BLUE,
    "Price": SERIES_ORANGE,
    "Mix": SERIES_AQUA,
}

# Every method in telemetry's taxonomy gets a fixed hue, so a stage added later
# is coloured without anyone choosing. Generation keeps the brand purple: it is
# a reserved slot, not a series, because "how much of this was the model" is the
# question this chart exists to answer.
METHOD_COLORS = {
    "sql": SERIES_ORANGE,
    "deterministic_logic": SERIES_BLUE,
    "business_rules": SERIES_YELLOW,
    "statistics": SERIES_MAGENTA,
    "traditional_ml": SERIES_AQUA,
    "causal_inference": SERIES_GREEN,
    "retrieval": SERIES_VIOLET,
    "llm": PURPLE,
}

# ---------------------------------------------------------------- stat icons
# Inline SVG rather than an icon font: a font is a second network request the
# demo cannot afford to have fail, and an emoji would be rendered by whatever
# the viewer's OS happens to ship. 24x24 viewBox, drawn in currentColor, so the
# chip inherits the colour of the number it belongs to.
ICONS = {
    # a level, for a current reading
    "level": '<rect x="4" y="12" width="3.5" height="8" rx="1"/>'
             '<rect x="10.2" y="8" width="3.5" height="12" rx="1"/>'
             '<rect x="16.4" y="4" width="3.5" height="16" rx="1"/>',
    # a clock, for the period before this one
    "clock": '<circle cx="12" cy="12" r="8.2" fill="none" stroke="currentColor" '
             'stroke-width="2"/><path d="M12 7.2V12l3.2 2.1" fill="none" '
             'stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
    # a trace, for how far outside normal variance this sits
    "pulse": '<path d="M3 12.5h3.2L9 6l3.6 12 2.8-8 1.8 2.5H21" fill="none" '
             'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
             'stroke-linejoin="round"/>',
    # a shield, for a claim that has passed its gates
    "shield": '<path d="M12 3.2l7 2.9v5c0 4.4-3 8-7 9.7-4-1.7-7-5.3-7-9.7v-5z" '
              'fill="none" stroke="currentColor" stroke-width="2" '
              'stroke-linejoin="round"/>'
              '<path d="M8.9 11.9l2.2 2.2 4.1-4.4" fill="none" '
              'stroke="currentColor" stroke-width="2" stroke-linecap="round" '
              'stroke-linejoin="round"/>',
}


def icon(name: str, colour: str) -> str:
    """One icon chip: the glyph in its stat's colour on a wash of the same."""
    body = ICONS.get(name)
    if not body:
        return ""
    # eight digit hex is an alpha channel: the chip is a 12% wash of its own
    # colour, so it never needs a second token per stat
    return (f'<span class="fr-stat-icon" style="color:{colour};'
            f'background:{colour}1F">'
            f'<svg viewBox="0 0 24 24" width="14" height="14" '
            f'fill="currentColor" aria-hidden="true">{body}</svg></span>')


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
  --c-page: {PAGE};
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

/* ---- page surface ----------------------------------------------------
   Main only. The sidebar keeps its own, deeper wash, and the tint stops at
   the content area so a dataframe's own white ground still reads as a
   surface laid on the page rather than as the page itself. */
[data-testid="stMain"] {{ background: var(--c-page); }}

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

/* ---- overview header -------------------------------------------------
   The top of the page is a dashboard header, not a sentence: a title row that
   names the page and fixes the period, then two cards - what moved, on the
   left, and the numbers, on the right. The cards are white with a hairline and
   a soft shadow so they read as raised surfaces. The tinted chips this
   replaces made the whole band one flat colour, which is why it read as
   crowded: seven boxes of the same purple, none of them ranked. */
.fr-top {{
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: var(--space-3); flex-wrap: wrap;
  margin: 0 0 var(--space-4) 0;
}}
.fr-top-title {{
  font-family: {FONT_SANS};
  font-size: 1.55rem; font-weight: 700; letter-spacing: -.02em;
  color: var(--c-black); line-height: 1.2;
}}
.fr-top-sub {{ font-size: .82rem; color: var(--c-muted); margin-top: 3px; }}
.fr-top-chip {{
  display: inline-flex; align-items: center; gap: 8px;
  background: var(--c-white); border: 1px solid var(--c-border);
  border-radius: 999px; padding: 7px 14px;
  font-family: {FONT_MONO}; font-size: .76rem; color: var(--c-ink);
  white-space: nowrap;
}}
.fr-top-chip b {{
  font-size: .64rem; font-weight: 700; letter-spacing: .09em;
  text-transform: uppercase; color: var(--c-muted);
}}

.fr-card {{
  display: flex; flex-direction: column;
  height: 100%; box-sizing: border-box;
  background: var(--c-white);
  border: 1px solid var(--c-border);
  border-radius: 12px;
  padding: var(--space-3) var(--space-4) var(--space-4);
  box-shadow: 0 1px 2px rgba(20, 20, 20, .05), 0 10px 26px rgba(61, 0, 102, .06);
}}
.fr-card-head {{
  display: flex; align-items: baseline; justify-content: space-between;
  gap: var(--space-2);
}}
.fr-card-title {{
  font-family: {FONT_SANS}; font-size: .95rem; font-weight: 700;
  color: var(--c-black);
}}
.fr-card-note {{ font-size: .74rem; color: var(--c-muted); white-space: nowrap; }}

/* Left card: one labelled row per fact, the label over its value. The rows
   share the card's height (flex 1 1 0), so the card stays level with the
   numbers beside it however long a region name runs. */
.fr-rows {{
  display: flex; flex-direction: column; flex: 1 1 auto;
  margin-top: var(--space-2);
}}
/* grow but never shrink: flex-shrink on a row lets three labelled facts
   compress until the value of one sits on the divider of the next, which is
   what "1 1 0" did here. The card takes its height from its rows instead, and
   the stat card beside it stretches to match. */
.fr-row {{
  flex: 1 0 auto;
  display: flex; flex-direction: column; justify-content: center; gap: 2px;
  padding: var(--space-1) 0;
  border-top: 1px solid var(--c-border);
}}
.fr-row:first-child {{ border-top: none; }}
.fr-row-k {{
  font-size: .68rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: .08em; color: var(--c-muted);
}}
.fr-row-v {{
  font-size: 1.05rem; font-weight: 700; line-height: 1.3;
  color: var(--c-primary-deep);
}}

/* Right card: the four numbers in one row, each over its own accent bar. The
   bar is not decoration - its colour is the reading of the number above it, so
   direction and confidence land before the words are read. Callers choose it,
   because only the caller knows what its number means. */
.fr-strip {{
  display: flex; gap: var(--space-4); flex: 1 1 auto; margin-top: var(--space-3);
  align-items: center;   /* the facts card is the taller of the two; centring
                            keeps the numbers off the top edge when it is */
}}
.fr-stat {{
  flex: 1 1 0; min-width: 0;
  display: flex; flex-direction: column; justify-content: flex-start;
}}
.fr-stat-head {{ display: flex; align-items: center; gap: 7px; min-width: 0; }}
.fr-stat-icon {{
  flex: 0 0 auto;
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 7px;
}}
.fr-stat-v {{
  font-family: {FONT_MONO}; font-size: 1.5rem; font-weight: 700;
  color: var(--c-black); line-height: 1.15; letter-spacing: -.02em;
  min-width: 0;
}}
/* Two by two, so each number has about 175px rather than 411. The chip takes
   29 of them, which "6,570,989" at the full size would not survive. */
.fr-grid .fr-stat-v {{ font-size: 1.35rem; }}
.fr-stat-bar {{ height: 4px; border-radius: 999px; margin: 9px 0 7px; }}
.fr-stat-k {{
  font-size: .72rem; font-weight: 600; color: var(--c-muted); line-height: 1.35;
}}
.fr-stat-d {{ font-size: .72rem; font-weight: 700; margin-top: 5px; }}
/* Two-by-two rather than one row of four, for when the card is a third of the
   page instead of two thirds. Four numbers across 360px would each get about
   80px, and these are the figures on the page that must survive a glance. */
.fr-strip.fr-grid {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3) var(--space-4);
  align-items: start;
}}

/* ---- causal chain, as a card -----------------------------------------
   Three equal boxes running down the card, root cause at the top and the
   movement it produced at the bottom, with the arrow between them saying
   which way the claim runs. Vertical because the card is a column: the
   horizontal banner this replaces spanned the page and made the chain look
   like a footer rather than a third of the finding. */
.fr-nodes {{
  display: flex; flex-direction: column; justify-content: center;
  flex: 1 1 auto; margin-top: var(--space-2);
}}
.fr-node {{
  flex: 0 0 auto;
  display: flex; align-items: center; justify-content: center; text-align: center;
  font-family: {FONT_MONO}; font-size: .8rem; font-weight: 600;
  color: var(--c-primary-deep);
  background: var(--c-wash);
  border: 1px solid var(--c-border);
  border-left: 4px solid var(--c-primary);
  border-radius: 6px;
  padding: 9px 10px; min-height: 38px; box-sizing: border-box;
}}
.fr-node-arrow {{
  color: var(--c-primary); font-weight: 900; font-size: .95rem;
  text-align: center; line-height: 1; padding: 4px 0;
}}
/* The help marker, as a "?" the reader can hover. st.metric's own help bubble
   is not available to hand-built markup, and a native title attribute is the
   one tooltip that needs no script. */
.fr-q {{
  display: inline-flex; align-items: center; justify-content: center;
  width: 14px; height: 14px; margin-left: 5px; border-radius: 50%;
  border: 1px solid var(--c-muted); color: var(--c-muted);
  font-size: .58rem; font-weight: 700; cursor: help; vertical-align: 1px;
}}
/* Same trick, and the same reason, as the stacked headline above: hand a
   definite height down the anonymous wrappers Streamlit puts between the
   column and the markdown, and zero the -16px margin it sets on the markdown
   container, or the two cards end at different heights. */
[data-testid="stColumn"]:has(.fr-card) div:has(.fr-card) {{
  display: flex; flex-direction: column; flex: 1 1 auto;
  min-height: 0; height: 100%; margin-bottom: 0;
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


def esc(value: object) -> str:
    """
    HTML-escape a value bound for markup. Quotes included: some of these land
    inside a title attribute.
    """
    return html.escape(str(value), quote=True)


def topbar(title: str, subtitle: str, period: str) -> str:
    """The page title row: what this page is, for whom, over which window."""
    return (f'<div class="fr-top"><div>'
            f'<div class="fr-top-title">{esc(title)}</div>'
            f'<div class="fr-top-sub">{esc(subtitle)}</div></div>'
            f'<span class="fr-top-chip"><b>period</b>{esc(period)}</span></div>')


def fact_card(title: str, note: str, rows: list[tuple[str, str]]) -> str:
    """
    The facts of the movement as a card: each label set over its value.

    Rows arrive as pairs rather than as "Label=value" strings, so the card can
    set the label and the value in different type without parsing anything.
    """
    body = "".join(f'<div class="fr-row"><div class="fr-row-k">{esc(k)}</div>'
                   f'<div class="fr-row-v">{esc(v)}</div></div>' for k, v in rows)
    return (f'<div class="fr-card"><div class="fr-card-head">'
            f'<span class="fr-card-title">{esc(title)}</span>'
            f'<span class="fr-card-note">{esc(note)}</span></div>'
            f'<div class="fr-rows">{body}</div></div>')


def chain_card(title: str, note: str, nodes: list[str]) -> str:
    """
    The finding as a chain: each node its own box, an arrow between them.

    The arrow is a real character rather than a rotated glyph, so it survives a
    font that has no vertical chevron and never overlaps the box below it.
    """
    inner = '<div class="fr-node-arrow">&darr;</div>'.join(
        f'<div class="fr-node">{esc(n)}</div>' for n in nodes)
    return (f'<div class="fr-card"><div class="fr-card-head">'
            f'<span class="fr-card-title">{esc(title)}</span>'
            f'<span class="fr-card-note">{esc(note)}</span></div>'
            f'<div class="fr-nodes">{inner}</div></div>')


def stat_card(title: str, note: str, stats: list[dict], grid: bool = False) -> str:
    """
    The headline numbers as one strip, each over a coloured accent bar.

    Each stat is a dict: `value` and `label` are required; `color` paints the
    bar, `help` adds a hoverable "?", and `note` with `note_color` is the small
    line beneath. Colours are passed in, never chosen here, because what a
    number means - a direction, a status - is the caller's to know.

    `grid` lays them two-by-two instead of in one row, for a narrower card.
    `icon` names one of ICONS, drawn in the stat's own colour.
    """
    cells = []
    for s in stats:
        mark = (f'<span class="fr-q" title="{esc(s["help"])}">?</span>'
                if s.get("help") else "")
        foot = (f'<div class="fr-stat-d" style="color:{s.get("note_color", MUTED)}">'
                f'{esc(s["note"])}</div>' if s.get("note") else "")
        cells.append(
            f'<div class="fr-stat">'
            f'<div class="fr-stat-head">'
            f'{icon(s.get("icon", ""), s.get("color", PURPLE))}'
            f'<div class="fr-stat-v">{esc(s["value"])}</div></div>'
            f'<div class="fr-stat-bar" style="background:{s.get("color", PURPLE)}">'
            f'</div>'
            f'<div class="fr-stat-k">{esc(s["label"])}{mark}</div>{foot}</div>')
    return (f'<div class="fr-card"><div class="fr-card-head">'
            f'<span class="fr-card-title">{esc(title)}</span>'
            f'<span class="fr-card-note">{esc(note)}</span></div>'
            f'<div class="fr-strip{" fr-grid" if grid else ""}">'
            f'{"".join(cells)}</div></div>')


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
