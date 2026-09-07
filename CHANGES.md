# FRIDAY — Changes

## Super FRIDAY Intelligence Expansion

FRIDAY's OSIRIS integration is now a broader read-only live-intelligence layer designed for natural tool selection rather than one-off endpoint calls.

### Live intelligence capabilities

- `osiris.news` — aggregated news.
- `osiris.live_news` — live-news feed.
- `osiris.weather` — severe weather / natural events.
- `osiris.air_quality` — air-quality observations.
- `osiris.radar` — radar/weather metadata.
- `osiris.conflicts` — active conflicts and incidents.
- `osiris.frontlines` — conflict-frontline data.
- `osiris.satellites` — tracked orbital objects.
- `osiris.flights` — live aircraft / ADS-B data.
- `osiris.earthquakes` — recent seismic events.
- `osiris.fires` — active wildfire hotspots.
- `osiris.space_weather` — solar and geomagnetic conditions.
- `osiris.gdelt` — geocoded world events.
- `osiris.country_risk` — country-level risk data.
- `osiris.markets` — defence-sector equities / commodities.
- `osiris.crypto` — cryptocurrency market data.
- `osiris.maritime` — maritime / vessel intelligence.
- `osiris.infrastructure` — infrastructure intelligence.
- `osiris.cyber_threats` — cyber-threat intelligence.
- `osiris.cyber_attacks` — reported cyber-attack data.
- `osiris.region_dossier` — composite location intelligence.
- `osiris.stats` — lightweight feed counters.
- `osiris.health` — API reachability check.
- `osiris.intelligence` — bounded generic access to an allow-listed read endpoint.

### Intelligence router

`osiris.intelligence_brief` is the multi-feed orchestration layer. It selects a bounded set of sources from the user's topic and fetches them concurrently.

Examples:

- news → news + live news
- weather → weather + air quality + radar
- war/conflict → conflicts + frontlines + GDELT + news
- geopolitics → conflicts + country risk + GDELT + news
- satellite/space → satellites + space weather
- aviation → flights + weather
- earthquake → earthquakes + GDELT
- wildfire → fires + weather
- markets → markets + news
- crypto → crypto + news
- cyber → cyber threats + cyber attacks + news
- maritime → maritime + news
- global/world → GDELT + news + conflicts + weather

The router now uses token-aware matching instead of loose substring matching, reducing accidental tool selection for unrelated words. Unknown topics safely fall back to news rather than generating arbitrary external requests.

### Tool-routing behavior

FRIDAY has two intelligence modes:

1. **Narrow request:** call the specific `osiris.*` tool that answers it.
2. **Broad situation request:** call `osiris.intelligence_brief`, which selects and gathers a bounded multi-feed snapshot.

### Safety / trust behavior

- OSIRIS access is read-only in FRIDAY.
- The client uses an allow-list of read endpoints rather than arbitrary URLs.
- Requests have a bounded timeout and response-size limit.
- No OSIRIS API key is committed or required for the public read endpoints currently documented by OSIRIS.
- Upstream machine-assessment/risk fields are treated as source metadata, not independently verified forecasts.
- Each result carries source and endpoint context so FRIDAY can distinguish live source data from its own interpretation.
- Active scanning/recon capabilities are intentionally not exposed through the FRIDAY OSIRIS tool registry.

## Repository workflow note

FRIDAY currently exposes read-only Git inspection tools (`git.status`, `git.diff`, `git.log`, `git.branch`) plus a permission-gated GitHub API tool. This document does not claim dedicated `git.add`, `git.commit`, or `git.push` tools because those are not currently implemented in the tool registry.

## Dependency impact

No new Python dependency was required; FRIDAY already includes `aiohttp`.

## Architecture

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
                         ┌────────┼─────────┐
                         ▼        ▼         ▼
                       news    conflicts  weather
                         │        │         │
                         └────────┼─────────┘
                                  ▼
                         source-aware snapshot
                                  │
                                  ▼
                         FRIDAY final answer
```

## Verification status

Repository-side implementation and diff were reviewed. Local FRIDAY test/build execution is not available from this environment, so no local test result is claimed.
