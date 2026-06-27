# M10-E Smoke Verification

M10-E Smoke is a **docs-only verification milestone**. It does not add code,
schemas, tests, data, or features. It re-runs all M10-E tests, performs static
guardrail checks, and records the state of the E sub-series as it enters the
final handoff gate.

Run date: 2026-06-28.
Environment: Windows, `D:\anaconda\python.exe` (Python 3.x), pytest.

## 1. Baseline

| Check | Result |
|---|---|
| `git status --short` | **Clean** (empty) |
| `git log --oneline -1` | `0b28729 Add M10-E4 roster membership schema` |
| `git tag --points-at HEAD` | `m10e4-roster-membership-schema` |
| Working tree | No uncommitted changes before this smoke doc is added |
| `D:\DraftMind` | Untouched |

Smoke scope:

- Re-run E2, E3, E4 schema tests.
- Re-run E2+E3+E4 combined.
- Re-run the full M10 metadata regression (B + C1 + C2 + D1 + E2 + E3 + E4).
- Perform static verification that no real data files, frontend/backend wiring,
  mutation endpoints, or real NBA players have been introduced.
- Produce this single verification document.

## 2. Scope

This milestone is explicitly **docs-only**. It:

- ✅ Re-runs all existing M10-E tests.
- ✅ Performs static checks on files, directories, schemas, and references.
- ✅ Adds this verification document.
- ❌ Does **not** change any code (frontend, backend, API, services, loader,
  orchestrator, natural-language-preview, trade/signing logic).
- ❌ Does **not** change any schema (source_manifest_schema,
  player_identities_schema, roster_memberships_schema, teams_schema,
  team_visual_metadata_schema, real_snapshot_manifest_schema).
- ❌ Does **not** change any test files.
- ❌ Does **not** add or modify any data snapshots (`data/snapshots/**`).
- ❌ Does **not** add real player identities, real roster memberships,
  contracts, salaries, or cap sheets.
- ❌ Does **not** add logos, headshots, or branding assets.
- ❌ Does **not** connect to the real NBA API, scrape websites, or call LLMs.
- ❌ Does **not** add execute/apply/commit/mutate/write/persist/save/delete/
  update/submit endpoints.
- ❌ Does **not** commit, tag, or push.

## 3. What M10-E currently contains

M10-E is a governance + schema + test sub-series. At the time of this smoke,
the real snapshot and the product surface remain exactly as sealed at M10-D2
(team selector + abbreviation badge only). The E sub-series adds only schema,
schema tests, and governance docs:

| Milestone | Commit | Tag | Artifacts |
|---|---|---|---|
| **E1** Governance gate | `22ca2a5` | `m10e1-player-roster-governance-gate` | `docs/m10-e-player-roster-data-governance-gate.md` (docs-only) |
| **E2** Source/freshness/lineage schema | `ff09f5f` | `m10e2-source-freshness-lineage-schema` | `schema/source_manifest_schema.json` (patched), `backend/app/tests/test_m10e_source_lineage_schema.py`, `docs/m10-e2-source-freshness-lineage-schema-patch.md` |
| **E3** Player identity schema | `26883e4` | `m10e3-player-identity-schema` | `schema/player_identities_schema.json`, `backend/app/tests/test_m10e_player_identity_schema.py`, `docs/m10-e3-player-identity-schema.md` |
| **E4** Roster membership schema | `0b28729` | `m10e4-roster-membership-schema` | `schema/roster_memberships_schema.json`, `backend/app/tests/test_m10e_roster_membership_schema.py`, `docs/m10-e4-roster-membership-schema.md` |

No E milestone adds data files, product wiring, frontend, API routes, or
backend services.

## 4. Test results

All commands run from `D:\FrontOffice-Offseason-Agent` using
`D:\anaconda\python.exe -m pytest`. Pre-existing Windows-only pytest tempdir
cleanup `PermissionError [WinError 5]` is an environmental atexit issue in
`_pytest.pathlib` and is unrelated to code under test; it appears after the
pytest summary line and does not affect pass/fail counts.

### 4.1 E2 — source lineage schema tests

```
pytest backend/app/tests/test_m10e_source_lineage_schema.py -q
```

**Result: 58 passed.** Covers: current sealed source_manifest still validates;
player_identities/roster_memberships future categories validate; forbidden
categories (contracts/salaries/cap_sheets/injuries/rumors/live_status/
current_roster/latest_roster/scouting_opinions) rejected; per-file
source_type/manual_review_required/live_eligible/data_freshness_warning/
limitations governance; file_hash coverage requirements; no real data files
in the snapshot.

### 4.2 E3 — player identity schema tests

```
pytest backend/app/tests/test_m10e_player_identity_schema.py -q
```

**Result: 178 passed.** Covers: synthetic player payload validates; multiple
fake players; null birthdate/height/weight; all 5 safe source_types;
manual_review_required=true; live_eligible=false; non-empty limitations;
data_freshness_warning; snapshot_id; position enum; optional notes/source_url
null; forbidden source_types (llm_generated/scraped_unreviewed/live_api); 56
forbidden fields rejected at top and per-player (parametrized); real NBA
player name content audit; real snapshot normalized/ dir unchanged.

### 4.3 E4 — roster membership schema tests

```
pytest backend/app/tests/test_m10e_roster_membership_schema.py -q
```

**Result: 244 passed.** Covers: synthetic roster payload validates; multiple
fake memberships; team_id nba-XXX pattern; player_id safe-id pattern; all 6
safe roster_status values (standard/two_way/training_camp/unsigned_draft_rights/
free_agent/unknown_manual_review); all 5 safe source_types;
manual_review_required=true; live_eligible=false; non-empty limitations;
data_freshness_warning; snapshot_id; optional membership_id/notes/source_url
null; 13 forbidden roster_status values rejected (inactive/waived/traded/
injured/suspended/questionable/probable/day_to_day/available/unavailable/
active_now/latest/current); forbidden source_types; 78 forbidden fields
rejected at top and per-membership (parametrized); real NBA player name
content audit; real snapshot normalized/ dir unchanged.

### 4.4 E2 + E3 + E4 combined

```
pytest backend/app/tests/test_m10e_source_lineage_schema.py
       backend/app/tests/test_m10e_player_identity_schema.py
       backend/app/tests/test_m10e_roster_membership_schema.py -q
```

**Result: 480 passed (58 + 178 + 244).** Confirms the E2 envelope, E3 record
schema, and E4 membership schema coexist cleanly without cross-schema
interference.

### 4.5 M10 metadata full regression

```
pytest backend/app/tests/test_m10_real_snapshot_schema.py
       backend/app/tests/test_m10c_team_metadata.py
       backend/app/tests/test_m10c_team_visual_metadata.py
       backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py
       backend/app/tests/test_m10e_source_lineage_schema.py
       backend/app/tests/test_m10e_player_identity_schema.py
       backend/app/tests/test_m10e_roster_membership_schema.py -q
```

**Result: 732 passed (48 + 62 + 95 + 47 + 58 + 178 + 244).** All pre-E M10
tests (M10-B real snapshot schema, M10-C1 teams, M10-C2 team visual metadata,
M10-D1 real snapshot metadata read model) continue to pass alongside the E
sub-series, confirming zero regression from the E envelope/record/membership
schemas.

## 5. Static verification results

### 5.1 No new data files in the real snapshot

Real snapshot normalized directory (`data/snapshots/nba_real_2026_preoffseason_v1/normalized/`):

| File | Status |
|---|---|
| `teams.json` | present (sealed at M10-C1) |
| `team_visual_metadata.json` | present (sealed at M10-C2) |
| `player_identities.json` | **absent** |
| `roster_memberships.json` | **absent** |
| `contracts.json` | **absent** |
| `salaries.json` | **absent** |
| `cap_sheet.json` | **absent** |
| `cap_sheets.json` | **absent** |
| `injuries.json` | **absent** |
| `rumors.json` | **absent** |
| `scouting_opinions.json` | **absent** |
| `players.json` | **absent** |
| `rosters.json` | **absent** |

Real snapshot root contains exactly `manifest.json`, `source_manifest.json`,
and `normalized/` — no new top-level files.

### 5.2 Sealed schemas present, not modified by this smoke

All six M10 schema files exist under `schema/`:

- `source_manifest_schema.json` (E2 patched, sealed at `ff09f5f`)
- `player_identities_schema.json` (E3 added, sealed at `26883e4`)
- `roster_memberships_schema.json` (E4 added, sealed at `0b28729`)
- `teams_schema.json` (M10-C1, untouched)
- `team_visual_metadata_schema.json` (M10-C2, untouched)
- `real_snapshot_manifest_schema.json` (M10-B, untouched)

This smoke document does not modify any of them.

### 5.3 No frontend / backend API / services / loader wiring

Static grep results:

- `backend/app/services/**` — **no references** to `player_identities` or
  `roster_memberships`.
- `backend/app/api.py` — existing `execute/apply/commit/mutate/write`
  references are the **guardrail rejection lists** (added in M10-B/D and
  already sealed); no new mutation endpoints were added in E1-E4.
- `backend/app/snapshot_loader.py` — untouched (verified by E2/E3/E4
  regression tests and clean git status).
- `frontend/**` (TS/TSX/JS/JSX) — **no references** to `player_identities` or
  `roster_memberships`; the `/offseason` panel remains M10-D2 team selector
  + abbreviation badge.
- Orchestrator / natural-language-preview / trade / signing logic — untouched;
  no import of player/roster data (grep over `backend/app/` shows references
  only inside the three E test files).

### 5.4 No mutation endpoint

No new route, function, or method is added that accepts execute/apply/commit/
mutate/write/persist/save/delete/update/submit/auto_execute/auto_approve
actions. The existing API layer continues to reject mutation semantics at the
guardrail level (documented in `api.py` lines 118/165-167/492-526/580-616/
677-689/740-788/853-905/945-1003).

### 5.5 No real NBA player data

A scan for 11 real NBA player names (LeBron James, Stephen Curry, Luka Dončić,
Victor Wembanyama, Giannis Antetokounmpo, Kevin Durant, Jayson Tatum,
Nikola Jokić, Joel Embiid, Shai Gilgeous-Alexander, Anthony Edwards) across
all M10-E schema/test/doc files shows hits **only** in:

- `test_m10e_player_identity_schema.py` — `REAL_NBA_PLAYER_NAMES` blacklist
  constant and docstring describing the content-audit test.
- `test_m10e_roster_membership_schema.py` — same `REAL_NBA_PLAYER_NAMES`
  blacklist constant and docstring.
- M10-E3 / E4 docs — descriptions of the content-audit guardrail.

Schema JSON files contain **zero** real NBA player names (grep confirmed).
All synthetic fixtures use clearly fake identities: `Test Player Alpha`,
`Test Player Beta`, ids `p-syn-alpha`, `p-syn-beta`, `player-test-alpha`,
`player-test-beta`, membership ids `rm-syn-alpha`/`rm-syn-beta`, team ids
`nba-ATL`/`nba-BOS`/`nba-GSW`/`nba-LAL`/`nba-MIA`/`nba-MIL` used only as
pattern coverage.

## 6. Guardrail verification

Each dangerous-field category is blocked at multiple layers (enum exclusion,
`additionalProperties: false`, `propertyNames` blacklist, and explicit negative
tests):

| Guardrail | Where enforced | Negative tests |
|---|---|---|
| **source_manifest rejects contracts/salaries/cap_sheets/live_status/rumors** | `schema/source_manifest_schema.json` data_categories enum + propertyNames; E2 test file | `test_m10e_source_lineage_schema.py` parametrized over all forbidden categories and fields |
| **Player identity schema rejects salary/contract/cap** | `schema/player_identities_schema.json` propertyNames (top + per-player) | E3 tests: `test_forbidden_top_level_field_fails` / `test_forbidden_per_player_field_fails` × 56 fields |
| **Player identity schema rejects injury/medical** | Same propertyNames blacklist | Covered by same parametrized tests (injury/injuries/injury_status/medical/medical_status/health) |
| **Player identity schema rejects social/agent/rumors/scouting/live/availability/projection** | Same propertyNames blacklist | Covered by same parametrized tests (social_media/agent/agent_representation/rumors/scouting_opinion/live_status/availability/real_time_availability/projected_depth_chart/depth_chart/minutes_projection/role_projection/trade_eligibility) |
| **Player identity schema rejects mutation verbs** | Same propertyNames blacklist | Covered (execute/apply/commit/mutate/write/persist/save/delete/update/submit/auto_execute/auto_approve) |
| **Player identity schema enforces live_eligible=false / manual_review_required=true** | `const: false` / `const: true` | E3 tests for top-level and per-player true/false variants |
| **Player identity schema rejects llm_generated/scraped_unreviewed/live_api source_type** | source_type enum | E3 parametrized tests × 3 × 2 levels |
| **Roster membership schema rejects inactive/waived/traded/injured/available/current/latest** | roster_status enum + propertyNames blacklist (defence in depth) | E4 tests: 13 forbidden roster_status values parametrized; same names also in propertyNames blacklist (× 2 levels) |
| **Roster membership schema rejects salary/contract/cap** | propertyNames blacklist (top + per-membership, 78 fields) | E4 parametrized tests × 78 × 2 levels |
| **Roster membership schema rejects injury/medical/trade_restriction/no_trade_clause** | Same propertyNames blacklist | Covered by same parametrized tests (injury/injuries/injury_status/medical/medical_status/health/trade_eligibility/trade_restriction/no_trade_clause) |
| **Roster membership schema rejects availability/live/current/latest** | Same propertyNames blacklist + enum | Covered (availability/real_time_availability/live_status/current_status/latest_status/active_now/current/latest/current_roster/latest_roster/live_data/latest_data/current_salaries/real_time_data) |
| **Roster membership schema rejects depth/role/rotation projections** | Same propertyNames blacklist | Covered (projected_depth_chart/depth_chart/minutes_projection/role_projection/starter/bench_role/rotation_role) |
| **Roster membership schema rejects mutation verbs** | Same propertyNames blacklist | Covered (execute/apply/commit/mutate/write/persist/save/delete/update/submit/auto_execute/auto_approve) |
| **Roster membership schema enforces team_id nba-XXX pattern / player_id safe-id pattern** | `pattern` on team_id (`^nba-[A-Z]{3}$`) and player_id (`^[a-z][a-z0-9_-]*$`) | E4 positive tests × 5 team ids × 4 player ids; negative tests for `nba-atl` (lowercase) and `ATL` (no prefix) |
| **file_hashes not bypassable** | `source_manifest_schema.json` requires hash entry per per_file_source; E2 tests assert missing hashes fail | E2 test `test_missing_file_hashes_for_player_identities_fails` |

All guardrails above are enforced at the **schema layer** (fail-closed), not
just in service code. Service-layer enforcement (xref checks, hard-error
HTTP 500 mapping) will be wired in a post-M10-E milestone when real data is
considered; at M10-E time there is no data to load, so no reader service
extension is needed.

## 7. Known limitations

M10-E is an intentionally narrow governance + schema + test gate. The
following are explicitly out of scope and remain deferred:

- **No real player identity data.** `normalized/player_identities.json` does
  not exist. When real player identities are curated, they will require a
  dedicated post-E milestone with manual review, hash sealing, and
  cross-reference tests against `teams.json`.
- **No real roster membership data.** `normalized/roster_memberships.json`
  does not exist. The safe six-value `roster_status` enum is deliberately
  narrow; inactive/waived/traded/injured/suspended/availability/current/
  latest statuses are deferred.
- **No backend read model for player/roster.** `real_snapshot_metadata_reader.py`
  continues to expose only team identity + visual metadata; it does not
  load or expose player or roster data.
- **No frontend player/roster UI.** The `/offseason` panel remains the
  M10-D2 team selector + abbreviation badge.
- **No Agent / NL-preview / trade / signing access to player/roster data.**
  Static-import guardrail tests (deferred to a post-E smoke) will enforce
  this when the read model is extended; at M10-E time grep already confirms
  no services import the new schemas.
- **Contracts / salaries / cap sheets remain deferred to M10-F or later,**
  under their own governance gate. The E2 `data_categories` enum explicitly
  removes `contracts` and `cap_sheets` from the allowed set, so any future
  attempt to add them fails schema validation before service code runs.
- **Headshots, agent info, social media, scouting opinions, rumors,
  projections, depth charts, minutes projections, and availability** are
  all forbidden at the schema layer in E3 and E4.

## 8. Final conclusion

**M10-E Smoke: PASSED.**

- All 732 M10 metadata regression tests pass (58 + 178 + 244 E tests;
  252 pre-E tests unchanged and passing).
- Static checks confirm: no new data files; no frontend/backend/API/loader
  wiring; no mutation endpoints; no real NBA player names outside audit
  blacklists; all dangerous-field categories are blocked at the schema
  layer; all three E schemas are sealed and unmodified by this smoke.
- The M10-E sub-series is internally consistent: E2 envelope validates
  future categories, E3 record schema enforces identity-only fields, E4
  membership schema enforces team↔player links with a narrow status enum,
  and the forbidden-field/const/pattern guards all hold.

**Recommendation: approve for ChatGPT验收 (acceptance review).**

**Next step recommended: M10-E Final Handoff.** The final handoff doc should
summarize the complete M10-E state (E1 governance, E2 envelope, E3 identity
schema, E4 membership schema, this smoke), list the locked guardrails and
known limitations, and explicitly hand off to the next milestone (M10-F or
later) which must open its own governance gate before any real player/roster
data — let alone contracts/salaries/cap sheets — can be curated.

**Still NOT recommended at this time:**

- Writing real player identities into `normalized/player_identities.json`.
- Writing real roster memberships into `normalized/roster_memberships.json`.
- Adding contracts/salaries/cap sheets in any form.
- Wiring player/roster data into the Agent, natural-language-preview,
  trade simulator, or signing logic.
- Adding a frontend player/roster UI.
- Widening the `roster_status` enum to include inactive/waived/traded/
  injured/available/current/latest.
- Adding any execute/apply/commit/mutate/write endpoint.
