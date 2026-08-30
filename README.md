# FRIDAY

KPI intelligence to action engine. Team Fab3, Accenture Innovation Challenge 2026,
Track 3 BusinessIntelligence.ai. Submission 30 August 2026.

```bash
pip install -r requirements.txt
python scripts/generate_data.py        # rebuild the three source systems
python scripts/verify_phase1.py        # foundations gate,   14/14
python scripts/verify_phase23.py       # analytics gate,     18/18
python scripts/verify_lane_b.py        # narrative gate,     22/22
python scripts/verify_lane_c.py        # governance gate,    23/23
python scripts/verify_byod.py          # unseen data gate,   15/15
python scripts/verify_submission.py    # the brief, item by item, 18/18
python scripts/calibrate_thresholds.py # false positive rate by threshold

streamlit run app.py                   # the demo UI
```

All six gates must pass: **110 checks**. Run them before you push.

### The web front end

Optional, and separate from the Streamlit demo above. The Streamlit app remains the
reference UI and still runs standalone; the React site is a second surface onto the
same engine, for the pitch.

```bash
uvicorn friday.api:app --port 8000    # REST layer over the same engine
cd friday-web && npm install && npm run dev
```

The site needs the API running: `/` is the overview, `/console` reads live engine
output, and the upload panel posts a CSV to `/analyse`. Node 18+.

## Layout

```
contracts/kpis.yaml      the semantic contract. single source of truth
friday/contracts.py      loader, validator, entitlement resolution
friday/profile.py        infers a contract from an unseen csv
friday/byod.py           runs the pipeline on uploaded data
friday/api.py            fastapi layer, used only by the web front end
pages/                   streamlit upload page
scripts/generate_data.py builds the three simulated sources
scripts/verify_phase1.py phase 1 gate
scripts/verify_byod.py   proves the engine works on data it has not seen
data/raw/                generated csv, reproducible from SEED
friday-web/              react front end, overview and console
ASSUMPTIONS.md           every assumption, stated as the brief requires
```

**Rule: no module hardcodes a KPI definition, threshold, driver or access rule.**
If it is not in `contracts/kpis.yaml`, the engine does not know it. This is what the
brief means by a semantic contract, and it is the thing most teams will not have.

## The planted movement

West net revenue, 28 days to 2026-08-20 against the prior 28 days:

```
movement    -19.2%  (-1,556,566 INR)   z = -5.34 against threshold 2.0
volume      -1,132,495  (72.8%)  Acme Corp stopped ordering
price         -286,059  (18.4%)  Aurora discounted in West
mix           -138,011   (8.9%)  demand drifted to the cheaper Vertex line
residual            0.000000     reconciles exactly
```

The engine is told none of this and recovers all of it:

| Planted | Recovered | 
|---|---|
| Acme stops ordering 2026-07-28 | onset detected 2026-07-27, Acme named top account at 71.4% |
| Logistics provider changed 2026-06-14 | change point found 2026-06-16, 5.5x its pre change rate |
| CRM warning 2026-07-22 | cited as evidence, precedes onset |
| Nova launched 2026-07-31 | 21 days against a 60 day minimum, sparse policy trips, abstains |
| Nothing planted in North | no change point, no alert, ratio 0.00x |

Full chain, stated with high confidence and no abstention:

    delivery_reliability -> volume (73% of the movement) -> net_revenue -19.2%

## Lanes

Three people, three lanes, one integration day.

| | Lane A, analytics | Lane B, evidence and narrative | Lane C, governance and ops |
|---|---|---|---|
| Owns | detection, attribution, causal screen | retrieval, narrative, personas, abstention | entitlements, telemetry, feedback, UI |
| Modules | `detect.py` `attribute.py` `causal.py` **done** | `evidence.py` `narrate.py` `personas.py` **done** | `access.py` `telemetry.py` `feedback.py` `app.py` **done** |
| Must never | call an LLM for a number | invent a number not passed in | let an unentitled row reach a narrative |

`engine.py` is the integration point. The UI, the gates and any future caller drive
the identical instrumented pipeline, so a demo cannot work by wiring stages in a
special order.

## Schedule

| Day | Date | A | B | C |
|---|---|---|---|---|
| 1 | Fri 21 Aug | contract and data **done**, whole team reads ASSUMPTIONS.md | | |
| 2 | Sat 22 Aug | ~~detection~~ ~~price volume mix~~ ~~causal screen~~ **done day 1** | build retrieval index over service_events | entitlement enforcement on dataframes |
| 3 | Sun 23 Aug | action recommendations from the contract schema | evidence scoring and freshness stamps | telemetry wrapper, latency and tokens |
| 4 | Mon 24 Aug | expand evidential drivers beyond delivery | narrative synthesis, numbers injected only | feedback store and threshold adjustment |
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
| 3 | Two personas, different narratives or actions | **done**, three personas, different prose and different levers |
| 4 | One multi factor movement with known drivers | **done**, price volume mix reconciles to zero residual |
| 5 | One low confidence case, engine asks or abstains | **done**, Nova abstains and names the next check |
| 6 | One sparse history or newly launched KPI | **done**, policy trips automatically |
| 7 | One role based security scenario | **done**, row filter + column mask + KPI denial + audit trail |
| 8 | Evidence with freshness, method, contribution, confidence, lineage | **done**, every citation carries all five |
| 9 | Clear LLM versus non LLM breakdown | **done**, enforced by `telemetry.Run.verify()` |
| 10 | Runtime telemetry: latency, model calls, tokens, estimated cost | **done**, stamped on every insight |

## Method split, LLM versus not

The brief says the LLM must not be the source of quantitative truth. This is the answer.

| Stage | Method | Why not an LLM |
|---|---|---|
| Materiality | robust z score against a 90 day baseline | must be reproducible, not judged |
| Attribution | price volume mix, deterministic arithmetic | must sum exactly to the movement |
| Driver ranking | contribution share plus lag correlation | auditable and stable across runs |
| Causal screen | sequence, magnitude, mechanism tests | rules must be inspectable |
| Evidence retrieval | BM25 over the free text source | retrieval, no generation |
| Narrative | **LLM**, every number injected | language is the only safe place for it |
| Abstention | deterministic rule on evidence sufficiency | must not be persuadable |
