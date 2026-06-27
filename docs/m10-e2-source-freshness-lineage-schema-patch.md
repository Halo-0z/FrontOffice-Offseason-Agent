# M10-E2 Source / Freshness / Lineage Schema Patch

M10-E2 extends the M10-B `source_manifest_schema.json` so that future
`player_identities` and `roster_memberships` data categories can be declared,
lineage-traced, hash-checked, and freshness-governed **without** writing any real
player data, real roster data, or any contracts/salaries/cap sheets yet.

This milestone is **schema + tests + docs only**. It does not touch backend
services, API routes, loaders, the orchestrator, natural-language-preview,
trade/signing logic, the demo snapshot, the frontend, or the real snapshot data
files.

Run date: 2026-06-27.
Preceding seal: M10-E1 governance gate at commit `22ca2a5` / tag
`m10e1-player-roster-governance-gate`.

## 1. Goal

Prepare the source/freshness/lineage schema layer for the M10-E3 (player identity
schema) and M10-E4 (roster membership schema) milestones by:

1. Adding `"player_identities"` and `"roster_memberships"` to the allowed
   `data_categories` enum in `source_manifest_schema.json`.
2. Removing `"contracts"` and `"cap_sheets"` from the allowed `data_categories`
   enum (they are deferred to M10-F+ per M10-E1 governance) so that a
   mis-labelled future file will fail schema validation.
3. Extending the `per_file_sources` entry schema to let each future file carry
   its own `source_type`, `manual_review_required`, `live_eligible=false`,
   `data_freshness_warning`, and `limitations` lineage fields.
4. Adding a constrained `source_type` enum that allows only curated/public
   reference sources and rejects `llm_generated` / `scraped_unreviewed`.
5. Extending the top-level `propertyNames` forbidden-field list to also reject
   `latest_roster`, `live_status`, `salaries`, `injuries`, `injury_status`,
   `scouting_opinions`, and `rumors` (defence-in-depth, mirroring M10-D1).
6. Adding schema tests that prove all of the above and that prove **no** real
   player/roster/contract/salary/cap data files exist yet in the real snapshot
   directory.

M10-E2 does **not** define the `player_identities.json` or
`roster_memberships.json` record schemas — that is E3 / E4 work.

## 2. Why extend source/freshness/lineage before player schema

M10-E1 governance explicitly ordered the milestones as:

`E1 governance → E2 source/freshness/lineage → E3 player identity schema →
E4 roster membership schema → E-smoke → E-final-handoff`

Source/freshness/lineage must be locked down first because:

- **Provenance is a safety invariant, not an afterthought.** Every future player
  and roster record will need a `source_name` / `source_url` / `source_type` /
  `as_of_date` at the file level before a single record is added. If we define
  the record schema first and bolt lineage on later, we risk curator drift
  where records are entered without provenance.
- **Freshness warnings and `live_eligible=false` have to be present per file**
  so that a future reader service can fail closed if a file is missing a
  staleness warning (player data is far more tempting to mislabel as "current"
  than team identity data is).
- **Forbidden categories have to be blocked at the schema layer** before any
  future contributor can slip a `data_categories: ["contracts"]` flag into a
  manifest and silently open a salary surface.
- **The existing sealed real source_manifest must remain valid after the patch.**
  Bumping the lineage envelope before we add files gives us a clean
  forward-compat test (old manifests validate, new future-shaped manifests
  validate).

In short, E2 is the "envelope" patch; E3/E4 fill the envelope with record-level
schemas.

## 3. What changed in `source_manifest_schema.json`

All changes are confined to
[schema/source_manifest_schema.json](file:///D:/FrontOffice-Offseason-Agent/schema/source_manifest_schema.json).

### 3.1 `data_categories` enum

Before:

```json
["teams", "team_visual_metadata", "players", "rosters", "contracts",
 "cap_config", "cap_sheets", "free_agents", "draft_assets", "evidence_notes"]
```

After:

```json
["teams", "team_visual_metadata", "players", "rosters", "player_identities",
 "roster_memberships", "cap_config", "free_agents", "draft_assets", "evidence_notes"]
```

- **Added:** `"player_identities"`, `"roster_memberships"` — the two categories
  E3/E4 will populate.
- **Removed:** `"contracts"`, `"cap_sheets"` — these categories are deferred to
  M10-F or later per M10-E1 governance. Any future manifest that lists them
  will fail schema validation until M10-F governance opens.
- `"cap_config"`, `"free_agents"`, `"draft_assets"`, `"evidence_notes"` are
  retained as forward-compatible placeholders but are not used in M10-E and
  have no data files.
- `"players"` and `"rosters"` are retained as legacy generic labels but the
  curated future categories are the specific `"player_identities"` and
  `"roster_memberships"` values. E3/E4 will reference these specific values.

### 3.2 `per_file_sources` entry schema

Previously each entry only supported `source_name`, `source_url`, `as_of_date`.
It now **additionally supports** (all optional, so the sealed M10-D2 manifest
remains valid):

- `source_type` — enum `"manual_curated" | "public_reference" | "league_roster" | "manual_non_official_ui"`. Any other string (including `"llm_generated"` and `"scraped_unreviewed"`) fails.
- `manual_review_required` — boolean; per-file governance flag.
- `live_eligible` — boolean with `const: false`; if present, must be `false`.
- `data_freshness_warning` — non-empty string for UI consumption.
- `limitations` — non-empty array of strings.

These fields are optional at the schema level because the sealed M10-D2
`per_file_sources` entries (teams / team_visual_metadata) don't carry them yet.
Future reader-service work in E-smoke will enforce that player/roster entries
**must** supply them (cross-reference check between `data_categories` and
per-file governance fields), exactly as M10-D1 enforced that every data
category in `data_categories` has a matching hash/source entry.

### 3.3 Top-level `propertyNames` forbidden list

Added to the existing execution/live/logo blacklist:

- `latest_roster` (live/current naming)
- `live_status` (live data)
- `salaries` (money)
- `injuries`, `injury_status` (medical/availability)
- `scouting_opinions`, `rumors` (opinion/non-factual)

These field names will cause validation failure if added at the top level of
any future source_manifest, providing defence-in-depth on top of the
`data_categories` enum and the reader service's recursive forbidden-key scan.

### 3.4 `description` strings updated

The top-level description now calls out the M10-E2 patch, and the
`per_file_sources` / `data_categories` descriptions explicitly note the
contracts/salaries/cap_sheets deferral and the player/roster governance
requirements.

## 4. `player_identities` / `roster_memberships` are future categories only

Crucially, this patch **only** makes the schema *aware* of these categories.
It does not:

- Create `normalized/player_identities.json`.
- Create `normalized/roster_memberships.json`.
- Add either filename to the sealed real snapshot's `per_file_sources` or
  `file_hashes`.
- Add either category to the sealed real snapshot's `data_categories` (which
  remains `["teams", "team_visual_metadata"]`).
- Modify the sealed real snapshot's `manifest.json` or `source_manifest.json`
  in any way.

Tests in `test_m10e_source_lineage_schema.py` explicitly assert that:

- The real `normalized/` directory contains **only** `teams.json` and
  `team_visual_metadata.json`.
- `player_identities.json`, `roster_memberships.json`, `contracts.json`,
  `salaries.json`, `cap_sheet.json`, `cap_sheets.json`, `players.json`,
  `rosters.json`, `injuries.json`, and `rumors.json` do not exist.
- The real snapshot root contains exactly `manifest.json`,
  `source_manifest.json`, and the `normalized/` directory — no new data files.

## 5. Current state: no real player/roster data, no contracts/salaries/cap sheets

At the M10-E2 seal:

- The real snapshot `data_categories` remains `["teams", "team_visual_metadata"]`.
- The only data files under `normalized/` remain `teams.json` and
  `team_visual_metadata.json`, both sealed at their M10-C1/C2 SHA-256 hashes.
- There is no player, roster, contract, salary, cap-sheet, injury, rumor, or
  scouting data in the real snapshot.
- The frontend `/offseason` real-snapshot panel continues to show only 30 teams
  and abbreviation badges; no player/roster UI exists.
- The Agent, orchestrator, and natural-language-preview have no access to
  player or roster data.

## 6. Per-file lineage / freshness / safety requirements

For any **future** file (introduced in E3/E4 or later) that adds
`player_identities` or `roster_memberships` to `data_categories`:

1. **`per_file_sources` coverage.** An entry keyed by the file's relative path
   (e.g. `normalized/player_identities.json`) must exist.
2. **`source_name`** (required, non-empty) — human-readable curator/source.
3. **`source_url`** (nullable) — public reference URL used for manual review;
   null only if no public URL is appropriate (e.g. a manual non-official
   palette).
4. **`source_type`** (E2 future-required) — must be one of
   `"manual_curated"`, `"public_reference"`, `"league_roster"`,
   `"manual_non_official_ui"`. `"llm_generated"` and `"scraped_unreviewed"`
   are rejected at the schema layer.
5. **`as_of_date`** (required, `YYYY-MM-DD`) — the cutoff date of the file.
6. **`manual_review_required`** (E2 future-required) — must be `true`.
7. **`live_eligible`** (E2 future-required) — must be `false` (schema-enforced
   by `const: false` if present).
8. **`data_freshness_warning`** (E2 future-required, non-empty) — UI-mandatory
   warning string.
9. **`limitations`** (E2 future-required, non-empty array) — caveats, e.g.
   "not live", "no contract/salary data".
10. **`file_hashes` coverage.** A SHA-256 entry must be present for the file;
    byte-level tampering raises `RealSnapshotHashError` (M10-D1 pattern).
11. **Cross-reference.** Every player/roster record must reference valid
    `team_id`s (xref `teams.json`) and — when both files exist — every
    roster `player_id` must xref `player_identities.json`. (Enforced by the
    future E3/E4 reader service, mirroring how D1 enforced team/visual xref.)
12. **`stale_after_date`** must be present at the top level (nullable
    permitted, but the key must exist). The reader service in E-smoke will
    either hard-fail or elevate staleness warnings past this date (policy
    decided in E-smoke).
13. **Hard error, no demo fallback.** As with M10-D1, any missing file, schema
    mismatch, hash mismatch, or xref mismatch must raise a typed error
    (mapped to HTTP 500), never fall back to demo roster/contract data.

## 7. Hard error / no-fallback-to-demo principle

The M10-D1 hard-error / no-fallback-to-demo contract continues to apply and is
extended:

- Player/roster files missing → `RealSnapshotNotFoundError`.
- Player/roster files with schema violations → `RealSnapshotSchemaError`.
- Player/roster hash mismatches → `RealSnapshotHashError`.
- Team/player xref failures, roster/player xref failures, team-count
  deviations → `RealSnapshotCrossReferenceError`.
- The real-snapshot metadata endpoint **must not** synthesize, demo-merge, or
  stub player/roster data on failure. The frontend error state continues to
  show the red "加载失败" card with "no fallback to demo" hint and Retry.
- Contracts/salaries/cap sheets are not in the allowed category set; any
  attempt to slip them in will fail schema validation before service code
  even runs.

## 8. Agent / frontend boundaries

### 8.1 Agent boundary (unchanged, reinforced)

- The Agent, orchestrator, intent classifier, natural-language-preview,
  proposal builder, trade simulator, and transaction rule engine remain
  isolated from real player/roster metadata in M10-E2.
- No module under `backend/app/services/` (other than the dedicated
  `real_snapshot_metadata_reader.py`) imports future player/roster data.
- E-Smoke will add explicit static-import guardrail tests mirroring M10-D1's
  snapshot_loader isolation test.
- No LLM is prompted with real player/roster data in any product flow during
  M10-E. LLM use remains limited to off-line design review (as in the GPT-5.5
  gate that produced M10-E1).

### 8.2 Frontend boundary (unchanged)

- M10-E2 does not modify any file under `frontend/`.
- No player roster UI is added. The `/offseason` panel continues to be the
  M10-D2 team selector + abbreviation badge.
- The selected team in the real-snapshot panel remains component-local
  `useState`; it does not drive signing/trade/hold/natural-language-preview
  flows.
- A future "player inspector" panel must wait until E-Smoke passes and a
  dedicated frontend design doc (mirroring `m10-d2-frontend-team-selector-badge.md`)
  is written, with its own browser smoke.

## 9. Test results

All tests run from `D:\FrontOffice-Offseason-Agent` with
`D:\anaconda\python.exe -m pytest`.

### 9.1 New E2 schema tests

```
pytest backend/app/tests/test_m10e_source_lineage_schema.py -q
```

Result: **58 passed** (11 positive, 22 negative, 4 regression/no-data
assertions, plus parametrized expansions covering all allowed
`source_type` values, all 9 forbidden data categories, and both forbidden
`source_type` values).

### 9.2 Existing M10-B schema tests (regression)

```
pytest backend/app/tests/test_m10_real_snapshot_schema.py -q
```

Result: **48 passed** (unchanged — the sealed M10-D2 source_manifest and
real manifest still validate after the patch).

### 9.3 Full M10 metadata regression

```
pytest backend/app/tests/test_m10_real_snapshot_schema.py
       backend/app/tests/test_m10c_team_metadata.py
       backend/app/tests/test_m10c_team_visual_metadata.py
       backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py
       backend/app/tests/test_m10e_source_lineage_schema.py -q
```

Result: **310 passed** (48 + 62 + 95 + 47 + 58). No failures. Pre-existing
Windows-only `PermissionError` on pytest tempdir cleanup is environmental and
unrelated to code under test.

### 9.4 E2 is schema + docs + tests; no services/API were touched

Per the hard constraints, no pytest run is required for
`frontend/` (no file changed under `frontend/`); typecheck/build are not
required for a schema-only/test-only patch that doesn't change runtime
behavior. (They will be re-run in E-Smoke before E-Final-Handoff.)

## 10. Next: M10-E3 Player Identity Schema (still schema-only)

M10-E3 will define `schema/player_identity_schema.json` (or the project's
equivalent layout) covering the minimal allowed player-identity fields locked
down in [m10-e-player-roster-data-governance-gate.md §3](file:///D:/FrontOffice-Offseason-Agent/docs/m10-e-player-roster-data-governance-gate.md):
`player_id`, `display_name`, `first_name`, `last_name`, optional
`birthdate`/`height`/`weight`, `position`, source/freshness fields,
`live_eligible=false`, `manual_review_required=true`. E3 must:

- Be schema-only + tests + docs; **no real player data file**.
- Use synthetic tmp_path fixtures (e.g. `p-syn-001`) only.
- Reject every forbidden field (salary, contract, cap_hold, medical,
  social/agent, rumors, live status, projection, branding, execution verbs).
- Add cross-reference tests against `teams.json` team_ids (team affiliation
  is a roster concern, but identity xref safety will be enforced in E3 tests).
- Not touch frontend, API, services, loader, or orchestrator.
- Pass the full M10 metadata regression.

M10-E4 (Roster Membership Schema) will then follow with the six-value
`roster_status` enum and team↔player cross-reference rules. **Neither E3 nor
E4 may write real player/roster data files.**
