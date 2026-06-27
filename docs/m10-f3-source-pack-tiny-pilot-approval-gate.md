# M10-F3: Source Pack + Tiny Pilot Approval Gate

Run date: 2026-06-28.
Baseline: commit `b26611d`, tag `m10f2-player-roster-read-model`, clean working tree.

This milestone is a **docs-only approval gate**. It defines the source pack,
reviewer sign-off checklist, hash plan, and tiny-pilot scope that M10-F4
(real data pilot implementation) must satisfy before any real player or
roster byte may be written to the repository. F3 itself does **not** write
any real data.

## 1. F3 verdict

- **M10-F3 is a source pack + tiny pilot approval gate.** It is the gate that
  must be passed before F4 can even begin staging a tiny pilot dataset.
- **F3 is docs-only.** The only artifact produced by this milestone is this
  document: `docs/m10-f3-source-pack-tiny-pilot-approval-gate.md`.
- **F3 does not write real data.** F3 does not create, modify, or stage
  `normalized/player_identities.json` or `normalized/roster_memberships.json`.
- **F3 does not touch code.** F3 does not modify `backend/`, `frontend/`,
  `schema/`, `tests/`, `data/snapshots/`, any API endpoint, any loader,
  any service, or any orchestrator.
- **F3 does not wire anything.** F3 does not connect the player/roster read
  model to a backend endpoint, frontend UI, Agent, natural-language preview,
  trade logic, or signing logic.
- **F3 only defines the approval conditions F4 must meet.** F4 (tiny pilot
  real-data implementation) is **not** approved by F3; F4 will require its
  own ChatGPT review after its source pack and pilot data are prepared.

## 2. Tiny pilot scope

If F3 is accepted and F4 is later opened, the F4 pilot is constrained to
the following maximum scope. The F4 curator may choose a smaller pilot,
but must not exceed these bounds.

### 2.1 Maximum scope

- **At most 2 teams.** Only two `team_id`s from `normalized/teams.json`
  may be referenced by any roster membership record.
- **At most 5 player identity records** across the two teams.
- **Identity + roster membership only.** Only the fields permitted by
  `schema/player_identities_schema.json` (M10-E3) and
  `schema/roster_memberships_schema.json` (M10-E4).
- **Frozen as-of point in time.** The pilot represents an offseason snapshot,
  not a live roster.

### 2.2 Explicitly out of scope for F4 (even after F3 approval)

- **No full-league roster.** 30-team intake is out of scope for F4.
- **No salary data.** No `salary`, `salaries`, `cap_hold`, `guarantee`,
  `guarantee_amount`, `cap_sheet`, or `cap_sheets` fields.
- **No contract data.** No `contract`, `contracts`, `option`, `extension`,
  `bird_rights`, `exception`, or buyout fields.
- **No cap data.** No salary cap, luxury tax, dead money, cap hit, or
  payroll fields.
- **No injury / medical data.** No `injury`, `injuries`, `injury_status`,
  `medical`, `medical_status`, `health`, `day_to_day`, `out`,
  `questionable`, `probable`, `doubtful`, `ir`, `gtd`, `available`,
  `unavailable`.
- **No rumors / scouting opinions.** No `rumors`, `rumor`, `scouting_opinion`,
  `scouting_opinions`, `grade`, `rating`, `trade_value`.
- **No live / current / latest semantics.** No `live_status`, `current_roster`,
  `latest_roster`, `live_data`, `latest_data`, `active_now`, `current_status`,
  `latest_status`, `real_time_data`, `real_time_availability`.
- **No depth chart / minutes / role projection.** No `depth_chart`,
  `projected_depth_chart`, `minutes_projection`, `role_projection`,
  `starter`, `bench_role`, `rotation_role`.
- **No trade eligibility / restrictions.** No `trade_eligibility`,
  `trade_restriction`, `no_trade_clause`.
- **No PII / representation / media.** No `social_media`, `agent`,
  `agent_representation`, `personal_sensitive_info`, `headshot`,
  `headshot_url`, `player_image`, `photo_url`, `official_headshot`,
  `logo_path`, `logo_url`, `official_logo`, `nba_logo`, `team_logo`,
  `mascot_image`.
- **No execution / mutation verbs.** No `execute`, `apply`, `commit`,
  `mutate`, `write`, `persist`, `save`, `delete`, `update`, `submit`,
  `auto_execute`, `auto_approve`.

### 2.3 F3 defines scope only

F3 defines the scope ceiling above. F3 does **not** fill any player or
roster record. F3 does **not** choose which two teams or which five
players; those are curator decisions to be documented in the F4 source pack
and reviewed at F4 time.

## 3. Source pack requirements

Before F4 may write any real byte, the F4 curator must prepare a **source
pack** — a written record (attached to the F4 review request, not committed
to the repository as data) listing, for every player identity record and
every roster membership record in the pilot, the following fields:

| Field | Required | Notes |
|---|---|---|
| `source_name` | Yes | Human-readable source name (e.g. "NBA.com Atlanta Hawks Roster"). |
| `source_type` | Yes | One of the five allowed enum values (see §4). |
| `source_url` | Yes for real records | Public URL to the specific page cited; must be non-null for every non-`manual_review` record. |
| `access_date` | Yes | YYYY-MM-DD on which the curator accessed the source page. |
| `as_of_date` | Yes | YYYY-MM-DD cutoff date for the data; must match file-level `as_of_date`. |
| `stale_after_date` | Yes (file-level) | YYYY-MM-DD after which the file is considered stale. Recommended window: `as_of_date + 7 to 30 days` for offseason rosters. |
| `curator` | Yes | Named individual who entered the data. |
| `reviewer` | Yes | Named individual who independently reviewed and signed off on the data (must differ from curator). |
| `review_status` | Yes | Must be `approved` before F4 lands; `draft` / `in_review` are not acceptable for landing. |
| `limitations` | Yes (file + per-record) | Non-empty array of strings; must include at least an identity-only / not-live caveat. |
| `data_freshness_warning` | Yes (file + per-record) | Non-empty string displayed to any future consumer. |
| `allowed_usage_notes` | Yes | Statement of what the data may be used for under this gate (read-only frozen reference; not for trade/signing recommendations in F-series). |
| `conflict_notes` | Yes (may be empty string) | Any conflicts observed across sources and how they were resolved; "no conflicts observed" is acceptable. |
| `manual_review_notes` | Yes (may be empty array) | Curator/reviewer caveats, disambiguation notes, open questions. |

Per-record `source_url` is mandatory for every real player identity and
every real roster membership (i.e. every record in the F4 pilot except
explicit `manual_review` placeholders, which must not be served by the read
model until promoted).

## 4. Allowed sources

Only the five `source_type` values permitted by the E3/E4 schemas are
allowed. Each real record in F4 must carry exactly one of these:

- `manual_curated` — Human-assembled data where the named curator has
  cross-checked values across at least two permitted public references.
  **Default and recommended for the F4 pilot.**
- `league_public_reference` — League-published public reference material
  (e.g. NBA.com team roster pages, NBA official stats public pages).
- `team_public_reference` — Team-published public reference material
  (e.g. an individual team's official public roster page).
- `public_reference` — Publicly available reference sites used as a
  cross-check citation (e.g. Basketball Reference, ESPN public rosters,
  Spotrac public pages).
- `manual_review` — Placeholder during curation only; records tagged
  `manual_review` must not be served by the read model until promoted to
  one of the other statuses and re-reviewed.

### 4.1 Source usage rules (carried forward from F1 §3.3)

- NBA.com public roster pages may be cited as `league_public_reference`.
- Individual team official sites may be cited as `team_public_reference`.
- Basketball Reference / ESPN public pages / Spotrac public pages may be
  cited as `public_reference`.
- All of the above are treated as **public citations only**. Facts
  verified from public pages are entered manually by a curator.
- **No runtime fetch.** The application must not make HTTP calls to
  NBA.com, team sites, or reference sites at request time.
- **No scraping.** Curation is manual, small-batch (≤ 5 players for F4),
  and human-reviewed. Bulk scripted ingestion is out of scope.
- **No copying from paid databases** or from sources whose terms of
  service prohibit reproduction.
- **No LLM output as fact.** The LLM may be used as a drafting assistant
  only; every value written to disk must be verified against a permitted
  public source by a human curator and reviewed by a second human.
- **Do not imply official authorization.** `league_public_reference` /
  `team_public_reference` mean "cited from a public league/team page";
  they do not imply partnership, endorsement, or licensed data feed.

## 5. Forbidden sources

The following sources and source types are forbidden at the schema layer
and remain forbidden for F4. Any record citing these must cause the F4
landing to be rejected.

- `llm_generated` — LLM output presented as fact without human verification
  against a permitted source.
- `scraped_unreviewed` — Bulk or scripted scraped data not curated line by
  line by a human.
- `live_api` — Any runtime API pull (paid or free) treated as authoritative.
- **Social media as fact source** — Tweets/X posts, Instagram posts,
  TikTok, player/team/agent social posts used as the primary source for
  any identity or roster fact. Social posts may inform curator attention
  but must not be cited as the `source_url` of record.
- **Reddit / forums / rumor aggregators as fact source** — Reddit,
  RealGM forums, HoopsHype rumor pages, and similar aggregators must not
  be cited as the source of record. They may be used to flag items for
  cross-checking against league/team/public-reference pages.
- **Unsourced copy-paste.** Any record whose `source_url` is null when
  `source_type` is not `manual_review` is rejected.
- **Bulk scraping.** Scripted mass download (even from otherwise-permitted
  domains) is out of scope and forbidden under F3/F4.
- **Paid database dumps.** Any data copied from a paid service
  (subscription site, B2B feed, licensed data product) is forbidden.
- **Terms-violating copied data.** Any data whose copying would violate
  the source site's Terms of Service or robots.txt must not be used.
- **Image-only sources without manual transcription review.** A roster
  page whose data is only presented as an image (no text) must not be
  used as the sole source; any transcribed values must be cross-checked
  against a second permitted source and the transcription must be
  documented in `manual_review_notes`.

## 6. Future player_identities tiny pilot requirements

Based on `schema/player_identities_schema.json` (M10-E3), every player
identity record written in F4 must satisfy all of the following. These
rules mirror the schema; the F4 review must verify each one per record.

### 6.1 File-level requirements

- Conform to `schema/player_identities_schema.json` (E3).
- Identity-only. No field beyond what E3 permits.
- `snapshot_id` matches the snapshot directory id
  (`nba_real_2026_preoffseason_v1` for the pilot).
- `manual_review_required` is `true` (const).
- `live_eligible` is `false` (const).
- `data_freshness_warning` is a non-empty string.
- `limitations` is a non-empty array of non-empty strings.
- `source_name` is non-empty; `source_type` is one of the five allowed
  values; `source_url` is non-null unless the file is a
  `manual_review` placeholder (which must not be served).

### 6.2 Per-player requirements

- `player_id` matches `^[a-z][a-z0-9_-]*$`, is stable, collision-resistant,
  and follows the namespaced slug scheme documented in F1 §5.3 (e.g.
  derived from the player's common public slug with a disambiguation
  suffix when names collide).
- `display_name`, `first_name`, `last_name` are non-empty strings.
- `position` is exactly one of `PG`, `SG`, `SF`, `PF`, `C`, `G`, `F`,
  `FC`, `GF`.
- `birthdate` is either `null` or a `YYYY-MM-DD` string.
- `height` is either `null` or a non-empty human-readable display string
  (e.g. `"6-7"`).
- `weight` is either `null` or a non-empty human-readable display string
  (e.g. `"220 lb"`).
- `source_name`, `source_type`, `as_of_date` per-record are populated;
  `source_url` is non-null for non-`manual_review` records.
- `manual_review_required=true`, `live_eligible=false` per record.
- `data_freshness_warning` non-empty per record.
- `snapshot_id` matches the file-level `snapshot_id` per record.
- `limitations[]` non-empty per record.
- `notes[]` is optional and may contain only curator disambiguation /
  caveats, not rumors/scouting/medical info.

### 6.3 Forbidden per player (enforced by E3 propertyNames blacklist + F2 recursive scan)

Any of the following keys at either file level or per-player level causes
F4 to be rejected:

- Money/contract/cap: `salary`, `salaries`, `contract`, `contracts`,
  `cap_hold`, `guarantee`, `guarantee_amount`, `cap_sheet`, `cap_sheets`.
- Injury/medical: `injury`, `injuries`, `injury_status`, `medical`,
  `medical_status`, `health`.
- PII/representation/media: `personal_sensitive_info`, `social_media`,
  `agent`, `agent_representation`, `headshot`, `headshot_url`,
  `player_image`, `photo_url`, `official_headshot`.
- Rumors/scouting: `rumors`, `rumor`, `scouting_opinion`, `scouting_opinions`.
- Live/availability/projection: `live_status`, `availability`,
  `real_time_availability`, `projected_depth_chart`, `depth_chart`,
  `minutes_projection`, `role_projection`, `trade_eligibility`.
- Logos: `logo_path`, `logo_url`, `official_logo`, `nba_logo`,
  `team_logo`, `mascot_image`.
- Live/current naming: `current_roster`, `latest_roster`, `live_salaries`,
  `latest_data`, `live_data`, `current_salaries`, `real_time_data`.
- Execution/mutation verbs: `execute`, `apply`, `commit`, `mutate`,
  `write`, `persist`, `save`, `delete`, `update`, `submit`,
  `auto_execute`, `auto_approve`.

## 7. Future roster_memberships tiny pilot requirements

Based on `schema/roster_memberships_schema.json` (M10-E4), every roster
membership record written in F4 must satisfy all of the following.

### 7.1 File-level requirements

- Conform to `schema/roster_memberships_schema.json` (E4).
- Team↔player linkage only; frozen as-of; not a live roster.
- `snapshot_id` matches the snapshot directory id.
- `manual_review_required=true` (const).
- `live_eligible=false` (const).
- `data_freshness_warning` non-empty.
- `limitations[]` non-empty.
- `source_name` non-empty; `source_type` one of the five allowed values;
  `source_url` non-null for non-`manual_review` records.

### 7.2 Per-membership requirements

- `team_id` matches `^nba-[A-Z]{3}$` and resolves to exactly one record
  in `normalized/teams.json` (already sealed from M10-C).
- `player_id` matches `^[a-z][a-z0-9_-]*$` and resolves to exactly one
  record in `normalized/player_identities.json` in the same snapshot.
- `roster_status` is exactly one of the six allowed values:
  - `standard` — standard NBA contract
  - `two_way` — two-way contract
  - `training_camp` — training camp / preseason Exhibit deal
  - `unsigned_draft_rights` — unsigned draft rights held by a team
  - `free_agent` — explicitly listed as an offseason free agent (only
    when the curator intentionally captures a known free agency state;
    must carry `manual_review_required` and a strong limitation caveat)
  - `unknown_manual_review` — placeholder during curation; must not be
    served by the read model until promoted
- `membership_id` is optional; if present it must be a stable, reviewable
  id (not a runtime UUID) matching `^[a-z][a-z0-9_-]*$`.
- `source_name`, `source_type`, `as_of_date` per-record are populated;
  `source_url` non-null for non-`manual_review` records.
- `manual_review_required=true`, `live_eligible=false` per record.
- `data_freshness_warning` non-empty per record.
- `snapshot_id` matches the file-level id per record.
- `limitations[]` non-empty per record.

### 7.3 Forbidden roster_status values

Any record whose `roster_status` is any of the following must cause F4
to be rejected (these are rejected by the E4 enum and propertyNames
blacklist today and remain forbidden):

- Transactional/injury/availability: `inactive`, `waived`, `traded`,
  `suspended`, `injured`, `questionable`, `probable`, `day_to_day`,
  `available`, `unavailable`.
- Live/current naming: `active_now`, `current`, `latest`, `current_status`,
  `latest_status`.

### 7.4 Forbidden per-membership fields (E4 propertyNames blacklist + F2 scan)

Same blacklist enforcement as §6.3, plus the additional E4-forbidden keys:
`trade_restriction`, `no_trade_clause`, `current_status`, `latest_status`,
`starter`, `bench_role`, `rotation_role`. Any presence of these keys at
file or per-record level rejects F4.

## 8. Hash and manifest plan

If F4 is approved for landing, the curator must update the snapshot's
`source_manifest.json` as follows. The `manifest.json` must remain
syntactically valid against `schema/real_snapshot_manifest_schema.json`
and must list the new normalized files.

### 8.1 data_categories

- `data_categories` must be extended to include exactly:
  - `player_identities`
  - `roster_memberships`
- `data_categories` must **not** include `contracts`, `salaries`,
  `cap_sheets`, `injuries`, `rumors`, `scouting`, `live_status`,
  or any other category not explicitly approved by a governance gate.

### 8.2 file_hashes

- `file_hashes` must include a SHA-256 entry (hex, prefixed `sha256:`) for:
  - `normalized/player_identities.json`
  - `normalized/roster_memberships.json`
- The hash must match the exact on-disk bytes at the moment of landing.
  The F2 reader raises `PlayerRosterHashError` on mismatch.
- Recommended command to compute (PowerShell):
  ```powershell
  $sha = [System.Security.Cryptography.SHA256]::Create()
  $bytes = [System.IO.File]::ReadAllBytes("path\to\normalized\player_identities.json")
  "sha256:" + ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-","").ToLower()
  ```

### 8.3 per_file_sources

- `per_file_sources` must include entries for:
  - `normalized/player_identities.json`
  - `normalized/roster_memberships.json`
- Each per-file entry must populate: `source_name`, `source_url`
  (non-null), `source_type` (one of the five allowed values),
  `as_of_date`, `manual_review_required=true`, `live_eligible=false`,
  `limitations[]` (non-empty), `data_freshness_warning` (non-empty).
- Each per-file entry's `source_type` must not be any of the forbidden
  source types (`llm_generated`, `scraped_unreviewed`, `live_api`,
  `social_media`, `rumors`).

### 8.4 Top-level source_manifest governance flags

- `live_eligible=false` (const) at top level.
- `manual_review_required=true` (const) at top level.
- `stale_after_date` must be set at top level (recommended:
  `as_of_date + 7 to 30 days` for offseason rosters).
- `data_freshness_warning` non-empty at top level.
- `limitations[]` non-empty at top level.

### 8.5 No fallback demo

- F4 must not introduce any code path that falls back to demo,
  generated, or stub data when the real snapshot's player/roster files
  fail to load, hash-verify, schema-validate, or cross-reference.
- The F2 read model's hard-error contract must remain intact.

## 9. Reviewer approval checklist

F4 must not land until every item below is checked off by a reviewer who
is not the curator. The checklist must be filled in the F4 review
request (ChatGPT conversation) before any `git add` of real data.

### 9.1 Source pack completeness

- [ ] Every pilot record has a non-empty `source_name`.
- [ ] Every pilot record has a `source_type` in the five allowed values.
- [ ] Every non-`manual_review` record has a non-null `source_url`.
- [ ] Every `source_url` is accessible at review time (HTTP 200 on a
      public page, no paywall, no login required to view the cited fact).
- [ ] Every pilot record has an `as_of_date` matching the file-level
      `as_of_date`.
- [ ] Top-level `stale_after_date` is set and is within 7–30 days of
      `as_of_date` unless an explicit exception is documented and
      approved in the review.
- [ ] `limitations[]` are non-empty at file level and per record.
- [ ] `data_freshness_warning` is non-empty at file level and per record.
- [ ] `curator` is named.
- [ ] `reviewer` is named and differs from `curator`.
- [ ] `review_status` is `approved`.

### 9.2 Content scope

- [ ] ≤ 2 teams referenced.
- [ ] ≤ 5 player identity records.
- [ ] No salary/contract/cap fields anywhere in either file.
- [ ] No injury/medical fields anywhere.
- [ ] No rumor/scouting/live/current/depth-chart/minutes/role-projection/
      trade-eligibility/PII/social/agent/media/mutation/logo fields
      anywhere.

### 9.3 Integrity

- [ ] `player_id`s are unique and match `^[a-z][a-z0-9_-]*$`.
- [ ] Every `roster_memberships[].player_id` resolves to exactly one
      player identity.
- [ ] Every `roster_memberships[].team_id` resolves to exactly one team
      in `teams.json` and is within the 2-team pilot scope.
- [ ] Every `roster_status` is one of the six allowed values.
- [ ] `manual_review_required=true` everywhere (file + per record).
- [ ] `live_eligible=false` everywhere (file + per record).
- [ ] `snapshot_id` is consistent across all four pilot files (players,
      rosters, manifest, source_manifest).
- [ ] Hash plan is documented (the exact SHA-256 command and values
      computed against the final bytes).
- [ ] Rollback plan is documented (how to revert if review finds issues
      after landing: `git revert` the F4 commit plus a follow-up note).

### 9.4 Test plan

- [ ] The F4 test plan is written: which tests will be added/modified,
      including any extension of the F2 synthetic fixtures with a
      parallel "real-pilot smoke" fixture loaded from tmp_path using
      the exact pilot bytes.
- [ ] M10-F2 read model tests will be re-run and stay green.
- [ ] M10-E schema tests will be re-run and stay green.
- [ ] M10 full metadata regression will be re-run and stay green.
- [ ] Static isolation tests (no frontend/Agent/NL/trade/signing import)
      will be re-run and stay green.

## 10. F4 allowed files only after F3 approval

If (and only if) F3 is accepted and F4 passes its own review, the F4
milestone is permitted to touch the following files. F4 must not touch
any file outside this list.

Permitted for F4:

- `data/snapshots/nba_real_2026_preoffseason_v1/normalized/player_identities.json` (new file)
- `data/snapshots/nba_real_2026_preoffseason_v1/normalized/roster_memberships.json` (new file)
- `data/snapshots/nba_real_2026_preoffseason_v1/source_manifest.json` (update to add categories / hashes / per_file_sources)
- `data/snapshots/nba_real_2026_preoffseason_v1/manifest.json` (update if needed to reflect new normalized files, under schema validation)
- `docs/m10-f4-real-player-roster-tiny-pilot.md` (new F4 handoff / verification doc)
- `backend/app/tests/test_m10f_player_roster_metadata_read_model.py`
  (may add a small real-pilot smoke test, still via tmp_path copy of
  the pilot bytes — never mutating data/snapshots in tests)

Still forbidden in F4:

- `frontend/**`
- `backend/app/api.py` (no new endpoint in F4; endpoint deferred to a later milestone)
- `backend/app/services/**` beyond any strictly necessary minimal fix
  to the existing `player_roster_metadata_reader.py` if a bug is found
  during pilot (documented and justified in F4 review)
- `backend/app/snapshot_loader.py`
- `backend/app/services/orchestrator*`
- Agent-related code
- Natural-language-preview code
- Trade logic
- Signing logic
- `schema/**` (no schema changes in F4; any schema change requires its own gate)
- Contracts / salaries / cap sheets files (any filename)
- Injury / medical data files
- Rumors / scouting opinions files
- Live / current / runtime-fetch code
- NBA API integration
- Scraping code
- LLM-as-fact code
- POST/PUT/PATCH/DELETE endpoints
- `execute/apply/commit/mutate/write/persist/save/delete/update/submit/auto_*` endpoints
- Operations on `D:\DraftMind`

## 11. F4 required tests

F4 must run and report the following test groups, all of which must be
green before F4 may be considered for acceptance:

- `backend/app/tests/test_m10f_player_roster_metadata_read_model.py` —
  M10-F2 read model tests (including the two new manifest/visual schema
  mismatch tests added in the F2 patch).
- `backend/app/tests/test_m10e_source_lineage_schema.py`
- `backend/app/tests/test_m10e_player_identity_schema.py`
- `backend/app/tests/test_m10e_roster_membership_schema.py`
- `backend/app/tests/test_m10_real_snapshot_schema.py`
- `backend/app/tests/test_m10c_team_metadata.py`
- `backend/app/tests/test_m10c_team_visual_metadata.py`
- `backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py`
- Plus any F4-specific pilot smoke tests added by F4, which must:
  - Load the pilot bytes via `tmp_path` (never by importing
    `data/snapshots/...` directly at module import time).
  - Validate that every pilot player_id and team_id cross-references.
  - Validate that file hashes match `source_manifest.file_hashes`.
  - Validate the recursive forbidden-field scan on the pilot bytes.
  - Validate that no forbidden files (contracts/salaries/cap/injuries/
    rumors/scouting/live) exist in the snapshot after F4 lands.
  - Validate no-demo-fallback behavior for the pilot snapshot.
- The full M10 metadata regression (all tests above) must be re-run
  after F4 lands and must remain green.

## 12. Risk register

### 12.1 High severity

| Risk | Impact | Mitigation carried into F4 |
|---|---|---|
| Frozen roster misread as live/current | User treats an as-of snapshot as live; misleading trade/signing implications | `live_eligible=false` const; mandatory `data_freshness_warning`; `stale_after_date` + F2 hard-error; ≤5-player pilot minimizes blast radius; Agent/NL/trade/signing remain disconnected in F4 |
| Source conflict between league/team/public pages | Curator writes wrong value; downstream consumers propagate errors | Source pack requires `conflict_notes`; `manual_curated` requires cross-checking ≥2 sources; league > team > public reference tie-break documented in §4.1; reviewer sign-off; ≤5 records make line-by-line recheck feasible |
| Source licensing / ToS / scraping risk | Legal / attribution issue | Manual small-batch curation only; ≤5 players explicitly scoped (no bulk); no runtime fetch; no scraping; every `source_url` is a public page the curator read directly; no paid database dumps; terms-violating copy forbidden by §5 |
| Salary/contract/cap data accidentally enters | Creates false precision and leaks a deferred category | E3/E4 propertyNames blacklists enforced by schema; F2 recursive forbidden-key scan; F4 test adds forbidden-file scan (no `contracts.json`/`salaries.json`/etc. in snapshot); code-review checklist in §9; F4 scope ceiling in §2 forbids it |
| Agent / trade / signing misuses real roster | Misleading proposals; user trust damage | Static import-guard tests retained from F2; §10 explicitly keeps Agent/NL/trade/signing disconnected in F4; endpoint not added in F4 |
| player_id or team_id cross-reference error | Wrong player linked to wrong team; silently corrupt data | F2 xref hard errors (`PlayerRosterCrossReferenceError`); F4 test plan requires per-record xref check; ≤5-player pilot keeps manual review tractable; id scheme documented per F1 §5.3 |
| Stale data misleads after the offseason window | User draws conclusions from outdated roster | Short `stale_after_date` (7–30 days) mandatory in §8.4; F2 raises `PlayerRosterStaleDataError` past the window; pilot lands in deep offseason so movements are rare |

### 12.2 Medium severity

| Risk | Impact | Mitigation carried into F4 |
|---|---|---|
| player_id naming collision | Two distinct players collapse to one id | Namespaced slug scheme from F1 §5.3; uniqueness test in F2; ≤5-player pilot makes collision astronomically unlikely; reviewer explicitly checks for collisions in §9.3 |
| Inconsistent height/weight/position across sources | Display inconsistency | Height/weight are free-form display strings (null permitted); position constrained to E3 enum; conflicts documented in `conflict_notes`; cross-source tie-break documented |
| `stale_after_date` set too long | Errors surface later than they should | Recommended 7–30 day window; reviewer must explicitly approve any window outside this range (§9.1) |
| `source_url` link rot after landing | Future reviewers can't re-verify provenance | `access_date` recorded; reviewer verifies URLs at review time; `source_name` + `as_of_date` remain useful even if URL later moves; snapshot is frozen-as-of and not auto-refreshed |
| `free_agent` roster_status over-applied | Non-free-agents incorrectly tagged, misleading users | `free_agent` requires strong limitation caveat per §7.2; reviewer must confirm each such record against ≥2 sources; recommended default is to exclude free agents from pilot entirely and stick to `standard`/`two_way` |

### 12.3 Low severity

| Risk | Impact | Mitigation carried into F4 |
|---|---|---|
| Typos / formatting in display names or height/weight strings | Cosmetic inconsistency | Line-by-line reviewer check (≤5 players); F2 read model surfaces strings as-is; typos fixed in a follow-up snapshot version (no in-place mutation of sealed snapshot) |
| Optional fields set to null inconsistently | Minor display variation | Schema permits `null` for `birthdate`/`height`/`weight`/`source_url` (for `manual_review` only); consistent null handling enforced by schema types |
| `notes[]` accidentally contains prohibited content | Forbidden concept leaks into free text | F2 forbidden-field scan recurses into `notes[]` values (substring); reviewer must spot-check `notes[]` against the §6.3/§7.4 blacklists |

## 13. Explicit forbidden scope for F3

This gate (M10-F3) is strictly docs-only. The following are explicitly
out of scope for F3 itself and must not appear as changes on disk:

- **No `backend/**` changes** (no API, no services, no loaders, no models)
- **No `frontend/**` changes**
- **No `schema/**` changes**
- **No `tests/` changes**
- **No `data/**` changes** (snapshots unchanged)
- **No `normalized/player_identities.json`**
- **No `normalized/roster_memberships.json`**
- **No contracts / salaries / cap sheets** (any filename)
- **No injury / medical / rumor / scouting data**
- **No Agent / NL-preview / trade / signing wiring**
- **No NBA API integration**
- **No scraping**
- **No LLM-generated real data**
- **No new HTTP endpoints** (GET/POST/PUT/PATCH/DELETE)
- **No `execute/apply/commit/mutate/write/persist/save/delete/update/submit/auto_*` endpoints**
- **No operations on `D:\DraftMind`**

F4 may relax a small subset of these (the three pilot data files and F4
docs/tests) only after F3 is accepted **and** F4's own ChatGPT review
passes.

## 14. Final conclusion

- **M10-F3 is docs-only.** The only artifact produced by this milestone
  is `docs/m10-f3-source-pack-tiny-pilot-approval-gate.md` (this file).
- **M10-F3 does not authorize real data writes.** No `player_identities.json`
  or `roster_memberships.json` is approved by F3; no byte of real player
  or roster data lands as part of F3.
- **M10-F3 defines the bar F4 must clear.** F4 (real data tiny-pilot
  implementation) must (a) honor the §2 scope ceiling (≤2 teams,
  ≤5 players, identity+roster only), (b) produce a complete §3 source
  pack, (c) use only §4 allowed sources, (d) satisfy every §6/§7 schema
  and field rule, (e) implement the §8 hash/manifest plan, (f) pass the
  §9 reviewer checklist, (g) stay within the §10 file list, and
  (h) pass the §11 test matrix.
- **F4 requires its own ChatGPT approval.** Passing F3 does not
  automatically open F4. The F4 curator must open a fresh ChatGPT review
  that demonstrates the source pack, pilot data (staged in tmp_path for
  review, not yet committed), hashes, checklist sign-off, and test plan
  before any real byte is committed.
- **Automatic progression to F4 is not permitted.** The sequence is
  strict: F1 (docs gate) → F2 (synthetic read model) → F3 (this gate)
  → F4 (tiny pilot, requires its own approval) → F-Smoke → F-Handoff.
  Skipping a milestone or approving F4 inside the F3 conversation is
  forbidden.
- **Contracts/salaries/cap sheets remain out of scope** for all of
  M10-F and require a future dedicated governance series (M10-G or later).
- **F3 is ready for ChatGPT review** after this document lands.
