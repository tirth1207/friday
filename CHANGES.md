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

FRIDAY now has a read-only OSIRIS client under `tools/osiris/`. OSIRIS documents 57 keyless GET endpoints across aviation, space, earth/environment, geopolitics, media/markets, infrastructure, cyber and OSINT. 

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

### Intelligence router

Added `osiris.intelligence_brief` as the multi-feed orchestration layer.

It maps broad intent to a bounded set of OSIRIS feeds and fetches them concurrently:

- news → news + live news
- weather → weather + air quality
- war/conflict → conflicts + frontlines + GDELT + news
- geopolitics → conflicts + country risk + GDELT + news
- satellite/space → satellites + space weather
- aviation → flights + weather
- earthquake → earthquakes + GDELT
- wildfire → fires + weather
- markets → markets + news
- cyber → cyber threats + cyber attacks + news
- maritime → maritime + news
- global/world → GDELT + news + conflicts + weather

Unknown broad topics safely fall back to news rather than making arbitrary external requests.

### Tool-routing behavior

FRIDAY now has two modes:

1. **Narrow request:** call the specific `osiris.*` tool that answers it.
2. **Broad situation request:** call `osiris.intelligence_brief`, which selects and gathers a bounded multi-feed snapshot.

Example:

```text
“What is the latest news?”
    -> osiris.news

“Any major conflicts right now?”
    -> osiris.conflicts

“What is happening in Europe?”
    -> osiris.intelligence_brief(topic="Europe/global situation")
    -> bounded multi-feed snapshot
```

The Developer Agent prompt explicitly teaches this distinction and keeps OSIRIS calls read-only. 

### Safety / trust behavior

- OSIRIS access is read-only in FRIDAY.
- The client uses an allow-list of read endpoints rather than arbitrary URLs.
- Requests have a bounded timeout and response-size limit.
- No OSIRIS API key is committed or required for the public read endpoints currently documented by OSIRIS.
- FRIDAY is instructed to treat upstream machine-assessment/risk fields as source metadata, not independently verified forecasts.
- Each result carries source and endpoint context so FRIDAY can distinguish live source data from its own interpretation.

### Dependency impact

No new Python dependency was required; FRIDAY already includes `aiohttp`.

### Architecture

```text
User request
    │
    ▼
FRIDAY model
    │
    ├── narrow intent ──────► specific osiris.* tool
    │
    └── broad situation ────► osiris.intelligence_brief
                                  │
                       ┌──────────┼──────────┐
                       ▼          ▼          ▼
                     news      conflicts   weather
                       │          │          │
                       └──────────┼──────────┘
                                  ▼
                         source-aware snapshot
                                  │
                                  ▼
                         FRIDAY final answer
```

## Verification status

The implementation was reviewed against the repository architecture and OSIRIS's current published API reference. Local FRIDAY test/build execution was not available from this environment, so no local test result is being claimed here.
