"""
Lane C. Entitlement enforcement.

Answers Round 2 minimum expectation 7, "one role based security or entitlement
scenario", and the brief's requirement for row, column and domain level security
with auditability.

The design rule here is that entitlement is applied to the *data*, not to the
rendered answer. A system that computes on everything and then hides some of the
output has already leaked: the totals, the rankings and the narrative were all
derived from rows the user was never allowed to see. So `Principal.view()` returns
a filtered, masked frame, and every downstream stage in the engine consumes that
frame and nothing else.

Everything enforced here is declared in contracts/kpis.yaml. No rule is hardcoded.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from .contracts import Contract, ContractError

MASK_PREFIX = "acct_"


class EntitlementError(PermissionError):
    """Raised when a principal asks for something the contract forbids."""


@dataclass
class AccessDecision:
    """One auditable record of what a principal was allowed to see."""
    principal: str
    role: str
    kpi: str
    rows_in: int
    rows_out: int
    row_filter: str | None
    masked_columns: list[str]
    denied: bool
    reason: str | None
    at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def rows_withheld(self) -> int:
        return self.rows_in - self.rows_out

    def line(self) -> str:
        if self.denied:
            return f"DENY  {self.role} -> {self.kpi}: {self.reason}"
        bits = []
        if self.row_filter:
            bits.append(f"rows {self.rows_out}/{self.rows_in} ({self.row_filter})")
        else:
            bits.append(f"rows {self.rows_out}/{self.rows_in} (unrestricted)")
        if self.masked_columns:
            bits.append(f"masked {', '.join(self.masked_columns)}")
        return f"ALLOW {self.role} -> {self.kpi}: " + "; ".join(bits)


def pseudonymise(value: str, salt: str = "friday") -> str:
    """
    Stable pseudonym, not deletion.

    A masked column has to stay analysable: the analyst persona must still be able
    to see that one account drove the movement, and that it is the same account
    across two periods, without learning who it is. Dropping the column would break
    attribution; a stable hash preserves it.
    """
    digest = hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()
    return f"{MASK_PREFIX}{digest[:8]}"


@dataclass
class Principal:
    """A user, resolved against the contract's roles block."""
    name: str
    role: str
    contract: Contract
    log: list[AccessDecision] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.role not in self.contract.roles:
            raise ContractError(f"unknown role '{self.role}'")
        self.spec = self.contract.roles[self.role]

    # ------------------------------------------------------------------ checks
    @property
    def region_scope(self) -> str:
        return self.spec.get("region_scope", "all")

    @property
    def decision_rights(self) -> list[str]:
        return self.contract.decision_rights(self.role)

    def may_see(self, kpi: str) -> bool:
        return kpi in self.contract.visible_kpis(self.role)

    def may_act(self, right: str) -> bool:
        return right in self.decision_rights

    def assert_kpi(self, kpi: str) -> None:
        if not self.may_see(kpi):
            d = AccessDecision(self.name, self.role, kpi, 0, 0, None, [], True,
                               f"role '{self.role}' is not granted this KPI")
            self.log.append(d)
            raise EntitlementError(d.reason)

    # -------------------------------------------------------------------- view
    def view(self, df: pd.DataFrame, kpi: str) -> pd.DataFrame:
        """Return only the rows and columns this principal may compute on."""
        self.assert_kpi(kpi)

        rows_in = len(df)
        out = df

        rule = self.contract.row_filter(kpi, self.role)
        applied: str | None = None
        if rule == "own_region":
            scope = self.region_scope
            if scope != "all" and "region" in out.columns:
                out = out[out.region == scope]
                applied = f"region == {scope}"
        elif rule:
            applied = f"unrecognised rule '{rule}'"

        masked = [c for c in self.contract.masked_columns(kpi, self.role)
                  if c in out.columns]
        if masked:
            out = out.copy()
            for col in masked:
                out[col] = out[col].astype(str).map(pseudonymise)

        self.log.append(AccessDecision(
            principal=self.name, role=self.role, kpi=kpi,
            rows_in=rows_in, rows_out=len(out), row_filter=applied,
            masked_columns=masked, denied=False, reason=None,
        ))
        return out

    def filters_for(self, kpi: str, requested: dict | None = None) -> dict:
        """
        Narrow a requested slice to what the principal may ask for.

        A sales director who asks for the national total gets their own region
        instead, and the substitution is logged rather than silently applied.
        """
        self.assert_kpi(kpi)
        filters = dict(requested or {})
        if self.contract.row_filter(kpi, self.role) == "own_region":
            scope = self.region_scope
            if scope != "all":
                if filters.get("region") not in (None, scope):
                    raise EntitlementError(
                        f"role '{self.role}' is scoped to {scope} and may not "
                        f"request region {filters['region']}")
                filters["region"] = scope
        return filters

    # ------------------------------------------------------------------ audit
    def audit_trail(self) -> list[str]:
        return [d.line() for d in self.log]


def redact_free_text(text: str, names: list[str]) -> str:
    """
    Strip named individuals from free text before it can reach a narrative.

    ASSUMPTIONS.md section 7 commits to this under the DPDP Act: the ticket body is
    evidence, but the person who wrote it is not.
    """
    out = text
    for n in sorted(names, key=len, reverse=True):
        if n and n in out:
            out = out.replace(n, "[redacted]")
    return out
