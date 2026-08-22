"""Lane B — narrative synthesis.

This is the one place in FRIDAY where language generation is allowed — and
even here, every number in the output must have been computed upstream by
detect.py / attribute.py / causal.py and handed in, never invented here.
The prompt built below is deliberately explicit about that boundary.

Two render modes:
  - template (default): pure Python string formatting, zero LLM calls,
    zero tokens, zero cost. Fully deterministic and works with no API key —
    this is what a fresh clone of the repo runs out of the box.
  - llm: hands the same structured facts to a caller-supplied client and
    asks it to write the prose. Opt-in, for a team that wants to plug in
    their own Claude/OpenAI key.

Either mode returns a NarrativeResult carrying the method used and (for
llm mode) usage figures, so friday/telemetry.py has something honest to
report for requirement #9 (clear LLM vs non-LLM breakdown).
"""
from __future__ import annotations

import dataclasses
from typing import Callable, Optional

from friday.evidence import EvidenceRecord
from friday.personas import PersonaView


@dataclasses.dataclass(frozen=True)
class NarrativeResult:
    text: str
    method: str            # "template" or "llm"
    model: str | None
    input_tokens: int
    output_tokens: int
    evidence_cited: list[str]   # event_ids actually referenced


def _format_evidence_lines(evidence: list[EvidenceRecord]) -> str:
    if not evidence:
        return "No supporting evidence available."
    lines = []
    for e in evidence:
        lines.append(f"  - [{e.timestamp.date()}, {e.event_type}, relevance={e.relevance_score}] {e.text}")
    return "\n".join(lines)


def render_template(view: PersonaView, evidence: list[EvidenceRecord]) -> NarrativeResult:
    """Deterministic, no-LLM narrative. Every figure in `view` was computed
    by an earlier module; this function only arranges sentences around it.
    """
    if view.abstained:
        text = (
            f"{view.headline}\n\n"
            f"Reason FRIDAY is not naming a cause: {view.abstain_reason}\n\n"
            f"No action is recommended while confidence is at this level."
        )
        cited = []
    else:
        action_line = f"\n\nRecommended action: {view.recommended_action}" if view.recommended_action else \
            "\n\nNo action recommended — this role has no decision rights over this movement."
        evidence_block = _format_evidence_lines(evidence)
        text = (
            f"{view.headline}\n\n"
            f"Confidence: {view.confidence}.\n\n"
            f"Supporting evidence:\n{evidence_block}"
            f"{action_line}"
        )
        cited = [e.event_id for e in evidence]

    return NarrativeResult(text=text, method="template", model=None,
                            input_tokens=0, output_tokens=0, evidence_cited=cited)


LlmClient = Callable[[str], tuple[str, int, int]]  # prompt -> (completion, input_tokens, output_tokens)


def build_llm_prompt(view: PersonaView, evidence: list[EvidenceRecord]) -> str:
    evidence_block = _format_evidence_lines(evidence)
    action_note = view.recommended_action or "none — this role has no decision rights over this movement"
    return f"""You are writing a one-paragraph business explanation for a {view.role}.

Use ONLY the facts given below. Do not invent, estimate, or restate any
number that is not explicitly provided here. If you need to refer to the
movement size, cause, or confidence, use the exact figures given.

Headline fact: {view.headline}
Confidence level (already determined, do not second-guess it): {view.confidence}
Abstained: {view.abstained}{f" — reason: {view.abstain_reason}" if view.abstained else ""}
Recommended action (already decided, just state it if present): {action_note}
Evidence (already retrieved and scored, cite it, do not add new evidence):
{evidence_block}

Write 3-5 sentences in plain business English for this persona's focus area: {view.focus}.
"""


def render_llm(view: PersonaView, evidence: list[EvidenceRecord],
               llm_client: LlmClient, model_name: str = "unspecified") -> NarrativeResult:
    """Opt-in LLM rendering. `llm_client` is any callable of (prompt) ->
    (completion_text, input_tokens, output_tokens) — deliberately generic
    so the team can wrap the Anthropic SDK, OpenAI SDK, or anything else
    without this module needing to know which."""
    prompt = build_llm_prompt(view, evidence)
    completion, in_tok, out_tok = llm_client(prompt)
    return NarrativeResult(
        text=completion, method="llm", model=model_name,
        input_tokens=in_tok, output_tokens=out_tok,
        evidence_cited=[e.event_id for e in evidence],
    )


def render_narrative(view: PersonaView, evidence: list[EvidenceRecord],
                      llm_client: Optional[LlmClient] = None,
                      model_name: str = "unspecified") -> NarrativeResult:
    """Single entry point Lane C's app.py should call. Falls back to the
    template renderer whenever no llm_client is supplied, so the app works
    with zero configuration."""
    if llm_client is None:
        return render_template(view, evidence)
    return render_llm(view, evidence, llm_client, model_name)
