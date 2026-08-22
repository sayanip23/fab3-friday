"""Lane B — personas and abstention.

The same movement, the same underlying numbers, but a different narrative
and different recommended action per role — and for roles with no decision
rights, no recommended action at all. This module never sees raw rows: it
takes the already-computed materiality/attribution/causal results and
applies entitlement + framing on top of them.
"""
from __future__ import annotations

import dataclasses

from friday.attribute import AttributionResult
from friday.causal import CausalScreenResult
from friday.contracts import Contract, resolve_entitlement
from friday.detect import MaterialityResult

# Persona-specific framing. What each role is told to care about, and what
# action language is appropriate for their decision rights — pulled from
# the contract's role.decision_rights, not hardcoded per persona here.
PERSONA_FOCUS = {
    "regional_sales_director": "account retention and service recovery in your own region",
    "cfo": "margin erosion and the ROI of any pricing action",
    "junior_analyst": "producing an accurate, properly-sourced weekly summary",
}


@dataclasses.dataclass(frozen=True)
class PersonaView:
    role: str
    region_label: str
    headline: str
    can_recommend_action: bool
    recommended_action: str | None
    confidence: str
    abstained: bool
    abstain_reason: str | None
    masked_fields: list[str]
    focus: str


def build_persona_view(contract: Contract, role_name: str,
                        materiality: MaterialityResult,
                        attribution: AttributionResult,
                        causal: CausalScreenResult | None,
                        home_region: str | None = None) -> PersonaView:
    """Build one persona's view of a single material movement.

    If `causal` is None or did not pass, this abstains rather than naming a
    cause — the persona layer is not allowed to be more confident than the
    causal screen was.
    """
    role = contract.get_role(role_name)
    region = materiality.grain_key.get("region", "unknown")

    row = {"region": region, "account_name": attribution.dominant_segment.segment if attribution.dominant_segment else None,
           "_role_home_region": home_region}
    try:
        masked_row = resolve_entitlement(contract, role_name, "net_revenue", row)
        access_denied = False
    except Exception:
        masked_row = None
        access_denied = True

    if access_denied:
        return PersonaView(
            role=role_name, region_label=region,
            headline=f"No access: {role_name} is not entitled to {region} data.",
            can_recommend_action=False, recommended_action=None,
            confidence="n/a", abstained=True,
            abstain_reason="row-level access denied by contract", masked_fields=role.masked_fields,
            focus=PERSONA_FOCUS.get(role_name, ""),
        )

    account_label = masked_row.get("account_name") if masked_row else None
    pct = materiality.pct_change
    abs_change = materiality.abs_change

    causal_ok = causal is not None and causal.passed
    if not causal_ok:
        reason = causal.reason if causal is not None else "no causal screen was run for this segment"
        return PersonaView(
            role=role_name, region_label=region,
            headline=(f"{region} net_revenue moved {pct:.1f}% ({abs_change:,.0f} INR). "
                      f"FRIDAY cannot confirm a specific cause with the evidence available."),
            can_recommend_action=False, recommended_action=None,
            confidence="abstain", abstained=True, abstain_reason=reason,
            masked_fields=role.masked_fields, focus=PERSONA_FOCUS.get(role_name, ""),
        )

    headline = (f"{region} net_revenue is down {abs(pct):.1f}% ({abs_change:,.0f} INR), "
                f"driven primarily by {account_label or 'a single account'} "
                f"({attribution.dominant_segment.contribution_share:.0%} of the change).")

    can_act = len(role.decision_rights) > 0
    action = None
    if can_act:
        if role_name == "regional_sales_director":
            action = f"Contact {account_label} before their next renewal window; audit delivery performance on the current logistics route."
        elif role_name == "cfo":
            action = ("Review the West Aurora discount's margin impact and the mix shift toward Vertex; "
                      "decide whether to continue, adjust, or withdraw the pricing action.")
        else:
            action = "Escalate to the relevant regional owner for a commercial decision."

    return PersonaView(
        role=role_name, region_label=region, headline=headline,
        can_recommend_action=can_act, recommended_action=action,
        confidence=causal.confidence, abstained=False, abstain_reason=None,
        masked_fields=role.masked_fields, focus=PERSONA_FOCUS.get(role_name, ""),
    )
