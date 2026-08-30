# FRIDAY — Round 2 Assumptions

Team Fab3 · Accenture Innovation Challenge 2026 · Track 3, BusinessIntelligence.ai

The Round 2 brief says teams are not expected to have access to real proprietary data, and
should "use reasonable assumptions and state them clearly". This file is that statement.
Everything the prototype does is traceable back to a decision recorded here.

---

## 1. The business we are modelling

A mid size B2B distributor selling four product lines through three channels across four
Indian regions. Ten named corporate accounts, all of them large enough to move a regional
number on their own, which is what makes single account attribution meaningful.
Twelve month revenue of INR 30.9 crore, measured from the generated data
rather than assumed. Materiality thresholds in the contract are calibrated to this scale.

This shape was chosen because it produces genuine price, volume and mix interaction, which
is what the brief asks us to separate.

## 2. Data sources (three, deliberately mismatched)

| Source | Grain | Refresh cadence | Lag | Nature |
|---|---|---|---|---|
| `sales_transactions` | Order line, daily | Nightly 02:00 IST | 6 h | Structured |
| `marketing_spend` | Campaign, weekly | Mondays 09:00 IST | 72 h | Structured, coarser grain |
| `service_events` | Event level | Every 15 min | 15 min | Semi structured, free text |

The mismatch is the point. Requirement 2 of the brief asks the engine to reconcile business
context across heterogeneous sources with different refresh cadences and granularities. A
weekly KPI that divides daily revenue by weekly spend cannot be computed without an explicit
grain reconciliation step, and the engine must know that the marketing figure is up to three
days stale before it is allowed to attribute anything to it.

## 3. KPIs

Five connected KPIs, related by identity rather than by coincidence, so that contribution
analysis reconciles exactly:

```
net_revenue      = units_sold × avg_selling_price      (exact identity, enables price/volume/mix)
gross_margin_pct = (revenue − cost) / revenue
marketing_efficiency = weekly net_revenue / weekly marketing_spend   (crosses two grains)
```

Full definitions, formulas, thresholds, lineage and access rules live in
`contracts/kpis.yaml`. Nothing in the codebase is allowed to hardcode a KPI definition.

## 4. Time frame

- History generated: 2025-09-01 to 2026-08-20
- Current period under analysis: 2026-07-24 to 2026-08-20 (28 days)
- Comparison period: 2026-06-26 to 2026-07-23 (28 days)

Equal length periods avoid a calendar artefact being mistaken for a business movement.

## 5. Ground truth we planted

The prototype must be verifiable, so the movement has a known answer. The engine is never
told any of this; it has to recover it from the data.

| Event | Date | Intended effect |
|---|---|---|
| West warehouse changes logistics provider | 2026-06-14 | Root cause, upstream |
| Acme Corp delivery complaints rise sharply | from 2026-06-20 | Text evidence trail |
| CRM note: "evaluating alternative suppliers" | weekly from 2026-07-22 | Text evidence. Account review notes recur weekly, so the retrieved copy is the most recent one inside the analysis window, not the first. The precedence claim rests on the delivery reliability change point of 2026-06-14, not on this note |
| Acme Corp stops ordering | from 2026-07-28 | **Volume** effect, large |
| Aurora line discounted in West | from 2026-08-01 | **Price** effect |
| Demand shifts toward lower priced Vertex | through August | **Mix** effect |
| Nova product line launches | 2026-07-31 | **Sparse history** scenario, 21 days only |

This satisfies the brief's requirement for one multi factor KPI movement with known
underlying drivers, and one sparse history scenario.

## 6. Personas

| Persona | Sees | Cares about | Decision rights |
|---|---|---|---|
| Regional Sales Director (West) | Account names, own region only | Retaining Acme | Can call the customer, can approve a service recovery |
| Chief Financial Officer | All regions, account names, margin detail | Margin erosion from discounting | Can approve or withdraw pricing action |
| Junior Analyst | All regions, **account names masked** | Producing the weekly pack | No action rights |

The same KPI movement produces three different narratives and three different recommended
actions. The third persona also serves the role based security requirement.

## 7. Regulatory and security posture

- Jurisdiction assumed: India, Digital Personal Data Protection Act 2023.
- Account names and buyer contact details are treated as commercially sensitive rather than
  personal data, but are masked by entitlement anyway.
- Free text in `service_events` may contain named individuals. It is redacted on ingest, in
  `Warehouse._redact`, before retrieval, the fact pack or the audit record can see it — a name
  removed from the narrative but left in the audit log has not been protected at all. The policy
  and the columns it applies to are declared in `contracts/kpis.yaml`, not hardcoded.
- That redaction is a **shape heuristic, not entity resolution**, and we do not claim otherwise.
  It removes two-word capitalised phrases that are not known business entities; account names and
  contract dimension values are protected so attribution can still name the account that moved.
  It therefore over-redacts an unfamiliar company that never appears as an account, and misses a
  mononym. On the generated corpus it alters 0 of 895 events while still removing a planted
  person name, which is the behaviour we want: the control runs, and it does not eat the evidence.
  Production would put a trained NER model behind the same interface.
- Every insight writes an audit record: who asked, what they were entitled to see, which
  sources and rows were used, which method ran, and what was returned.

## 8. Scope boundaries (stated honestly)

- Synthetic data, generated by `scripts/generate_data.py` with a fixed seed. Reproducible.
- The feedback loop adjusts driver priors and materiality thresholds. It does not retrain a
  model, and we do not claim it does.
- Causal screening uses sequence, magnitude and mechanism tests plus a lag correlation check.
  We do not claim formal causal identification.
- Cost figures are computed from real token counts against published list prices, and are
  labelled as estimates.

## 9. Stack

Python, with no machine learning dependency at all.

| Concern | What we use | Why |
|---|---|---|
| Deterministic computation | pandas, numpy | the quantitative path must be checkable by hand |
| The semantic contract | PyYAML | a definition a non-engineer can read and change |
| Anomaly baseline | robust z score, implemented in `friday/detect.py` | median and MAD against the slice's own 90 day history. A library estimator would add a dependency and remove the ability to explain the threshold |
| Evidence retrieval | BM25, implemented in `friday/evidence.py` | reproducible run to run, needs no model download and no embedding service, and is inspectable term by term. Swapping in embeddings later means replacing `_score` and nothing else |
| Narrative | one optional LLM call | the only stage a model touches. Off by default |
| Demo UI | Streamlit | `app.py` |
| REST layer | FastAPI | used only by `friday-web/` |

There is no scikit-learn, no sentence-transformers and no vector store in
`requirements.txt`, and this is deliberate rather than unfinished: a judge should be able to
clone the repository, install four packages and reproduce every number without network access
to a model. The engine is importable and UI independent by design.
