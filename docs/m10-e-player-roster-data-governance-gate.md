# M10-E1 Docs-only Data Governance Gate

M10-E1 is the **data governance gate** that must pass before any schema, fixture,
or real-data work begins for player identity and roster membership in the
`nba_real_2026_preoffseason_v1` real snapshot. It is a **docs-only** milestone:
no code, no schema, no fixtures, no data files are created or modified.

Run date: 2026-06-27.
Preceding seal: M10-D closed at commit `88e686c` / tag `m10d-final-handoff`.
Recommended tag after ChatGPT acceptance: `m10e1-player-roster-governance-gate`.

## 1. M10-E verdict (from GPT-5.5 Design Gate)

GPT-5.5 has reviewed the M10-D handoff and issued the following verdict:

- **GO** to enter M10-E docs-only governance (this document, M10-E1).
- **GO** to enter M10-E docs-only implementation of governance/schema scaffolding
  in subsequent E2–E4 milestones.
- **HOLD** on player/roster schema-only implementation until E1 governance is
  reviewed and accepted.
- **HOLD** on real player data writes and real roster data writes until schema
  and source/freshness rules in E2–E4 are sealed.
- **HOLD** on contracts / salaries / cap sheets — defer to M10-F or later.
- **Recommended path:** E = M10-E1 Docs-only Data Governance Gate → E2 → E3 →
  E4 → E-Smoke → E Final Handoff, each gated.

### What M10-E can do (starting after E1 acceptance)
- Write governance and design docs.
- Extend `source_manifest` / `manifest` schema to support new `data_categories`.
- Define JSON Schema for player identities and roster memberships.
- Write loader/service **tests** that operate on synthetic tmp_path fixtures.
- Add schema-level validation and forbidden-field scanning.

### What M10-E cannot do (at any sub-step, including E2–E4)
- **Cannot** write real player data (no real NBA player identities in
  `data/snapshots/`).
- **Cannot** write real roster data (no real 30-team roster memberships).
- **Cannot** write contracts, salaries, cap holds, guarantee amounts, cap-sheet
  figures of any kind.
- **Cannot** connect to the real NBA API, any stats endpoint, or any
  third-party live data source.
- **Cannot** scrape any website (Basketball-Reference, NBA.com, ESPN, etc.).
- **Cannot** call any LLM (GPT, GLM, or otherwise) to fetch, infer, verify, or
  judge real roster memberships, real player attributes, or real cap figures.
- **Cannot** wire real player/roster metadata into the Agent / orchestrator /
  natural-language-preview decision chains for trade/signing recommendations.
- **Cannot** switch the default data source away from demo.
- **Cannot** add any execute/apply/commit/mutate/write/persist endpoint under
  `/api/snapshots/` or anywhere else.
- **Cannot** bypass the hard-error / no-fallback-to-demo semantics established in
  M10-D1.

## 2. Recommended M10-E milestone breakdown

M10-E is split into six sub-milestones. E1 is this governance gate. E2–E4 are
schema-only and test-only. E-Smoke and E Final Handoff close the loop. No real
player/roster/contract/salary data is written at any point in M10-E.

### M10-E1 — Docs-only Data Governance Gate (this document)

- **Goal:** Lock down the "what is allowed / what is forbidden / how to verify"
  contract for player identity and roster membership before any schema file is
  edited.
- **File scope:** `docs/m10-e-player-roster-data-governance-gate.md` only.
- **Docs-only:** Yes.
- **Schema-only:** N/A (no schema changes).
- **Fixtures allowed:** No.
- **Real data allowed:** No.
- **Testing requirement:** Baseline `git status`/HEAD/tag check; `git diff`
  after writing must show only this one new doc. No pytest run required.
- **Exit criteria:** ChatGPT accepts governance; tag
  `m10e1-player-roster-governance-gate` applied by reviewer.

### M10-E2 — Source/Freshness/Lineage Schema Patch

- **Goal:** Extend the existing `manifest.json` / `source_manifest.json` schema
  (currently defined in M10-B/C) to admit two new `data_categories`:
  `"player_identities"` and `"roster_memberships"`, and strengthen per-file
  source/freshness rules (per_file_sources, file_hashes, stale_after_date,
  limitations) that E3/E4 will rely on.
- **File scope (expected):**
  - `backend/app/schemas/` (JSON schema definitions for manifest/source_manifest
    additions, or their equivalent location as established in M10-B).
  - `backend/app/tests/test_m10e*_source_manifest_schema.py` (new tests).
  - `docs/m10-e2-source-freshness-lineage-schema.md` (design doc).
- **Docs-only:** Partially (docs + schema + tests).
- **Schema-only:** Yes (manifest/source_manifest schema only; no player/roster
  schema yet).
- **Fixtures allowed:** Synthetic tmp_path fixtures only (no real data).
- **Real data allowed:** No. No new files under `data/snapshots/nba_real_*/normalized/`.
- **Testing requirement:** New schema tests; M10-B/C/D regression (at minimum
  `test_m10_real_snapshot_schema.py` + the M10-D1 47-test set) must still pass;
  forbidden-field scan must include new categories; explicit tests that missing
  per_file_sources / missing file_hashes / missing stale_after_date raise
  SchemaError or HashError.
- **Exit criteria:** Schema + tests + doc sealed; no real data; no frontend
  change; no Agent wiring; tag to be assigned (e.g. `m10e2-source-freshness-schema`).

### M10-E3 — Player Identity Schema

- **Goal:** Define the JSON Schema for `normalized/player_identities.json` (or
  equivalent) covering the minimal allowed player-identity fields listed in
  Section 3. Add schema validation tests; do not create the data file.
- **File scope (expected):**
  - `backend/app/schemas/` (new player identity JSON Schema).
  - `backend/app/services/real_snapshot_metadata_reader.py` may be extended in
    **E-Smoke / E-Final-Handoff**, not in E3 — E3 is schema + tests only.
  - `backend/app/tests/test_m10e*_player_identity_schema.py`.
  - `docs/m10-e3-player-identity-schema.md`.
- **Docs-only:** Partially (docs + schema + tests).
- **Schema-only:** Yes (player identity schema; no roster; no data file).
- **Fixtures allowed:** Synthetic tmp_path fixtures (synthetic `player_id`s such
  as `p-syn-001`, not real NBA players).
- **Real data allowed:** No.
- **Testing requirement:** Positive tests for the minimal allowed fields;
  negative tests for every forbidden field in Section 3 (each must fail schema
  validation); cross-reference tests against teams.json team_ids come later;
  M10-D regression must still pass.
- **Exit criteria:** Schema + tests + doc sealed; no real player data file
  exists; tag to be assigned.

### M10-E4 — Roster Membership Schema

- **Goal:** Define the JSON Schema for `normalized/roster_memberships.json` (or
  equivalent) covering the minimal allowed roster-membership fields and the
  six-value `roster_status` enum listed in Section 4. Add schema validation
  tests; do not create the data file.
- **File scope (expected):**
  - `backend/app/schemas/` (new roster membership JSON Schema).
  - `backend/app/tests/test_m10e*_roster_membership_schema.py`.
  - `docs/m10-e4-roster-membership-schema.md`.
- **Docs-only:** Partially (docs + schema + tests).
- **Schema-only:** Yes (roster membership schema; no service wiring yet; no
  data file).
- **Fixtures allowed:** Synthetic tmp_path fixtures; `player_id`s must reference
  the synthetic IDs from E3 tests, not real NBA players.
- **Real data allowed:** No.
- **Testing requirement:** Positive tests for all six `roster_status` values;
  negative tests for every forbidden roster field in Section 4; tests that
  `team_id` xref against `teams.json`, `player_id` xref against
  `player_identities.json`; tests that `inactive` / `waived` / `traded` are
  rejected unless/until a future milestone explicitly adds them with
  as_of_date/source provenance.
- **Exit criteria:** Schema + tests + doc sealed; no real roster data file
  exists; tag to be assigned.

### M10-E Smoke

- **Goal:** Verify that the entire E2–E4 chain works end-to-end **without** any
  real data: schema tests pass, manifest/source_manifest extensions validate
  synthetic fixtures, forbidden-field scans reject salary/contract/logo
  payloads, no frontend/backend/API/loader code paths are broken, and M10-D
  regression still passes.
- **File scope:** `docs/m10-e-smoke.md` (only new doc expected; smoke may also
  add test files if gaps are found).
- **Docs-only:** Primarily (smoke run produces a report; any test gap found is
  fixed as a test, not as a behavior change).
- **Schema-only:** N/A.
- **Fixtures allowed:** Synthetic tmp_path fixtures only.
- **Real data allowed:** No.
- **Testing requirement:**
  - M10-D backend regression (D1 47 tests + M10 metadata full 252 tests).
  - All new E2/E3/E4 schema tests.
  - Explicit tests that real player/roster data files do **not** exist under
    `data/snapshots/nba_real_2026_preoffseason_v1/normalized/` at the end of E.
  - Frontend `npm run typecheck` + `npm run build` (frontend source must be
    unchanged; this guards against accidental imports).
  - Explicit tests that `/api/snapshots/metadata?snapshot_mode=real_snapshot`
    still returns the M10-D shape (teams + team_visual_metadata) even after
    schema extensions (no premature roster projection).
  - No browser smoke is required in E-Smoke (no frontend change).
- **Exit criteria:** All tests pass; report doc written; tag to be assigned.

### M10-E Final Handoff

- **Goal:** Docs-only close of M10-E. Explicitly state that M10-E delivered
  governance + schema + tests only, that no real player/roster data was
  written, that contracts/salaries/cap sheets remain deferred to M10-F+, and
  that the frontend and Agent have not been modified.
- **File scope:** `docs/m10-e-final-handoff.md` only.
- **Docs-only:** Yes.
- **Schema-only:** N/A.
- **Fixtures allowed:** Retained as test-only tmp_path fixtures.
- **Real data allowed:** No.
- **Testing requirement:** Final full regression run (M10 252 tests + E2/E3/E4
  schema tests + frontend typecheck/build) captured in the handoff doc.
- **Exit criteria:** ChatGPT accepts; recommended tag `m10e-final-handoff`; M10-F
  (contracts/salaries/cap governance) can only begin after this handoff is
  sealed.

## 3. Player identity — minimal field design

### Allowed fields (E3 schema baseline)

| Field | Type | Required? | Notes |
|---|---|---|---|
| `player_id` | string | required | Namespaced, e.g. `nba-{surname}-{number-or-suffix}`; synthetic tests use `p-syn-NNN`. Must be stable across snapshots. |
| `display_name` | string | required | How the name should be shown in a UI (e.g. "LeBron James"). |
| `first_name` | string | required | |
| `last_name` | string | required | |
| `birthdate` | string (ISO date) | optional | Allowed but PII-light; governed by Section 10 (privacy risk). |
| `height` | string or number | optional | Display height only; must not be used to infer medical/availability state. |
| `weight` | string or number | optional | Display weight only; same caveat. |
| `position` | string | required | Guard/forward/center bucketed enum (e.g. `"PG"`, `"SG"`, `"SF"`, `"PF"`, `"C"`, `"G"`, `"F"`, `"FC"`, `"GF"`); precise positional deployment is out of scope. |
| `source_name` | string | required | Human-readable source name, e.g. `"manual curated player identity seed"`. |
| `source_url` | string | required per future manifest rule | Pointer to the public source page used for manual review; not fetched at runtime. |
| `source_type` | string enum | required | e.g. `"manual_curated"`, `"public_reference"`, `"league_roster"` — exact enum defined in E2. |
| `as_of_date` | string (ISO date) | required | Snapshot date for this identity record. |
| `manual_review_required` | boolean | required, fixed `true` | Enforced at schema level, mirroring M10-D1. |
| `data_freshness_warning` | string | required | UI-mandatory warning text. |
| `live_eligible` | boolean | required, fixed `false` | Enforced at schema level. |
| `snapshot_id` | string | required | Must equal the enclosing snapshot id (e.g. `"nba_real_2026_preoffseason_v1"`). |
| `notes` | string[] | optional | Curator notes, caveats, disambiguation notes. |
| `limitations` | string[] | required | Must include non-official / not-live / no-medical disclaimers. |

### Forbidden fields (must be rejected by schema + recursive scan)

Any occurrence of the following at any nesting level under
`player_identities` must raise schema or metadata error (defence-in-depth,
mirroring M10-D1 §7):

- **Money/contract fields:** `salary`, `contract`, `cap_hold`, `guarantee`,
  `guaranteed_amount`, `option`, `dead_cap`, `trade_kicker`, `percent_of_cap`.
- **Medical/injury fields:** `injury`, `injury_status`, `medical`, `health`,
  `condition`, `concussion`, `surgery`, `recovery`, `gtd`, `doubtful`, `out`.
- **Sensitive personal information:** `ssn`, `passport`, `national_id`,
  `address`, `phone`, `email`, `personal_contact`, `family_contact`,
  `religion`, `political_view`.
- **Social / off-court:** `social_media`, `twitter`, `instagram`, `tiktok`,
  `agent_representation`, `agent_name`, `agent_tel`, `endorsements`.
- **Rumors / opinion:** `rumors`, `rumor`, `trade_rumor`, `scouting_opinion`,
  `scouting_report`, `grade`, `rating`, `projection`, `comparison`.
- **Live / availability:** `live_status`, `availability`, `is_active`,
  `is_playing`, `minutes_projection`, `minutes`, `projected_minutes`,
  `projected_role`, `projected_depth_chart`, `depth_chart`, `starting`,
  `rotation_status`.
- **Branding / logo:** `headshot_url`, `player_image`, `headshot`, `photo_url`,
  `official_headshot`, `signature`, `brand_deal`.
- **Execution / mutation:** any of the M10-D1 execution verbs (`execute`,
  `apply`, `commit`, `mutate`, `write`, `persist`, `save`, `delete`, `update`,
  `submit`, `auto_execute`, `auto_approve`).

Player identity is, and must remain, **static identity metadata** only —
name, physical display attributes, position, and provenance. It must never
answer "is this player available tonight" or "what does this player cost".

## 4. Roster membership — minimal field design

### Allowed fields (E4 schema baseline)

| Field | Type | Required? | Notes |
|---|---|---|---|
| `team_id` | string | required | Must xref a team in `normalized/teams.json` (e.g. `"nba-LAL"`). |
| `player_id` | string | required | Must xref a player in `normalized/player_identities.json`. |
| `roster_status` | string enum | required | Six values only (see below). |
| `source_name` | string | required | Same semantics as player identity. |
| `source_url` | string | required per future manifest rule | Same semantics as player identity. |
| `source_type` | string enum | required | Same enum as player identity. |
| `as_of_date` | string (ISO date) | required | Snapshot/as-of date. |
| `manual_review_required` | boolean | required, fixed `true` | Enforced at schema level. |
| `live_eligible` | boolean | required, fixed `false` | Enforced at schema level. |
| `data_freshness_warning` | string | required | UI-mandatory warning text. |
| `snapshot_id` | string | required | Must match enclosing snapshot id. |
| `limitations` | string[] | required | Must include not-live / no-contract / no-availability disclaimers. |

### `roster_status` v1 enum

The first version of the roster status enum contains exactly six values:

| Value | Meaning |
|---|---|
| `standard` | Standard NBA contract on the 15-man (or 15+ injury replacement) regular roster for the as-of date. |
| `two_way` | Two-way contract player. |
| `training_camp` | Player in camp / Exhibit camp deal; not yet a standard or two-way contract at the as-of date. |
| `unsigned_draft_rights` | Draft rights held by a team but player not signed (draft-stash / unsigned pick). |
| `free_agent` | Player is a known free agent as of the as-of date (curated set only; must be a minimal, defensible list — not an exhaustive FA directory). |
| `unknown_manual_review` | Placeholder for entries that a curator has flagged as needing human review; displayed as "unknown" in any UI. |

### Deferred / forbidden status values (M10-E)

The following values are explicitly **out of scope for M10-E** and must be
rejected by the E4 schema:

- `inactive` — do not add in M10-E. Inactive status is time-varying and close
  to live data; requires explicit as_of_date/source pair and a future gate.
- `waived` — do not add in M10-E. Waivers are time-sensitive; only add with a
  future milestone that enforces explicit `as_of_date` + source provenance.
- `traded` — do **not** encode `traded` as a `roster_status`. Trades are
  transactions (M10-F+); they must not be conflated with static roster
  membership. Roster membership at a given as-of date is resolved by the
  curator, not by a "traded" pseudo-status.
- `exhibit_10`, `exhibit`, `summer_league`, `g_league_affiliate` — the
  `exhibit` family may be designed as an enum extension in a future milestone
  after review, but no real Exhibit-10 data is entered before that review.

### Forbidden roster fields (must be rejected)

Any occurrence of the following under `roster_memberships` must raise schema or
metadata error:

- **Money / cap:** `salary`, `cap_hold`, `guarantee_amount`, `guaranteed`,
  `dead_cap`, `trade_bonus`, `trade_kicker`, `cap_figure`, `cap_hit`,
  `percent_of_cap`, `bird_rights`, `early_bird`, `non_bird`, `qualifying_offer`,
  `extension`.
- **Eligibility / legalistic:** `trade_eligibility`, `trade_eligible`,
  `contract_status`, `waiver_status`, `option_status`, `bird_status`.
- **Availability:** `injury_status`, `real_time_availability`, `availability`,
  `is_active`, `is_playing`, `gtd`, `doubtful`, `out`, `suspension_status`.
- **Projection:** `projected_depth_chart`, `minutes_projection`,
  `role_projection`, `starting_projection`, `rotation_projection`.
- **Execution/mutation** verbs (same list as player identity and M10-D1).

Roster membership is, and must remain, **static membership metadata** — who is
affiliated with which team at a single as-of date, under what broad contract
bucket. It must never answer "is this player playing tonight", "what is this
player making", or "can this team trade this player".

## 5. Contracts / salaries / cap sheets — verdict

Contracts, salaries, and cap sheets are **strictly out of scope for M10-E**
and must not be touched in E1–E4, E-Smoke, or E-Final-Handoff.

### Why they are higher-risk than identities / rosters

- **Numerical / contractual accuracy.** Unlike a player's name or a team's
  15-man membership (which changes slowly and is curated with a clear
  as-of date), salary figures and cap hits change frequently due to trades,
  waivers, buyouts, extensions, 10-days, hardship exceptions, and end-of-season
  adjustments. A wrong number can mislead downstream cap reasoning.
- **Cross-team coupling.** Cap figures are relational: a trade changes the cap
  sheet of both teams; cap holds depend on renouncement decisions; exceptions
  (Bi-Annual, Mid-Level, Room) interact with team salary above/below the apron.
  Identity and roster membership are mostly per-team, per-player facts.
- **Decision surface is directly actionable.** A user can act on a displayed
  cap figure ("I can sign this FA for $X"); a user cannot directly act on a
  player's date of birth or height/weight the same way.
- **Branding / CBA risk.** Cap terminology (Bird rights, cap holds, QOs) is
  CBA-encumbered and easy to mis-label across CBA years. Identity/roster
  fields are far more stable across CBAs.

### M10-E verdict on salary/contract surfaces

- M10-E does **not** touch salary data.
- M10-E does **not** touch contract data.
- M10-E does **not** touch cap sheets, cap holds, cap hits, guaranteed
  amounts, exceptions, Bird rights, or any other money-valued field.
- Contracts / salaries / cap sheets are **deferred to M10-F or later**, where
  they must go through their own governance gate (mirroring this document)
  before any schema is drafted.
- If a future milestone proposes a salary/contract schema, that work must
  remain **schema/docs-only** in its first pass, with **no real data**
  populated, and explicit tests that zero real salary figures appear in
  `data/snapshots/`.
- The Agent and any LLM must **never** be allowed to infer, compute, or judge
  salary/contract/cap legality on their own. Cap math must only come from a
  curator-reviewed, source-backed, hash-checked data file, and even then only
  after M10-F governance gates open.
- The recursive forbidden-field scans introduced in M10-D1 and extended in
  E2–E4 must continue to reject every money-valued field name listed in
  Sections 3 and 4.

## 6. Source / freshness / manifest rules

Future E2+ milestones must extend the existing manifest/source_manifest
contract (from M10-B/C) to cover player identities and roster memberships.
The following rules apply to any future `player_identities` or
`roster_memberships` `data_categories`:

- `source_manifest.json` must support `"player_identities"` and
  `"roster_memberships"` as valid `data_categories`, alongside the existing
  `"teams"` and `"team_visual_metadata"`.
- Every data file (e.g. `normalized/player_identities.json`,
  `normalized/roster_memberships.json`) must have a `per_file_sources` entry
  that records `source_name`, `source_url`, `source_type`, and `as_of_date`
  for the file.
- Every data file must have a `file_hashes` entry (SHA-256), mirroring the
  M10-D1 hash-verify rule. Byte-level tampering must raise `RealSnapshotHashError`.
- Every data file must carry `limitations` strings in the projected response
  (e.g. not-live, manual-review, no-contract, no-availability).
- Every data file must have a `stale_after_date` field (ISO date) in
  `source_manifest.json`, after which the service must either refuse to serve
  the snapshot or serve it with an elevated staleness warning. The exact
  policy (hard error vs elevated warning) is decided in E2 and must be
  codified in tests; default behaviour must be **safe** (hard error if
  misconfigured).
- All future player/roster data must have `live_eligible: false` enforced at
  the schema level (mirroring M10-D1).
- All future player/roster data must have `manual_review_required: true`
  enforced at the schema level.
- Missing files, schema mismatch, hash mismatch, and cross-reference mismatch
  (e.g. roster entry pointing to a non-existent player_id) must raise
  hard errors (`RealSnapshotNotFoundError` / `RealSnapshotSchemaError` /
  `RealSnapshotHashError` / `RealSnapshotCrossReferenceError`).
- The real_snapshot path must **never** fall back to demo. If a
  player/roster file is corrupt, missing, or fails hash/xref checks, the
  metadata endpoint must return HTTP 500; the frontend panel must render its
  existing error state with Retry and explicit "no fallback to demo" hint.
- Every individual record in `player_identities` and `roster_memberships`
  must carry `source_name`, `source_url`, `source_type`, `as_of_date`,
  `manual_review_required=true`, and `live_eligible=false` at the record
  level, in addition to file-level declarations. This is defence-in-depth: a
  UI can display provenance per record without guessing.
- No record may be marked as coming from an LLM, from a scraped page without
  source_url, or from `source_type="live_feed"`. Live feeds are prohibited
  outright in M10-E.

## 7. Frontend boundary

M10-E does **not** modify the frontend. The `/offseason` UI at the end of
M10-E must be indistinguishable from the M10-D sealed UI.

Concrete invariants:

- No file under `frontend/` is modified in E1–E4 or E-Final-Handoff. (If smoke
  finds a type error caused by a shared-type change, the fix must be a
  minimal defensive update, not a new feature, and must be explicitly called
  out in E-Smoke.)
- No player roster UI is added during M10-E. The existing
  `RealSnapshotTeamSelector` panel stays exactly as sealed at M10-D2: 30-team
  identity + abbreviation badge + safety copy, no player list, no roster.
- The `/offseason` team selector's selected team remains **component-local**
  `useState`. It does not drive any future player/roster panel, does not
  change the session team, and does not get lifted to a context in M10-E.
- The selected team must **not** influence signing / trade / hold /
  natural-language-preview requests. This invariant must continue to be
  verifiable by smoke.
- Any future frontend "player inspector" panel must wait until:
  1. The backend read model exposes a player/roster endpoint (post-M10-E).
  2. Its own design doc (similar to `m10-d2-frontend-team-selector-badge.md`)
     is written and reviewed.
  3. Its own browser smoke doc is written and all safety copy, no-logo,
     no-live, no-contract disclaimers are verified.
- The frontend must never display a contract, salary, cap figure, or
  availability status until a post-M10-F milestone explicitly unlocks that
  surface with matching backend, schema, and governance.

## 8. Agent boundary

The Agent / orchestrator / natural-language-preview stack must remain
isolated from real player/roster metadata throughout M10-E.

Hard rules:

- **Prohibition on decision use.** The Agent must not use real player
  identities or real roster memberships as an input to trade, signing, hold,
  or natural-language-preview recommendations in M10-E.
- **Natural-language-preview** must not read from any future player/roster
  endpoint; it continues to operate on the demo snapshot as sealed in M9/M10-D.
- **LLMs must not make roster judgments.** An LLM must never be prompted with
  real roster data and asked to "suggest a trade" or "who should we sign" in
  M10-E. The only permissible use of an LLM in the vicinity of this data is
  off-line design review (e.g. the GPT-5.5 design gate that produced this
  verdict), which does not touch live endpoints or user flows.
- **Read-only metadata inspector is the long-term ceiling for M10-E.** Even
  after a future frontend player inspector exists, it must be read-only and
  explicitly decoupled from the Agent. The M10-D pattern applies: panel-local
  selection, no mutation, no Agent wiring, explicit safety/non-live/manual-review
  copy.
- **Guardrail tests (mandatory for E-Smoke).** E-Smoke must add tests that
  assert:
  - `agent_orchestrator` does not import the future player/roster reader
    service.
  - `agent_natural_language_preview` does not import the player/roster reader
    service.
  - `/api/snapshots/metadata` remains GET-only and exposes no player/roster
    fields in M10-E (the response shape stays at teams + team_visual_metadata
    until a future milestone explicitly adds a separate, opt-in endpoint).
  - No new POST/PUT/PATCH/DELETE endpoint exists under `/api/snapshots/`.
  - The existing M9 guardrail tests (`test_agent_guardrails.py`,
    `test_agent_orchestrator_api.py`, `test_agent_natural_language_preview_api.py`,
    `test_api_endpoints.py`) all still pass without modification.

## 9. Test strategy

### Tests that must exist by E-Smoke

1. **Schema tests (E2/E3/E4)**
   - Positive: minimal valid payloads for manifest extension, player identity,
     roster membership (synthetic IDs only).
   - Negative: every forbidden field listed in Sections 3 and 4 must raise a
     schema validation error.
   - Enum tests: every allowed `roster_status` value validates; `inactive`,
     `waived`, `traded`, and any exhibit status are rejected in M10-E.
   - Boolean invariants: `live_eligible=false` and `manual_review_required=true`
     are enforced at the schema level for both player and roster records.
2. **Manifest / source_manifest tests (E2)**
   - Missing `per_file_sources` entry → SchemaError.
   - Missing `file_hashes` entry → SchemaError/HashError.
   - Missing `stale_after_date` → SchemaError.
   - Missing `limitations` → SchemaError.
   - Tampered file bytes → HashError.
   - Source record without `source_url` for `source_type` that requires it →
     SchemaError.
3. **No-salary / no-contract / no-cap tests (E3/E4)**
   - Recursive forbidden-field scan (identical pattern to M10-D1 §7) extended
     with the Section 3/4 field lists.
   - Tests that inject a hidden `salary`/`cap_hold`/`guarantee_amount` into a
     fixture and assert HTTP 500 / metadata error.
4. **No-Agent-wiring tests (E-Smoke)**
   - Static-import checks that `agent_orchestrator`,
     `agent_natural_language_preview`, `proposal_builder`, `trade_simulator`,
     and `transaction_rule_engine` do not import the player/roster reader
     module.
   - OpenAPI schema check that `/api/snapshots/metadata` (and any future
     `/api/snapshots/*` endpoint added later) is GET-only.
5. **No-frontend-change tests (E-Smoke)**
   - `npm run typecheck` and `npm run build` must pass with no frontend
     source edits.
   - Optional: a smoke-time grep that `frontend/**` does not contain the
     strings `player_identities` or `roster_memberships` imported from
     non-test paths.
6. **No-fallback-to-demo tests (E2/E3/E4)**
   - If player/roster file is missing, corrupt, hash-mismatched, or
     xref-mismatched, the service must raise a typed error and must not
     serve demo stub data.
   - The existing M10-D1 pattern of using `tmp_path` isolated copies with
     deliberate corruption applies here.
7. **No-mutation-endpoint tests (E-Smoke)**
   - OpenAPI scan that `/api/snapshots/` exposes no POST/PUT/PATCH/DELETE.
   - Explicit 405/404 tests for any non-GET method on future metadata
     endpoints.
8. **M10-D regression (all sub-milestones)**
   - `test_m10d_real_snapshot_metadata_read_model.py` (47 tests).
   - `test_m10_real_snapshot_schema.py` + `test_m10c_team_metadata.py` +
     `test_m10c_team_visual_metadata.py` +
     `test_m10d_real_snapshot_metadata_read_model.py` (252 tests total).
   - M9 guardrail suite.

### M10-E1 (this milestone) test requirement

Because E1 is docs-only, **no pytest run is required**. The only verification
for E1 is:

- `git status --short` is clean before this document is written (baseline).
- After this document is written, `git status --short` shows exactly one
  untracked file: `docs/m10-e-player-roster-data-governance-gate.md`.
- `git diff --stat` shows zero tracked-file changes.
- No backend/frontend/schema/data file has been modified.

## 10. Risk register

| ID | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | Treating a frozen snapshot as live / up-to-date roster data. | **High** | `live_eligible=false` enforced at schema; `freshness_label` remains frozen; `as_of_date` and `data_freshness_warning` mandatory per record and per file; `stale_after_date` hard-fails service after cutoff. |
| R2 | Stale roster (e.g. post-trade) displayed as current. | **High** | Hash + `stale_after_date`; manual review required; free_agent bucket curated conservatively; no "traded" pseudo-status; future gates required before any time-varying status. |
| R3 | Player identity mismatch (wrong player linked to a team, name collisions). | **Medium** | Stable `player_id` namespace; disambiguation `notes` field; cross-reference tests in E4; `unknown_manual_review` status bucket; curator sign-off required. |
| R4 | Contract / salary misinformation leaking into UI or Agent. | **High** | Money-valued fields on the forbidden list for E3/E4; recursive scan; M10-F+ required before any salary surface; Agent/LLM prohibited from inferring cap figures. |
| R5 | Source licensing / scraping risk. | **High** | No scraping in M10-E; `source_type` enum excludes `scraped`; every record requires a named `source_url` the curator has rights to; no runtime fetch; snapshot is curated offline. |
| R6 | Frontend misleading UI (implying "current roster" or "official"). | **Medium** | No frontend change in M10-E; future player inspector requires its own design+smoke doc; mandatory "not live / non-official / manual review" copy; no logos, no headshots. |
| R7 | Agent using metadata as decision input ("sign this player because he's on this team"). | **High** | Static-import guardrail tests; no Agent wiring; LLM prompts must not include real roster in M10-E; panel-local selection only. |
| R8 | Fallback-to-demo risk on real snapshot error, hiding corruption. | **Medium** | Hard-error semantics from M10-D1 extended to player/roster files; frontend error state must never substitute demo teams for real roster data; explicit no-fallback tests. |
| R9 | Schema drift (E2/E3/E4 shipped but service/loader not enforcing the new rules). | **Medium** | E-Smoke requires schema tests to run in CI-like fashion; reader-service wiring happens only after schema is sealed and only in a post-E milestone with its own gate. |
| R10 | Privacy / sensitive-data leak (birthdate, contact, social, medical). | **Medium** | Birthdate is optional and PII-light; social/contact/medical fields on the forbidden list; recursive scan; future privacy review required before adding any new optional PII field. |

## 11. Final conclusion

- **M10-E1 is a governance gate, not a data or code implementation.** It does
  not introduce player identities, roster memberships, contracts, salaries,
  cap sheets, or any frontend/Agent change.
- **M10-E1 does not introduce any real player, roster, contract, salary, or
  cap-sheet data** into `data/snapshots/`.
- **No schema file is modified in E1.** E2 is the earliest milestone where
  manifest/source_manifest schema may be extended, and E3/E4 are the earliest
  milestones where player/roster schemas may be defined — in all cases using
  synthetic tmp_path fixtures only.
- **No player/roster schema is drafted in E1.** Field allow/deny lists in
  Sections 3 and 4 are governance constraints, not JSON Schema files.
- **Contracts / salaries / cap sheets are deferred to M10-F or later**, behind
  their own governance gate; M10-E must not contain any money-valued field
  anywhere in schema, fixtures, or tests beyond negative assertions that
  reject them.
- After ChatGPT accepts this governance document, the reviewer may commit it
  and apply tag **`m10e1-player-roster-governance-gate`**.
- Work on M10-E2 (Source/Freshness/Lineage Schema Patch) must not start until
  E1 is accepted and tagged. M10-E3 and M10-E4 must not start until E2 is
  sealed. M10-E does not end until E-Smoke passes and E-Final-Handoff is
  accepted, at which point M10-F governance (contracts/salaries) may be
  opened.
