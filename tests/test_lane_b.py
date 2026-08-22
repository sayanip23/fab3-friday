"""Lane B smoke test — evidence retrieval, personas, narration, abstention.

Usage: python tests/test_lane_b.py
"""
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from friday.contracts import load_contract
from friday.detect import detect_region_revenue_movement
from friday.attribute import attribute_region_movement
from friday.causal import screen_account_effect
from friday.evidence import EvidenceIndex
from friday.personas import build_persona_view
from friday.narrate import render_narrative

COMPARISON_PERIOD = (pd.Timestamp("2026-06-26"), pd.Timestamp("2026-07-23"))
CURRENT_PERIOD = (pd.Timestamp("2026-07-24"), pd.Timestamp("2026-08-20"))
AS_OF = CURRENT_PERIOD[1]


def main():
    contract = load_contract("contracts/kpis.yaml")
    sales = pd.read_csv("data/raw/sales_transactions.csv")
    events = pd.read_csv("data/raw/service_events.csv")

    materiality = detect_region_revenue_movement(sales, contract, "West", COMPARISON_PERIOD, CURRENT_PERIOD)
    attribution = attribute_region_movement(sales, "West", COMPARISON_PERIOD, CURRENT_PERIOD)
    causal = screen_account_effect(events, "Acme Corp", CURRENT_PERIOD[0])

    index = EvidenceIndex(events)
    evidence = index.search("delivery complaints supplier risk", as_of=AS_OF,
                             account_name="Acme Corp", top_k=5)

    checks = []

    checks.append(("Evidence retrieval returns Acme-only, pre-cutoff results",
                    len(evidence) > 0 and all(e.account_name == "Acme Corp" for e in evidence)
                    and all(e.timestamp <= AS_OF for e in evidence),
                    f"{len(evidence)} record(s), top relevance={evidence[0].relevance_score if evidence else None}"))

    # Three personas, same underlying facts, different narratives/actions.
    views = {role: build_persona_view(contract, role, materiality, attribution, causal, home_region="West")
             for role in ["regional_sales_director", "cfo", "junior_analyst"]}

    checks.append(("Regional director sees the real account name",
                    views["regional_sales_director"].recommended_action is not None
                    and "Acme Corp" in views["regional_sales_director"].headline,
                    views["regional_sales_director"].headline))

    checks.append(("Junior analyst's view has account name masked",
                    "account_name" in views["junior_analyst"].masked_fields,
                    f"masked_fields={views['junior_analyst'].masked_fields}"))

    checks.append(("Junior analyst has no recommended action (no decision rights)",
                    not views["junior_analyst"].can_recommend_action,
                    f"can_recommend_action={views['junior_analyst'].can_recommend_action}"))

    checks.append(("CFO and regional director get different recommended actions",
                    views["cfo"].recommended_action != views["regional_sales_director"].recommended_action,
                    f"cfo='{views['cfo'].recommended_action[:40]}...' vs "
                    f"director='{views['regional_sales_director'].recommended_action[:40]}...'"))

    narrative = render_narrative(views["regional_sales_director"], evidence)
    checks.append(("Template narrative renders with zero LLM tokens",
                    narrative.method == "template" and narrative.input_tokens == 0 and narrative.output_tokens == 0,
                    f"method={narrative.method}, tokens=({narrative.input_tokens},{narrative.output_tokens})"))

    checks.append(("Narrative only cites evidence event_ids that were actually retrieved",
                    set(narrative.evidence_cited) <= {e.event_id for e in evidence},
                    f"cited={narrative.evidence_cited}"))

    # --- Abstention path: a low-confidence account should produce an
    # abstaining narrative, not a fabricated cause.
    control_causal = screen_account_effect(events, "Meridian Foods", CURRENT_PERIOD[0])
    control_view = build_persona_view(contract, "regional_sales_director", materiality, attribution,
                                       control_causal, home_region="West")
    control_narrative = render_narrative(control_view, [])
    checks.append(("Abstention path fires for low-confidence causal screen",
                    control_view.abstained and control_view.recommended_action is None
                    and "not naming a cause" in control_narrative.text,
                    f"abstained={control_view.abstained}, reason={control_view.abstain_reason}"))

    # --- Access control: a director scoped to East should be denied West data.
    east_denied = build_persona_view(contract, "regional_sales_director", materiality, attribution,
                                      causal, home_region="East")
    checks.append(("Out-of-region director is denied access, not shown masked data",
                    east_denied.abstained and "not entitled" in east_denied.headline,
                    east_denied.headline))

    width = max(len(name) for name, _, _ in checks)
    passed = 0
    for i, (name, ok, detail) in enumerate(checks, 1):
        mark = "✓" if ok else "✗"
        print(f"{i}. [{mark}] {name.ljust(width)}  {detail}")
        passed += ok
    print(f"\n{passed}/{len(checks)} Lane B checks passed.")

    print("\n--- Sample rendered narrative (regional_sales_director) ---")
    print(narrative.text)
    print("\n--- Sample abstention narrative (control account) ---")
    print(control_narrative.text)

    sys.exit(0 if passed == len(checks) else 1)


if __name__ == "__main__":
    main()
