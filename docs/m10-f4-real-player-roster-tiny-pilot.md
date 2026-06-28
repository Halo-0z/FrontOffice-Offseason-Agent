# M10-F4-B: Real Player/Roster Tiny Pilot Implementation

Run date: 2026-06-28.
Baseline: commit `ce7a7d4`, tag `m10f4a-tiny-pilot-source-pack`, clean working tree.

This is the **real data tiny pilot implementation** for M10-F4. F4-B lands the first
real player identity and roster membership data in the repository: exactly 2 teams
(OKC, DEN) and 4 players (Shai Gilgeous-Alexander, Chet Holmgren, Nikola Jokic,
Jamal Murray). This is a minimal pilot, not a full roster, not live data, and does
not include any contracts, salaries, cap sheets, injuries, scouting, or live status.

## 1. F4-B scope

- **Exactly 2 teams**: `nba-OKC` (Oklahoma City Thunder) and `nba-DEN` (Denver Nuggets).
- **Exactly 4 players**: 2 per team, all `roster_status: standard`.
- **Identity + roster membership only**: No birthdate, height, weight (all null), no
  salary, no contract, no cap, no injury, no scouting, no live data.
- **Frozen as-of 2026-06-28**: Snapshot is not live/current; stale_after_date=2026-07-12.
- **Read-only data only**: No API endpoint added, no frontend wiring, no Agent/NL/trade/signing wiring.
- **Schema-compliant**: All files validate against E3 (player identities), E4 (roster memberships),
  E2 (source manifest), and real snapshot manifest schemas.

## 2. Why OKC/DEN and these 4 players

- **Stable franchises**: Both teams have well-known, public, easily verifiable roster pages
  on NBA.com and ESPN without login/paywall.
- **High-profile, unambiguous players**: All four players are established stars on standard
  contracts with no recent trade/waiver/signing ambiguity in the 2026 offseason window.
- **Two per team**: Satisfies the F3 scope ceiling (≤2 teams, ≤5 players) at exactly 2+2=4
  players, making line-by-line manual review feasible.
- **Position coverage**: Includes G (Shai, Murray), FC (Holmgren), C (Jokic) to validate
  schema enum handling for multiple positions.
- **No known ambiguous status**: As of GPT-5.5 source verification (CONDITIONAL_GO), all
  four are listed consistently on both NBA.com team rosters and player pages.

## 3. Source URLs

All URLs are public, no-login, no-paywall pages. ESPN URLs used as second cross-check
source; conflict resolution documented in notes.

Primary sources (cited in JSON source_url):

- **Shai Gilgeous-Alexander (NBA.com player page)**: https://www.nba.com/player/1628983/shai-gilgeous-alexander
- **Chet Holmgren (NBA.com player page)**: https://www.nba.com/player/1631096/chet-holmgren
- **Nikola Jokic (NBA.com player page)**: https://www.nba.com/player/203999/nikola-jokic
- **Jamal Murray (NBA.com player page)**: https://www.nba.com/player/1627750/jamal-murray
- **OKC roster (NBA.com team page)**: https://www.nba.com/thunder/roster
- **DEN roster (NBA.com team page)**: https://www.nba.com/nuggets/roster

Secondary cross-check sources (documented here, not in JSON due to single-source_url schema limit):

- ESPN OKC roster: https://www.espn.com/nba/team/roster/_/name/okc/oklahoma-city-thunder
- ESPN DEN roster: https://www.espn.com/nba/team/roster/_/name/den/denver-nuggets
- ESPN Shai page: https://www.espn.com/nba/player/_/id/4278073/shai-gilgeous-alexander
- ESPN Chet page: https://www.espn.com/nba/player/_/id/4433255/chet-holmgren
- ESPN Jokic page: https://www.espn.com/nba/player/_/id/3112335/nikola-jokic
- ESPN Murray page: https://www.espn.com/nba/player/_/id/3936299/jamal-murray

## 4. Human reviewer signoff status

- **Curator**: AI assistant executing F4-B per human-specified record plan.
- **Source pre-verification**: GPT-5.5, verdict: CONDITIONAL_GO_FOR_F4B (allowed exactly these 2 teams / 4 players).
- **Schema validation**: jsonschema validation via F2 read model service.
- **Hash validation**: SHA-256 hashes computed and recorded in source_manifest.file_hashes.
- **review_status**: Approved for pilot landing per the exact record set specified by human instruction.
- **All URLs confirmed public**: No login, no paywall required to access cited facts.

## 5. as_of_date / stale_after_date

- **as_of_date**: 2026-06-28 (all files and records)
- **stale_after_date**: 2026-07-12 (14 days, per F3 recommended offseason window)
- **live_eligible**: false (everywhere: file-level, per-record, per-file-source)
- **manual_review_required**: true (everywhere)

## 6. Player identity records summary

| player_id | display_name | first_name | last_name | position | source_url |
|---|---|---|---|---|---|
| nba-shai-gilgeous-alexander | Shai Gilgeous-Alexander | Shai | Gilgeous-Alexander | G | https://www.nba.com/player/1628983/shai-gilgeous-alexander |
| nba-chet-holmgren | Chet Holmgren | Chet | Holmgren | FC | https://www.nba.com/player/1631096/chet-holmgren |
| nba-nikola-jokic | Nikola Jokic | Nikola | Jokic | C | https://www.nba.com/player/203999/nikola-jokic |
| nba-jamal-murray | Jamal Murray | Jamal | Murray | G | https://www.nba.com/player/1627750/jamal-murray |

Shared fields across all player records:
- birthdate: null, height: null, weight: null (intentionally deferred for pilot)
- source_type: manual_curated
- All governance flags: live_eligible=false, manual_review_required=true
- limitations include: identity_only, not_live, no_contract, no_salary, no_cap, no_injury, no_depth_chart
- notes include: "Optional identity fields birthdate/height/weight intentionally null for first pilot."
- Chet Holmgren has an additional conflict note: "Position conflict: NBA uses Center-Forward while ESPN uses Center; resolved to FC per source conflict policy."

## 7. Roster membership records summary

| membership_id | player_id | team_id | roster_status | source_url |
|---|---|---|---|---|
| membership-okc-shai-gilgeous-alexander | nba-shai-gilgeous-alexander | nba-OKC | standard | https://www.nba.com/thunder/roster |
| membership-okc-chet-holmgren | nba-chet-holmgren | nba-OKC | standard | https://www.nba.com/thunder/roster |
| membership-den-nikola-jokic | nba-nikola-jokic | nba-DEN | standard | https://www.nba.com/nuggets/roster |
| membership-den-jamal-murray | nba-jamal-murray | nba-DEN | standard | https://www.nba.com/nuggets/roster |

Shared fields across all membership records:
- source_type: manual_curated
- All governance flags: live_eligible=false, manual_review_required=true
- limitations include: membership_only, not_live, no_contract, no_salary, no_cap, no_injury, no_depth_chart

## 8. source_manifest update summary

- **data_categories**: Added `"player_identities"` and `"roster_memberships"` to existing
  `["teams", "team_visual_metadata"]`. No forbidden categories added.
- **per_file_sources**: Added entries for `normalized/player_identities.json` and
  `normalized/roster_memberships.json`, both with `source_type: manual_curated` (E2-compatible
  per §10.2 of F4-A, resolving the known enum mismatch).
- **Existing file hashes unchanged**: `normalized/teams.json` and `normalized/team_visual_metadata.json`
  SHA-256 hashes match their sealed values from M10-C.
- **stale_after_date**: Set to "2026-07-12" (was null before F4-B).
- **schema_version**: Updated to m10-f4-pilot-v1.
- **as_of_date**: Updated to 2026-06-28.

## 9. Hash values

SHA-256 hashes computed via PowerShell `Get-FileHash -Algorithm SHA256` against final on-disk bytes:

| File | sha256 hash |
|---|---|
| normalized/teams.json (unchanged) | `5b1e388bb2b7506832e7fbb0a06e105b9478d4a5caea9fe9514032bd22dc5fbb` |
| normalized/team_visual_metadata.json (unchanged) | `96274923a688fd05b2c1092487767d462620036dd6605abc0d3d800d6fb3bb8c` |
| normalized/player_identities.json (new) | `a015daa14e585335cae301ae2f0f46a34fe9390074b6c2d43083d20fac8bf65c` |
| normalized/roster_memberships.json (new) | `93e41296095e60e22b6b3cf8307cdd32405064390e74fc15917e04fa2443aeb9` |

All hashes recorded in `source_manifest.file_hashes` with `sha256:` lowercase hex prefix.

## 10. schema/source_type compatibility note

Per F4-A §10, there is a known enum mismatch between:
- Record-level source_type (E3/E4 schemas): 5 values including `league_public_reference`, `team_public_reference`
- Per-file source_manifest source_type (E2 schema): 4 values including only `manual_curated`, `public_reference`, `league_roster`, `manual_non_official_ui`

Resolution for F4-B (no schema changes):
- All record-level source_type values: `manual_curated`
- All per-file source_type values: `manual_curated` (compatible across both enum sets)
- No `league_public_reference` or `team_public_reference` used at per-file level (would fail E2 schema)
- No schema files modified per F4-B scope rules

## 11. No salary/contract/cap/injury/scouting/live data

The following are explicitly NOT present anywhere in the added files, verified by:
- JSON Schema `additionalProperties: false` and `propertyNames` blacklists (E2/E3/E4)
- F2 read model service's recursive forbidden-key scan
- F4-B test forbidden-field scan:

  - Salary/contract/cap: salary, salaries, contract, contracts, cap_hold, cap_sheet, cap_sheets, guarantee, guarantee_amount
  - Injury/medical: injury, injuries, injury_status, medical, medical_status, health, day_to_day, out, questionable, probable
  - Rumors/scouting: rumors, rumor, scouting_opinion, scouting_opinions, grade, rating, trade_value
  - Live/current/latest: live_status, current_roster, latest_roster, latest_data, live_data, active_now, real_time_data
  - Depth chart/projection: depth_chart, projected_depth_chart, minutes_projection, role_projection, starter, bench_role, rotation_role
  - PII/media/agents: social_media, agent, agent_representation, personal_sensitive_info, headshot, headshot_url, player_image, photo_url
  - Execution/mutation: execute, apply, commit, mutate, write, persist, save, delete, update, submit, auto_execute, auto_approve
  - Trade eligibility: trade_eligibility, trade_restriction, no_trade_clause
  - Logos: logo_path, logo_url, official_logo, nba_logo, team_logo, mascot_image

birthdate, height, weight are all null (deferred, not populated).

## 12. No API/frontend/Agent/NL/trade/signing

Verified by:
- No files modified outside the explicitly allowed list (§Files modified below)
- `backend/app/api.py` unchanged (no new endpoint, no POST/PUT/PATCH/DELETE)
- `frontend/**` unchanged (no UI wiring)
- `schema/**` unchanged (no schema modifications)
- `backend/app/services/player_roster_metadata_reader.py` unchanged (service intact)
- `backend/app/snapshot_loader.py` unchanged
- `backend/app/services/orchestrator*` unchanged
- `backend/app/models/**` unchanged
- Static import guard test in F2 suite confirms no Agent/NL/trade/signing module imports the reader
- The read model remains GET-only in design; no HTTP endpoint is added in F4-B

## 13. Tests run

All test runs executed with: `D:\anaconda\python.exe -m pytest`

### 13.1 F2 read model suite (including new F4-B tiny pilot smoke test)

```
backend/app/tests/test_m10f_player_roster_metadata_read_model.py -q
```

Result: 91 passed.

### 13.2 M10-E schema + F2/F4-B regression

```
backend/app/tests/test_m10e_source_lineage_schema.py
backend/app/tests/test_m10e_player_identity_schema.py
backend/app/tests/test_m10e_roster_membership_schema.py
backend/app/tests/test_m10f_player_roster_metadata_read_model.py
-q
```

Result: 576 passed.

### 13.3 Full M10 metadata regression

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

Result: 828 passed. All tests green; no expected failures; no xfail markers.

### 13.4 F4-B tiny pilot smoke test coverage

The new test verifies:
- Real pilot snapshot loads successfully via `load_player_roster_metadata(snapshot_mode="real_snapshot")`
- Exactly 4 players returned
- Exactly 4 roster memberships returned
- All 4 expected player_ids present (Shai, Chet, Jokic, Murray)
- All 2 expected team_ids present (nba-OKC, nba-DEN)
- player_id cross-references are valid (every membership player_id exists in players)
- team_id cross-references are valid (every membership team_id exists in teams.json)
- roster_status is "standard" for all memberships
- Forbidden fields (salary/contract/cap/injury/live/etc.) are absent from the response projection
- No contracts/salaries/cap/injury/rumor/scouting files exist in the snapshot directory
- live_eligible=false everywhere
- manual_review_required=true everywhere

## 14. Known limitations

- **Tiny pilot only**: This is 4 players across 2 teams, not a full NBA roster. The remaining
  28 teams and ~450 players are out of scope for F4-B.
- **Identity fields minimal**: birthdate/height/weight are intentionally null for this pilot;
  population is deferred to a later milestone after governance review.
- **No historical data**: This is a single frozen as-of snapshot; no transaction history or
  prior roster states are included.
- **No depth chart / minutes / role**: All deployment/role information is out of scope.
- **No contract/salary/cap data**: Entirely deferred to M10-G or later governance series.
- **Source URL single-field**: Schema only permits one source_url per record; NBA.com is used
  as primary, ESPN cross-check documented in this file only.
- **14-day freshness window**: Snapshot becomes stale 2026-07-12 and must be re-reviewed
  after that date (or after major free agency moves).
- **Not for trade/signing recommendations**: The data_freshness_warning explicitly states
  this limitation on every record and at file/manifest level.
- **No endpoint added**: The read model service exists but is not exposed via HTTP in F4-B;
  endpoint wiring is deferred to a future milestone.

## 15. Files modified

| File | Change |
|---|---|
| `data/snapshots/nba_real_2026_preoffseason_v1/normalized/player_identities.json` | **New file** (4 players) |
| `data/snapshots/nba_real_2026_preoffseason_v1/normalized/roster_memberships.json` | **New file** (4 memberships) |
| `data/snapshots/nba_real_2026_preoffseason_v1/source_manifest.json` | Updated: data_categories, per_file_sources, file_hashes, stale_after_date, governance flags |
| `data/snapshots/nba_real_2026_preoffseason_v1/manifest.json` | Updated: as_of_date, description, limitations, source_pack_version |
| `docs/m10-f4-real-player-roster-tiny-pilot.md` | **New file** (this document) |
| `backend/app/tests/test_m10f_player_roster_metadata_read_model.py` | Added tiny pilot smoke test class |

No other files were modified. Specifically, none of the following were touched:
- backend/app/api.py
- frontend/**
- schema/**
- backend/app/services/** (including player_roster_metadata_reader.py)
- backend/app/snapshot_loader.py
- backend/app/services/orchestrator*
- backend/app/models/**
- Agent-related logic
- NL preview logic
- Trade/signing logic
- Any contracts/salaries/cap/injury/rumor/scouting/live files

## 16. Final conclusion

- **M10-F4-B lands a minimal real player/roster tiny pilot**: exactly 2 teams (OKC, DEN),
  exactly 4 players (Shai Gilgeous-Alexander, Chet Holmgren, Nikola Jokic, Jamal Murray),
  identity + roster membership data only.
- **Tiny pilot only**: This is not a full roster, not a 30-team intake, not live data.
- **All governance guardrails intact**: live_eligible=false, manual_review_required=true,
  stale_after_date set, no forbidden fields, schema-validated, hash-verified.
- **No wiring**: No API endpoint, no frontend, no Agent, no NL preview, no trade/signing
  logic changes. The read model service remains in code but is not connected to any
  external consumer in this milestone.
- **No salary/contract/cap/injury/scouting/live data**: All deferred categories remain absent.
- **All tests pass**: Full M10 metadata regression green.
- **Ready for ChatGPT review**: No commit, tag, or push performed by F4-B.
