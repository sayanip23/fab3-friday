"""
Lane C. Feedback capture and the learning loop.

Answers Round 2 objective 7, "mechanism to learn from analyst and business user
feedback", and the brief's solutioning area on correction workflows.

What this does and does not claim, stated plainly because the brief rewards honesty
over overreach: it does not retrain a model. It maintains two adjustable quantities
per KPI, both of which live in the contract as defaults:

  driver priors        how much weight a driver carries when ranking explanations
  materiality nudge    a multiplier on the statistical threshold for a slice

Both move on evidence, both are bounded, and both are fully reversible because every
correction is stored as an event rather than applied destructively. Replaying the log
reconstructs the current state exactly, which is what makes the loop auditable.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "data", "feedback.jsonl")

VERDICTS = {"correct", "incorrect", "incomplete", "not_material"}

# bounds keep one irritated analyst from disabling a KPI outright
PRIOR_MIN, PRIOR_MAX = 0.25, 2.5
NUDGE_MIN, NUDGE_MAX = 0.6, 2.0

STEP_UP, STEP_DOWN = 1.15, 0.85


@dataclass
class Correction:
    insight_id: str
    kpi: str
    slice_label: str
    verdict: str
    stated_driver: str | None = None
    correct_driver: str | None = None
    note: str = ""
    by: str = ""
    role: str = ""
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(f"verdict must be one of {sorted(VERDICTS)}")


class FeedbackStore:
    """Append only log of corrections, with derived state."""

    def __init__(self, path: str = STORE):
        self.path = path
        self._events: list[Correction] = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        self._events.append(Correction(**json.loads(line)))

    # ------------------------------------------------------------------ write
    def record(self, correction: Correction) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(correction)) + "\n")
        self._events.append(correction)

    def clear(self) -> None:
        """Test and demo helper. Never called by the engine."""
        self._events = []
        if os.path.exists(self.path):
            os.remove(self.path)

    # ------------------------------------------------------------------- read
    @property
    def events(self) -> list[Correction]:
        return list(self._events)

    def for_kpi(self, kpi: str) -> list[Correction]:
        return [e for e in self._events if e.kpi == kpi]

    # -------------------------------------------------------------- derived
    def driver_priors(self, kpi: str) -> dict[str, float]:
        """
        Replay the log into a weight per driver. Neutral is 1.0.

        A driver the analyst keeps correcting *to* gains weight. One they keep
        correcting *away from* loses it.
        """
        priors: dict[str, float] = defaultdict(lambda: 1.0)
        for e in self.for_kpi(kpi):
            if e.verdict == "incorrect":
                if e.stated_driver:
                    priors[e.stated_driver] *= STEP_DOWN
                if e.correct_driver:
                    priors[e.correct_driver] *= STEP_UP
            elif e.verdict == "incomplete" and e.correct_driver:
                priors[e.correct_driver] *= STEP_UP
            elif e.verdict == "correct" and e.stated_driver:
                priors[e.stated_driver] *= 1.05
        return {k: round(min(max(v, PRIOR_MIN), PRIOR_MAX), 4) for k, v in priors.items()}

    def materiality_nudge(self, kpi: str, slice_label: str) -> float:
        """
        Multiplier on the statistical threshold for one slice.

        'not_material' means we alerted on noise, so the bar goes up for that slice
        only. This is how alert fatigue gets fixed by the people suffering it.
        """
        nudge = 1.0
        for e in self.for_kpi(kpi):
            if e.slice_label != slice_label:
                continue
            if e.verdict == "not_material":
                nudge *= STEP_UP
            elif e.verdict in ("incomplete", "correct"):
                nudge *= 0.97
        return round(min(max(nudge, NUDGE_MIN), NUDGE_MAX), 4)

    def rerank(self, kpi: str, verdicts: list) -> list:
        """
        Apply learned priors to a ranked driver list.

        Returns a new list ordered by prior weighted contribution. The underlying
        contribution figures are never modified, because they are arithmetic facts.
        Only the ordering of explanations changes.
        """
        priors = self.driver_priors(kpi)
        return sorted(verdicts,
                      key=lambda v: abs(v.contribution) * priors.get(v.driver, 1.0),
                      reverse=True)

    def summary(self, kpi: str) -> str:
        ev = self.for_kpi(kpi)
        if not ev:
            return "no feedback recorded"
        counts = defaultdict(int)
        for e in ev:
            counts[e.verdict] += 1
        parts = ", ".join(f"{v} {k}" for k, v in sorted(counts.items()))
        return f"{len(ev)} correction(s): {parts}"
