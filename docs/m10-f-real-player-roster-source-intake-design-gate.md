# M10-F1: Real Player/Roster Source Intake Design Gate

Run date: 2026-06-28.
Baseline: commit `276526e`, tag `m10e-final-handoff`, clean working tree.

This document is a **design gate**. It is a docs-only milestone. It does
not add real player data, real roster data, backend code, frontend code,
schemas, tests, snapshots, or any form of wiring. It prescribes how
real player/roster data may be admitted to the repository in future
M10-F sub-milestones and where the hard stop-lines are.

## 1. Design gate verdict

- **M10-F verdict: CONDITIONAL GO.**
- The only step approved at this gate is **M10-F1: docs-only source intake
  design gate** (this document).
- **NO** to directly writing real `normalized/player_identities.json`.
- **NO** to directly writing real `normalized/roster_memberships.json`.
- **DEFERRED** (not yet approved) for a backend read model: F1 does not
  approve a backend read model implementation. The read model (M10-F2)
  must itself pass a design-and-smoke gate using synthetic fixtures
  before any real data is considered.
- **NO** to frontend wiring.
- **NO** to Agent / NL-preview / trade / signing integration.
- **NO** to contracts / salaries / cap sheets (remain deferred past M10-F).
- **NO** to live/current/latest roster semantics, injury/medical data,
  rumors, scouting opinions, or any mutation endpoints.

M10-F1 approval does **not** grant automatic permission to enter real
data intake. After F1 is accepted, the next gate (F2) must be opened
and passed before any code moves; real data intake is not approved until
F3 (source-pack approval) and F4 (pilot implementation) both pass.

## 2. Recommended M10-F route

M10-F must proceed through the following sub-milestones **in order**. No
milestone may be skipped. Each milestone ends with its own smoke/handoff
and must be reviewed before the next begins.

| # | Milestone | Type | Real data? |
|---|---|---|---|
| F1 | **Source Intake Design Gate** (this document) | docs-only | No |
| F2 | Backend read model with **synthetic** fixture; no real data | code + tests | No (synthetic only) |
| F3 | Source pack + tiny pilot data approval gate | docs + source pack review (data staged, not yet landed) | Pilot data staged for review only |
| F4 | Real data pilot implementation | code + tiny pilot data | Yes — tiny pilot only, if F3 passes |
| F-Smoke | Full M10-F smoke verification | tests + docs | — |
| F-Handoff | M10-F Final Handoff | docs-only | — |

Key ordering rules:

- After F1, do **not** auto-proceed to writing real data. F1 only sets
  intake rules.
- F2 must land and smoke with synthetic fixtures before any real-data
  reader exists. The synthetic reader path is what proves the
  hard-error / no-demo-fallback contract before real bytes ever appear.
- F3 is a **review-only** gate. The source pack (source list, lineage
  values, hash plan, scope of pilot, reviewer sign-off sheet) must be
  approved on paper before any real record is written.
- F4 is the first milestone allowed to write real data, and only a
  **tiny pilot** (see §3, §7). It must re-run the full M10 metadata
  regression plus new F tests.
- Contracts / salaries / cap sheets are **not** in scope for any F
  milestone. They belong to a later series (M10-G or beyond) and must
  have their own governance gate.

## 3. Source policy

### 3.1 Allowed source_type values

These are the only values permitted by the E3/E4 schemas'
`source_type` enum, and the only values this gate approves for future
real data:

- `manual_curated` — Human-assembled data where a named curator has
  cross-checked values across public references. Default for the pilot.
- `public_reference` — Publicly available reference sites
  (e.g. Basketball Reference, ESPN public rosters, Spotrac public pages)
  used as a citation only.
- `league_public_reference` — League-published public reference material
  (e.g. NBA.com team roster pages, NBA official stats public pages).
- `team_public_reference` — Team-published public reference material
  (e.g. an individual team's official public roster page).
- `manual_review` — Value is under active manual review and must not be
  treated as authoritative; used only for placeholders during the
  curation process.

### 3.2 Forbidden source_type values

The following are forbidden at the schema layer today and remain
forbidden under this gate. F2/F3/F4 tests must continue to reject them:

- `llm_generated`
- `scraped_unreviewed`
- `live_api` (any runtime API pull)
- `social_media`
- `rumors` / forums / Reddit as a fact source
- Unsourced copy-paste from any site
- Bulk scraping of any kind (scripted mass download without an explicit
  design gate)
- Paid database dumps or any data copied in violation of a source's
  terms of service.

### 3.3 Source usage rules

- NBA.com may be cited as `league_public_reference`.
- Individual team official sites may be cited as `team_public_reference`.
- Basketball Reference / ESPN public pages / Spotrac public pages may be
  cited as `public_reference`.
- All of the above are treated as **public citations only**. They are
  used to verify facts that are then entered manually by a curator.
- **No runtime fetch.** The application must not make HTTP calls to
  NBA.com, team sites, or reference sites at request time.
- **No scraping.** Curation is manual, small-batch, and human-reviewed.
  Bulk scripted ingestion is out of scope for M10-F and would require a
  separate governance gate covering terms-of-service, rate limits, and
  attribution.
- **Do not imply official authorization.** `league_public_reference` /
  `team_public_reference` mean "cited from a public league/team page";
  they do not imply partnership, endorsement, or licensed data feed.
- **No LLM-generated real data.** LLM output must never be written into
  `player_identities.json` or `roster_memberships.json` as fact. The
  LLM may be used only as a drafting assistant for human review, and
  every value must be verified against a permitted source before
  landing.

## 4. Manual curation rules

Future real data (when approved in F3/F4) must follow these curation
rules:

- **Small batch only.** Curate in small, reviewable batches. No bulk
  imports.
- **Every real record is source-backed.** There is no "common knowledge"
  exception. Every record carries its own `source_name` and (for real
  intake) a non-null `source_url` at the record level.
- **Top-level + per-record lineage.** Both the file-level and
  per-record lineage fields must be populated:
  - `source_name` (non-empty string)
  - `source_url` (non-null string for the real-data pilot; `null` is
    permissible only for placeholders that are explicitly `manual_review`
    and blocked from the read model until filled)
  - `source_type` (one of the five allowed enum values)
  - `as_of_date` (YYYY-MM-DD cutoff date; same or newer than the snapshot
    `as_of_date`)
  - `manual_review_required: true` (const)
  - `live_eligible: false` (const)
  - `data_freshness_warning` (non-empty string; UI-mandatory)
  - `limitations` (non-empty array of strings)
- **stale_after_date must be defined.** The source manifest's per-file
  entry must include a `stale_after_date` (YYYY-MM-DD) after which the
  data is considered stale. A recommended default for roster data is
  `as_of_date + 7 to 30 days`, depending on the curation point in the
  offseason (closer to the season = shorter window; deep offseason = up
  to 30 days).
- **Post-staleness policy.** After `stale_after_date`, the future read
  model must at minimum surface an **elevated staleness warning**; the
  preferred behavior (and the behavior F2 must implement) is **hard
  error until re-review** (raises a typed `StaleDataError` surfaced as
  HTTP 500), matching the existing hard-error philosophy for
  schema/hash/xref errors.
- **Manual sign-off.** Each batch must have a named reviewer sign-off
  recorded in the F3 source pack before F4 lands any byte.

## 5. Future player_identities.json requirements

Based on `schema/player_identities_schema.json` (M10-E3), future real
player identity data must be **identity-only**.

### 5.1 Allowed fields (only these)

Top-level:

- `schema_version`, `snapshot_id`, `as_of_date`, `generated_at`
- `source_name`, `source_url`, `source_type`
- `manual_review_required` (must be `true`),
  `live_eligible` (must be `false`)
- `data_freshness_warning`, `limitations`
- `players[]`

Per-player:

- `player_id`, `display_name`, `first_name`, `last_name`, `position`
- `birthdate` (string `YYYY-MM-DD` or `null`)
- `height` (string or `null`), `weight` (string or `null`)
- `source_name`, `source_url`, `source_type`, `as_of_date`
- `manual_review_required: true`, `live_eligible: false`
- `data_freshness_warning`, `snapshot_id`, `limitations`
- `notes[]` (optional, curator caveats only)

### 5.2 Forbidden (must not appear at any level)

The following must **not** appear as keys or as values implying these
concepts; today they are blocked by the E3 56-field `propertyNames`
blacklist, and F2/F4 tests must keep them blocked:

- Money / contract / cap: `salary`, `salaries`, `contract`, `contracts`,
  `cap_hold`, `guarantee`, `guarantee_amount`, `cap_sheet`, `cap_sheets`
- Medical / injury: `injury`, `injuries`, `injury_status`, `medical`,
  `medical_status`, `health`
- PII / representation / personal: `personal_sensitive_info`,
  `social_media`, `agent`, `agent_representation`, `headshot`,
  `headshot_url`, `player_image`, `photo_url`, `official_headshot`
- Rumors / scouting: `rumors`, `rumor`, `scouting_opinion`,
  `scouting_opinions`
- Live / availability / projection: `live_status`, `availability`,
  `real_time_availability`, `projected_depth_chart`, `depth_chart`,
  `minutes_projection`, `role_projection`, `trade_eligibility`
- Mutation / execution verbs: `execute`, `apply`, `commit`, `mutate`,
  `write`, `persist`, `save`, `delete`, `update`, `submit`,
  `auto_execute`, `auto_approve`
- Live/current naming: `current_roster`, `latest_roster`,
  `live_salaries`, `latest_data`, `live_data`, `current_salaries`,
  `real_time_data`
- Logos: `logo_path`, `logo_url`, `official_logo`, `nba_logo`,
  `team_logo`, `mascot_image`

### 5.3 player_id naming rule

- Pattern: `^[a-z][a-z0-9_-]*$` (already enforced by schema).
- Must be **stable, reviewable, collision-resistant**. For the pilot,
  use a namespaced slug derived from the player's common public name
  (e.g. the Basketball Reference slug) with a disambiguation suffix when
  names collide.
- The id scheme must be documented in the F3 source pack and applied
  consistently. Re-mapping ids after landing is forbidden; any id change
  requires a new snapshot version.

## 6. Future roster_memberships.json requirements

Based on `schema/roster_memberships_schema.json` (M10-E4), future real
roster memberships represent a **frozen point-in-time team↔player
linkage**, not a live roster.

### 6.1 Allowed roster_status values (only these)

`roster_status` must be exactly one of:

- `standard` — standard NBA contract
- `two_way` — two-way contract
- `training_camp` — training camp / preseason Exhibit deal
- `unsigned_draft_rights` — unsigned draft rights held by a team
- `free_agent` — explicitly listed as an offseason free agent (only
  when the curator is intentionally capturing a known free agency
  state; must carry `manual_review_required` and a strong limitation
  caveat)
- `unknown_manual_review` — placeholder during curation; must not be
  served by the read model until promoted to one of the other statuses

### 6.2 Forbidden roster_status values

The following statuses are rejected by both the enum and the E4
propertyNames blacklist today, and remain forbidden for M10-F:

- Transactional statuses: `inactive`, `waived`, `traded`, `suspended`
- Availability/injury: `injured`, `questionable`, `probable`,
  `day_to_day`, `available`, `unavailable`
- Live/current naming: `active_now`, `current`, `latest`

### 6.3 Cross-reference and field rules

- `team_id` must match the pattern `^nba-[A-Z]{3}$` and must exist as a
  key in `normalized/teams.json`. A missing or mismatched team id must
  raise a typed `CrossReferenceError` → HTTP 500 (no demo fallback).
- `player_id` must match the pattern `^[a-z][a-z0-9_-]*$` and must
  resolve to exactly one record in `normalized/player_identities.json`.
  Missing or duplicate player ids must raise `CrossReferenceError` /
  `DuplicatePlayerIdError` → HTTP 500.
- `membership_id` is optional; if present it must be a stable,
  reviewable id (not a runtime UUID).
- Roster memberships must **not** imply a live/current roster. Every
  response served by a future read model must be presented as a frozen
  as-of snapshot with `live_eligible=false` and the mandatory freshness
  warning.
- Forbidden fields (money/contract/cap, injury/medical, trade
  restrictions, depth/role/rotation, live/current, mutation verbs,
  logos) are blocked by the E4 78-field `propertyNames` blacklist
  today. F2/F4 must retain and extend this protection. Specifically,
  F2/F4 must continue to reject: salary/contract/cap, injury/medical,
  `trade_eligibility` / `no_trade_clause` / trade restriction fields,
  depth-chart/role/minutes projections, and any live/current/latest
  naming.

## 7. Source manifest rules

Future real-data snapshots (approved in F3/F4) must satisfy the
following source-manifest rules on top of the E2 schema:

- `data_categories` may be extended with exactly two future categories,
  and only when those files actually exist in the snapshot:
  - `player_identities`
  - `roster_memberships`
- `data_categories` must **never** include `contracts`, `salaries`,
  `cap_sheets`, `injuries`, `rumors`, `live_status`, or any other
  category not explicitly approved by a future governance gate.
- `per_file_sources` must contain entries for:
  - `normalized/player_identities.json`
  - `normalized/roster_memberships.json`
- `file_hashes` must include SHA-256 entries for both files; hashes must
  match the bytes on disk or the reader raises `HashMismatchError` →
  HTTP 500.
- Each per-file entry must populate (non-empty, non-null where
  applicable):
  - `source_name`, `source_url`, `source_type`
  - `as_of_date`
  - `manual_review_required: true`
  - `live_eligible: false`
  - `limitations[]` (non-empty)
  - `data_freshness_warning` (non-empty)
  - `stale_after_date` (YYYY-MM-DD; see §4)
- Missing hashes are hard errors. Missing sources are hard errors.
- No fallback to demo/generated data on any of these errors.

## 8. Backend read model planning (F2, not F1)

A backend read model may be added in **M10-F2**, subject to its own
gate. F1 does not approve or implement it. When built, it must satisfy:

### 8.1 Endpoint shape (proposal, for F2 review)

- `GET /api/snapshots/player-roster-metadata?snapshot_mode=real_snapshot`
- **Read-only.** GET only. The path must not accept POST/PUT/PATCH/
  DELETE. F2 tests must assert this via OpenAPI scan and direct method
  probes.
- The endpoint must require `snapshot_mode=real_snapshot`; it must not
  serve data from demo/generated snapshots.

### 8.2 Error contract (must be hard errors → HTTP 500)

- Missing file (`player_identities.json` or `roster_memberships.json`
  absent from the selected real snapshot)
- Schema mismatch (fails schema validation)
- Hash mismatch (file bytes do not match `file_hashes`)
- Cross-reference mismatch:
  - `team_id` not present in `teams.json`
  - `player_id` not present in `player_identities.json`
  - Duplicate `player_id`
- Stale data past `stale_after_date` (preferred behavior; minimum:
  elevated warning field in every response)
- **No fallback to demo/generated data.** No stub data, no empty
  defaults for missing teams/players.

### 8.3 Response contract

- Returned payload must contain only identity + roster-membership
  fields as defined by the E3/E4 schemas. It must not add or infer:
  salary/contract/cap, injury/medical, rumors/scouting, depth chart,
  minutes/role projection, trade eligibility, or live/current hints.
- Every response must surface the lineage fields
  (`source_name`, `source_url`, `source_type`, `as_of_date`,
  `data_freshness_warning`, `limitations`, `live_eligible=false`,
  `manual_review_required=true`, `stale_after_date`) and make the
  non-live / frozen-snapshot semantics visible to the caller.

### 8.4 Consumer isolation (F2 must enforce with static tests)

- The Agent must not import the new player/roster reader.
- Trade logic must not import the new player/roster reader.
- Signing logic must not import the new player/roster reader.
- Natural-language-preview must not import the new player/roster reader.
- The demo/generated snapshot paths must not import the new reader.
- F1 explicitly does not approve any frontend wiring. Frontend must
  remain isolated in F2.

## 9. Frontend / Agent / NL preview boundary

F1 imposes a strict consumer boundary that must hold until a future
dedicated gate explicitly opens it:

- **F1: no frontend UI.** No player list, no roster panel, no player
  inspector, no headshots, no logos.
- **F1: no Agent use.** The Agent must not see player/roster metadata,
  even as read-only context.
- **F1: no NL-preview use.** The natural-language preview must not cite
  or summarize player/roster data.
- **F1: no trade/signing use.** Trade simulator and signing logic must
  continue to operate on demo/generated data only.
- **F1: no selected-team→roster wiring.** Selecting a team in the
  existing /offseason panel must not trigger a player/roster request
  or feed the Agent a team-linked player list.

### 9.1 Why this boundary is strict

Real roster data entering the recommendation chain would create a
user-visible lie: the project does **not** have real salary/cap/contract
data, so any trade or signing proposal that appears to be grounded in a
"real" roster will be misleading (e.g., it will propose trades against a
real-looking roster while using placeholder salaries). Until
salary/contract/cap data is itself governed and landed (M10-G or
later), roster data cannot be allowed to flow into recommendation
surfaces. Frozen identity/roster data may be exposed as a read-only
reference surface only after a dedicated frontend-gate milestone
(post-F4) that re-confirms this semantic boundary.

## 10. Testing strategy for later M10-F milestones

F2 and later must add (and keep green) at least the following tests:

**Schema / integrity**

- Schema validation against `player_identities_schema.json` and
  `roster_memberships_schema.json` (positive + negative).
- `source_manifest_schema.json` validation including
  `data_categories`, `per_file_sources`, and `file_hashes`.
- File hashes validate against on-disk bytes; tampered bytes raise
  `HashMismatchError`.
- Per-file source entry presence; missing entries or missing fields
  raise errors.

**Cross-reference**

- `player_id` uniqueness within `player_identities.json`.
- Every `roster_memberships[].player_id` resolves to exactly one
  player identity.
- Every `roster_memberships[].team_id` resolves to exactly one team in
  `teams.json`.

**Forbidden content**

- Forbidden files absent from any real snapshot:
  `contracts.json`, `salaries.json`, `cap_sheet(s).json`,
  `injuries.json`, `rumors.json`, `scouting_opinions.json`.
- Recursive scan over `player_identities.json` and
  `roster_memberships.json` for forbidden keys and forbidden values
  (salary/contract/cap/injury/medical/rumor/scouting/live/current/
  latest/active_now) — both as keys and as substrings in free-text
  `notes[]`.
- Mutation verbs (`execute/apply/commit/mutate/write/persist/save/
  delete/update/submit/auto_*/`) absent from schemas, routes, and
  services related to player/roster.

**Reader behavior (F2)**

- No fallback demo on any of: missing file, schema error, hash error,
  xref error, stale data.
- GET-only endpoint; OpenAPI scan rejects POST/PUT/PATCH/DELETE on
  the player-roster endpoint.
- Static import guard tests: importing the player/roster reader from
  Agent, NL-preview, trade logic, signing logic, or demo paths fails
  the test suite (enforced via grep/importlib assertions per existing
  project convention).

**Frontend isolation**

- Frontend build does not reference player/roster endpoints until a
  dedicated frontend gate opens; verified by a content-scan test over
  the built bundle or source.

**Regression**

- The existing M10 metadata regression (732 tests at the time of
  M10-E seal) must remain green. F2/F3/F4 must extend it, not relax
  it.

## 11. Risk register

### High

| Risk | Impact | Mitigation |
|---|---|---|
| Frozen roster misread as current/live | User treats an as-of snapshot as live; misleading trade/signing implications | `live_eligible=false` const; mandatory `data_freshness_warning`; `stale_after_date` + hard error; UI must show as-of date prominently; no Agent/NL/trade/signing consumption in F1-F4 |
| player/team cross-reference errors | Wrong player linked to wrong team; silently corrupt data | F2 adds xref tests; duplicate/missing ids → HTTP 500; file_hashes enforced; no demo fallback |
| Salary/contract/cap data accidentally enters player/roster files | Creates false precision and leaks a deferred category | E3/E4 propertyNames blacklists retained and extended; F2/F4 add recursive content-scan tests; code review checklist; forbidden-file tests |
| Agent misuses real roster to drive trade/signing | Misleading proposals; user trust damage | Static import guard tests (F2); explicit boundary in §9; no reader import from Agent/trade/signing/NL-preview paths |
| Fallback-to-demo masks real-data errors | Silent corruption appears as "working" UI | Hard-error contract enforced by tests; typed errors → HTTP 500; no stub/empty defaults |

### Medium

| Risk | Impact | Mitigation |
|---|---|---|
| Source licensing / ToS / scraping risk | Legal / attribution issue | Manual small-batch curation only; no bulk scraping; no runtime fetch; sources cited; any automated intake requires its own governance gate |
| Stale roster misleads even within the window | User draws conclusions from outdated roster | Short `stale_after_date` (7-30d); elevated staleness signaling; prefer hard error over silent serve; offseason timing noted in `limitations` |
| Conflicting sources (NBA.com vs team site vs reference) | Curator picks wrong value | `limitations[]` must note conflicts; prefer league_public_reference over public_reference when values disagree; `source_url` non-null for every real record; reviewer sign-off in F3 |
| Schema drift (future milestones loosen guards) | Guardrails silently weaken | Any schema change to E3/E4 schemas requires a governance gate; propertyNames blacklist only grows (never shrinks) within M10-F; M10 regression stays green |

### Low

| Risk | Impact | Mitigation |
|---|---|---|
| Height/weight/birthdate format differences across sources | Display inconsistency | Free-form display strings for height/weight; YYYY-MM-DD for birthdate (null if unavailable); document format choices in F3 source pack |
| player_id naming collisions or instability | Duplicate ids or broken xrefs after id changes | Namespaced slug scheme documented in F3; no id remapping post-landing (new snapshot version required); uniqueness + xref tests in F2 |

## 12. Explicit forbidden scope for F1

This gate (M10-F1) is strictly docs-only. The following are explicitly
out of scope for F1 and must not appear as changes on disk:

- **No `frontend/**` changes**
- **No `backend/**` changes** (no API, no services, no loaders)
- **No `snapshot_loader.py` changes**
- **No orchestrator changes**
- **No `natural-language-preview` changes**
- **No trade/signing logic changes**
- **No `schema/**` changes**
- **No `tests/` changes**
- **No `data/**` changes** (snapshots unchanged)
- **No `normalized/player_identities.json`**
- **No `normalized/roster_memberships.json`**
- **No contracts/salaries/cap sheets** (any filename)
- **No injury/medical/rumor/scouting data**
- **No Agent/NL/trade/signing wiring for player/roster**
- **No NBA API integration**
- **No scraping**
- **No LLM-generated real data**
- **No `D:\DraftMind` operations**
- **No execute/apply/commit/mutate/write/persist/save/delete/update/
  submit/auto_*/ endpoints**

F2 and later may relax some of these only under their own approved
gates; F1 itself produces exactly one artifact: this document.

## 13. Final conclusion

- **M10-F1 is docs-only.** The only artifact produced by this milestone
  is `docs/m10-f-real-player-roster-source-intake-design-gate.md`.
- **M10-F1 is ready for ChatGPT review** after completion of this step.
- **Do not proceed directly to real-data writing.** Writing
  `player_identities.json` or `roster_memberships.json` is not approved
  by F1.
- **Do not proceed directly to a read model implementation.** F2 may
  begin only after F1 is accepted; F2 itself must use synthetic
  fixtures and must land its own smoke before any real data is
  considered.
- **Next recommended step if F1 is accepted:** M10-F2 Backend Read
  Model with synthetic fixtures / no real data, scoped per §8 and §10,
  followed by F3 (source pack approval gate), then F4 (tiny pilot
  real-data implementation). F3 is the first point at which a real
  pilot dataset may even be staged for review.
- **Contracts/salaries/cap sheets remain out of scope** for all of
  M10-F and require a future dedicated governance series.
