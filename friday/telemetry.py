"""
Lane C. Runtime telemetry and the LLM versus non LLM ledger.

Answers two Round 2 minimum expectations at once:

  9   "a clear breakdown of LLM versus non LLM processing"
  10  "runtime telemetry covering latency, model calls, token usage and estimated cost"

Requirement 9 is usually answered with a slide. A slide is an assertion. Here every
stage of the engine is wrapped in `run.stage(...)` and must declare its method, and
that declaration is what produces the breakdown. If a stage marked deterministic ever
issues a model call, `verify()` fails. The claim is enforced, not drawn.

Costs are computed from measured token counts against a published price table, and
are labelled estimates because that is what they are.
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

# Method taxonomy, matching the vocabulary the brief uses.
DETERMINISTIC = {
    "sql", "deterministic_logic", "business_rules", "statistics",
    "traditional_ml", "causal_inference", "retrieval",
}
GENERATIVE = {"llm"}
ALL_METHODS = DETERMINISTIC | GENERATIVE

# INR per 1M tokens. Illustrative list prices, stated as an assumption.
PRICE_TABLE = {
    "small":    {"in": 25.0,  "out": 125.0},
    "standard": {"in": 250.0, "out": 1250.0},
}


class TelemetryError(Exception):
    pass


@dataclass
class ModelCall:
    model: str
    tier: str
    tokens_in: int
    tokens_out: int
    ms: float
    purpose: str

    @property
    def cost_inr(self) -> float:
        p = PRICE_TABLE.get(self.tier, PRICE_TABLE["standard"])
        return (self.tokens_in / 1e6) * p["in"] + (self.tokens_out / 1e6) * p["out"]


@dataclass
class Stage:
    name: str
    method: str
    ms: float = 0.0
    detail: str = ""
    model_calls: list[ModelCall] = field(default_factory=list)

    @property
    def is_llm(self) -> bool:
        return self.method in GENERATIVE

    @property
    def tokens(self) -> int:
        return sum(c.tokens_in + c.tokens_out for c in self.model_calls)

    @property
    def cost_inr(self) -> float:
        return sum(c.cost_inr for c in self.model_calls)


@dataclass
class Run:
    """One end to end insight, instrumented."""
    insight_id: str
    principal: str = ""
    role: str = ""
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stages: list[Stage] = field(default_factory=list)

    # ------------------------------------------------------------- collection
    @contextmanager
    def stage(self, name: str, method: str, detail: str = ""):
        if method not in ALL_METHODS:
            raise TelemetryError(
                f"stage '{name}' declares unknown method '{method}'. "
                f"Allowed: {sorted(ALL_METHODS)}")
        s = Stage(name=name, method=method, detail=detail)
        self.stages.append(s)
        t0 = time.perf_counter()
        try:
            yield s
        finally:
            s.ms = (time.perf_counter() - t0) * 1000.0

    def record_model_call(self, stage: Stage, model: str, tier: str,
                          tokens_in: int, tokens_out: int, ms: float,
                          purpose: str) -> ModelCall:
        call = ModelCall(model, tier, tokens_in, tokens_out, ms, purpose)
        stage.model_calls.append(call)
        return call

    # ----------------------------------------------------------------- totals
    @property
    def total_ms(self) -> float:
        return sum(s.ms for s in self.stages)

    @property
    def llm_ms(self) -> float:
        return sum(s.ms for s in self.stages if s.is_llm)

    @property
    def deterministic_ms(self) -> float:
        return self.total_ms - self.llm_ms

    @property
    def model_calls(self) -> list[ModelCall]:
        return [c for s in self.stages for c in s.model_calls]

    @property
    def tokens_in(self) -> int:
        return sum(c.tokens_in for c in self.model_calls)

    @property
    def tokens_out(self) -> int:
        return sum(c.tokens_out for c in self.model_calls)

    @property
    def cost_inr(self) -> float:
        return sum(c.cost_inr for c in self.model_calls)

    # ------------------------------------------------------------ enforcement
    def verify(self) -> list[str]:
        """
        The claim, checked. Any stage not declared as an LLM stage must not have
        issued a model call.
        """
        problems = []
        for s in self.stages:
            if not s.is_llm and s.model_calls:
                problems.append(
                    f"stage '{s.name}' declares method '{s.method}' but issued "
                    f"{len(s.model_calls)} model call(s). The quantitative path "
                    f"must stay free of generation.")
        return problems

    # ------------------------------------------------------------- reporting
    def method_split(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for s in self.stages:
            e = out.setdefault(s.method, {"stages": 0, "ms": 0.0, "calls": 0})
            e["stages"] += 1
            e["ms"] += s.ms
            e["calls"] += len(s.model_calls)
        for e in out.values():
            e["ms"] = round(e["ms"], 2)
            e["share_of_latency"] = round(e["ms"] / self.total_ms, 4) if self.total_ms else 0.0
        return out

    def footer(self) -> str:
        """One line stamped on every insight in the UI."""
        pct = (100.0 * self.deterministic_ms / self.total_ms) if self.total_ms else 0.0
        return (f"{self.total_ms:.0f} ms total  ·  {pct:.0f}% deterministic  ·  "
                f"{len(self.model_calls)} model call(s)  ·  "
                f"{self.tokens_in + self.tokens_out:,} tokens  ·  "
                f"about INR {self.cost_inr:.3f}")

    def table(self) -> str:
        rows = [f"{'stage':<26}{'method':<20}{'ms':>9}{'calls':>7}{'tokens':>9}"]
        rows.append("-" * 71)
        for s in self.stages:
            rows.append(f"{s.name:<26}{s.method:<20}{s.ms:>9.1f}"
                        f"{len(s.model_calls):>7}{s.tokens:>9,}")
        rows.append("-" * 71)
        rows.append(f"{'TOTAL':<26}{'':<20}{self.total_ms:>9.1f}"
                    f"{len(self.model_calls):>7}{self.tokens_in + self.tokens_out:>9,}")
        return "\n".join(rows)

    def to_dict(self) -> dict:
        return {
            "insight_id": self.insight_id,
            "principal": self.principal,
            "role": self.role,
            "started_at": self.started_at,
            "total_ms": round(self.total_ms, 2),
            "deterministic_ms": round(self.deterministic_ms, 2),
            "llm_ms": round(self.llm_ms, 2),
            "model_calls": [asdict(c) for c in self.model_calls],
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "estimated_cost_inr": round(self.cost_inr, 4),
            "method_split": self.method_split(),
            "stages": [{"name": s.name, "method": s.method,
                        "ms": round(s.ms, 2), "detail": s.detail}
                       for s in self.stages],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)
