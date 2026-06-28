# M10-F4 Smoke / Handoff

Run date: 2026-06-28.
Baseline: commit `a973760`, tag `m10f4b-real-player-roster-tiny-pilot`, clean working tree.

This document is the **docs-only smoke/handoff** for M10-F4 (Real Player/Roster
Tiny Pilot). It records the sealed state of F4-B, fixes the test evidence
chain, enumerates boundaries and risks, and explicitly states what this
handoff does NOT authorize going forward.

## 1. F4 Smoke / Handoff verdict

- **M10-F4-B tiny pilot is sealed.** The commit `a973760` / tag
  `m10f4b-real-player-roster-tiny-pilot` is the authoritative sealed state.
- **F4 smoke/handoff is docs-only.** This handoff document does not add data,
  code, tests, endpoints, schemas, or wiring.
- **F4-B does NOT authorize frontend/API/Agent/trade/signing consumption** of
  the tiny pilot data. No consumer wiring is permitted without a separate
  design gate.
- **F4-B does NOT represent a full roster.** It is exactly 4 players across
  2 teams.
- **F4-B does NOT represent current/live NBA data.** It is a frozen
  as-of snapshot dated 2026-06-28 with `stale_after_date=2026-07-12`.
- **F4-B is a frozen as-of tiny pilot only.** Identity + roster membership
  data, no contracts, no salaries, no cap, no injury, no scouting, no live
  status.

## 2. Completed milestone chain

| Milestone | Commit | Tag | Purpose |
|---|---|---|---|
| F1 Source Intake Design Gate | `5973b70` | `m10f1-source-intake-design-gate` | Design gate defining source classes, data categories, and governance rules for real player/roster data. No real data landed. |
| F2 Backend Read Model (Synthetic) | `b26611d` | `m10f2-player-roster-read-model` | Read-only service layer with synthetic fixture validation, tmp_path tests, forbidden-key scanning, and static import guards. No API endpoint, no frontend, no real data at F2. |
| F3 Source Pack Approval Gate | `57b2bce` | `m10f3-source-pack-approval-gate` | Docs-only approval gate that defined tiny pilot scope (≤2 teams, ≤5 players), source verification requirements, and governance flags. Did not authorize automatic real-data landing. |
| F4-A Source Pack Framework | `ce7a7d4` | `m10f4a-tiny-pilot-source-pack` | Docs-only/source-pack-only deliverable defining exact player/team set, source URLs, schema compatibility notes, and source verification workflow. Verdict was HOLD_FOR_SOURCE_VERIFICATION; no real JSON written. |
| F4-B Tiny Pilot Implementation | `a973760` | `m10f4b-real-player-roster-tiny-pilot` | Landed the first real player identity and roster membership data: 2 teams / 4 players, schema-validated, hash-verified, regression-aligned, all tests green. |

## 3. Landed tiny pilot scope

**Teams: exactly 2**

- `nba-OKC` — Oklahoma City Thunder
- `nba-DEN` — Denver Nuggets

**Players: exactly 4, identity + roster membership only**

| player_id | display_name | team_id | position | roster_status |
|---|---|---|---|---|
| nba-shai-gilgeous-alexander | Shai Gilgeous-Alexander | nba-OKC | G | standard |
| nba-chet-holmgren | Chet Holmgren | nba-OKC | FC | standard |
| nba-nikola-jokic | Nikola Jokic | nba-DEN | C | standard |
| nba-jamal-murray | Jamal Murray | nba-DEN | G | standard |

**Data categories in this pilot:**

- `teams` (30 teams, sealed from M10-C)
- `team_visual_metadata` (non-official UI accents, sealed from M10-C)
- `player_identities` (new in F4-B: exactly 4 records)
- `roster_memberships` (new in F4-B: exactly 4 records)

**Data categories NOT present (and forbidden at file level):**

- `contracts`, `salaries`, `cap_sheets`, `injuries`, `rumors`, `scouting`, `live_status`

**Identity fields intentionally null for all pilot players:**

- `birthdate: null`
- `height: null`
- `weight: null`

## 4. Files changed in F4-B (including regression alignment)

The F4-B commit `a973760` modifies/creates the following files:

| File | Change |
|---|---|
| `data/snapshots/nba_real_2026_preoffseason_v1/normalized/player_identities.json` | **New** — 4 pilot player identity records |
| `data/snapshots/nba_real_2026_preoffseason_v1/normalized/roster_memberships.json` | **New** — 4 pilot roster membership records |
| `data/snapshots/nba_real_2026_preoffseason_v1/source_manifest.json` | Updated — added `player_identities`/`roster_memberships` to data_categories, per_file_sources, file_hashes; set as_of_date, stale_after_date, validation_status |
| `data/snapshots/nba_real_2026_preoffseason_v1/manifest.json` | Updated — description, limitations, data_categories, as_of_date, source_pack_version |
| `docs/m10-f4-real-player-roster-tiny-pilot.md` | **New** — F4-B implementation documentation |
| `backend/app/tests/test_m10f_player_roster_metadata_read_model.py` | Added — tiny pilot smoke test class (loads real snapshot, verifies 4 players / 4 memberships / forbidden keys / cross-references / governance flags) |
| `backend/app/tests/test_m10c_team_visual_metadata.py` | Regression alignment — updated `validation_status` assertion from `provisional` to `partially_validated` |
| `backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py` | Regression alignment — updated `as_of_date` assertion from `2026-06-25` to `2026-06-28` |
| `backend/app/tests/test_m10e_player_identity_schema.py` | Regression alignment — migrated no-real-data guard to F4-B tiny-pilot guard: asserts player_identities.json exists with exactly 4 expected players; extends forbidden-file list |
| `backend/app/tests/test_m10e_roster_membership_schema.py` | Regression alignment — migrated no-real-data guard to F4-B tiny-pilot guard: asserts roster_memberships.json exists with exactly 4 expected memberships, 2 expected teams, all roster_status=standard; extends forbidden-file list |
| `backend/app/tests/test_m10e_source_lineage_schema.py` | Regression alignment — migrated no-real-data guard to F4-B tiny-pilot guard: asserts normalized dir contains exactly 4 expected files, asserts source_manifest data_categories and per_file_sources match pilot scope |

**Important:** The test file changes (test_m10c through test_m10e) are **regression
alignment**, not feature expansion. They migrate old M10-E "no real data
allowed" assertions to F4-B "only the tiny pilot 4/4/2 is allowed; everything
else remains forbidden" assertions. This is a guard migration, not a
weakening of tests.

## 5. Test evidence

All test runs executed with `D:\anaconda\python.exe -m pytest`.

### 5.1 F2/F4-B read model suite

```
backend/app/tests/test_m10f_player_roster_metadata_read_model.py -q
```

**Result: 91 passed.**

### 5.2 M10-E schema + F2/F4-B regression

```
backend/app/tests/test_m10e_source_lineage_schema.py
backend/app/tests/test_m10e_player_identity_schema.py
backend/app/tests/test_m10e_roster_membership_schema.py
backend/app/tests/test_m10f_player_roster_metadata_read_model.py
-q
```

**Result: 576 passed.**

### 5.3 Full M10 metadata regression

```
backend/app/tests/test_m10_real_snapshot_schema.py
backend/app/tests/test_m10c_team_metadata.py
backend/app/tests/test_m10c_team_visual_metadata.py
backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py
backend/app/tests/test_m10e_source_lineage_schema.py
backend/app/tests/test_m10e_player_identity_schema.py
backend/app/tests/test_m10e_roster_membership_schema.py
backend/app/tests/test_m10f_player_roster_metadata_read_model.py
-q
```

**Result: 828 passed.**

### 5.4 Test quality notes

- **No expected failures.** No `xfail`, no `pytest.xfail`, no skipped tests
  related to real data.
- **No xfail markers.** Every test in the three suites ran and passed.
- **Windows pytest tempdir cleanup warning:** A `PermissionError: [WinError 5]
  拒绝访问` may appear during pytest's tempdir cleanup atexit callback on
  Windows. This is a known pytest/Windows temp directory race condition in
  the cleanup path. It does NOT affect test results, does NOT change the exit
  code, and is unrelated to F4-B data or code. Exit code is 0 across all
  three runs.
- **Static import guard:** F2 suite includes a test that scans imports to
  confirm no Agent/NL/trade/signing module imports the player roster reader.

## 6. Guardrails preserved

The following are explicitly NOT present in F4-B, verified by code inspection
(`git diff --name-only`), schema validation, and forbidden-field scanning
tests:

- **No API endpoint** — `backend/app/api.py` unchanged; no GET/POST/PUT/PATCH/DELETE routes for player/roster data.
- **No frontend UI** — `frontend/**` completely untouched.
- **No schema changes** — `schema/**` completely untouched; all pilot data validates against existing E2/E3/E4 schemas.
- **No service changes** — `backend/app/services/player_roster_metadata_reader.py` unchanged; `backend/app/snapshot_loader.py` unchanged.
- **No Agent/orchestrator wiring** — `backend/app/services/orchestrator*` unchanged.
- **No NL preview wiring** — no NL preview components modified.
- **No trade/signing wiring** — trade and signing logic untouched.
- **No POST/PUT/PATCH/DELETE endpoints** — no mutation endpoints of any kind added.
- **No execute/apply/mutate/write endpoints** — the system remains read-only for player/roster data.
- **No contracts/salaries/cap sheets** — these files do not exist and are forbidden by regression tests.
- **No injury/medical data** — no injury fields, no injury JSON.
- **No rumors/scouting** — no rumor fields, no scouting opinions.
- **No live/current/latest status** — `live_eligible=false` everywhere; no live_status.json.
- **No depth chart/minutes/role projection** — no depth chart data, no minutes projection, no role/starter/bench designations.
- **No trade eligibility** — no trade eligibility fields, no no-trade clauses.
- **No headshot/logo/media asset** — no player photos, no team logos, no media URLs.
- **No model changes** — `backend/app/models/**` untouched.

## 7. Source and manifest notes

- **record-level `source_type` uses `manual_curated`:** All 4 player identity
  records and all 4 roster membership records set `source_type: "manual_curated"`.
- **`source_manifest.per_file_sources.source_type` uses `manual_curated`:**
  Both per-file source entries for `normalized/player_identities.json` and
  `normalized/roster_memberships.json` use `source_type: "manual_curated"`.
- **Why `manual_curated` everywhere:** There is a known enum mismatch between
  record-level source_type (E3/E4 schemas: 5 values including
  `league_public_reference`, `team_public_reference`) and per-file
  source_manifest source_type (E2 schema: 4 values including `manual_curated`,
  `public_reference`, `league_roster`, `manual_non_official_ui`). Using
  `manual_curated` across both levels avoids schema violations without any
  schema changes. This was documented in F4-A §10 and executed in F4-B §10.
- **`source_manifest.file_hashes` covers pilot files:** SHA-256 hashes for
  `normalized/player_identities.json` and `normalized/roster_memberships.json`
  are recorded in source_manifest.file_hashes, matching on-disk bytes.
  Existing hashes for teams.json and team_visual_metadata.json are unchanged
  from M10-C seal.
- **`source_manifest.data_categories` includes pilot categories:**
  `["teams", "team_visual_metadata", "player_identities", "roster_memberships"]`.
- **Forbidden categories remain absent:**
  `contracts`, `salaries`, `cap_sheets`, `injuries`, `rumors`, `scouting`,
  `live_status` are not in data_categories, not in per_file_sources, and the
  corresponding files do not exist on disk (asserted by regression tests).
- **`validation_status: "partially_validated"`:** The snapshot has passed
  schema validation, hash verification, and cross-reference checks for the
  pilot data but is not fully validated (no contracts/salaries/etc. to
  validate).
- **`stale_after_date: "2026-07-12"`:** 14-day freshness window from as_of_date.

## 8. Regression alignment explanation

### What changed

M10-E established a strict no-real-data guard: the `normalized/` directory
for `nba_real_2026_preoffseason_v1` could only contain `teams.json` and
`team_visual_metadata.json`, and tests explicitly asserted that
`player_identities.json` and `roster_memberships.json` did NOT exist.

After F4-B lands real pilot data, those assertions became false. The
regression alignment patch (included in commit `a973760`) migrated these
old guards.

### Why this is NOT weakening tests

The migration does NOT simply delete or relax the old "file must not exist"
assertions. It **replaces** them with stronger, more specific assertions:

1. **Directory whitelist upgraded from 2 files to 4 files:** The old test
   asserted exactly `["team_visual_metadata.json", "teams.json"]`. The new
   test asserts exactly `["player_identities.json", "roster_memberships.json",
   "team_visual_metadata.json", "teams.json"]` — still an exact whitelist,
   not a prefix match.
2. **Player count hard-coded to exactly 4:** The new test opens
   player_identities.json, parses it, and asserts `len(players) == 4` and
   that the player_id set equals exactly {Shai, Chet, Jokic, Murray}.
3. **Membership count hard-coded to exactly 4:** Similarly asserts exactly
   4 memberships with player_id set matching and team_id set exactly
   {nba-OKC, nba-DEN}.
4. **roster_status locked to "standard":** Every membership must have
   `roster_status == "standard"`.
5. **Governance flags asserted everywhere:** `live_eligible=false` and
   `manual_review_required=true` at file level and per-record.
6. **Forbidden file list extended, not shortened:** The parametrized
   "forbidden files must not exist" test still covers contracts/salaries/
   cap_sheet/players/rosters/injuries/rumors/scouting_opinions and adds
   `live_status.json` to the list.
7. **No forbidden fields:** The F2 read model's recursive forbidden-key scan
   still runs and still blocks any salary/contract/cap/injury/live/scouting
   keys from appearing in the response projection.
8. **No import leaks:** The static import guard test still confirms no
   Agent/NL/trade/signing modules import the reader.

In summary: the old guard was "no real player/roster data at all." The new
guard is "exactly these 4 players on these 2 teams with standard contracts
only, and absolutely nothing else." This is appropriate for the F4-B seal.

## 9. Known limitations

- **Not a full roster.** This is 4 players across 2 teams. The remaining
  28 NBA teams and approximately 440 players are out of scope. Do not
  treat this as representative roster coverage.
- **Not a live/current roster.** The snapshot is frozen as of 2026-06-28.
  Free agency, trades, waivers, and signings after this date are NOT
  reflected. It will become stale on 2026-07-12.
- **Only suitable for read-model smoke verification.** The primary purpose
  of F4-B is to validate that the F2 read model can load, parse, validate,
  and project real (not synthetic) player/roster data. It demonstrates
  pipeline correctness with real data shape.
- **Not for trade/signing recommendations.** Every record and file-level
  metadata carries an explicit `data_freshness_warning` stating this.
  The `allowed_usage` field in source_manifest also explicitly prohibits
  trade/signing use.
- **No salary/contract/cap/injury/depth/scouting data.** These categories
  are entirely absent. Any downstream consumer expecting these fields will
  find them missing (or will be blocked by forbidden-key scans if they
  attempt to inject them).
- **birthdate/height/weight are null.** These optional identity fields were
  intentionally deferred for the pilot. Population requires a future
  milestone with additional source verification.
- **Source URLs may expire.** The cited NBA.com URLs are public today but
  may change or be removed in the future. URLs were verified at F4-B
  landing time; no ongoing availability guarantee exists.
- **`stale_after_date: 2026-07-12`.** After this date, the snapshot must be
  re-reviewed or replaced. F4-B does not implement stale refresh automation.
- **F4-B does not handle stale refresh.** There is no automated refresh,
  no scheduled job, no webhook, no polling mechanism. Staleness is a
  manual review concern.
- **No endpoint exposed.** The read model service exists in code but is not
  wired to any HTTP endpoint. It is only reachable via direct function call
  in tests or internal service usage.

## 10. Next-step recommendation

1. **Proceed to M10-F4 final handoff or M10-F final handoff** for the overall
   F-series closure, now that F4-B is sealed and all regression tests are green.
2. **Do NOT directly connect API/frontend/Agent to the pilot data.** The
   pilot is a sealed data verification point, not a consumable dataset.
3. **If data expansion is desired (more teams, more players, additional
   fields like birthdate/height/weight), a new source pack and approval
   gate MUST be opened first.** Do not grow the pilot dataset by appending
   records; follow the F3/F4-A process for any expansion.
4. **If API exposure is desired, a separate API design gate MUST be opened
   first.** This must cover: GET endpoint design, pagination, caching,
   rate limiting, authentication (if any), error handling for stale data,
   and explicit warnings/headers communicating the frozen/pilot nature.
5. **If frontend exposure is desired, a separate read-only UI design gate
   MUST be opened first.** This must cover: how to surface data_freshness_warning
   and manual_review_required, how to display "not live / not for trade/signing"
   disclaimers, and how to prevent accidental implication of official status.
6. **Agent/NL/trade/signing remain HOLD.** No milestone after F4-B authorizes
   wiring the player/roster read model into agent orchestration, natural
   language preview, trade simulation, or signing recommendation logic.
   These require dedicated design gates with explicit safety review.

## 11. Final conclusion

- **M10-F4-B is sealed.** Commit `a973760` / tag
  `m10f4b-real-player-roster-tiny-pilot` contains the complete, test-verified
  tiny pilot.
- **M10-F4 Smoke/Handoff is ready for ChatGPT review.** This document
  (m10-f4-smoke-handoff.md) is the sole artifact of this handoff step.
- **This handoff does NOT authorize new data expansion.** Adding more
  players, teams, or data categories requires a new source pack / approval
  gate process, not direct edits.
- **This handoff does NOT authorize API/frontend/Agent/trade/signing
  consumption.** Each consumer surface requires its own design gate before
  wiring.
- **M10-F should remain read-only and guarded** unless and until a new
  design gate explicitly approves expansion or consumer wiring. The frozen,
  minimal, manually-reviewed, live_eligible=false posture is the correct
  default state for real NBA data at this stage of the project.
