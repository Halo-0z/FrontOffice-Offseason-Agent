# M10-E4 Roster Membership Schema

M10-E4 defines the **record-level schema** for future
`normalized/roster_memberships.json`. It is the fourth milestone in the E
sub-series (E1 governance gate → E2 source/freshness/lineage envelope →
E3 player identity schema → **E4 roster membership schema** → E-smoke →
E-final-handoff).

This milestone is **schema + tests + docs only**. It does not create
`normalized/roster_memberships.json`, does not populate any real NBA
roster mappings, does not touch contracts/salaries/cap sheets, does not
touch frontend/backend API/services/loader/Agent, and does not wire
roster memberships into any product feature.

Run date: 2026-06-28.
Preceding seal: M10-E3 at commit `26883e4` / tag `m10e3-player-identity-schema`.

## 1. Goal

Provide a strict JSON Schema for the upcoming
`normalized/roster_memberships.json` that:

1. Allows only membership-level metadata: `team_id`, `player_id`, a
   constrained low-risk `roster_status` enum, and full provenance.
2. Requires per-file and per-record lineage: `source_name`, `source_url`,
   `source_type`, `as_of_date`, `manual_review_required=true`,
   `live_eligible=false`, `data_freshness_warning`, `limitations`,
   `snapshot_id`.
3. Enforces a **deliberately narrow `roster_status` enum** (only six
   low-risk values) and hard-rejects statuses that imply live roster
   state, injury, transactions, or availability (`inactive`, `waived`,
   `traded`, `injured`, `suspended`, `questionable`, `probable`,
   `day_to_day`, `available`, `unavailable`, `active_now`, `latest`,
   `current`).
4. Rejects money/contract fields (`salary`, `salaries`, `contract`,
   `contracts`, `cap_hold`, `guarantee`, `guarantee_amount`, `cap_sheet`,
   `cap_sheets`).
5. Rejects medical/injury fields (`injury`, `injuries`, `injury_status`,
   `medical`, `medical_status`, `health`).
6. Rejects trade/restriction fields (`trade_eligibility`,
   `trade_restriction`, `no_trade_clause`).
7. Rejects live/availability/current fields (`availability`,
   `real_time_availability`, `live_status`, `current_status`,
   `latest_status`, `active_now`, `current_roster`, `latest_roster`,
   `live_data`, `latest_data`, `current_salaries`, `real_time_data`,
   `current`, `latest`).
8. Rejects deployment/projection fields (`projected_depth_chart`,
   `depth_chart`, `minutes_projection`, `role_projection`, `starter`,
   `bench_role`, `rotation_role`).
9. Rejects non-factual/opinion fields (`rumors`, `rumor`,
   `scouting_opinion`, `scouting_opinions`).
10. Rejects PII/sensitive fields (`personal_sensitive_info`,
    `social_media`, `agent`, `agent_representation`, `headshot`,
    `headshot_url`, `player_image`, `photo_url`, `official_headshot`).
11. Rejects execution/mutation verbs (`execute`, `apply`, `commit`,
    `mutate`, `write`, `persist`, `save`, `delete`, `update`, `submit`,
    `auto_execute`, `auto_approve`).
12. Rejects logo/brand fields (defence-in-depth, consistent with E2/E3).
13. Uses the E3-compatible `source_type` enum (only `manual_curated`,
    `public_reference`, `league_public_reference`, `team_public_reference`,
    `manual_review`) and hard-rejects `llm_generated` /
    `scraped_unreviewed` / `live_api`.
14. Enforces `team_id` pattern `^nba-[A-Z]{3}$` (matching `teams.json`)
    and `player_id` pattern `^[a-z][a-z0-9_-]*$` (matching
    `player_identities_schema.json`), so future cross-reference checks
    can rely on stable id shapes.

## 2. Why E4 is schema-only (no real roster data)

The same safety-before-content principle that drove E3 applies to E4,
with one additional concern: roster status is far more tempting to
mislabel as "live/current" than identity is. A too-broad `roster_status`
enum (e.g. including `active` / `injured` / `waived`) would let a future
curator or service silently ship near-live availability data through a
file that is supposed to be a frozen as-of snapshot. E4 therefore:

- Narrows the enum to six explicitly low-risk values.
- Defers any live/transaction/injury/availability statuses to M10-F+
  with their own governance review.
- Tests the forbidden statuses directly (13 values, parametrized) so
  that a future enum widening must also widen the test suite and the
  accompanying governance document.
- Uses synthetic fake-only fixtures (`player-test-alpha`,
  `player-test-beta`, membership ids `rm-syn-alpha`/`rm-syn-beta`,
  team ids `nba-ATL`/`nba-BOS`).
- Does **not** create `normalized/roster_memberships.json` in
  `data/snapshots/nba_real_2026_preoffseason_v1/`.
- Does **not** add any real player-to-team mapping. A dedicated
  content-audit test (`test_fixture_contains_no_real_nba_player_names`)
  walks every string in the synthetic fixture and fails if any of the
  listed real NBA names appear.
- Does **not** touch identity data, contracts/salaries/cap sheets, or
  any frontend/backend service code.

## 3. `schema/roster_memberships_schema.json` structure

The new schema file is at
[schema/roster_memberships_schema.json](file:///D:/FrontOffice-Offseason-Agent/schema/roster_memberships_schema.json).

It follows the same conventions as
[teams_schema.json](file:///D:/FrontOffice-Offseason-Agent/schema/teams_schema.json),
[team_visual_metadata_schema.json](file:///D:/FrontOffice-Offseason-Agent/schema/team_visual_metadata_schema.json),
and
[player_identities_schema.json](file:///D:/FrontOffice-Offseason-Agent/schema/player_identities_schema.json):
draft 2020-12, `$id` under `frontoffice-offseason-agent/schemas/`,
`additionalProperties: false`, a `$defs.membership` sub-schema, and
`propertyNames` forbidden-key lists at both top level and per-membership
level.

### 3.1 Top-level required fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | ✅ | e.g. `m10-e4-v1` |
| `snapshot_id` | string (pattern `^[a-z0-9_-]+$`) | ✅ | Must match per-record `snapshot_id` |
| `as_of_date` | string (`YYYY-MM-DD`) | ✅ | Cutoff date |
| `generated_at` | string | optional | ISO 8601 timestamp |
| `source_name` | string (non-empty) | ✅ | |
| `source_url` | string \| null | optional | |
| `source_type` | enum | ✅ | Safe provenance enum (E3-compatible) |
| `manual_review_required` | boolean `const: true` | ✅ | |
| `live_eligible` | boolean `const: false` | ✅ | |
| `data_freshness_warning` | string (non-empty) | ✅ | UI-consumable warning |
| `limitations` | string[] (minItems: 1) | ✅ | Caveats |
| `roster_memberships` | array of `$defs.membership` | ✅ | Membership records |

Top-level `additionalProperties: false` and a comprehensive
`propertyNames.not.enum` list reject 78 forbidden keys (money, medical,
trade restrictions, availability/live, projections, role labels,
opinion/rumors, PII, mutation verbs, forbidden status names, current/
latest naming, logos).

### 3.2 Per-membership object (`$defs.membership`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `membership_id` | string (pattern `^[a-z][a-z0-9_-]*$`) | optional | Stable lowercase id; synthetic tests use `rm-syn-XXX`. |
| `team_id` | string (pattern `^nba-[A-Z]{3}$`) | ✅ | Matches `teams.json` team ids (e.g. `nba-ATL`). |
| `player_id` | string (pattern `^[a-z][a-z0-9_-]*$`) | ✅ | Matches `player_identities_schema.json` player ids (e.g. `p-syn-alpha`). |
| `roster_status` | enum | ✅ | Six-value safe enum; see §4. |
| `source_name` | string (non-empty) | ✅ | Per-record source |
| `source_url` | string \| null | optional | |
| `source_type` | enum | ✅ | Same safe enum as top-level |
| `as_of_date` | `YYYY-MM-DD` string | ✅ | Record-level cutoff |
| `manual_review_required` | boolean `const: true` | ✅ | |
| `live_eligible` | boolean `const: false` | ✅ | |
| `data_freshness_warning` | string (non-empty) | ✅ | Per-record warning |
| `snapshot_id` | string (pattern) | ✅ | Must equal top-level snapshot id |
| `notes` | string[] | optional | Curator disambiguation notes |
| `limitations` | string[] (minItems: 1) | ✅ | Per-record caveats |

Per-membership `additionalProperties: false` and an identical
`propertyNames` forbidden-key list mirror the top-level guard. Unknown
keys like `jersey_number` are rejected at the schema layer (caught by
`test_additional_properties_per_membership_fails`).

Note: `membership_id` is optional in E4 to keep the door open for
curators who prefer composite keys; the schema still validates ids
when present and rejects uppercase/id-spaces via pattern.

### 3.3 `source_type` safe enum (same as E3)

Allowed values: `manual_curated`, `public_reference`,
`league_public_reference`, `team_public_reference`, `manual_review`.

Forbidden (and any other string): `llm_generated`, `scraped_unreviewed`,
`live_api`.

## 4. `roster_status` safe enum — what's allowed, what's deferred

### Allowed in M10-E

| Value | Meaning |
|---|---|
| `standard` | Standard NBA contract (generic membership, no salary/term details) |
| `two_way` | Two-way contract affiliation (generic membership only) |
| `training_camp` | Training-camp / preseason roster invitee |
| `unsigned_draft_rights` | Player whose draft rights are held but is unsigned |
| `free_agent` | Offseason free-agent placeholder for identity-only listings |
| `unknown_manual_review` | Explicit "needs human review" bucket; UI must surface this clearly |

These six values are deliberately chosen so that:

- They describe membership *category*, not availability, injury, or
  transaction state.
- They don't imply the data is live or current.
- They don't encode money, contract length, options, or guarantees.
- They don't encode role (starter/bench) or minutes.

### Explicitly DEFERRED to M10-F+ (forbidden at schema layer)

The following strings are **rejected** by both the `roster_status` enum
and the top-level/per-membership `propertyNames` blacklist, so they
cannot sneak in via any field:

- **Injury / medical:** `injured`, `questionable`, `probable`,
  `day_to_day`
- **Transactions / roster churn:** `waived`, `traded`, `suspended`,
  `inactive`
- **Availability:** `available`, `unavailable`, `active_now`
- **Live / current / latest naming:** `current`, `latest`,
  `current_status`, `latest_status`, `current_roster`, `latest_roster`,
  `active_now`, `live_data`, `latest_data`, `real_time_data`

Each of these would imply either real-time data flow, medical
disclosure, or transaction processing — all outside the M10-E envelope.
Parametrized tests (`test_forbidden_roster_status_fails`) cover all 13
forbidden status strings.

## 5. What this schema deliberately does NOT contain

- **No salary / contract / cap data.** Ever, in M10-E. Those are M10-F+
  with separate governance.
- **No injury / medical / availability status.**
- **No transaction / waiver / trade state.**
- **No depth chart, minutes projection, or starter/bench labels.**
- **No live/current/latest naming.** All records are frozen as of
  `as_of_date`.
- **No jersey numbers, headshots, agent info, or social media.**
- **No execution / mutation hooks.** There is no field that implies a
  write path can be triggered from roster membership data.
- **No player display fields.** Identity lives in
  `player_identities.json`; this file is strictly a join table with
  lineage and a narrow status enum.

## 6. Hard error / no demo fallback, Agent/frontend boundaries

The M10-D1 hard-error contract continues:

- Any future load of `normalized/roster_memberships.json` that fails
  schema validation must raise a typed error (`RealSnapshotSchemaError`),
  mapped to HTTP 500. There is no fallback to demo/generated roster data
  and no stub/silent merge.
- Hash mismatches raise `RealSnapshotHashError`; file-not-found raises
  `RealSnapshotNotFoundError`; team-id / player-id cross-reference
  failures (when both files exist) will raise
  `RealSnapshotCrossReferenceError`; E-Smoke will wire those checks.

### 6.1 Agent boundary

- The Agent, orchestrator, intent classifier, natural-language-preview,
  proposal builder, trade simulator, and transaction rule engine remain
  isolated from real roster membership data in M10-E4.
- No LLM is prompted with real roster data in any product flow.
- No module under `backend/app/services/` other than the dedicated
  future reader service may import roster membership data; E-Smoke will
  add static-import guardrail tests mirroring M10-D1.

### 6.2 Frontend boundary

- M10-E4 does not modify any file under `frontend/`.
- No roster UI is added. The `/offseason` panel continues to be the
  M10-D2 team selector + abbreviation badge.
- Selected team remains component-local `useState`; it does not drive
  roster inspection, signing, trade, hold, or natural-language-preview
  flows.
- A future "roster inspector" panel must wait until E-Smoke passes and
  a dedicated frontend design doc is written, with its own browser
  smoke.

## 7. `data/snapshots/` is untouched; no real roster data

- `data/snapshots/nba_real_2026_preoffseason_v1/normalized/` continues
  to contain exactly `teams.json` and `team_visual_metadata.json`
  (asserted by `test_real_normalized_dir_contains_only_expected_files`).
- There is **no** `roster_memberships.json` in the real snapshot
  directory.
- There is **no** `player_identities.json` yet in the real snapshot
  directory (that is E3+E-smoke real-data work, post-M10-E).
- There is **no** `contracts.json`, `salaries.json`, `cap_sheet(s).json`,
  `players.json`, `rosters.json`, `injuries.json`, `rumors.json`, or
  `scouting_opinions.json`.
- The sealed real `source_manifest.json` still lists only
  `["teams", "team_visual_metadata"]`.
- All test fixtures are in-memory dicts; no file is written into
  `data/snapshots/` by the test suite.

## 8. Test results

All tests run from `D:\FrontOffice-Offseason-Agent` with
`D:\anaconda\python.exe -m pytest`.

### 8.1 New E4 schema tests

```
pytest backend/app/tests/test_m10e_roster_membership_schema.py -q
```

Result: **244 passed** (14 positive, plus parametrized expansions
covering 5 team ids, 4 player ids, 6 safe roster statuses, 5 safe source
types; negative coverage parametrized across 13 forbidden statuses, 78
forbidden fields at top level, 78 forbidden fields per membership, and 3
forbidden source types at each level; plus 1 real-name content audit
and 13 regression/real-snapshot-directory checks).

### 8.2 E2 + E3 + E4 combined

```
pytest backend/app/tests/test_m10e_source_lineage_schema.py
       backend/app/tests/test_m10e_player_identity_schema.py
       backend/app/tests/test_m10e_roster_membership_schema.py -q
```

Result: **480 passed** (58 E2 + 178 E3 + 244 E4), confirming the E2
envelope, E3 record schema, and E4 membership schema all coexist
cleanly.

### 8.3 Full M10 metadata regression

```
pytest backend/app/tests/test_m10_real_snapshot_schema.py
       backend/app/tests/test_m10c_team_metadata.py
       backend/app/tests/test_m10c_team_visual_metadata.py
       backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py
       backend/app/tests/test_m10e_source_lineage_schema.py
       backend/app/tests/test_m10e_player_identity_schema.py
       backend/app/tests/test_m10e_roster_membership_schema.py -q
```

Result: **732 passed** (48 + 62 + 95 + 47 + 58 + 178 + 244). No
failures. The Windows-only pytest tempdir `PermissionError [WinError 5]`
on cleanup is the pre-existing environmental issue noted in M10-E2/E3
and is unrelated to code under test.

### 8.4 E4 is schema + docs + tests only

No frontend/API/service/loader/orchestrator/Agent files were touched. No
data files under `data/snapshots/` were created or modified. No
contracts/salaries/cap sheets data was introduced. No real NBA player
or roster data is present in the repo after this milestone.

## 9. Next: M10-E Smoke (still schema/docs/tests governance)

M10-E Smoke is the **schema + test + governance integration smoke**
milestone. It does **not** add real player or roster data, and it does
**not** wire product features. It will:

1. Add a small set of cross-reference tests (synthetic, in-memory):
   - `roster_memberships.team_id` must match a known `team_id` from
     `teams.json`.
   - When both `player_identities.json` and `roster_memberships.json`
     are present, `roster_memberships.player_id` must match a known
     `player_id` from `player_identities.json`.
2. Confirm the real snapshot still loads through
   `real_snapshot_metadata_reader.py` and that the new schemas do not
   interfere with existing M10-D1/D2 behaviour (no player/roster
   leakage into the existing endpoint).
3. Confirm the E2 source_manifest per-file `source_type` /
   `manual_review_required` / `live_eligible` / `data_freshness_warning`
   / `limitations` governance fields are consistent across the three
   future categories.
4. Add static-import guardrail tests ensuring Agent /
   natural-language-preview / trade/signing logic cannot import player
   or roster data directly (mirroring M10-D1's snapshot_loader
   isolation test).
5. Still **not** create `normalized/player_identities.json` or
   `normalized/roster_memberships.json`; still use synthetic in-memory
   fixtures.
6. Produce a final E-Smoke governance doc that opens the door for a
   post-M10-E milestone (M10-F or later) to consider real player/
   roster data curation under the locked-down envelope.
