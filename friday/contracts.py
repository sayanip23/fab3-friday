"""Semantic contract loader, validator, and entitlement resolver.

The contract at contracts/kpis.yaml is the single source of truth for every
KPI definition, threshold, driver, lineage rule, and access rule in FRIDAY.
No other module may hardcode any of these — they must come through this
loader. This module is what makes that rule enforceable rather than just
stated.
"""
from __future__ import annotations

import dataclasses
import pathlib
from typing import Any

import yaml

REQUIRED_KPI_FIELDS = ["description", "formula", "grain", "source", "unit",
                        "materiality", "lineage", "access"]
REQUIRED_MATERIALITY_FIELDS = ["method", "baseline_window_days", "threshold_z"]
REQUIRED_LINEAGE_FIELDS = ["source_tables", "max_staleness_hours"]


class ContractError(ValueError):
    """Raised when contracts/kpis.yaml is missing, malformed, or incomplete."""


@dataclasses.dataclass(frozen=True)
class Kpi:
    name: str
    description: str
    formula: str
    grain: list[str]
    source: Any
    unit: str
    drivers: list[str]
    materiality: dict
    lineage: dict
    access: dict


@dataclasses.dataclass(frozen=True)
class Role:
    name: str
    description: str
    scope: str
    masked_fields: list[str]
    decision_rights: list[str]


@dataclasses.dataclass(frozen=True)
class Contract:
    version: int
    business: dict
    roles: dict[str, Role]
    sources: dict[str, dict]
    kpis: dict[str, Kpi]
    policies: dict

    def get_kpi(self, name: str) -> Kpi:
        if name not in self.kpis:
            raise ContractError(
                f"'{name}' is not a defined KPI. Known KPIs: "
                f"{sorted(self.kpis)}. FRIDAY will not compute an "
                f"undefined metric."
            )
        return self.kpis[name]

    def get_role(self, name: str) -> Role:
        if name not in self.roles:
            raise ContractError(
                f"'{name}' is not a defined role. Known roles: {sorted(self.roles)}."
            )
        return self.roles[name]


def load_contract(path: str | pathlib.Path = "contracts/kpis.yaml") -> Contract:
    """Load and validate the KPI semantic contract.

    Raises ContractError with a specific, actionable message on any
    structural problem — a missing field fails loudly here rather than
    silently producing a wrong number three modules downstream.
    """
    path = pathlib.Path(path)
    if not path.exists():
        raise ContractError(f"Contract not found at {path}.")

    with open(path) as f:
        raw = yaml.safe_load(f)

    for top in ["version", "business", "roles", "sources", "kpis", "policies"]:
        if top not in raw:
            raise ContractError(f"Contract is missing top-level key '{top}'.")

    roles = {}
    for rname, rdef in raw["roles"].items():
        for field in ["description", "scope", "masked_fields", "decision_rights"]:
            if field not in rdef:
                raise ContractError(f"Role '{rname}' is missing field '{field}'.")
        roles[rname] = Role(name=rname, **rdef)

    kpis = {}
    for kname, kdef in raw["kpis"].items():
        missing = [f for f in REQUIRED_KPI_FIELDS if f not in kdef]
        if missing:
            raise ContractError(f"KPI '{kname}' is missing required field(s): {missing}.")
        mat_missing = [f for f in REQUIRED_MATERIALITY_FIELDS if f not in kdef["materiality"]]
        if mat_missing:
            raise ContractError(f"KPI '{kname}'.materiality is missing: {mat_missing}.")
        lin_missing = [f for f in REQUIRED_LINEAGE_FIELDS if f not in kdef["lineage"]]
        if lin_missing:
            raise ContractError(f"KPI '{kname}'.lineage is missing: {lin_missing}.")
        kpis[kname] = Kpi(
            name=kname,
            description=kdef["description"],
            formula=kdef["formula"],
            grain=kdef["grain"],
            source=kdef["source"],
            unit=kdef["unit"],
            drivers=kdef.get("drivers", []),
            materiality=kdef["materiality"],
            lineage=kdef["lineage"],
            access=kdef["access"],
        )

    if len(kpis) < 5:
        raise ContractError(
            f"Contract defines only {len(kpis)} KPIs; the Round 2 brief "
            f"requires three to five connected KPIs."
        )
    if len(roles) < 2:
        raise ContractError(
            f"Contract defines only {len(roles)} role(s); the brief requires "
            f"at least two personas with different narratives or actions."
        )

    return Contract(
        version=raw["version"],
        business=raw["business"],
        roles=roles,
        sources=raw["sources"],
        kpis=kpis,
        policies=raw["policies"],
    )


def resolve_entitlement(contract: Contract, role_name: str, kpi_name: str,
                         row: dict) -> dict:
    """Apply row- and column-level access rules for a role to a single record.

    Returns a copy of `row` with masked fields replaced by "[MASKED]", and
    raises ContractError if the role has no row-level access to this record
    at all (e.g. a regional director asking about a region that is not
    theirs). This is the only function in FRIDAY allowed to decide whether
    a row reaches a narrative — see friday/access.py, which calls this for
    every record before it is handed to evidence retrieval or narration.
    """
    role = contract.get_role(role_name)
    kpi = contract.get_kpi(kpi_name)

    if kpi.access.get("row_level") == "region_scope" and role.scope == "own_region":
        home_region = row.get("_role_home_region")
        if home_region is not None and row.get("region") != home_region:
            raise ContractError(
                f"Role '{role_name}' is scoped to '{home_region}' and has no "
                f"row-level access to region '{row.get('region')}'."
            )

    masked = dict(row)
    for field in role.masked_fields:
        if field in masked:
            masked[field] = "[MASKED]"
    return masked
