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

`osiris.intelligence_brief` selects a bounded set of sources from the user's topic and fetches them concurrently. It supports news, weather, war/conflict, geopolitics, satellites/space, aviation, earthquakes, wildfire, markets, crypto, cyber, maritime, infrastructure, and global situations. Token-aware matching reduces accidental substring routing; unknown topics safely fall back to news.

### Git-aware engineering loop

FRIDAY now has explicit permission-gated Git mutation tools:

- `git.add` — stage only explicitly selected paths.
- `git.commit` — create a bounded conventional commit message.
- `git.push` — push a configured remote/ref without force-push support.

The Developer Agent is taught to use these only after implementation and concrete verification succeed. It must not force-push, rewrite history, stage secrets/generated junk, or commit an empty change set. Pull-request creation and merging remain separate GitHub operations.

### Safety / trust behavior

- OSIRIS access is read-only in FRIDAY.
- The OSIRIS client uses an allow-list of read endpoints rather than arbitrary URLs.
- Requests have a bounded timeout and response-size limit.
- No OSIRIS API key is committed or required for the public read endpoints currently documented by OSIRIS.
- Upstream machine-assessment/risk fields are treated as source metadata, not independently verified forecasts.
- Each result carries source and endpoint context so FRIDAY can distinguish live source data from its own interpretation.
- Active scanning/recon capabilities are intentionally not exposed through the FRIDAY OSIRIS tool registry.
- Git mutation tools are still executor permission-gated even when the Developer Agent is operating autonomously.

## Architecture

```text
User request
    │
    ▼
FRIDAY supervisor
    │
    ├── narrow live-data intent ──► specific osiris.* tool
    │
    ├── broad situation ──────────► intelligence_brief
    │
    └── engineering goal ────────► Developer Agent
                                      │
                               inspect → implement
                                      │
                                verify → repair
                                      │
                              git.add → commit → push
                                      │
                                      ▼
                              feature branch / PR
```

## Verification status

Repository-side implementation and diff were reviewed. Local FRIDAY test/build execution is not available from this environment, so no local test result is claimed.
