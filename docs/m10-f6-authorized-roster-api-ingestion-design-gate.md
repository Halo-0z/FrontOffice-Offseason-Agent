# M10-F6 Authorized Roster API Ingestion Design Gate

## Verdict: CONDITIONAL GO

- **GO** for F6-A docs-only design gate (this document)
- **GO** for F6-B provider adapter skeleton with no key / no network tests
- **HOLD** for F6-C raw snapshot capture until an authorized API key exists
- **HOLD** for F6-D 30-team normalized roster until authorized raw snapshot capture is reviewed

---

## 1. Why F6 Exists

M10-F5-A exposed a fundamental limitation in the manual curation workflow:

- **Manual web verification is vulnerable to confirmation bias.** Curators relied on Chinese sports media recap reports and "long-term contract / franchise cornerstone / should still be on team" heuristics, which lag actual transactions.
- **Two players were incorrectly landed:** Darius Garland was listed under Cleveland Cavaliers (NBA.com and ESPN both confirm current affiliation is LA Clippers), and Jalen Green was listed under Houston Rockets (NBA.com and ESPN both confirm current affiliation is Phoenix Suns).
- **Schema/hash/xref tests prevent structural errors but cannot prove source facts are correct.** A player with a well-formed JSON record, valid hash, and correct cross-references can still have the wrong team affiliation.
- **Source correctness overrides roster completeness.** Both players were removed (not reassigned), and no replacement players were added to compensate. CLE and HOU intentionally landed with 1 player each rather than adding unverified alternatives.

The conclusion: manual curation alone cannot reliably scale to 30 teams. An authorized/offline API ingestion pipeline is required to produce trustworthy frozen snapshots while preserving all existing isolation boundaries.

---

## 2. Core Principle

**API is an offline data production tool, not a runtime dependency.**

The authorized API is used exclusively during data ingestion to produce checked-in, frozen, hashed, source-verified snapshot files. At no point does the application service, API layer, frontend, Agent/orchestrator, NL preview, or trade/signing logic make runtime HTTP calls to an external roster provider.

**Target data flow:**

```
authorized API / official source
  -> raw snapshot files (checked-in, hashed)
  -> normalized player_identities.json / roster_memberships.json
  -> source_manifest hashes
  -> tests (network-free, key-free)
  -> docs/handoff
```

The application service continues to read only from disk snapshots. No network access exists in the backend request path.

---

## 3. Recommended Source Ranking

### Primary: Sportradar NBA API

- Official documentation includes an NBA Team Profile endpoint
- Team Profile returns team information + full roster of active players
- Requires API key, has quota and QPS limits
- Suitable as an offline snapshot source
- **Not recommended as a runtime dependency**

### Secondary: SportsDataIO NBA API

- Has NBA API documentation and developer tiers
- Requires key and license review
- Covers NBA teams/rosters/players and related data families
- Also exposes forbidden domains (injuries, depth charts, salaries) — strict field whitelisting mandatory
- Suitable as an offline source; **not recommended as a runtime dependency**

### Experimental / non-primary: BALLDONTLIE

- Has paid API key and active players/team fields
- Not an NBA official or explicitly authorized primary source
- `standard`/`two_way` contract status semantics are unclear
- Not selected as F6 primary source

### Cautious / not recommended for production primary: nba_api / stats.nba.com

- Python client for NBA.com endpoints
- NBA.com endpoint stability and authorization boundaries are insufficient
- Acceptable for research/prototyping only
- **Should not be the primary source for 30-team production ingest**

### Other providers

API-Sports, Sportmonks, SportsBlaze, and similar providers must complete license review before being considered. None enter F6-C.

---

## 4. Minimum Implementation Scope

### Allowed in F6 scope

- Offline fetch script (tools/roster_ingestion/)
- Checked-in raw API response snapshot files
- Normalized `player_identities.json`
- Normalized `roster_memberships.json`
- source_manifest hash updates
- manifest.json updates
- Tests (network-free, key-free)
- Docs/handoff

### Continually prohibited

- API endpoints in the backend
- Frontend UI changes
- Agent/orchestrator integration
- NL preview integration
- Trade/signing logic changes
- Salary / contract / cap data
- Injury / medical data
- Scouting / rumor data
- Live / current / latest runtime status
- Runtime fetch inside the application service
- Depth chart / minutes / role projection / trade eligibility fields

---

## 5. Recommended Architecture

### Script location

Fetch and normalization scripts should live under:

```
tools/roster_ingestion/
```

This location is preferred over `backend/scripts/` to avoid any misunderstanding that these scripts are part of the runtime backend. They are offline data production utilities.

### Raw snapshot location

Raw API responses should be stored at:

```
data/snapshots/nba_real_2026_preoffseason_v1/raw/authorized_roster_api/{provider}/{as_of_date}/
```

- One directory per provider per access date
- Raw response JSON preserved verbatim (minus any API keys or auth headers)
- Raw files are hashed in source_manifest

### Normalized output location

Normalized files continue to be written to the existing paths:

- `data/snapshots/nba_real_2026_preoffseason_v1/normalized/player_identities.json`
- `data/snapshots/nba_real_2026_preoffseason_v1/normalized/roster_memberships.json`

### source_manifest requirements

Each per_file_sources entry for API-ingested files must record:

- Provider name (e.g., `sportradar`)
- Endpoint documentation URL or template (not the live call URL with key)
- `access_date` (when the fetch was performed)
- `as_of_date` (frozen snapshot date)
- File hash (SHA-256)
- License note (brief attribution, no overclaiming)

### manifest description constraints

- Must **not** describe data as "live", "current", "latest", or "full roster"
- Must state frozen/as-of nature explicitly
- Must include stale_after_date
- Must state that data is identity + roster membership only

### Application service boundary

- The backend service (`player_roster_metadata_reader.py`) continues to read exclusively from disk snapshots
- No HTTP client, no API key, no network call exists in the service layer
- The service has no knowledge of which provider produced the data

### Test boundary

- Tests never make network calls
- Tests never read API keys from environment
- Tests validate only checked-in snapshot files and synthetic fixtures

---

## 6. API Key / Environment Plan

### Environment variables

- `SPORTRADAR_NBA_API_KEY`
- `SPORTSDATAIO_NBA_API_KEY`

### Key handling rules

- Keys are read **only** from environment variables
- CLI flag key passing is not supported (prevents accidental key exposure in shell history)
- `.env` files are not created or checked in
- Keys must never appear in raw files, logs, manifest, source_manifest, or pytest output
- Header-based authentication is preferred to avoid keys appearing in URLs
- When no key is present, the fetch script must **fail closed**:
  - Exit with non-zero status code
  - Do not create empty raw files
  - Do not update normalized files
  - Do not modify manifest or source_manifest

---

## 7. Schema Compatibility

### F6-A / F6-B

No schema patch is required for F6-A or F6-B. The existing normalized schemas can accommodate identity + roster membership data sourced from an authorized API.

### F6-D pre-requisite (recommended small schema patch)

Before F6-D normalized landing, a small schema patch is recommended:

- Add `authorized_api_snapshot` or `authorized_provider_reference` to `source_manifest.per_file_sources.source_type` enum
- This allows proper attribution without overloading `manual_curated` or `public_reference`

If the schema patch is deferred to a later milestone, F6-D can use `manual_curated` / `public_reference` temporarily, but must record the provider name and authorization context in `source_name`, `license_notes`, and `limitations`.

### player_id scheme

- Normalized `player_id` continues to use stable slugs (`nba-first-last` format)
- `provider_player_id` should not be added to normalized files without a dedicated schema patch
- If cross-provider ID mapping becomes necessary, open a separate schema milestone

### roster_status mapping

- If the provider explicitly indicates a two-way contract, map to `two_way`
- If the provider explicitly indicates an active standard contract, map to `standard`
- If contract status cannot be determined, **do not default to `standard`**. The record must be HOLD for blocked review rather than silently assigned a status.

---

## 8. Testing Plan

F6-B adapter skeleton tests and F6-D normalized roster tests must include:

### Count and completeness
- 30 teams expected (all NBA franchises present in team_id set)
- No duplicate `player_id`
- No duplicate `membership_id`

### Cross-reference integrity
- Every `membership.player_id` must reference an existing player
- Every `membership.team_id` must reference an existing team in teams.json

### Enum validation
- `roster_status` values are in the allowed enum (`standard`, `two_way`)
- `position` values conform to the position enum
- No `unknown_manual_review` status unless the record is explicitly blocked from serving

### Source manifest
- `source_manifest` hash validation for all files
- `file_hashes` match actual file contents
- Required metadata fields present (provider, access_date, as_of_date)

### Forbidden field scans
No record may contain any of the following fields:
- `salary`, `salaries`, `contract`, `contracts`, `cap_hold`, `guarantee_amount`
- `cap_sheet`, `cap_sheets`
- `injury`, `injuries`, `injury_status`, `medical`, `medical_status`, `health`
- `rumor`, `rumors`, `scouting_opinion`, `scouting_opinions`
- `live_status`, `availability`, `real_time_availability`, `active_now`
- `current_roster`, `latest_roster`, `latest_data`, `live_data`, `current_salaries`, `real_time_data`
- `projected_depth_chart`, `depth_chart`, `minutes_projection`, `role_projection`
- `trade_eligibility`
- Mutation verbs: `execute`, `apply`, `commit`, `mutate`, `write`, `persist`, `save`, `delete`, `update`, `submit`, `auto_execute`, `auto_approve`

### Forbidden file scans
The normalized directory must not contain:
- `contracts.json`
- `salaries.json`
- `cap_sheet.json` / `cap_sheets.json`
- `injuries.json`
- `rumors.json`
- `scouting_opinions.json`
- `live_status.json`

### Isolation guards
- No API endpoint imports in services
- No frontend imports in backend
- No Agent/orchestrator imports in data path
- No runtime fetch in application service (no `requests`, `httpx`, `aiohttp`, `urllib` in `backend/app/services/`)
- Tests are network-free (no HTTP calls)
- `pytest` never requires an API key to run

### Freshness warnings
- `stale_after_date` present and in the future relative to `as_of_date`
- `data_freshness_warning` present on all records
- `live_eligible: false` on all records
- `manual_review_required: true` on all records

---

## 9. Milestone Split

### F6-A: Design Gate (this document)
- Scope: docs-only
- Allowed file: `docs/m10-f6-authorized-roster-api-ingestion-design-gate.md`
- No code, no data, no schema changes
- Stop condition: design document accepted

### F6-B: Provider Adapter Skeleton
- Scope: build tooling structure with zero real data
- Allowed: `tools/roster_ingestion/**`, tests, docs
- No API key required
- No network calls in tests
- No real data landing (synthetic fixtures only)
- Stop condition: fixture-only tests green, adapter can parse a mock API response into normalized format offline

### F6-C: Authorized Raw Snapshot Capture
- Requires: valid API key for an authorized provider (Sportradar preferred)
- Raw response files only — no normalized landing
- Fetch script runs once offline; raw files checked in
- Raw files reviewed for license, field coverage, and forbidden data before any normalization
- Stop condition: raw files hashed, source capture reviewed and approved

### F6-D: Normalize 30-Team Roster
- Allowed: normalized data files, source_manifest, manifest, tests, docs
- Identity + roster membership only
- Forbidden field/file scans must pass
- Cross-reference, duplicate, and count tests must pass
- Stop condition: 30 teams, xrefs green, hashes green, forbidden scans green

### F6-E: Full Regression and Handoff
- Full M10 metadata regression test suite must pass
- Smoke verification document
- Final handoff document
- Stop condition: regression green, docs sealed

---

## 10. Stop/Go Decision Matrix

| Scenario | Decision |
|----------|----------|
| No authorized API key available | **GO** F6-A/F6-B only; **HOLD** F6-C/F6-D |
| Only nba_api / stats.nba.com available | **HOLD** 30-team production ingest; acceptable for prototype research only |
| Sportradar key acquired | Fastest safe route: Teams endpoint → 30 Team Profile calls → raw snapshots → whitelist normalize identity/membership only → tests |
| SportsDataIO key acquired | Possible, but must complete license review and field mapping review first; forbidden domain whitelist must be proven |
| Manual Batch 2 (more hand-curated players) | **PAUSE.** Prioritize F6-A/F6-B over further manual expansion. Source correction risk is too high without an authorized source. |

---

## 11. Risks

1. **Forbidden field leakage.** Provider responses will include salary, injury, depth chart, and other forbidden domains. The importer must use an **allowlist** (whitelist) of permitted fields, not a blocklist (blacklist) of forbidden fields. Any field not explicitly on the allowlist is dropped.

2. **Contract status ambiguity.** `standard` vs `two_way` status may not be cleanly exposed by all providers. Unknown status must HOLD for manual review; it must never silently default to `standard`.

3. **License and redistribution restrictions.** Provider terms may limit data redistribution. Documentation and source evidence must be preserved. Do not overclaim authorization status in manifest or source_manifest.

4. **Rate limits and bounded fetch.** Offline ingestion must respect provider QPS/quota limits. The fetch script should implement bounded delays and clear retry/abort logic; never hammer endpoints.

5. **Data staleness.** Frozen snapshots are as-of a specific date. `stale_after_date` must be set explicitly, and records must carry `data_freshness_warning`. A raw snapshot is never "live", "current", or "latest" once checked in.

6. **Raw snapshot drift over time.** If the provider updates their API schema between fetches, the adapter must handle versioning. Raw files are immutable once checked in; re-fetch produces a new as_of_date directory.

7. **Key exposure.** API keys must never appear in URLs (use header auth), logs, raw files, manifest, source_manifest, test output, or git history. Fail closed when key is absent.

---

## 12. Doubao Future Execution Boundary (F6-B)

When F6-B adapter skeleton is executed in a future session:

### Allowed
- `tools/roster_ingestion/**` (new scripts and modules)
- Tests for the adapter skeleton (synthetic fixtures only)
- Docs

### Prohibited
- `backend/app/api.py`
- `frontend/**`
- `backend/app/services/**` (including `player_roster_metadata_reader.py`)
- `backend/app/snapshot_loader.py`
- `backend/app/models/**`
- Agent/orchestrator code
- NL preview code
- Trade/signing logic
- `data/snapshots/**/normalized/**` data modifications (unless F6-D is explicitly approved)
- `data/snapshots/**/raw/**` raw data files (unless F6-C is explicitly approved)
- Schema modifications
- API endpoints
- Real API key usage in tests
- Network calls in tests

---

## 13. Final Conclusion

**M10-F6 is conditionally approved.**

- The F5-A source correction (Garland/LAC, Green/PHX) demonstrated that manual web verification cannot reliably scale to 30 teams. An authorized/offline API ingestion pipeline is the correct path forward.
- The authorized API is strictly an offline data production tool. It is never a runtime dependency. The backend service continues to read frozen disk snapshots only.
- **Next immediate task: F6-A docs-only design gate (this document).**
- **F6-B (adapter skeleton) may proceed** without an API key using synthetic fixtures.
- **F6-C (raw snapshot capture) and F6-D (30-team normalized roster) are HOLD** until an authorized provider API key (Sportradar preferred) is acquired and license terms are reviewed.
- Manual Batch 2 expansion is paused in favor of building the authorized ingestion pipeline.
- All existing isolation boundaries remain in effect: no salary/contract/cap/injury/scouting/rumor/live data, no frontend changes, no API endpoints, no Agent/NL/trade/signing integration.
