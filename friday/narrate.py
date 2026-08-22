"""
Lane B. Narrative synthesis, with a numeric guard.

The brief's hardest instruction is that "the LLM should not be treated as the source
of quantitative truth". Telemetry enforces that at the stage layer: no deterministic
stage may issue a model call. This module enforces it at the output layer, which is
the one that actually reaches a human.

The mechanism is a fact pack. Every number the narrative is permitted to state is
computed upstream by deterministic code, written into a `FactPack`, and injected into
the prompt. After generation, every number appearing in the text is extracted and
checked against that pack. A number that is not in the pack was invented, and an
invented number fails the render rather than reaching a reader.

That is a stronger claim than "we told the model not to make things up", and it is
the claim a sceptical stakeholder will actually test.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Protocol

# matches 1,556,566 and 19.2 and 73% and -0.7
NUMBER = re.compile(r"-?\d[\d,]*(?:\.\d+)?%?")
TOLERANCE = 0.051


class GuardViolation(Exception):
    """Raised when generated prose contains a number nobody computed."""


@dataclass(frozen=True)
class Fact:
    key: str
    value: float | int | str | date
    display: str
    unit: str = ""
    provenance: str = ""

    @property
    def numeric(self) -> float | None:
        if isinstance(self.value, bool):
            return None
        if isinstance(self.value, (int, float)):
            return float(self.value)
        return None


def _variants(v: float) -> set[float]:
    """Every rounding of a value a writer might legitimately use."""
    out: set[float] = set()
    for x in (v, abs(v)):
        out.update({x, round(x), round(x, 1), round(x, 2)})
        # a share stored as 0.728 may legitimately be written as 72.8 or 73
        if abs(x) <= 1.0:
            for y in (x * 100,):
                out.update({y, round(y), round(y, 1), round(y, 2)})
        # a figure in rupees may be written in lakh
        if abs(x) >= 100_000:
            for y in (x / 100_000,):
                out.update({round(y), round(y, 1), round(y, 2)})
    return {float(o) for o in out}


@dataclass
class FactPack:
    """The complete set of things a narrative is allowed to assert."""
    facts: dict[str, Fact] = field(default_factory=dict)

    def add(self, key: str, value, display: str, unit: str = "",
            provenance: str = "") -> "FactPack":
        self.facts[key] = Fact(key, value, display, unit, provenance)
        return self

    def __getitem__(self, key: str) -> Fact:
        return self.facts[key]

    def get(self, key: str, default=None):
        f = self.facts.get(key)
        return f.display if f else default

    @property
    def allowed(self) -> set[float]:
        out: set[float] = set()
        for f in self.facts.values():
            n = f.numeric
            if n is not None:
                out |= _variants(n)
            if isinstance(f.value, date):
                out |= {float(f.value.year), float(f.value.month), float(f.value.day)}
        return out

    def prompt_block(self) -> str:
        """The only numbers the model is given, labelled."""
        return "\n".join(f"- {f.key}: {f.display}"
                         + (f"   [{f.provenance}]" if f.provenance else "")
                         for f in self.facts.values())

    def lineage(self) -> list[dict]:
        return [{"fact": f.key, "value": f.display, "produced_by": f.provenance}
                for f in self.facts.values() if f.provenance]


def extract_numbers(text: str) -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    for m in NUMBER.finditer(text):
        raw = m.group(0)
        cleaned = raw.rstrip("%").replace(",", "")
        try:
            out.append((raw, float(cleaned)))
        except ValueError:
            continue
    return out


def unauthorised_numbers(text: str, pack: FactPack) -> list[str]:
    """Numbers in the prose that no upstream stage computed."""
    allowed = pack.allowed
    bad: list[str] = []
    for raw, val in extract_numbers(text):
        if any(abs(val - a) <= TOLERANCE for a in allowed):
            continue
        bad.append(raw)
    return bad


# --------------------------------------------------------------------- clients
class LLMClient(Protocol):
    def complete(self, system: str, prompt: str) -> tuple[str, int, int]:
        """Return (text, tokens_in, tokens_out)."""


@dataclass
class ScriptedClient:
    """
    Stands in for a hosted model so the prototype runs offline and reproducibly.

    Swapping in a real client means implementing `complete` and nothing else. The
    guard, the prompt and the fact pack are unchanged, which is the point: the safety
    property does not depend on which model is behind it.
    """
    script: Callable[[str, str], str]
    name: str = "friday-narrator"

    def complete(self, system: str, prompt: str) -> tuple[str, int, int]:
        text = self.script(system, prompt)
        return text, len(system.split()) + len(prompt.split()), len(text.split())


SYSTEM_PROMPT = (
    "You are a business analyst writing a short explanation of a KPI movement. "
    "You may ONLY state numbers that appear in the FACTS block. You may not compute, "
    "infer, round differently, or estimate any figure. If a number is not in FACTS, "
    "do not mention it. Write plainly and do not speculate about causes that are not "
    "listed."
)


def build_prompt(pack: FactPack, persona: str, instruction: str,
                 citations: list[str]) -> str:
    cites = "\n".join(f"- {c}" for c in citations) if citations else "- none"
    return (f"FACTS (the only numbers you may use):\n{pack.prompt_block()}\n\n"
            f"EVIDENCE (quote at most one, verbatim):\n{cites}\n\n"
            f"AUDIENCE: {persona}\n\nTASK: {instruction}\n")


# ------------------------------------------------------------------- renderers
@dataclass
class Rendered:
    text: str
    renderer: str
    guarded: bool
    violations: list[str] = field(default_factory=list)
    fell_back: bool = False
    tokens_in: int = 0
    tokens_out: int = 0


def render_guarded(client: LLMClient, pack: FactPack, persona: str,
                   instruction: str, citations: list[str],
                   fallback: Callable[[], str]) -> Rendered:
    """
    Generate, then verify. On violation, fall back to deterministic prose.

    Falling back rather than retrying is deliberate. A reader waiting on an insight
    is better served by plainer language than by a second roll of the dice, and a
    silent retry would hide how often the guard fires. The violation is recorded.
    """
    system = SYSTEM_PROMPT
    prompt = build_prompt(pack, persona, instruction, citations)
    text, t_in, t_out = client.complete(system, prompt)

    bad = unauthorised_numbers(text, pack)
    if bad:
        return Rendered(text=fallback(), renderer="template_fallback", guarded=True,
                        violations=bad, fell_back=True,
                        tokens_in=t_in, tokens_out=t_out)

    return Rendered(text=text, renderer="llm", guarded=True,
                    tokens_in=t_in, tokens_out=t_out)
