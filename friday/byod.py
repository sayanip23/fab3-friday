"""
Bring-your-own-data analysis.

One entry point that takes a DataFrame and returns the same kind of finding the
demo path produces, so a judge can point the engine at their own file.

The deliberate design choice here is that this module contains *no analysis*.
It profiles, synthesises a contract, injects the frame, and then calls exactly
the same detect / attribute / causal / narrate stages the bundled dataset uses.
If uploaded data got its own quieter code path, "it works on your data too"
would be a claim rather than a demonstration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from . import attribute, causal, detect, narrate, personas, profile as prof, telemetry
from .access import Principal
from .contracts import Contract
from .kpi import Period, Warehouse

SOURCE = "uploaded"


@dataclass
class Finding:
    """One analysed KPI on the uploaded data."""
    kpi: str
    label: str
    movement: detect.Movement
    assessment: causal.Assessment
    contribution: attribute.Decomposition | None
    dimension: str | None
    insight: personas.Insight | None
    run: telemetry.Run
    notes: list[str] = field(default_factory=list)


@dataclass
class Analysis:
    profile: prof.Profile
    period: Period
    prior: Period
    findings: list[Finding] = field(default_factory=list)
    contract: Contract | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def material(self) -> list[Finding]:
        return [f for f in self.findings if f.movement.material]


def choose_periods(df: pd.DataFrame, window: int | None = None) -> tuple[Period, Period]:
    """
    Two equal, adjacent windows ending at the last date in the file.

    Equal length matters more than the specific size: comparing a 31-day month
    against a 28-day one manufactures a movement out of the calendar.
    """
    last = max(df["_d"])
    first = min(df["_d"])
    span = (last - first).days + 1

    if window is None:
        # Prefer 28 days; shrink for short files so something can still run.
        window = 28 if span >= 84 else max(7, span // 3)

    cur_start = last - timedelta(days=window - 1)
    current = Period(cur_start, last)
    return current, current.shifted(window)


def analyse(df: pd.DataFrame, window: int | None = None,
            client: narrate.LLMClient | None = None,
            max_kpis: int = 6) -> Analysis:
    """Profile, contract, then run the standard pipeline over every measure."""
    profile = prof.profile_frame(df)

    if not profile.usable:
        reason = (
            "no usable date column" if not profile.date_column
            else "no numeric measure column" if not profile.measures
            else f"only {profile.rows} rows"
        )
        return Analysis(profile=profile, period=Period(date.today(), date.today()),
                        prior=Period(date.today(), date.today()),
                        errors=[f"Cannot analyse this file: {reason}."])

    frame = prof.normalise(df, profile)
    if frame.empty:
        return Analysis(profile=profile, period=Period(date.today(), date.today()),
                        prior=Period(date.today(), date.today()),
                        errors=["Every row failed date parsing."])

    raw = prof.build_contract(profile, frame, SOURCE)
    contract = Contract(raw)
    wh = Warehouse(contract, frames={SOURCE: frame})

    current, prior = choose_periods(frame, window)
    principal = Principal("Data owner", "owner", contract)

    analysis = Analysis(profile=profile, period=current, prior=prior, contract=contract)

    for kpi in list(contract.kpis)[:max_kpis]:
        try:
            analysis.findings.append(
                _one(wh, contract, principal, kpi, current, profile, client)
            )
        except Exception as exc:                      # noqa: BLE001
            # One bad column must not take the whole upload down.
            analysis.errors.append(f"{kpi}: {type(exc).__name__}: {exc}")

    # Most important first, same prioritisation the demo path uses.
    analysis.findings.sort(key=lambda f: (f.movement.material, f.movement.priority),
                           reverse=True)
    return analysis


def _one(wh: Warehouse, contract: Contract, principal: Principal, kpi: str,
         period: Period, profile: prof.Profile,
         client: narrate.LLMClient | None) -> Finding:
    run = telemetry.Run(insight_id=f"byod_{kpi[:16]}", principal=principal.name,
                        role=principal.role)
    notes: list[str] = []

    with run.stage("detection", "statistics", "robust z against the file's own history") as s:
        movement = detect.evaluate(wh, kpi, period, None)
        s.detail = f"z={movement.z_score:.2f}, material={movement.material}"

    # Attribution over the dimension that explains the most of the movement.
    contribution, best_dim = None, None
    with run.stage("attribution", "deterministic_logic", "contribution by dimension") as s:
        best_share = 0.0
        for dim in profile.dimensions:
            try:
                d = attribute.by_dimension(wh, kpi, period, dim, None)
            except ValueError:
                continue
            if not d.effects:
                continue
            share = max(abs(e.share) for e in d.effects)
            if share > best_share:
                contribution, best_dim, best_share = d, dim, share
        s.detail = (f"best dimension '{best_dim}' at {best_share:.0%}"
                    if best_dim else "no usable dimension")

    if not profile.supports_pvm:
        notes.append(
            "Price, volume and mix cannot be separated for this file: that "
            "decomposition needs a unit-count column and a unit-price column. "
            "Contribution by segment is shown instead."
        )

    with run.stage("causal_screen", "causal_inference", "sequence, magnitude, mechanism") as s:
        effects = contribution.effects if contribution else []
        # Segments are not levers: without a text corpus the engine may report
        # where a movement sits, never why it happened.
        assessment = causal.screen(wh, movement, effects, period, None,
                                   allow_causal_claims=False)
        s.detail = f"confidence={assessment.confidence}, abstain={assessment.abstain}"

    notes.append(
        "No free-text source was supplied, so no upstream cause could be "
        "corroborated. Findings are reported as associations."
    )

    insight = None
    with run.stage("narrative", "llm" if client else "business_rules",
                   "synthesis only, every number injected") as s:
        try:
            by_acct = contribution if contribution else attribute.Decomposition(
                method="none", total_movement=movement.delta, effects=[],
                residual=0.0, reconciled=True)
            insight = personas.build_insight(
                wh, principal, movement,
                contribution or by_acct, by_acct, assessment, [], period, client=client)
            s.detail = f"renderer={insight.narrative.renderer}"
        except Exception as exc:                      # noqa: BLE001
            notes.append(f"Narrative unavailable: {type(exc).__name__}")

    problems = run.verify()
    if problems:
        notes.append("; ".join(problems))

    return Finding(kpi=kpi, label=contract.kpis[kpi].label, movement=movement,
                   assessment=assessment, contribution=contribution,
                   dimension=best_dim, insight=insight, run=run, notes=notes)
