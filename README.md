# FRIDAY

KPI intelligence to action engine. Team Fab3, Accenture Innovation Challenge 2026,
Track 3 BusinessIntelligence.ai. Submission 30 August 2026.

```bash
pip install pandas numpy pyyaml scikit-learn
python scripts/generate_data.py     # rebuild the three source systems
python scripts/verify_phase1.py     # phase gate, must be 14/14
```

## Layout

```
contracts/kpis.yaml      the semantic contract. single source of truth
friday/contracts.py      loader, validator, entitlement resolution
scripts/generate_data.py builds the three simulated sources
scripts/verify_phase1.py phase 1 gate
data/raw/                generated csv, reproducible from SEED
ASSUMPTIONS.md           every assumption, stated as the brief requires
```

**Rule: no module hardcodes a KPI definition, threshold, driver or access rule.**
If it is not in `contracts/kpis.yaml`, the engine does not know it. This is what the
brief means by a semantic contract, and it is the thing most teams will not have.

## The planted movement

West net revenue, 28 days to 2026-08-20 against the prior 28 days:

```
movement    -9.2%   (-744,243 INR)
volume      -155,522     Acme Corp stopped ordering 2026-07-28
price+mix   -588,722     Aurora discounted 8% from 08-01, demand drifted to Vertex
reconciles  -744,243     exactly
```

Evidence trail: Acme delivery complaints run 11.4x baseline after the West logistics
provider changed on 2026-06-14, and one CRM note on 2026-07-22 names supplier risk.
Nova line has 21 days of history against a 60 day minimum, so it trips the sparse policy.

The engine is told none of this. It has to recover it.

## Lanes

Three people, three lanes, one integration day.

| | Lane A, analytics | Lane B, evidence and narrative | Lane C, governance and ops |
|---|---|---|---|
| Owns | detection, attribution, causal screen | retrieval, narrative, personas, abstention | entitlements, telemetry, feedback, UI |
| Modules | `detect.py` `attribute.py` `causal.py` | `evidence.py` `narrate.py` `personas.py` | `access.py` `telemetry.py` `feedback.py` `app.py` |
| Must never | call an LLM for a number | invent a number not passed in | let an unentitled row reach a narrative |

## Schedule

| Day | Date | A | B | C |
|---|---|---|---|---|
| 1 | Fri 21 Aug | contract and data **done**, whole team reads ASSUMPTIONS.md | | |
| 2 | Sat 22 Aug | baseline and materiality detection | build retrieval index over service_events | entitlement enforcement on dataframes |
| 3 | Sun 23 Aug | price volume mix decomposition | evidence scoring and freshness stamps | telemetry wrapper, latency and tokens |
| 4 | Mon 24 Aug | causal screen, sequence magnitude mechanism | narrative synthesis, numbers injected only | feedback store and threshold adjustment |
| 5 | Tue 25 Aug | confidence scoring, sparse handling | persona templates and abstention path | Streamlit shell wired to the engine |
| 6 | Wed 26 Aug | **integration**, all three lanes meet | | |
| 7 | Thu 27 Aug | **verify**, all ten checklist items demonstrable | | |
| 8 | Fri 28 Aug | business proposal and pitch deck | | |
| 9 | Sat 29 Aug | record video, rehearse | | |
| 10 | Sun 30 Aug | buffer, submit | | |

Day 6 and 7 are not optional. A prototype that works only on one machine on the last
evening cannot be filmed.

## The ten things the demo must show

Round 2 minimum prototype expectations. Tick these, not features.

| # | Requirement | Status |
|---|---|---|
| 1 | 3 to 5 connected KPIs, 2 to 3 sources, different grains and cadences | **done** |
| 2 | KPI semantic contract: definitions, calculations, drivers, thresholds, lineage, access | **done** |
| 3 | Two personas, different narratives or actions | contract ready, narratives pending |
| 4 | One multi factor movement with known drivers | **data done**, attribution pending |
| 5 | One low confidence case, engine asks or abstains | policy written, path pending |
| 6 | One sparse history or newly launched KPI | **data done**, handling pending |
| 7 | One role based security scenario | contract ready, enforcement pending |
| 8 | Evidence with freshness, method, contribution, confidence, lineage | **data done**, panel pending |
| 9 | Clear LLM versus non LLM breakdown | design fixed, instrumentation pending |
| 10 | Runtime telemetry: latency, model calls, tokens, estimated cost | pending |

## Method split, LLM versus not

The brief says the LLM must not be the source of quantitative truth. This is the answer.

| Stage | Method | Why not an LLM |
|---|---|---|
| Materiality | robust z score against a 90 day baseline | must be reproducible, not judged |
| Attribution | price volume mix, deterministic arithmetic | must sum exactly to the movement |
| Driver ranking | contribution share plus lag correlation | auditable and stable across runs |
| Causal screen | sequence, magnitude, mechanism tests | rules must be inspectable |
| Evidence retrieval | embedding search over text | retrieval, no generation |
| Narrative | **LLM**, every number injected | language is the only safe place for it |
| Abstention | deterministic rule on evidence sufficiency | must not be persuadable |
