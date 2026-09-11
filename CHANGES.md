# FRIDAY — Changes

## Super FRIDAY Intelligence Expansion

FRIDAY's OSIRIS integration is now a broader read-only live-intelligence layer designed for natural tool selection rather than one-off endpoint calls.

### Live intelligence capabilities

- `osiris.news`, `osiris.live_news`
- `osiris.weather`, `osiris.air_quality`, `osiris.radar`
- `osiris.conflicts`, `osiris.frontlines`
- `osiris.satellites`, `osiris.flights`
- `osiris.earthquakes`, `osiris.fires`, `osiris.space_weather`
- `osiris.gdelt`, `osiris.country_risk`, `osiris.region_dossier`
- `osiris.markets`, `osiris.crypto`
- `osiris.maritime`, `osiris.infrastructure`
- `osiris.cyber_threats`, `osiris.cyber_attacks`
- `osiris.stats`, `osiris.health`, `osiris.intelligence`

### Intelligence router

`osiris.intelligence_brief` selects a bounded set of sources from the user's topic and fetches them concurrently. It supports news, weather, war/conflict, geopolitics, satellites/space, aviation, earthquakes, wildfire, markets, crypto, cyber, maritime, infrastructure, and global situations. Token-aware matching reduces accidental substring routing; unknown topics safely fall back to news.

### Git-aware engineering loop

FRIDAY now has explicit permission-gated Git mutation tools:

- `git.add` — stage only explicitly selected paths.
- `git.commit` — create a bounded commit message.
- `git.push` — push a configured remote/ref without force-push support.

The Developer Agent is taught to use these after implementation and concrete verification succeeds. It must not force-push, rewrite history, stage secrets/generated junk, or commit an empty change set. Pull-request creation and merging remain separate GitHub operations.

### Safety / trust behavior

- OSIRIS access is read-only and allow-listed.
- Network requests have bounded timeout and response-size limits.
- Upstream machine-assessment/risk fields are treated as source metadata, not verified forecasts.
- Source/endpoint context is retained for live-data responses.
- Active scanning/recon capabilities are intentionally not exposed through the OSIRIS registry.
- Git mutation tools remain executor permission-gated.

## Architecture

```text
User request
    │
    ▼
FRIDAY supervisor
    │
    ├── narrow live-data intent ──► specific osiris.* tool
    ├── broad situation ──────────► intelligence_brief
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
