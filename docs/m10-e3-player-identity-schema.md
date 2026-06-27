# M10-E3 Player Identity Schema

M10-E3 defines the **record-level schema** for future `normalized/player_identities.json`.
It is the third milestone in the E sub-series (E1 governance gate → E2 source/
freshness/lineage envelope → **E3 player identity schema** → E4 roster membership
schema → E-smoke → E-final-handoff).

This milestone is **schema + tests + docs only**. It does not create
`normalized/player_identities.json`, does not populate any real NBA players,
does not touch contracts/salaries/cap sheets, does not touch frontend/backend
API/services/loader/Agent, and does not wire player identities into any product
feature.

Run date: 2026-06-28.
Preceding seal: M10-E2 at commit `ff09f5f` / tag `m10e2-source-freshness-lineage-schema`.

## 1. Goal

Provide a strict JSON Schema for the upcoming `normalized/player_identities.json`
that:

1. Allows only identity-level metadata (names, display name, position,
   optional birthdate/height/weight).
2. Requires full per-file and per-record lineage: `source_name`, `source_url`,
   `source_type`, `as_of_date`, `manual_review_required=true`,
   `live_eligible=false`, `data_freshness_warning`, `limitations`, `snapshot_id`.
3. Rejects money/contract fields (`salary`, `salaries`, `contract`, `contracts`,
   `cap_hold`, `guarantee`, `guarantee_amount`, `cap_sheet`, `cap_sheets`).
4. Rejects medical/injury fields (`injury`, `injuries`, `injury_status`,
   `medical`, `medical_status`, `health`).
5. Rejects PII/sensitive fields (`personal_sensitive_info`, `social_media`,
   `agent`, `agent_representation`, `headshot`, `photo_url`, `player_image`,
   `official_headshot`).
6. Rejects non-factual/opinion fields (`rumors`, `rumor`, `scouting_opinion`,
   `scouting_opinions`).
7. Rejects live/availability/projection fields (`live_status`, `availability`,
   `real_time_availability`, `projected_depth_chart`, `depth_chart`,
   `minutes_projection`, `role_projection`, `trade_eligibility`).
8. Rejects execution/mutation verbs (`execute`, `apply`, `commit`, `mutate`,
   `write`, `persist`, `save`, `delete`, `update`, `submit`, `auto_execute`,
   `auto_approve`).
9. Rejects live/current/latest naming (`current_roster`, `latest_roster`,
   `live_salaries`, `latest_data`, `live_data`, `current_salaries`,
   `real_time_data`).
10. Rejects logo/brand fields (defence-in-depth, consistent with
    `teams_schema.json` and `team_visual_metadata_schema.json`).
11. Uses the E2-extended `source_type` enum (only `manual_curated`,
    `public_reference`, `league_public_reference`, `team_public_reference`,
    `manual_review`) and hard-rejects `llm_generated` / `scraped_unreviewed` /
    `live_api`.

## 2. Why E3 is schema-only (no real players)

M10-E1 governance set a strict ordering:

> E1 governance → E2 source/freshness/lineage envelope → E3 player identity
> schema → E4 roster membership schema → E-smoke → E-final-handoff.

Schema must precede data for three reasons:

- **Safety before content.** The forbidden-field list (40+ rejected keys) is
  the safety net that prevents any future curator (or LLM assist) from
  silently introducing salary, medical, or live-status columns. If we add
  records before the schema exists, we lose the ability to fail closed.
- **Provenance defaults.** Every future record is required to carry
  `manual_review_required=true` and `live_eligible=false`. Making these
  `const`-enforced at the schema level means a forgotten flag is a hard
  validation error, not a service-level fallback.
- **Hard-error, no-demo-fallback contract.** As with M10-D1 and M10-E2, any
  schema violation must raise a typed error (HTTP 500), never fall back to
  demo/generated player data. The schema is the line in the sand.

M10-E3 therefore:

- Defines `schema/player_identities_schema.json`.
- Tests it with **synthetic fake-only fixtures** (`Test Player Alpha`,
  `Test Player Beta`, player ids `p-syn-alpha`, `p-syn-beta`, …).
- Does **not** create `normalized/player_identities.json` in
  `data/snapshots/nba_real_2026_preoffseason_v1/`.
- Does **not** add LeBron James, Stephen Curry, Luka Dončić, Victor
  Wembanyama, or any real NBA player. A dedicated content-audit test
  (`test_fixture_contains_no_real_nba_player_names`) walks every string in
  the synthetic fixture and fails if any of the listed real names appear.
- Does **not** touch roster, contracts, salaries, cap sheets, or any
  frontend/backend service code.

Real player data — when governance allows it in a post-E-smoke milestone —
will be curated into a separate milestone with its own browser smoke, cross-
reference checks against `teams.json`, and a dedicated governance review.

## 3. `schema/player_identities_schema.json` structure

The new schema file is at
[schema/player_identities_schema.json](file:///D:/FrontOffice-Offseason-Agent/schema/player_identities_schema.json).

It follows the same conventions as
[schema/teams_schema.json](file:///D:/FrontOffice-Offseason-Agent/schema/teams_schema.json)
and
[schema/team_visual_metadata_schema.json](file:///D:/FrontOffice-Offseason-Agent/schema/team_visual_metadata_schema.json):
draft 2020-12, `$id` under `frontoffice-offseason-agent/schemas/`,
`additionalProperties: false`, a `$defs.player` sub-schema, and `propertyNames`
forbidden-key lists at both top level and per-player level.

### 3.1 Top-level required fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | string | ✅ | e.g. `m10-e3-v1` |
| `snapshot_id` | string (pattern `^[a-z0-9_-]+$`) | ✅ | Must match per-record `snapshot_id` |
| `as_of_date` | string (`YYYY-MM-DD`) | ✅ | Cutoff date |
| `generated_at` | string | optional | ISO 8601 timestamp |
| `source_name` | string (non-empty) | ✅ | |
| `source_url` | string \| null | optional | |
| `source_type` | enum | ✅ | Safe provenance enum |
| `manual_review_required` | boolean `const: true` | ✅ | |
| `live_eligible` | boolean `const: false` | ✅ | |
| `data_freshness_warning` | string (non-empty) | ✅ | UI-consumable warning |
| `limitations` | string[] (minItems: 1) | ✅ | Caveats |
| `players` | array of `$defs.player` | ✅ | Identity records |

Top-level `additionalProperties: false` and a `propertyNames.not.enum` list
reject 56 forbidden keys (money, medical, PII, rumors, live/projection,
mutation verbs, live naming, logos).

### 3.2 Per-player object (`$defs.player`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `player_id` | string (pattern `^[a-z][a-z0-9_-]*$`) | ✅ | Stable lowercase id. Synthetic tests use `p-syn-XXX`; future curated data may use e.g. `nba-player-slug`. |
| `display_name` | string (non-empty) | ✅ | UI display form, e.g. `T. Alpha` for the synthetic fixture |
| `first_name` | string (non-empty) | ✅ | Given name |
| `last_name` | string (non-empty) | ✅ | Family name |
| `birthdate` | `YYYY-MM-DD` string \| null | optional | Null if unknown/withheld |
| `height` | string (non-empty) \| null | optional | Human-readable display string, e.g. `6-7` |
| `weight` | string (non-empty) \| null | optional | Human-readable display string, e.g. `220 lb` |
| `position` | enum | ✅ | `PG`/`SG`/`SF`/`PF`/`C`/`G`/`F`/`FC`/`GF` |
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

Per-player `additionalProperties: false` and an identical `propertyNames`
forbidden-key list mirror the top-level guard. Unknown keys like
`jersey_number` are rejected at the schema layer (caught by
`test_additional_properties_per_player_fails`).

### 3.3 `source_type` safe enum

Allowed values:

- `manual_curated` — hand-curated identity record
- `public_reference` — public reference site (non-live)
- `league_public_reference` — league-provided public reference
- `team_public_reference` — team-provided public reference
- `manual_review` — explicitly flagged for manual review

Forbidden values (and any other string):

- `llm_generated`
- `scraped_unreviewed`
- `live_api`

Forbidden values are **not** listed in the enum, so any attempt to set them
fails with a standard enum validation error.

### 3.4 `position` enum

- Guards: `PG`, `SG`, `SF`, `PF`, `C`
- Combo/wing labels: `G`, `F`, `FC`, `GF`

Precise positional deployment, minutes, and depth-chart placement are out of
scope for identity metadata and are explicitly forbidden (see §3.5).

### 3.5 Forbidden fields (union of top-level and per-player bans)

Forbidden at both top-level **and** per-player, producing a hard validation
error if present:

- **Money / contract:** `salary`, `salaries`, `contract`, `contracts`,
  `cap_hold`, `guarantee`, `guarantee_amount`, `cap_sheet`, `cap_sheets`
- **Medical / injury:** `injury`, `injuries`, `injury_status`, `medical`,
  `medical_status`, `health`
- **Sensitive / PII / representation:** `personal_sensitive_info`,
  `social_media`, `agent`, `agent_representation`, `headshot`, `headshot_url`,
  `player_image`, `photo_url`, `official_headshot`
- **Non-factual / opinion:** `rumors`, `rumor`, `scouting_opinion`,
  `scouting_opinions`
- **Live / availability / projection:** `live_status`, `availability`,
  `real_time_availability`, `projected_depth_chart`, `depth_chart`,
  `minutes_projection`, `role_projection`, `trade_eligibility`
- **Mutation / execution verbs:** `execute`, `apply`, `commit`, `mutate`,
  `write`, `persist`, `save`, `delete`, `update`, `submit`, `auto_execute`,
  `auto_approve`
- **Live / current / latest naming:** `current_roster`, `latest_roster`,
  `live_salaries`, `latest_data`, `live_data`, `current_salaries`,
  `real_time_data`
- **Logos / branding:** `logo_path`, `logo_url`, `official_logo`, `nba_logo`,
  `team_logo`, `mascot_image`

## 4. What this schema deliberately does NOT contain

- **No salary / contract / cap data.** Ever. Those are M10-F+ concerns and
  require a separate governance review.
- **No injury / medical status.**
- **No scouting / rumors / projections.**
- **No live/current/latest data.** All records are frozen as of `as_of_date`.
- **No jersey numbers, headshots, agent info, or social media.**
- **No execution / mutation hooks.** There is no field that implies a write
  path can be triggered from player identity data.

## 5. Hard error / no demo fallback, Agent/frontend boundaries

The M10-D1 hard-error contract continues:

- Any future load of `normalized/player_identities.json` that fails schema
  validation must raise a typed error (`RealSnapshotSchemaError`), mapped to
  HTTP 500. There is no fallback to demo/generated player data and no
  stub/silent merge.
- Hash mismatches will raise `RealSnapshotHashError`; file-not-found will
  raise `RealSnapshotNotFoundError`; team-id cross-reference failures (in E4)
  will raise `RealSnapshotCrossReferenceError`.

### 5.1 Agent boundary

- The Agent, orchestrator, intent classifier, natural-language-preview,
  proposal builder, trade simulator, and transaction rule engine remain
  isolated from real player identity data in M10-E3.
- No LLM is prompted with real player data in any product flow.
- No module under `backend/app/services/` other than the dedicated future
  reader service may import player identity data; E-Smoke will add static-
  import guardrail tests mirroring M10-D1.

### 5.2 Frontend boundary

- M10-E3 does not modify any file under `frontend/`.
- No player UI is added. The `/offseason` panel continues to be the M10-D2
  team selector + abbreviation badge.
- Selected team remains component-local `useState`; it does not drive player
  inspection, signing, trade, hold, or natural-language-preview flows.
- A future "player inspector" panel must wait until E-Smoke passes and a
  dedicated frontend design doc is written, with its own browser smoke.

## 6. `data/snapshots/` is untouched; no real player data

- `data/snapshots/nba_real_2026_preoffseason_v1/normalized/` continues to
  contain exactly `teams.json` and `team_visual_metadata.json` (asserted by
  `test_real_normalized_dir_contains_only_expected_files`).
- There is **no** `player_identities.json` in the real snapshot directory.
- There is **no** `roster_memberships.json`, `contracts.json`, `salaries.json`,
  `cap_sheet(s).json`, `players.json`, `rosters.json`, `injuries.json`,
  `rumors.json`, or `scouting_opinions.json`.
- The sealed real `source_manifest.json` still lists only `["teams",
  "team_visual_metadata"]`.
- All test fixtures are in-memory dicts; no file is written into
  `data/snapshots/` by the test suite.

## 7. Test results

All tests run from `D:\FrontOffice-Offseason-Agent` with
`D:\anaconda\python.exe -m pytest`.

### 7.1 New E3 schema tests

```
pytest backend/app/tests/test_m10e_player_identity_schema.py -q
```

Result: **178 passed** (13 positive, multiple parametrized expansions
covering all 5 safe source types and the standard position enum; 14 negative
base cases expanded via parametrize to 56 forbidden top-level fields and 56
forbidden per-player fields plus 3 forbidden source types at each level;
1 real-name content audit; 12 regression/real-snapshot-directory checks).

### 7.2 E2 + E3 combined

```
pytest backend/app/tests/test_m10e_source_lineage_schema.py
       backend/app/tests/test_m10e_player_identity_schema.py -q
```

Result: **236 passed** (58 E2 + 178 E3), confirming the E2 envelope and
E3 record schema coexist cleanly.

### 7.3 Full M10 metadata regression

```
pytest backend/app/tests/test_m10_real_snapshot_schema.py
       backend/app/tests/test_m10c_team_metadata.py
       backend/app/tests/test_m10c_team_visual_metadata.py
       backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py
       backend/app/tests/test_m10e_source_lineage_schema.py
       backend/app/tests/test_m10e_player_identity_schema.py -q
```

Result: **488 passed** (48 + 62 + 95 + 47 + 58 + 178). No failures. The
Windows-only pytest tempdir `PermissionError [WinError 5]` on cleanup is the
pre-existing environmental issue noted in M10-E2 and is unrelated to code
under test.

### 7.4 E3 is schema + docs + tests only

No frontend/API/service/loader/orchestrator/Agent files were touched. No
data files under `data/snapshots/` were created or modified. No contracts/
salaries/cap sheets data was introduced. No real NBA player data is present
in the repo after this milestone.

## 8. Next: M10-E4 Roster Membership Schema (still schema-only)

M10-E4 will define `schema/roster_memberships_schema.json`, covering:

- A `roster_memberships` array with per-membership records.
- Required `roster_membership_id`, `player_id` (xref to future
  `player_identities.json`), `team_id` (xref `teams.json`), `as_of_date`.
- A six-value `roster_status` enum (per M10-E1: standard / two_way /
  exhibit_10 / training_camp / unsigned_draft_rights / inactive_reserve) —
  exact enum will be finalized in E4.
- Same lineage envelope (source_name/source_url/source_type/as_of_date/
  manual_review_required/live_eligible/data_freshness_warning/limitations/
  snapshot_id).
- Cross-reference rules that every roster membership must reference an
  existing `team_id` (and, when both files exist in a future milestone, an
  existing `player_id`).
- Same comprehensive forbidden-field list as E3.

E4 must remain **schema + tests + docs only**, using synthetic fixtures
(`p-syn-alpha → nba-GSW` etc.) and must not:

- Create `normalized/roster_memberships.json`.
- Add any real player-to-team mapping.
- Touch contracts/salaries/cap sheets.
- Touch frontend/API/services/loader/Agent.
