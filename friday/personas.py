"""
Lane B. Persona specific insight assembly.

Answers Round 2 objectives 4 and 6, and minimum expectation 3: the same KPI movement
must produce different narratives and different recommended actions for different
people, each supported by traceable evidence.

The differences are not cosmetic rewording. Three things genuinely change:

  what they may see      entitlement filters the facts before a sentence is written
  what they care about   the lever a role owns determines which driver leads
  what they may do       an action is only offered to someone holding the right

An analyst with no decision rights therefore receives no actions at all, which is the
correct behaviour and not an omission.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

from . import narrate
from .access import Principal, pseudonymise
from .attribute import Decomposition
from .causal import Assessment, Verdict
from .detect import Movement
from .evidence import Passage
from .kpi import Period, Warehouse

# an association below this share of the movement earns no action at all
ASSOCIATION_FLOOR = 0.15

CONFIDENCE_ORDER = ["none", "low", "medium", "high"]


def _downgrade(level: str) -> str:
    i = CONFIDENCE_ORDER.index(level) if level in CONFIDENCE_ORDER else 0
    return CONFIDENCE_ORDER[max(i - 1, 0)]


@dataclass
class Action:
    """The brief's action schema, filled exactly."""
    driver: str
    controllable_lever: str
    action: str
    expected_impact: str
    owner: str
    confidence: str
    monitoring_plan: str

    def as_dict(self) -> dict:
        return {
            "driver": self.driver,
            "controllable_lever": self.controllable_lever,
            "action": self.action,
            "expected_impact": self.expected_impact,
            "owner": self.owner,
            "confidence": self.confidence,
            "monitoring_plan": self.monitoring_plan,
        }

    def line(self) -> str:
        return (f"{self.driver} -> {self.controllable_lever} -> {self.action} "
                f"-> {self.expected_impact} -> {self.owner} -> {self.confidence} "
                f"-> {self.monitoring_plan}")


@dataclass
class Insight:
    persona: str
    role: str
    headline: str
    narrative: narrate.Rendered
    actions: list[Action]
    evidence: list[Passage]
    confidence: str
    abstained: bool
    abstain_reasons: list[str] = field(default_factory=list)
    next_check: str | None = None
    facts: narrate.FactPack | None = None
    masked: bool = False

    def render(self) -> str:
        out = [self.headline, "", self.narrative.text]
        if self.abstained:
            out += ["", "Not asserting a cause. " + "; ".join(self.abstain_reasons)]
            if self.next_check:
                out += [f"Check that would settle it: {self.next_check}"]
        if self.actions:
            out += ["", "Recommended actions:"]
            out += [f"  {i+1}. {a.action}  (owner: {a.owner}, "
                    f"confidence: {a.confidence})" for i, a in enumerate(self.actions)]
        elif not self.abstained:
            out += ["", "No actions offered: this role holds no decision rights."]
        if self.evidence:
            out += ["", "Evidence:"]
            out += [f"  - {p.cite(120)}" for p in self.evidence]
        return "\n".join(out)


# ------------------------------------------------------------------ fact pack
def build_facts(wh: Warehouse, principal: Principal, movement: Movement,
                pvm: Decomposition, by_account: Decomposition,
                assessment: Assessment, period: Period) -> narrate.FactPack:
    """
    Every number the narrative may state, each stamped with what produced it.

    Nothing enters this pack that was not computed by a deterministic stage.
    """
    pack = narrate.FactPack()
    unit = movement.unit

    def q(v: float) -> str:
        """Ratio KPIs live near 1, so ',.0f' destroys them: -1.63 becomes '-2'."""
        if v != v:
            return "n/a"
        return f"{v:+,.2f}" if abs(v) < 1000 else f"{v:+,.0f}"
    masks = "account_name" in principal.contract.masked_columns(movement.kpi, principal.role)

    pack.add("kpi", movement.label, movement.label, provenance="contract")
    pack.add("slice", movement.slice_label, movement.slice_label, provenance="contract")
    pack.add("period", str(period), str(period), provenance="request")
    pack.add("current_value", movement.current, f"{q(movement.current).lstrip(chr(43))} {unit}",
             unit, "kpi.value, deterministic sql")
    pack.add("prior_value", movement.prior, f"{q(movement.prior).lstrip(chr(43))} {unit}",
             unit, "kpi.value, deterministic sql")
    pack.add("change_abs", movement.delta, f"{q(movement.delta)} {unit}",
             unit, "kpi.value, deterministic sql")
    pack.add("change_pct", movement.pct, f"{movement.pct:+.1f}%", "percent",
             "kpi.value, deterministic sql")
    pack.add("z_score", movement.z_score, f"{movement.z_score:.2f}", "sigma",
             "detect.evaluate, robust z score")
    pack.add("normal_swing", movement.baseline_median_pct,
             f"{abs(movement.baseline_median_pct):.1f}%", "percent",
             "detect, 90 day baseline median")

    for eff in pvm.effects:
        key = f"{eff.driver}_effect"
        pack.add(key, eff.value, f"{q(eff.value)} {unit}", unit,
                 "attribute.price_volume_mix, deterministic arithmetic")
        pack.add(f"{eff.driver}_share", abs(eff.share), f"{abs(eff.share):.0%}",
                 "percent", "attribute.price_volume_mix")

    top = by_account.top(1)
    if top:
        name = pseudonymise(top[0].name) if masks else top[0].name
        pack.add("top_account", name, name, provenance="attribute.by_dimension")
        pack.add("top_account_effect", top[0].value, f"{top[0].value:+,.0f} {unit}",
                 unit, "attribute.by_dimension, deterministic arithmetic")

    for v in assessment.causes:
        if v.kind == "evidential":
            pack.add("root_cause", v.driver, v.driver.replace("_", " "),
                     provenance="causal.screen, three gate test")
            pack.add("root_cause_strength", v.strength, f"{v.strength:.1f} times",
                     "ratio", "causal.evidence_rate_ratio, changepoint anchored")
            if v.first_evidence:
                pack.add("root_cause_from", v.first_evidence,
                         v.first_evidence.isoformat(),
                         provenance="causal.driver_change_point")
    if assessment.verdicts and assessment.verdicts[0].onset:
        pack.add("onset", assessment.verdicts[0].onset,
                 assessment.verdicts[0].onset.isoformat(),
                 provenance="causal.movement_onset")

    pack.add("confidence", assessment.confidence, assessment.confidence,
             provenance="causal, calibrated")
    return pack


# -------------------------------------------------------------------- actions
def build_actions(principal: Principal, assessment: Assessment,
                  pack: narrate.FactPack, movement: Movement,
                  pvm: Decomposition) -> list[Action]:
    """
    One action per controllable cause, owned by whoever holds the matching right.

    Two rules from the contract are enforced here rather than assumed: a driver that
    is not controllable gets no action, and an action is withheld from a principal
    who does not hold the right it requires.
    """
    c = principal.contract
    schema = c.action_schema
    rights = schema.get("lever_rights", {})
    phrasing = schema.get("lever_actions", {})
    out: list[Action] = []

    if assessment.abstain:
        return out

    region = movement.filters.get("region", "the affected region")
    top_segment = max(pvm.effects, key=lambda e: abs(e.value)).name if pvm.effects else "affected"

    # Causes first, then material associations.
    #
    # Restricting actions to causes alone looks rigorous but fails the person it
    # matters to. Price here accounts for 18% of the movement and is the only lever
    # the CFO owns; screening it out because it missed the 35% causal bar leaves the
    # one person able to act on discounting with nothing to do. So an association
    # above the floor still earns an action, at reduced confidence and framed as a
    # review rather than a fix.
    candidates: list[tuple[Verdict, bool]] = [(v, True) for v in assessment.causes]
    seen = {v.driver for v in assessment.causes}
    for v in assessment.verdicts:
        if (v.driver not in seen and v.kind == "arithmetic"
                and v.controllable and v.share >= ASSOCIATION_FLOOR):
            candidates.append((v, False))

    for v, is_cause in candidates:
        if not v.controllable:
            continue
        right = rights.get(v.lever)
        if not right or not principal.may_act(right):
            continue

        template = phrasing.get(v.lever)
        if not template:
            continue

        text = " ".join(template.split()).format(
            account=pack.get("top_account", "the account"),
            region=region, segment=top_segment)

        if v.kind == "arithmetic":
            impact = (f"worth {pack.get(f'{v.driver}_effect', 'the observed amount')} "
                      f"over the period, being "
                      f"{pack.get(f'{v.driver}_share', 'its share')} of the movement")
        else:
            impact = (f"addresses the upstream cause running at "
                      f"{pack.get('root_cause_strength', 'an elevated rate')} "
                      f"its pre change rate")
        if not is_cause:
            impact += ", association only, not established as a cause"

        conf = assessment.confidence if is_cause else _downgrade(assessment.confidence)

        out.append(Action(
            driver=v.driver,
            controllable_lever=v.lever,
            action=text,
            expected_impact=impact,
            owner=c.roles[principal.role]["label"],
            confidence=conf,
            monitoring_plan=(
                f"Track {movement.label} for {movement.slice_label} weekly. "
                f"Re-alert if the {v.driver} effect has not reversed within "
                f"three periods."),
        ))

    missing = [f for f in schema.get("required_fields", []) if not
               all(getattr(a, f, None) for a in out)]
    if out and missing:
        raise ValueError(f"action schema incomplete, missing {missing}")
    return out


# ------------------------------------------------------------------ narrative
def _headline(principal: Principal, movement: Movement,
              pack: narrate.FactPack) -> str:
    return (f"{movement.label} · {movement.slice_label} · "
            f"{pack.get('change_pct')} against the prior period")


def _slice_phrase(movement: Movement) -> str:
    """
    The slice as English rather than as a filter expression.

    'region=West' is what the engine calls it internally; a reader wants 'West'.
    The label still names the dimension when it is not the obvious one.
    """
    if not movement.filters:
        return "across every region"
    parts = []
    for key, value in movement.filters.items():
        parts.append(str(value) if key == "region"
                     else f"{value} ({key.replace('_', ' ')})")
    return " and ".join(parts)


def _template(principal: Principal, movement: Movement, pack: narrate.FactPack,
              assessment: Assessment) -> str:
    """Deterministic prose. Also the fallback when the guard fires."""
    depth = principal.contract.roles[principal.role].get("narrative_depth", "detailed")
    p = pack.get

    swing = pack["normal_swing"].numeric if "normal_swing" in pack.facts else None
    swing_txt = (f", where the usual swing is about {p('normal_swing')}"
                 if swing is not None and math.isfinite(swing) else
                 ", against a baseline too short to characterise")
    lead = (f"{movement.label} in {_slice_phrase(movement)} moved "
            f"{p('change_pct')} ({p('change_abs')}) against the prior "
            f"period{swing_txt}.")

    if assessment.abstain:
        return lead + " The evidence is not sufficient to name a cause."

    if depth == "operational":
        body = (f" The movement is concentrated in {p('top_account')}, which accounts "
                f"for {p('top_account_effect')} of it, and volume explains "
                f"{p('volume_share')} of the total. Upstream, {p('root_cause')} has "
                f"been running at {p('root_cause_strength')} its previous rate since "
                f"{p('root_cause_from')} — before the movement began on "
                f"{p('onset')}.")
    elif depth == "financial":
        body = (f" Volume accounts for {p('volume_share')} of the movement and price "
                f"for {p('price_share')}, with the price effect worth "
                f"{p('price_effect')}. The upstream cause is {p('root_cause')}, which "
                f"has run at {p('root_cause_strength')} its previous rate since "
                f"{p('root_cause_from')}.")
    else:
        body = (f" The decomposition attributes {p('volume_share')} to volume, "
                f"{p('price_share')} to price and {p('mix_share')} to mix, "
                f"reconciling exactly to {p('change_abs')}. The largest single "
                f"account is {p('top_account')}, at {p('top_account_effect')}, and "
                f"detection fired at {p('z_score')} sigma. The upstream cause is "
                f"{p('root_cause')}, at {p('root_cause_strength')} its pre-change "
                f"rate from {p('root_cause_from')}.")

    return lead + body + f" Confidence is {p('confidence')}."


def build_insight(wh: Warehouse, principal: Principal, movement: Movement,
                  pvm: Decomposition, by_account: Decomposition,
                  assessment: Assessment, evidence: list[Passage],
                  period: Period,
                  client: narrate.LLMClient | None = None) -> Insight:
    """Assemble one persona's complete insight."""
    pack = build_facts(wh, principal, movement, pvm, by_account, assessment, period)
    label = principal.contract.roles[principal.role]["label"]
    fallback = lambda: _template(principal, movement, pack, assessment)   # noqa: E731

    if client is None:
        rendered = narrate.Rendered(text=fallback(), renderer="template",
                                    guarded=False)
    else:
        depth = principal.contract.roles[principal.role].get("narrative_depth", "detailed")
        rendered = narrate.render_guarded(
            client, pack, persona=f"{label} ({depth} depth)",
            instruction=("Explain in three sentences what moved, what accounts for "
                         "it, and what upstream cause precedes it."),
            citations=[p.cite(120) for p in evidence[:2]],
            fallback=fallback)

    return Insight(
        persona=label, role=principal.role,
        headline=_headline(principal, movement, pack),
        narrative=rendered,
        actions=build_actions(principal, assessment, pack, movement, pvm),
        evidence=evidence,
        confidence=assessment.confidence,
        abstained=assessment.abstain,
        abstain_reasons=assessment.abstain_reasons,
        next_check=assessment.discriminating_check,
        facts=pack,
        masked=bool(principal.contract.masked_columns(movement.kpi, principal.role)),
    )
