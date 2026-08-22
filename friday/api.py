"""
JSON API over the engine.

The Streamlit app and this API are two front doors onto the *same* `Engine`.
Neither computes anything itself — that matters, because a console showing
numbers it derived independently would prove nothing about the engine.

Run:  python -m uvicorn friday.api:app --port 8000
"""
from __future__ import annotations

import io
from datetime import date
from functools import lru_cache

import pandas as pd
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from . import byod, contracts
from .access import EntitlementError, Principal
from .engine import Engine
from .kpi import Period

PERIOD = Period(date(2026, 7, 24), date(2026, 8, 20))

USERS = {
    "sales_director": ("R. Mehta", "Regional Sales Director, West"),
    "cfo": ("S. Iyer", "Chief Financial Officer"),
    "analyst": ("A. Rao", "Junior Analyst"),
}

app = FastAPI(title="FRIDAY Engine API", version="1.0.0")

# The console is served by Vite on another port, so the browser treats it as a
# different origin. Restricted to localhost: this is a demo API with no auth,
# and it must not be reachable from a page the user did not open themselves.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:4173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Built once. Loading the contract and BM25 index per request would make
    every call an order of magnitude slower than the analysis itself."""
    return Engine(contracts.load())


def principal_for(role: str) -> Principal:
    if role not in USERS:
        raise HTTPException(404, f"unknown role '{role}'")
    name, _ = USERS[role]
    return Principal(name, role, get_engine().contract)


# ─────────────────────────────────────────────────────────────── meta
@app.get("/health")
def health() -> dict:
    eng = get_engine()
    return {
        "status": "ok",
        "kpis": len(eng.contract.kpis),
        "sources": len(eng.contract.sources),
        "period": str(PERIOD),
    }


@app.get("/roles")
def roles() -> list[dict]:
    eng = get_engine()
    out = []
    for key, (name, label) in USERS.items():
        spec = eng.contract.roles[key]
        out.append({
            "id": key,
            "name": name,
            "label": label,
            "scope": spec.get("region_scope", "all"),
            "visibleKpis": len(eng.contract.visible_kpis(key)),
            "totalKpis": len(eng.contract.kpis),
            "decisionRights": eng.contract.decision_rights(key),
            "masksAccounts": not spec.get("can_see_account_names", True),
        })
    return out


# ─────────────────────────────────────────────────────────────── alerts
@app.get("/alerts")
def alerts(role: str = Query("cfo")) -> list[dict]:
    eng = get_engine()
    p = principal_for(role)
    return [{
        "kpi": m.kpi,
        "label": m.label,
        "slice": m.slice_label,
        "filters": m.filters,
        "current": None if m.current != m.current else round(m.current, 2),
        "prior": None if m.prior != m.prior else round(m.prior, 2),
        "delta": None if m.delta != m.delta else round(m.delta, 2),
        "pct": None if m.pct != m.pct else round(m.pct, 2),
        "unit": m.unit,
        "z": None if m.z_score != m.z_score else round(m.z_score, 2),
        "priority": m.priority,
        "sparse": m.sparse,
    } for m in eng.alerts(p, PERIOD)]


# ────────────────────────────────────────────────────────────── explain
@app.get("/explain")
def explain(role: str = Query("cfo"), kpi: str = Query("net_revenue"),
            region: str | None = Query(None)) -> dict:
    eng = get_engine()
    p = principal_for(role)
    filters = {"region": region} if region else None

    try:
        r = eng.explain(p, kpi, PERIOD, filters)
    except EntitlementError as e:
        # 403 rather than 500: being refused is a correct outcome here, and the
        # console renders it as a feature rather than an error.
        raise HTTPException(403, str(e)) from e
    except Exception as e:                                   # noqa: BLE001
        raise HTTPException(400, f"{type(e).__name__}: {e}") from e

    ins, mv, assess = r.insight, r.movement, r.assessment
    root = next((v for v in assess.causes if v.kind == "evidential"), None)
    lever = next((v for v in assess.causes if v.kind == "arithmetic"), None)

    return {
        "insightId": r.insight_id,
        "persona": ins.persona,
        "headline": ins.headline,
        "narrative": ins.narrative.text,
        "renderer": ins.narrative.renderer,
        "guardViolations": ins.narrative.violations,
        "masked": ins.masked,
        "movement": {
            "kpi": mv.kpi, "label": mv.label, "slice": mv.slice_label,
            "current": round(mv.current, 2), "prior": round(mv.prior, 2),
            "delta": round(mv.delta, 2), "pct": round(mv.pct, 2),
            "unit": mv.unit,
            "z": None if mv.z_score != mv.z_score else round(mv.z_score, 2),
            "normalSwing": None if mv.baseline_median_pct != mv.baseline_median_pct
                           else round(abs(mv.baseline_median_pct), 2),
            "material": mv.material, "sparse": mv.sparse,
        },
        "confidence": assess.confidence,
        "abstained": assess.abstain,
        "abstainReasons": assess.abstain_reasons,
        "nextCheck": assess.discriminating_check,
        "chain": {
            "rootCause": root.driver.replace("_", " ") if root else None,
            "rootStrength": round(root.strength, 1) if root else None,
            "lever": lever.driver if lever else None,
            "leverShare": round(lever.share, 4) if lever else None,
        },
        "contributions": r.pvm.as_frame().to_dict("records"),
        "reconciled": r.pvm.reconciled,
        "residual": r.pvm.residual,
        "byAccount": (r.by_account.as_frame().head(6).to_dict("records")
                      if r.by_account is not r.pvm else []),
        "gates": [{
            "driver": v.driver, "kind": v.kind,
            "share": round(v.share, 4), "strength": round(v.strength, 2),
            "sequence": v.sequence_ok, "magnitude": v.magnitude_ok,
            "mechanism": v.mechanism_ok, "status": v.status,
            "reasons": v.reasons,
        } for v in assess.verdicts],
        "evidence": [{
            "text": p_.text, "date": p_.when.isoformat(), "kind": p_.kind,
            "source": p_.source, "score": round(p_.score, 3),
            "ageDays": p_.age_days,
        } for p_ in r.evidence],
        "freshness": r.freshness,
        "actions": [a.as_dict() for a in ins.actions],
        "factPack": ins.facts.lineage() if ins.facts else [],
        "telemetry": {
            "totalMs": round(r.run.total_ms, 1),
            "deterministicMs": round(r.run.deterministic_ms, 1),
            "llmMs": round(r.run.llm_ms, 1),
            "modelCalls": len(r.run.model_calls),
            "tokens": r.run.tokens_in + r.run.tokens_out,
            "costInr": round(r.run.cost_inr, 4),
            "stages": [{"name": s.name, "method": s.method,
                        "ms": round(s.ms, 2), "detail": s.detail}
                       for s in r.run.stages],
            "methodSplit": r.run.method_split(),
            "violations": r.run.verify(),
        },
    }


@app.get("/series")
def series(kpi: str = Query("net_revenue"), region: str | None = Query(None),
           days: int = Query(120, ge=14, le=400)) -> list[dict]:
    """Daily values for sparklines. Straight from the warehouse, no smoothing."""
    eng = get_engine()
    filters = {"region": region} if region else None
    start = PERIOD.end.replace()  # copy
    from datetime import timedelta
    start = PERIOD.end - timedelta(days=days - 1)
    try:
        s, _ = eng.wh.series(kpi, start, PERIOD.end, filters)
    except Exception as e:                                   # noqa: BLE001
        raise HTTPException(400, str(e)) from e
    return [{"date": str(d), "value": None if v != v else round(float(v), 2)}
            for d, v in s.items()]


# ───────────────────────────────────────────────────────── bring your own
@app.post("/analyse")
async def analyse(file: UploadFile = File(...), window: int = Query(28)) -> dict:
    """Same pipeline, on a file the engine has never seen."""
    raw = await file.read()
    if len(raw) > 12_000_000:
        raise HTTPException(413, "file too large (12 MB limit)")
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as e:                                   # noqa: BLE001
        raise HTTPException(400, f"could not read CSV: {e}") from e

    a = byod.analyse(df, window=window)
    p = a.profile

    return {
        "filename": file.filename,
        "profile": {
            "rows": p.rows, "dateColumn": p.date_column,
            "measures": p.measures, "dimensions": p.dimensions,
            "dateMin": p.date_min, "dateMax": p.date_max,
            "spanDays": p.span_days, "supportsPvm": p.supports_pvm,
            "warnings": p.warnings,
        },
        "period": str(a.period), "prior": str(a.prior),
        "errors": a.errors,
        "findings": [{
            "kpi": f.kpi, "label": f.label,
            "current": None if f.movement.current != f.movement.current
                       else round(f.movement.current, 2),
            "prior": None if f.movement.prior != f.movement.prior
                     else round(f.movement.prior, 2),
            "pct": None if f.movement.pct != f.movement.pct else round(f.movement.pct, 2),
            "z": None if f.movement.z_score != f.movement.z_score
                 else round(f.movement.z_score, 2),
            "material": f.movement.material,
            "confidence": f.assessment.confidence,
            "abstained": f.assessment.abstain,
            "abstainReasons": f.assessment.abstain_reasons,
            "dimension": f.dimension,
            "contributions": (f.contribution.as_frame().to_dict("records")
                              if f.contribution else []),
            "reconciled": f.contribution.reconciled if f.contribution else None,
            "narrative": f.insight.narrative.text if f.insight else None,
            "notes": f.notes,
            "telemetry": {"totalMs": round(f.run.total_ms, 1),
                          "modelCalls": len(f.run.model_calls)},
        } for f in a.findings],
    }
