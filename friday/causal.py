"""Lane A — causal screen.

Decides whether an attributed driver may be stated as a *cause*, or whether
FRIDAY must abstain. Per contracts/kpis.yaml policies.low_confidence, a
causal claim requires all three of: sequence (evidence precedes the
effect), magnitude (evidence intensity plausibly matches the size of the
effect), and mechanism (the evidence type is a recognized way that cause
could produce that effect). Failing any one means abstain and say why —
this is the one function in FRIDAY that is not allowed to be persuaded by
a compelling-sounding narrative alone.
"""
from __future__ import annotations

import dataclasses

import pandas as pd

# Which service_event types are recognized mechanisms for which kind of
# effect. Deliberately conservative and explicit — an inquiry alone is not
# a mechanism for an account going silent, no matter how well it correlates.
MECHANISM_MAP = {
    "account_revenue_loss": {"complaint", "crm_note"},
}


@dataclasses.dataclass(frozen=True)
class CausalScreenResult:
    segment: str
    effect: str
    sequence_ok: bool
    magnitude_ok: bool
    mechanism_ok: bool
    passed: bool
    confidence: str          # "high" | "medium" | "abstain"
    reason: str
    evidence_count: int


def _segment_evidence(events: pd.DataFrame, account_name: str) -> pd.DataFrame:
    e = events[events["account_name"] == account_name].copy()
    e["timestamp"] = pd.to_datetime(e["timestamp"])
    return e.sort_values("timestamp")


def _sequence_check(evidence: pd.DataFrame, effect_date: pd.Timestamp) -> tuple[bool, str]:
    leading = evidence[evidence["timestamp"] < effect_date]
    if len(leading) == 0:
        return False, "no evidence predates the effect date"
    return True, f"{len(leading)} evidence record(s) predate {effect_date.date()}"


def _magnitude_check(evidence: pd.DataFrame, effect_date: pd.Timestamp,
                      baseline_weeks: int = 8, surge_ratio_threshold: float = 2.0) -> tuple[bool, str]:
    """Compares the complaint rate in the weeks immediately before the
    effect date to the account's own earlier baseline rate. A real
    escalation should show a step change, not just noise."""
    complaints = evidence[evidence["event_type"] == "complaint"]
    if len(complaints) == 0:
        return False, "no complaint-type evidence to assess magnitude"

    pre_window_start = effect_date - pd.Timedelta(weeks=4)
    recent = complaints[(complaints["timestamp"] >= pre_window_start) & (complaints["timestamp"] < effect_date)]
    baseline_start = pre_window_start - pd.Timedelta(weeks=baseline_weeks)
    baseline = complaints[(complaints["timestamp"] >= baseline_start) & (complaints["timestamp"] < pre_window_start)]

    recent_rate = len(recent) / 4.0
    baseline_rate = len(baseline) / baseline_weeks if baseline_weeks else 0.0

    if baseline_rate == 0:
        ok = recent_rate > 0
        return ok, f"baseline rate was 0/week, recent rate {recent_rate:.2f}/week"

    ratio = recent_rate / baseline_rate
    ok = ratio >= surge_ratio_threshold
    return ok, f"recent rate {recent_rate:.2f}/week vs baseline {baseline_rate:.2f}/week ({ratio:.1f}x)"


def _mechanism_check(evidence: pd.DataFrame, effect: str) -> tuple[bool, str]:
    allowed_types = MECHANISM_MAP.get(effect, set())
    present_types = set(evidence["event_type"].unique())
    matched = present_types & allowed_types
    if not matched:
        return False, f"no evidence of a recognized mechanism type for '{effect}' (need one of {sorted(allowed_types)})"
    return True, f"evidence includes recognized mechanism type(s): {sorted(matched)}"


def screen_account_effect(events: pd.DataFrame, account_name: str, effect_date: pd.Timestamp,
                           effect: str = "account_revenue_loss") -> CausalScreenResult:
    """Run the sequence/magnitude/mechanism screen for one account-level
    effect (e.g. an account going silent). Returns a result that states
    plainly which criteria passed — never just a single confidence number
    with no way to audit it.
    """
    evidence = _segment_evidence(events, account_name)

    seq_ok, seq_reason = _sequence_check(evidence, effect_date)
    mag_ok, mag_reason = _magnitude_check(evidence, effect_date)
    mech_ok, mech_reason = _mechanism_check(evidence, effect)

    passed = seq_ok and mag_ok and mech_ok
    if passed:
        confidence = "high"
        reason = f"all criteria satisfied — sequence: {seq_reason}; magnitude: {mag_reason}; mechanism: {mech_reason}"
    else:
        confidence = "abstain"
        failed = [name for name, ok in [("sequence", seq_ok), ("magnitude", mag_ok), ("mechanism", mech_ok)] if not ok]
        reason = f"abstaining — failed criteria: {failed}. sequence: {seq_reason}; magnitude: {mag_reason}; mechanism: {mech_reason}"

    return CausalScreenResult(
        segment=account_name,
        effect=effect,
        sequence_ok=seq_ok,
        magnitude_ok=mag_ok,
        mechanism_ok=mech_ok,
        passed=passed,
        confidence=confidence,
        reason=reason,
        evidence_count=len(evidence),
    )
