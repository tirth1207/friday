# FRIDAY — Changes

## Git Mutation Workflow

**Branch:** `feat/git-mutation-workflow`

### What changed

- Added explicit Git mutation capabilities for the Developer Agent:
  - `git.add` — stage selected files.
  - `git.commit` — create a local commit with an explicit message.
  - `git.push` — push an approved branch/ref to its configured remote.
- Kept mutation operations permission-gated through FRIDAY's existing executor.
- Added the mutation tools to the Developer Agent's available tool set for the approved implementation/finalization phase.
- Preserved the existing inspect → implement → verify workflow and its requirement for concrete verification evidence.
- Added documentation for the intended approval boundary: code changes and verification happen first; staging, committing, and pushing remain explicit mutation operations.

## OSIRIS Intelligence Layer

### New integration

FRIDAY now has a read-only OSIRIS client under `tools/osiris/`.

The integration is designed around **tool selection by user intent** instead of calling every feed for every request.

### Primary tools

- `osiris.news` — aggregated news.
- `osiris.weather` — severe weather / natural events.
- `osiris.conflicts` — active conflicts and incidents.
- `osiris.satellites` — tracked orbital objects.
- `osiris.flights` — live aircraft / ADS-B data.
- `osiris.earthquakes` — recent seismic events.
- `osiris.fires` — active wildfire hotspots.
- `osiris.space_weather` — solar and geomagnetic conditions.
- `osiris.gdelt` — geocoded world events.
- `osiris.country_risk` — country-level risk data.
- `osiris.markets` — defence-sector equities / commodities.
- `osiris.region_dossier` — composite location intelligence.
- `osiris.stats` — lightweight feed counters.
- `osiris.health` — API reachability check.
- `osiris.intelligence` — bounded generic access to an allow-listed read endpoint.

### Tool-routing behavior

FRIDAY's Developer Agent prompt now teaches the model to choose the narrowest OSIRIS capability that answers a live-data request.

Examples:

- “What is the latest news?” → `osiris.news`
- “Any major conflicts right now?” → `osiris.conflicts`
- “What is the weather situation?” → `osiris.weather`
- “Show satellites / aircraft” → `osiris.satellites` / `osiris.flights`
- “What happened globally?” → `osiris.gdelt`
- “Give me a location intelligence brief” → `osiris.region_dossier`

Multiple OSIRIS calls should only be composed when a cross-domain brief actually needs them.

### Safety / trust behavior

- OSIRIS access is read-only in FRIDAY.
- The integration uses an allow-list of read endpoints rather than arbitrary URLs.
- Requests have a bounded timeout and response-size limit.
- No OSIRIS API key is committed or required for the public read endpoints currently documented by OSIRIS.
- FRIDAY is instructed to treat upstream machine-assessment/risk fields as source metadata, not independently verified forecasts.
- The `osiris.news` wrapper explicitly flags this trust boundary because the upstream project has a reported issue involving randomized machine-assessment probabilities.
- Each result carries source and endpoint context so FRIDAY can distinguish live source data from its own interpretation.

### Dependency impact

No new Python dependency was required; FRIDAY already includes `aiohttp`.

### Main architecture

```text
User request
    │
    ▼
FRIDAY model / tool caller
    │
    ├── news? ───────────────► osiris.news
    ├── weather? ────────────► osiris.weather
    ├── war/conflict? ───────► osiris.conflicts
    ├── satellites? ─────────► osiris.satellites
    ├── flights? ────────────► osiris.flights
    ├── earthquake? ─────────► osiris.earthquakes
    ├── wildfire? ───────────► osiris.fires
    ├── space weather? ──────► osiris.space_weather
    └── location brief? ─────► osiris.region_dossier
                    │
                    ▼
             OSIRIS JSON feed
                    │
                    ▼
        FRIDAY source-aware response
```

### Next expansion

The next logical layer is a broader **FRIDAY intelligence router** that adds other approved information providers behind the same intent-based interface, with caching, source ranking, freshness checks, and optional multi-tool correlation for requests such as “Give me the situation in Europe right now.”

## Verification status

The implementation was reviewed against the repository architecture and OSIRIS's current published API reference. Local FRIDAY test/build execution was not available from this environment, so no local test result is being claimed here.
