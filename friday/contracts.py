"""
Load and validate the KPI semantic contract.

Every other module in FRIDAY reads KPI meaning from here. Nothing is allowed to
hardcode a definition, threshold, driver list or access rule.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACT_PATH = os.path.join(ROOT, "contracts", "kpis.yaml")

REQUIRED_KPI_FIELDS = [
    "label", "definition", "formula", "calculation_method", "time_grain",
    "unit", "direction", "drivers", "materiality", "min_history_days",
    "lineage", "access",
]

REQUIRED_SOURCE_FIELDS = [
    "label", "grain", "time_grain", "refresh_cadence", "expected_lag_hours", "file",
]


class ContractError(Exception):
    """Raised when the contract is structurally invalid."""


@dataclass(frozen=True)
class KPI:
    name: str
    spec: dict[str, Any]

    def __getattr__(self, item: str) -> Any:
        try:
            return self.spec[item]
        except KeyError as exc:
            raise AttributeError(f"KPI '{self.name}' has no field '{item}'") from exc

    @property
    def sources(self) -> list[str]:
        if "sources" in self.spec:
            return list(self.spec["sources"])
        if "source" in self.spec:
            return [self.spec["source"]]
        return []

    @property
    def controllable_drivers(self) -> list[dict]:
        return [d for d in self.spec["drivers"] if d.get("controllable")]

    def thresholds(self) -> tuple[dict, dict, bool]:
        m = self.spec["materiality"]
        return m.get("statistical", {}), m.get("business", {}), m.get("require_both", True)


class Contract:
    def __init__(self, raw: dict[str, Any]):
        self.raw = raw
        self.sources: dict[str, dict] = raw.get("sources", {})
        self.dimensions: dict[str, dict] = raw.get("dimensions", {})
        self.roles: dict[str, dict] = raw.get("roles", {})
        self.kpis: dict[str, KPI] = {n: KPI(n, s) for n, s in raw.get("kpis", {}).items()}
        self.sparse_policy: dict = raw.get("sparse_history_policy", {})
        self.action_schema: dict = raw.get("action_schema", {})
        self.abstention: dict = raw.get("abstention", {})

    # ---------------------------------------------------------------- access
    def visible_kpis(self, role: str) -> list[str]:
        if role not in self.roles:
            raise ContractError(f"unknown role '{role}'")
        allowed = set(self.roles[role].get("kpis", []))
        return [n for n, k in self.kpis.items()
                if n in allowed and role in k.spec["access"].get("roles_allowed", [])]

    def row_filter(self, kpi: str, role: str) -> str | None:
        """Returns 'own_region' style token, or None for unrestricted."""
        rules = self.kpis[kpi].spec["access"].get("row_level_filter", {})
        return rules.get(role)

    def masked_columns(self, kpi: str, role: str) -> list[str]:
        rules = self.kpis[kpi].spec["access"].get("column_masking", {})
        cols = list(rules.get(role, []))
        if not self.roles.get(role, {}).get("can_see_account_names", True):
            if "account_name" not in cols:
                cols.append("account_name")
        return cols

    def decision_rights(self, role: str) -> list[str]:
        return list(self.roles.get(role, {}).get("decision_rights", []))

    # ------------------------------------------------------------ validation
    def validate(self) -> list[str]:
        problems: list[str] = []

        if not self.sources:
            problems.append("no sources declared")
        for name, spec in self.sources.items():
            for f in REQUIRED_SOURCE_FIELDS:
                if f not in spec:
                    problems.append(f"source '{name}' missing '{f}'")

        if not self.kpis:
            problems.append("no kpis declared")
        for name, kpi in self.kpis.items():
            for f in REQUIRED_KPI_FIELDS:
                if f not in kpi.spec:
                    problems.append(f"kpi '{name}' missing '{f}'")
            for src in kpi.sources:
                if src not in self.sources:
                    problems.append(f"kpi '{name}' references unknown source '{src}'")
            for dep in kpi.spec.get("depends_on", []):
                if dep not in self.kpis:
                    problems.append(f"kpi '{name}' depends on unknown kpi '{dep}'")
            for role in kpi.spec.get("access", {}).get("roles_allowed", []):
                if role not in self.roles:
                    problems.append(f"kpi '{name}' grants access to unknown role '{role}'")
            for d in kpi.spec.get("drivers", []):
                if "controllable" not in d or "lever" not in d:
                    problems.append(f"kpi '{name}' driver '{d.get('name')}' "
                                    f"missing controllable/lever")

        if not self.action_schema.get("required_fields"):
            problems.append("action_schema.required_fields is empty")
        if not self.abstention.get("abstain_when"):
            problems.append("abstention.abstain_when is empty")

        return problems


def load(path: str = CONTRACT_PATH, strict: bool = True) -> Contract:
    with open(path, encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    c = Contract(raw)
    if strict:
        problems = c.validate()
        if problems:
            raise ContractError("invalid contract:\n  " + "\n  ".join(problems))
    return c
