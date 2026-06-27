# M10-F2: Backend Player/Roster Read Model with Synthetic Fixture / No Real Data

Run date: 2026-06-28.
Baseline: commit `5973b70`, tag `m10f1-source-intake-design-gate`, clean working tree.

This milestone implements the backend read-only service for player and roster
metadata, validated entirely against **synthetic** (fake) fixtures in pytest
`tmp_path`. No real NBA player names, roster memberships, contracts, salaries,
cap sheets, or any other sensitive/non-team-identity data is added to the
repository. F2 is the second gate in the M10-F series (see §1 of
`m10-f-real-player-roster-source-intake-design-gate.md`).

## 1. F2 goal

Build a single-purpose read-only service that:

1. Loads `normalized/player_identities.json` and `normalized/roster_memberships.json`
   from a future `real_snapshot` directory (the sealed F1 snapshot
   `nba_real_2026_preoffseason_v1` does **not** yet contain these files).
2. Performs strict schema validation against
   `schema/player_identities_schema.json` and `schema/roster_memberships_schema.json`
   (plus the existing teams/source_manifest/manifest schemas).
3. Verifies `source_manifest.file_hashes` (SHA-256) for both new files.
4. Verifies `source_manifest.per_file_sources` entries exist for both new files
   and that `source_type` is not in the forbidden set
   (`llm_generated`, `scraped_unreviewed`, `live_api`).
5. Enforces governance flags: `live_eligible=false`, `manual_review_required=true`,
   non-empty `limitations`, presence of `data_freshness_warning`.
6. Cross-references `roster_memberships[].player_id` against `player_identities[].player_id`.
7. Cross-references `roster_memberships[].team_id` against `teams[].team_id`.
8. Raises hard errors for any violation; **never** falls back to demo data.
9. Returns a read-only projection (DTO) that contains **no** salary/contract/cap/
   injury/medical/rumor/scouting/live/depth-chart/projection/trade-eligibility/
   execution/mutation fields.

The service is proven correct against synthetic fixtures only. It is not wired
to any API endpoint, frontend view, Agent, NL preview, or trade/signing logic.
It does not and cannot read real player/roster data because none exists in the
repository yet.

## 2. Why F2 is synthetic-only / no real data

Per the F1 design gate (§1, §2 of `m10-f-real-player-roster-source-intake-design-gate.md`):

- F2 is the **synthetic validation gate**. Its purpose is to prove the
  hard-error, no-demo-fallback, field-sanitization contract with 100% fake data
  before any real player bytes are allowed in the repo.
- Real player_identities and roster_memberships will not land until M10-F3
  (source-pack + tiny-pilot approval gate) and M10-F4 (real data pilot
  implementation), both of which must pass their own review.
- Using synthetic fixtures guarantees F2 cannot accidentally leak, reference,
  or cement real player names or statuses.

## 3. Files added/modified

| File | Change | Purpose |
|---|---|---|
| `backend/app/services/player_roster_metadata_reader.py` | **Added** | Read-only service + DTO + exceptions |
| `backend/app/tests/test_m10f_player_roster_metadata_read_model.py` | **Added** | Synthetic-fixture test suite (78 tests) |
| `docs/m10-f2-backend-player-roster-read-model.md` | **Added** | This document |

**Not modified:**

- `backend/app/api.py` — **no new endpoint added in F2** (see §5 for rationale).
- `frontend/**` — no change.
- `data/snapshots/**` — no change (verified still contains only teams/visual metadata
  + source_manifest + manifest; no player_identities.json, no roster_memberships.json).
- `schema/**` — no change (E3/E4 schemas from M10-E are reused as-is).
- `backend/app/models/**`, `backend/app/snapshot_loader.py`,
  `backend/app/services/orchestrator*` — no change.
- Natural-language preview, trade logic, signing logic, Agent, contracts, salaries,
  cap sheets, injury/medical, rumors, scouting — **not touched**.

## 4. Read model contract

### 4.1 Entry point

```python
from backend.app.services.player_roster_metadata_reader import (
    load_player_roster_metadata,
    PlayerRosterMetadata,
)

md: PlayerRosterMetadata = load_player_roster_metadata(
    snapshot_mode="real_snapshot",  # any other value raises PlayerRosterModeError
    reference_date="2026-09-01",    # optional; defaults to date.today()
)
d = md.to_dict()  # JSON-serializable read-only projection
```

For tests, pass `snapshot_dir=tmp_path / "some_synth_snapshot"` and
`schema_dir=Path("schema")` to point at synthetic fixtures.

### 4.2 Returned fields

The `to_dict()` projection contains only (matching the DTOs in
`player_roster_metadata_reader.py` exactly):

Top-level (`PlayerRosterMetadata.to_dict()`):

- `snapshot_id`, `snapshot_mode` (always `"real_snapshot"`), `as_of_date`
- `data_freshness_warning` (from `source_manifest`, falling back to `player_identities`)
- `limitations` (from `player_identities.doc`)
- `manual_review_required` (always `true`), `live_eligible` (always `false`)
- `no_official_branding` (always `true` — inherited from team_visual_metadata)
- `players[]` — entries produced by `PlayerIdentity.to_dict()`:
  - `player_id`, `display_name`, `first_name`, `last_name`, `position`
  - `birthdate` (string or null), `height` (string or null), `weight` (string or null)
  - `source_name`, `source_type`, `as_of_date`
  - `data_freshness_warning`, `limitations[]`, `notes[]`
- `roster_memberships[]` — entries produced by `RosterMembership.to_dict()`:
  - `team_id`, `player_id`, `roster_status`, `membership_id` (string or null)
  - `source_name`, `source_type`, `as_of_date`
  - `data_freshness_warning`, `limitations[]`, `notes[]`
- `source_summary[]` — entries produced by `SourceFileSummary.to_dict()` for the
  two player/roster normalized files (player_identities.json and
  roster_memberships.json):
  - `file_path`, `source_name`, `source_type`, `as_of_date`
  - `manual_review_required`, `live_eligible`, `stale_after_date` (always null,
    as staleness is tracked at top-level source_manifest)
  - `data_freshness_warning`, `limitations[]`
- `warnings[]` — soft warnings (e.g., defaulted stale_after_date)

### 4.3 Explicitly excluded fields (defense-in-depth)

The returned projection never contains, and a post-load scan will hard-error
if any of these keys (or any key starting with them) appear in loaded data
as extra fields beyond the schema:

- Salary / contract / cap: `salary`, `contract`, `cap_hold`, `cap_hit`,
  `cap_number`, `cap`, `payroll`, `luxury_tax`, `dead_money`,
  `bird_rights`, `exception`, `waiver`, `guaranteed`, `option`,
  `extension`, `buyout`, `salary_cap`
- Injury / medical: `injury`, `injured`, `medical`, `health`,
  `injury_status`, `injury_note`, `day_to_day`, `out`, `questionable`,
  `probable`, `doubtful`, `ir`, `gtd`
- Rumors / scouting: `rumor`, `scouting`, `scout`, `scouting_opinion`,
  `grade`, `rating`, `projection` (depth-chart/minutes projection),
  `trade_value`, `trade_eligibility`, `trade_eligible`
- Live / current / latest: `live_status`, `live`, `current_`, `latest`,
  `depth_chart`, `minutes`, `usage_rate`, `starter`, `backup`
- Execution / mutation: `execute`, `apply`, `mutate`, `write`, `commit`,
  `create_`, `update_`, `delete_`, `sign_player`, `trade_player`,
  `waive_player`, `extend_player`

A recursive `_scan_forbidden_keys` walks every dict in the loaded documents
and raises `PlayerRosterForbiddenFieldError` on any hit. This is
defense-in-depth **on top of** `additionalProperties: false` in the schemas.

### 4.4 Exception types

All errors are hard failures; the caller must handle them. There is no
automatic fallback to demo data.

| Exception | Raised when |
|---|---|
| `PlayerRosterModeError` | `snapshot_mode` is not `"real_snapshot"` |
| `PlayerRosterNotFoundError` | Snapshot dir or any required file is missing |
| `PlayerRosterSchemaError` | Any file fails jsonschema validation, or governance flags are wrong |
| `PlayerRosterHashError` | SHA-256 hash mismatch vs `source_manifest.file_hashes` |
| `PlayerRosterCrossReferenceError` | `roster_memberships.player_id` missing from players, or `team_id` missing from teams, or duplicate player_id, or snapshot_id mismatch across files |
| `PlayerRosterSourceError` | `per_file_sources` missing for player/roster files; forbidden `source_type`; forbidden `data_categories` present |
| `PlayerRosterStaleDataError` | Reference date is past `stale_after_date` |
| `PlayerRosterForbiddenFieldError` | Forbidden key appears anywhere in the loaded documents |

All classes inherit from a common `PlayerRosterMetadataError`.

## 5. API endpoint decision: NOT added in F2

F2 does **not** add an HTTP endpoint for `GET /api/snapshots/player-roster-metadata`.

Rationale:

1. **No real data exists yet.** The sealed snapshot
   (`nba_real_2026_preoffseason_v1/normalized/`) does not contain
   `player_identities.json` or `roster_memberships.json`. Exposing an endpoint
   that only ever returns 4xx for now creates dead surface area.
2. **No consumer is wired.** Per F1, frontend, Agent, NL preview, and
   trade/signing logic must not consume player/roster data until after F4.
   Adding an endpoint before a consumer exists invites premature integration.
3. **Service is testable in isolation.** The service accepts a `snapshot_dir`
   parameter, which is exactly what both the synthetic test suite and the future
   API handler will use. The endpoint itself is a trivial GET-only wrapper and
   belongs in F4 (real data pilot) alongside the first tiny real-data payload
   and its API tests.
4. **Minimizes diff.** Keeping F2 to service + tests + docs makes the gate
   review smaller and reduces the chance of accidental coupling to existing
   API/orchestrator code.

A future milestone (F4 recommended) will add a GET-only handler. That handler
will:

- Be GET-only.
- Accept only `snapshot_mode=real_snapshot` (reject all other modes with 400).
- Translate each `PlayerRosterMetadataError` subclass to an appropriate HTTP
  status (400 / 404 / 409 / 422 / 500).
- Never fall back to demo data.
- Not wire into Agent/NL/trade/signing.

## 6. Validation rules (service-enforced)

The service performs the following checks in order. The first failure raises a
hard error and aborts the load.

1. **Mode gate** — `snapshot_mode == "real_snapshot"` (before any disk I/O).
2. **File existence** — snapshot dir exists; all six required files exist:
   - `manifest.json`
   - `source_manifest.json`
   - `normalized/teams.json`
   - `normalized/team_visual_metadata.json`
   - `normalized/player_identities.json`
   - `normalized/roster_memberships.json`
3. **Schema validation** (jsonschema) — all six files are validated against
   their respective schemas (hard error on any mismatch):
   - `manifest.json` ← `schema/real_snapshot_manifest_schema.json`
   - `source_manifest.json` ← `schema/source_manifest_schema.json`
   - `normalized/teams.json` ← `schema/teams_schema.json`
   - `normalized/team_visual_metadata.json` ← `schema/team_visual_metadata_schema.json`
   - `normalized/player_identities.json` ← `schema/player_identities_schema.json`
   - `normalized/roster_memberships.json` ← `schema/roster_memberships_schema.json`
4. **Top-level governance flags** on both player_identities and roster_memberships:
   - `live_eligible` must be `false`
   - `manual_review_required` must be `true`
   - `limitations` must be a non-empty list
   - `data_freshness_warning` must be a non-empty string
   - `snapshot_id` must match `manifest.snapshot_id`
5. **player_identities local invariants**:
   - `player_id`s are unique (no duplicates)
   - each `player.source_type` is not in FORBIDDEN_SOURCE_TYPES
6. **roster_memberships local invariants**:
   - `roster_status` is in `ALLOWED_ROSTER_STATUSES = {"standard", "two_way",
     "training_camp", "unsigned_draft_rights", "free_agent",
     "unknown_manual_review"}`
   - each membership `source_type` not in FORBIDDEN_SOURCE_TYPES
7. **Cross-references**:
   - every `roster_memberships[].player_id` exists in `player_identities[].player_id`
   - every `roster_memberships[].team_id` exists in `teams[].team_id`
8. **source_manifest governance**:
   - `live_eligible` is `false`
   - `manual_review_required` is `true`
   - `data_categories` contains `player_identities` and `roster_memberships`
   - `data_categories` does NOT contain `contracts`, `salaries`, `cap_sheets`,
     `injuries`, `rumors`, `scouting`, or `live_status`
   - `per_file_sources` has entries for both `normalized/player_identities.json`
     and `normalized/roster_memberships.json`
   - each per-file entry's `source_type` is not in FORBIDDEN_SOURCE_TYPES
9. **Hash verification** — SHA-256 of each file's bytes matches
   `source_manifest.file_hashes[rel]` (prefix `sha256:`).
10. **Staleness** — reference date (today, or explicit override) is not later
    than `source_manifest.stale_after_date`. If `stale_after_date` is null,
    default to `as_of_date + 30 days` and emit a warning.
11. **Forbidden-field scan** — recursive walk of all loaded dicts for forbidden
    key prefixes (see §4.3).

## 7. Hard error / no-demo-fallback policy

There is **no** fallback path. Specifically:

- If any file is missing: hard `PlayerRosterNotFoundError` (no silent demotion
  to demo data, no empty players list, no synthetic placeholder).
- If any schema check fails: hard `PlayerRosterSchemaError`.
- If any hash fails: hard `PlayerRosterHashError`.
- If any cross-reference fails: hard `PlayerRosterCrossReferenceError`.
- If any forbidden field is found in data: hard `PlayerRosterForbiddenFieldError`
  (even if the schema allowed it through — defense in depth).
- If `snapshot_mode` is anything other than `real_snapshot`: hard
  `PlayerRosterModeError` before touching disk.
- If data is stale: hard `PlayerRosterStaleDataError`.

There is no warning-only mode. There is no UI "proceed anyway" path. The
returned DTO is only constructed after all checks pass.

## 8. No real data / no frontend / no Agent wiring

F2 guarantees the following:

- **No real player data**: The service is tested exclusively with pytest
  `tmp_path` synthetic fixtures. The fake players are named
  `Test Player Alpha` / `Test Player Beta` with ids `player-test-alpha` /
  `player-test-beta`. No real NBA player name appears as data (real names may
  appear only in the *forbidden-name audit* test, where they are asserted NOT
  to be present in the synthetic fixture).
- **No real roster data**: The synthetic roster binds only the two fake players
  to the 30 real team IDs (team IDs are identity facts already present in the
  sealed teams.json, which ships from M10-C).
- **data/snapshots untouched**: `data/snapshots/nba_real_2026_preoffseason_v1/normalized/`
  still contains only `teams.json` and `team_visual_metadata.json`.
- **No player_identities.json or roster_memberships.json anywhere under data/snapshots**
  (verified by an explicit regression test in the F2 suite).
- **No frontend changes**: no component, page, style, or route changes.
- **No Agent wiring**: no import of `player_roster_metadata_reader` from
  any Agent, orchestrator, NL-preview, trade, or signing module (verified by
  grep in the F2 test suite).
- **No contracts/salaries/cap sheets/injuries/rumors/scouting/live/current/
  latest/depth-chart/projection/trade-eligibility/mutation fields** — all are
  rejected by schema AND by the service's forbidden-key scan.

## 9. Synthetic fixture design

The test suite uses a single helper `_write_snapshot(tmp_path, ...)` that writes
a valid synthetic snapshot to a pytest `tmp_path` directory. The helper accepts
overrides for every document (players_doc, rosters_doc, manifest_doc,
source_manifest_doc, source_manifest_mutator, teams_doc, visual_doc) so that
negative tests can inject exactly one failure at a time.

To satisfy `teams_schema.json` (which requires `minItems: 30`) and
`team_visual_metadata.json` (which has many required identity fields), the
fixture **clones the sealed teams.json and team_visual_metadata.json** from
`data/snapshots/nba_real_2026_preoffseason_v1/normalized/`. These files contain
only team identity facts (abbreviation, city, nickname, conference, division,
non-official colors) approved in M10-B/C; no player or roster data is present
in them. The clone overwrites `snapshot_id` / `as_of_date` / `generated_at`
to match the synthetic snapshot id (`m10-f2-synth-snapshot`). This approach
avoids inventing 28 extra fake teams that would only exist in test code.

To satisfy `source_manifest_schema.json` (which requires many top-level fields
like `license_notes`, `freshness_policy`, `allowed_usage`, `redistribution_notes`),
the fixture similarly clones the sealed `source_manifest.json`, then overwrites
fields specific to the synthetic snapshot (`snapshot_id`, `as_of_date`,
`data_categories`, `per_file_sources`, `file_hashes`, `stale_after_date`, etc.).

The two synthetic players and two synthetic roster memberships are built from
scratch in `_base_players()` / `_base_rosters()` with no relation to any real
NBA player.

## 10. Test results

Test file: `backend/app/tests/test_m10f_player_roster_metadata_read_model.py`
Command: `D:\anaconda\python.exe -m pytest backend/app/tests/test_m10f_player_roster_metadata_read_model.py -q`
Result: **78 passed**.

Test classes and coverage:

- **`TestModuleShape`** (4 tests) — module exports exception classes, function
  signature, frozen DTO, `to_dict()` shape.
- **`TestServicePositive`** (11 tests) — valid synthetic snapshot loads, returns
  players and roster_memberships, correct as_of_date/warnings/limitations,
  player_id xref to players, team_id xref to teams, hash validation passes,
  per_file_sources fully covered, data_categories include player/roster,
  response excludes all forbidden fields, synthetic player names are fake.
- **`TestServiceNegative`** (26 tests, many parametrized — 63 total assertions)
  - mode != real_snapshot
  - missing player_identities.json / roster_memberships.json / manifest.json /
    source_manifest.json / teams.json / team_visual_metadata.json
  - missing file_hashes entry for player/roster files
  - missing per_file_sources entry for player/roster files
  - hash mismatch on player/roster files
  - player schema mismatch (bad player_id, missing display_name, etc.)
  - roster schema mismatch (bad membership_id, missing team_id, etc.)
  - manifest schema mismatch (missing required top-level field)
  - team_visual_metadata schema mismatch (missing required top-level field)
  - roster player_id not in players
  - roster team_id not in teams
  - live_eligible=true (players, rosters, source_manifest)
  - manual_review_required=false (players, rosters)
  - forbidden source_type (llm_generated, scraped_unreviewed, live_api) at both
    per-record and per-file levels
  - forbidden data_categories (contracts)
  - forbidden roster_status values (inactive, waived, traded, injured, active_now,
    current, latest, etc.)
  - forbidden fields appearing as extra keys (salary, contract, cap_hold,
    injury_status, rumors, scouting_opinion, live_status, execute, apply,
    mutate, write)
  - stale_after_date in the past
  - duplicate player_id
  - snapshot_id mismatch across files
- **`TestIsolation`** (4 tests) — regression guarantees:
  - No `player_identities.json` or `roster_memberships.json` exists under
    `data/snapshots/**`.
  - `data/snapshots/nba_real_2026_preoffseason_v1/normalized/` contains only
    `teams.json` and `team_visual_metadata.json`.
  - No frontend/Agent/NL/trade/signing module imports the reader.
  - No POST/PUT/PATCH/DELETE is added anywhere related to player/roster metadata.

## 11. Regression with M10-E and M10 metadata full suite

After F2's own tests pass, the following regressions must be run and pass:

- M10-E schema/read-model tests:
  - `test_m10e_source_lineage_schema.py`
  - `test_m10e_player_identity_schema.py`
  - `test_m10e_roster_membership_schema.py`
  - `test_m10f_player_roster_metadata_read_model.py` (this milestone)

- Full M10 metadata regression:
  - `test_m10_real_snapshot_schema.py`
  - `test_m10c_team_metadata.py`
  - `test_m10c_team_visual_metadata.py`
  - `test_m10d_real_snapshot_metadata_read_model.py`
  - all M10-E and M10-F tests above

Because F2 does not modify any existing file (only adds new service/tests/docs),
all pre-existing tests must continue to pass unchanged.

## 12. Next step: F3 (not F4)

F2 approval does **not** grant permission to write real player/roster data.
The next milestone must be:

**M10-F3: Source Pack + Tiny Pilot Approval Gate (docs + source pack review only)**

F3 deliverables:

1. A written source pack listing the exact public references that will be used
   for the tiny pilot (e.g., which public roster pages, which date, which
   curator, which reviewer).
2. Tiny pilot scope: max ~5 players across ~2 teams (one conference, one small
   slice) — NOT the full 30-team roster.
3. Hash plan: explicit hashing command for each real data file before landing.
4. Reviewer sign-off sheet.
5. F3 must be reviewed and approved before any real player_identities.json or
   roster_memberships.json is written to `data/snapshots/`.

Only after F3 is approved does M10-F4 (real data pilot implementation) open.
Contracts / salaries / cap sheets remain deferred past M10-F entirely.

## 13. Acceptance checklist (for ChatGPT/reviewer)

- [ ] `git status --short` shows only the three files listed in §3.
- [ ] `backend/app/services/player_roster_metadata_reader.py` is read-only
      (no file writes, no mutation of snapshot, no demo fallback).
- [ ] `backend/app/tests/test_m10f_player_roster_metadata_read_model.py` uses
      `tmp_path` for all synthetic fixtures; no files are written to
      `data/snapshots/`.
- [ ] Synthetic player names are fake (Test Player Alpha/Beta), not real NBA
      players.
- [ ] All 78 tests in the F2 suite pass.
- [ ] All M10-E and M10 metadata regression tests still pass.
- [ ] `data/snapshots/nba_real_2026_preoffseason_v1/normalized/` contains only
      `teams.json` and `team_visual_metadata.json`.
- [ ] No `player_identities.json` or `roster_memberships.json` exists under
      `data/snapshots/**`.
- [ ] No file in `frontend/**`, `backend/app/api.py`, `backend/app/models/**`,
      `backend/app/snapshot_loader.py`, `backend/app/services/orchestrator*`,
      Agent, NL preview, trade, or signing is modified.
- [ ] No POST/PUT/PATCH/DELETE endpoint is added.
- [ ] No contracts/salaries/cap sheets/injuries/rumors/scouting/live data are
      introduced.
- [ ] This document (`m10-f2-backend-player-roster-read-model.md`) is included.
