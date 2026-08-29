"""
The orchestrator. One instrumented path from a question to an insight.

Everything before this file is a capability. This is where they become a product,
and it exists so that the UI, the verification scripts and any future caller all
drive the identical pipeline. A demo that works because the UI wires the stages in a
special order is a demo that proves nothing.

Every stage is wrapped in telemetry and declares its method, so requirements 9 and 10
are satisfied by construction rather than by a separate reporting pass.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field, replace
from datetime import date

from . import attribute, causal, detect, evidence, narrate, personas, telemetry
from .access import Principal, pseudonymise
from .attribute import Decomposition
from .causal import Assessment
from .contracts import Contract, load as load_contract
from .detect import Movement
from .evidence import Passage
from .feedback import Correction, FeedbackStore
from .kpi import Filters, Period, Warehouse
from .personas import Insight

_counter = itertools.count(1)


@dataclass
class InsightResult:
    """Everything one question produced, including how it was produced."""
    insight: Insight
    run: telemetry.Run
    movement: Movement
    pvm: Decomposition
    by_account: Decomposition
    assessment: Assessment
    evidence: list[Passage] = field(default_factory=list)
    freshness: list[dict] = field(default_factory=list)

    @property
    def insight_id(self) -> str:
        return self.run.insight_id

    def audit_record(self) -> dict:
        """The single artefact an auditor would ask for."""
        return {
            "insight_id": self.insight_id,
            "principal": self.run.principal,
            "role": self.run.role,
            "kpi": self.movement.kpi,
            "slice": self.movement.slice_label,
            "movement_pct": round(self.movement.pct, 3),
            "material": self.movement.material,
            "confidence": self.assessment.confidence,
            "abstained": self.assessment.abstain,
            "contributions": self.pvm.as_frame().to_dict("records"),
            "reconciled": self.pvm.reconciled,
            "gates": [{"driver": v.driver, "kind": v.kind, "status": v.status,
                       "gates": v.gates()} for v in self.assessment.verdicts],
            "evidence": [p.provenance() for p in self.evidence],
            "fact_lineage": self.insight.facts.lineage() if self.insight.facts else [],
            "actions": [a.as_dict() for a in self.insight.actions],
            "narrative_renderer": self.insight.narrative.renderer,
            "guard_violations": self.insight.narrative.violations,
            "telemetry": self.run.to_dict(),
        }


class Engine:
    """Stateful across questions only through the feedback store, by design."""

    def __init__(self, contract: Contract | None = None,
                 client: narrate.LLMClient | None = None,
                 store: FeedbackStore | None = None):
        self.contract = contract or load_contract()
        self.wh = Warehouse(self.contract)
        self.index = evidence.Index.build(self.wh)
        self.client = client
        self.store = store or FeedbackStore()

    # ------------------------------------------------------------------ alerts
    def alerts(self, principal: Principal, period: Period,
               dimension: str = "region") -> list[Movement]:
        """Material movements this principal may see, most important first."""
        found = detect.scan(self.wh, period, principal.role, dimension)
        return detect.dedupe_overlapping(found)

    # ----------------------------------------------------------------- explain
    def explain(self, principal: Principal, kpi: str, period: Period,
                filters: Filters = None) -> InsightResult:
        run = telemetry.Run(insight_id=f"ins_{next(_counter):04d}",
                            principal=principal.name, role=principal.role)

        with run.stage("entitlement", "business_rules",
                       "row filter, column mask, KPI grant") as s:
            filters = principal.filters_for(kpi, filters)
            principal.view(self.wh.frame("sales_transactions"), kpi)
            s.detail = f"scoped to {filters or 'all'}"

        with run.stage("detection", "statistics",
                       "robust z against the slice's own history") as s:
            slice_label = ", ".join(f"{k}={v}" for k, v in (filters or {}).items()) or "all"
            nudge = self.store.materiality_nudge(kpi, slice_label)
            movement = detect.evaluate(self.wh, kpi, period, filters,
                                       threshold_multiplier=nudge)
            s.detail = (f"z={movement.z_score:.2f}, material={movement.material}"
                        + (f", feedback nudge x{nudge}" if nudge != 1.0 else ""))

        with run.stage("attribution", "deterministic_logic",
                       "price volume mix, must reconcile exactly") as s:
            pvm = attribute.price_volume_mix(self.wh, period, filters)
            by_account = attribute.by_dimension(self.wh, "net_revenue", period,
                                                "account_name", filters) \
                if kpi in ("net_revenue", "units_sold") else pvm

            # by_dimension() reads the warehouse directly, so it bypasses the
            # entitlement layer that masks columns -- and account_name is the
            # one column the contract masks. Without this, a role whose
            # narrative correctly refuses to name the customer still saw the
            # customer named in the attribution table, on a page that states
            # the opposite. Pseudonymise here, at the boundary, so the split
            # stays analysable while the identity does not leak.
            if (by_account is not pvm
                    and "account_name" in self.contract.masked_columns(
                        kpi, principal.role)):
                by_account.effects = [
                    e if e.name.startswith("all other")
                    else replace(e, name=pseudonymise(e.name))
                    for e in by_account.effects
                ]

            s.detail = f"residual={pvm.residual:.6f}, reconciled={pvm.reconciled}"

        with run.stage("causal_screen", "causal_inference",
                       "sequence, magnitude, mechanism") as s:
            assessment = causal.screen(self.wh, movement, pvm.effects, period, filters)
            assessment.verdicts = self.store.rerank(kpi, assessment.verdicts)
            s.detail = (f"confidence={assessment.confidence}, "
                        f"abstain={assessment.abstain}")

        with run.stage("evidence_retrieval", "retrieval", "bm25 over service_events") as s:
            # Every established driver, not only the evidential one. The
            # arithmetic drivers carry queries too, and 'volume' is the one
            # that finds the churn signal -- the passage that actually
            # explains why the units stopped arriving.
            drivers = [v.driver for v in assessment.causes]
            if not drivers:
                drivers = ["delivery_reliability"]
            passages = evidence.for_drivers(self.index, drivers, period, filters)
            driver = ", ".join(drivers)
            fresh = evidence.freshness_report(
                self.wh, list(self.contract.kpis[kpi].sources) + ["service_events"])
            s.detail = f"{len(passages)} passage(s) for '{driver}'"

        with run.stage("narrative", "llm" if self.client else "business_rules",
                       "synthesis only, every number injected") as s:
            insight = personas.build_insight(
                self.wh, principal, movement, pvm, by_account, assessment,
                passages, period, client=self.client)
            if self.client and insight.narrative.tokens_in:
                run.record_model_call(
                    s, model=getattr(self.client, "name", "narrator"),
                    tier="standard", tokens_in=insight.narrative.tokens_in,
                    tokens_out=insight.narrative.tokens_out,
                    ms=s.ms, purpose="persona narrative")
            s.detail = (f"renderer={insight.narrative.renderer}, "
                        f"guard violations={len(insight.narrative.violations)}")

        problems = run.verify()
        if problems:
            raise telemetry.TelemetryError("; ".join(problems))

        return InsightResult(insight=insight, run=run, movement=movement, pvm=pvm,
                             by_account=by_account, assessment=assessment,
                             evidence=passages, freshness=fresh)

    # ---------------------------------------------------------------- feedback
    def record_feedback(self, result: InsightResult, verdict: str,
                        principal: Principal, correct_driver: str | None = None,
                        note: str = "") -> Correction:
        stated = (result.assessment.verdicts[0].driver
                  if result.assessment.verdicts else None)
        corr = Correction(
            insight_id=result.insight_id, kpi=result.movement.kpi,
            slice_label=result.movement.slice_label, verdict=verdict,
            stated_driver=stated, correct_driver=correct_driver, note=note,
            by=principal.name, role=principal.role)
        self.store.record(corr)
        return corr
