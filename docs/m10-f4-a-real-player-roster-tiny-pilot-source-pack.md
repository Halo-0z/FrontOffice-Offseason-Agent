# M10-F4-A: Real Player/Roster Tiny Pilot — Source Pack

Run date: 2026-06-28.
Baseline: commit `57b2bce`, tag `m10f3-source-pack-approval-gate`, clean working tree.

This is the **source-pack sub-gate** for M10-F4. F4-A is docs-only / source-pack-only:
it records the planned tiny-pilot scope, candidate records, source citations,
hash plan, and approval checklist that F4-B (real data implementation) must
satisfy before any real `player_identities.json` or `roster_memberships.json`
byte is written to disk.

## 1. F4-A verdict

- **M10-F4-A verdict: CONDITIONAL GO for the source pack framework,
  HOLD_FOR_SOURCE_VERIFICATION for landing.**
- The source-pack framework, candidate selection methodology, field mapping,
  hash plan, allowed/forbidden file list, test plan, reviewer checklist, and
  risk register defined in this document are approved for use in F4-B.
- **HOLD_FOR_SOURCE_VERIFICATION on the actual candidate player records.**
  This document does not finalize specific player names, NBA.com / team-site /
  reference-site URLs, access dates, or current roster statuses because those
  facts cannot be independently verified from within this authoring
  environment without live public-web access at review time. The curator
  performing F4-B must fill in the `TBD — curator to verify` cells in §5 and
  §6 by manually visiting the cited public pages, must double-source every
  record, and must re-confirm roster status on the access date before F4-B
  lands.
- **F4-A does not write real JSON.** No `player_identities.json`, no
  `roster_memberships.json`, no `source_manifest.json` edits, and no
  `manifest.json` edits are performed as part of F4-A.
- **F4-A does not authorize F4-B.** F4-B remains HOLD until (a) every
  `TBD — curator to verify` cell in §5/§6 is filled, (b) double-source
  cross-check is documented for every record, (c) the reviewer checklist in
  §15 is signed off, and (d) a fresh ChatGPT review is opened specifically
  for F4-B.
- **F4-A is not live data.** Any planned records in §5/§6 represent a frozen
  historical/as-of offseason snapshot, not a live/current roster.

## 2. Why F4-A exists

F3 (source pack + tiny pilot approval gate) defined the rules that any future
tiny pilot must obey. F4-A translates those rules into a concrete, record-level
source pack that a human curator can execute against public web pages.

The split (F4-A source pack → F4-B implementation) exists for three reasons:

1. **Source verification must happen before bytes land.** Reviewers must be
   able to inspect URLs, access dates, conflict notes, and source-type choices
   before any real data is committed, so that a flawed source plan is rejected
   on paper rather than corrected after the fact.
2. **Schema compatibility must be resolved up front.** There is a known enum
   mismatch between record-level `source_type` (E3/E4 schema: 5 values) and
   source_manifest per-file `source_type` (E2 schema: 4 values). F4-A resolves
   this on paper so F4-B does not introduce a schema violation.
3. **Scope discipline must be enforceable at the record level.** The "≤2 teams,
   ≤5 players, identity+roster-only" ceiling is easy to state in the abstract;
   F4-A forces an explicit row-by-row table so reviewers can confirm the pilot
   does not silently grow beyond the approved ceiling.

## 3. Tiny pilot candidate scope

F4-B (when it is later approved) is bounded by the following scope ceiling.
F4-B must not exceed it.

### 3.1 Maximum scope

- **At most 2 teams** selected from `normalized/teams.json` (already sealed).
- **At most 4 player identity records** total across those two teams (2 per team
  preferred; 5 absolute maximum per F3; we recommend 4 for the initial pilot
  to keep review tight).
- **Exactly 4 roster membership records** (one per player; every pilot player
  must be linked to exactly one pilot team).
- **Identity fields + roster linkage only.** Only the fields permitted by
  `schema/player_identities_schema.json` (M10-E3) and
  `schema/roster_memberships_schema.json` (M10-E4).

### 3.2 Roster status restriction for first pilot

- Initial F4-B pilot records must use only:
  - `standard` — standard NBA contract (preferred default)
  - `two_way` — two-way contract (acceptable if both sources agree)
- Initial F4-B pilot must **not** use:
  - `free_agent` — even though schema-permitted, it introduces ambiguity about
    team linkage and is deferred to a later pilot.
  - `training_camp` / `unsigned_draft_rights` — carry additional
    caveats; deferred.
  - `unknown_manual_review` — placeholder status; no landed record may use it.
- No `manual_review` placeholder records may be landed in F4-B.

### 3.3 Out of scope (still forbidden in F4-B)

- No full-league roster; no 30-team roster.
- No salary / contract / cap data (`salary`, `cap_hold`, `guarantee`,
  `contracts`, `cap_sheet(s)`, `luxury_tax`, etc.).
- No injury / medical data (`injury_status`, `medical`, `health`, `day_to_day`,
  `questionable`, `probable`, `out`, etc.).
- No rumors / scouting opinions / grades / ratings / trade value.
- No live / current / latest semantics (`live_status`, `current_roster`,
  `latest_roster`, `active_now`, `real_time_*`).
- No depth chart / minutes / role projection (`depth_chart`, `starter`,
  `bench_role`, `rotation_role`, `minutes_projection`, `role_projection`).
- No trade eligibility / restrictions (`trade_eligibility`,
  `trade_restriction`, `no_trade_clause`).
- No PII / representation / media (`social_media`, `agent`,
  `agent_representation`, `personal_sensitive_info`, `headshot`,
  `headshot_url`, `player_image`, `photo_url`, `official_headshot`,
  `logo_*`, `*_logo`, `mascot_image`).
- No execution / mutation verbs (`execute`, `apply`, `commit`, `mutate`,
  `write`, `persist`, `save`, `delete`, `update`, `submit`, `auto_*`).
- No frontend wiring, no Agent wiring, no NL-preview wiring, no trade/signing
  wiring, no new HTTP endpoint.

## 4. Candidate teams and players table

### 4.1 Team selection methodology (curator guidance)

Since this authoring environment cannot independently verify live roster
composition or transaction status in June 2026, the curator must choose two
teams from `normalized/teams.json` using the following criteria:

1. **Public roster page exists and is accessible** without login / paywall on
   both NBA.com (league public reference) and the team's official site
   (team public reference), and at least one of: Basketball Reference,
   ESPN public rosters, or Spotrac public pages (public reference).
2. **No known ambiguous roster status** in the week prior to `access_date`.
   Avoid teams with major trades, signings, waivers, or buyouts in the last
   7 days.
3. **Pilot players are standard-contract or two-way** and have been listed on
   the team's public roster continuously for at least 30 days before
   `as_of_date`.
4. **Conferences / divisions do not matter** for the pilot; pick any two teams
   whose public sources are easy to verify.
5. **Do not pick teams whose most recent public-roster publication is older
   than 14 days** relative to `as_of_date` (risk of stale data).

### 4.2 Candidate team slots (to be filled by curator)

The curator must select exactly 2 teams and record their team_ids (from
sealed `teams.json`) in the table below before F4-B can proceed. The slots
below are intentionally `TBD`; F4-A does not finalize them.

| Slot | team_id (nba-XXX) | City | Name | Conference | Rationale |
|---|---|---|---|---|---|
| Team A | `TBD — curator to verify` | TBD | TBD | TBD | Stable roster; all three public sources reachable; no recent major transactions |
| Team B | `TBD — curator to verify` | TBD | TBD | TBD | Same criteria; must be a different team from Team A |

### 4.3 Candidate player slots (to be filled by curator)

For each of the 2 teams, the curator must select exactly 2 players (4 total),
using the following selection criteria:

1. Listed on the team's NBA.com public roster page **and** the team's official
   roster page **and** a public-reference roster page (Basketball Reference /
   ESPN / Spotrac) at access time.
2. `roster_status` is `standard` or `two_way` on all sources.
3. No player who has been traded, signed, waived, bought out, or suspended in
   the 30 days prior to `access_date` as far as the three sources agree.
4. No two-way / Exhibit-10 / training-camp ambiguity that causes the sources
   to disagree on status; any disagreement → move to a different player.
5. Names (display / first / last) are consistent across sources.
6. Position is one of `PG`, `SG`, `SF`, `PF`, `C`, `G`, `F`, `FC`, `GF`
   (E3 enum); resolve any cross-source position disagreements per §9.

| Slot | team_id | planned_player_id | display_name | first_name | last_name | position | roster_status | Rationale |
|---|---|---|---|---|---|---|---|---|
| Player A1 | Team A team_id | `TBD — curator to verify` | TBD | TBD | TBD | TBD | standard (preferred) or two_way | Listed consistently on all three sources; no recent transaction |
| Player A2 | Team A team_id | `TBD — curator to verify` | TBD | TBD | TBD | TBD | standard (preferred) or two_way | Same criteria; distinct from A1 |
| Player B1 | Team B team_id | `TBD — curator to verify` | TBD | TBD | TBD | TBD | standard (preferred) or two_way | Same criteria for Team B |
| Player B2 | Team B team_id | `TBD — curator to verify` | TBD | TBD | TBD | TBD | standard (preferred) or two_way | Same criteria; distinct from B1 |

**player_id naming rule** (from F1 §5.3): pattern `^[a-z][a-z0-9_-]*$`; use a
namespaced slug derived from the player's common public name (Basketball
Reference slug recommended); add a disambiguation suffix on collision. No id
may be remapped after landing; any id change requires a new snapshot version.

## 5. Planned player identity records table

The curator must complete one row per pilot player (4 rows). All fields are
recorded per F3 §3 source-pack requirements and match E3 schema required
fields. Fields marked `null/deferred` are optional and may be set to `null`
if the curator cannot verify them against two sources; the F4-B record
must use JSON `null` (not empty string) for any deferred optional field.

| Field | Player A1 | Player A2 | Player B1 | Player B2 |
|---|---|---|---|---|
| planned_player_id | TBD — curator to verify | TBD — curator to verify | TBD — curator to verify | TBD — curator to verify |
| display_name | TBD — curator to verify | TBD — curator to verify | TBD — curator to verify | TBD — curator to verify |
| first_name | TBD — curator to verify | TBD — curator to verify | TBD — curator to verify | TBD — curator to verify |
| last_name | TBD — curator to verify | TBD — curator to verify | TBD — curator to verify | TBD — curator to verify |
| position (E3 enum) | TBD — curator to verify | TBD — curator to verify | TBD — curator to verify | TBD — curator to verify |
| birthdate (YYYY-MM-DD or null) | Recommended null/deferred for F4-B unless two sources agree exactly | null/deferred (recommended) | null/deferred (recommended) | null/deferred (recommended) |
| height (display string or null) | null/deferred (recommended; add only if two sources agree) | null/deferred | null/deferred | null/deferred |
| weight (display string or null) | null/deferred (recommended; add only if two sources agree) | null/deferred | null/deferred | null/deferred |
| source_name (record-level) | TBD — e.g. "NBA.com [Team A] Roster" primary; name the actual page | TBD | TBD | TBD |
| source_url (record-level, non-null) | TBD — curator to verify; must be specific public page, not home page | TBD | TBD | TBD |
| source_type (record-level, E3 5-enum) | TBD (`league_public_reference` / `team_public_reference` / `public_reference` / `manual_curated`) | TBD | TBD | TBD |
| access_date (YYYY-MM-DD) | TBD — curator to verify (date curator visited the URL) | TBD | TBD | TBD |
| as_of_date (YYYY-MM-DD) | Same as snapshot as_of_date (see §7) | same | same | same |
| manual_review_required | `true` (const) | `true` | `true` | `true` |
| live_eligible | `false` (const) | `false` | `false` | `false` |
| data_freshness_warning (per-record) | TBD — e.g. "Frozen identity-only offseason pilot snapshot; not a live roster." | same | same | same |
| limitations[] (per-record, ≥1) | TBD — at least: ["identity_only","not_live","no_contract","as_of_snapshot_only"] | same | same | same |
| notes[] (optional) | TBD or empty | TBD or empty | TBD or empty | TBD or empty |
| snapshot_id | `nba_real_2026_preoffseason_v1` (const) | same | same | same |
| curator | TBD — curator name | same | same | same |
| reviewer | TBD — reviewer name (different from curator) | same | same | same |
| review_status | Must be `approved` before F4-B landing | same | same | same |
| conflict_notes | TBD — "no conflicts observed" or describe + resolution | TBD | TBD | TBD |
| manual_review_notes | TBD or empty | TBD or empty | TBD or empty | TBD or empty |

### 5.1 Optional field policy for F4-B

Birthdate, height, and weight are explicitly deferred / `null` recommended for
F4-B. The purpose of the initial pilot is to validate schema, hashes,
cross-references, and lineage plumbing — not to maximize field coverage.
Populating optional identity fields is deferred to a later F-series milestone.

## 6. Planned roster membership records table

The curator must complete one row per pilot player (4 rows, one per player).
Every membership links exactly one player to one team; no player may be
linked to two teams in F4-B.

| Field | Membership A1 | Membership A2 | Membership B1 | Membership B2 |
|---|---|---|---|---|
| planned_membership_id (optional, pattern `^[a-z][a-z0-9_-]*$`) | TBD or null for F4-B (optional field) | TBD or null | TBD or null | TBD or null |
| planned_player_id | Must match Player A1 `planned_player_id` exactly | Player A2 | Player B1 | Player B2 |
| team_id (pattern `^nba-[A-Z]{3}$`) | Team A team_id | Team A team_id | Team B team_id | Team B team_id |
| roster_status (E4 6-enum; F4-B restricted) | `standard` preferred; `two_way` acceptable if dual-sourced | same | same | same |
| source_name (record-level) | TBD — typically same as identity record's primary source | TBD | TBD | TBD |
| source_url (record-level, non-null) | TBD — specific public roster page | TBD | TBD | TBD |
| source_type (record-level, E4 5-enum) | TBD | TBD | TBD | TBD |
| access_date (YYYY-MM-DD) | Same as identity record access_date | same | same | same |
| as_of_date (YYYY-MM-DD) | Same as snapshot as_of_date | same | same | same |
| manual_review_required | `true` (const) | `true` | `true` | `true` |
| live_eligible | `false` (const) | `false` | `false` | `false` |
| data_freshness_warning (per-record) | TBD — e.g. "Frozen roster membership snapshot; not a live roster; offseason pilot." | same | same | same |
| limitations[] (per-record, ≥1) | TBD — at least: ["membership_only","not_live","no_contract","as_of_snapshot_only"] | same | same | same |
| notes[] (optional) | TBD or empty | TBD or empty | TBD or empty | TBD or empty |
| snapshot_id | `nba_real_2026_preoffseason_v1` (const) | same | same | same |
| curator | same as §5 | same | same | same |
| reviewer | same as §5 | same | same | same |
| review_status | `approved` required before landing | same | same | same |
| conflict_notes | TBD | TBD | TBD | TBD |
| manual_review_notes | TBD or empty | TBD or empty | TBD or empty | TBD or empty |

## 7. Source pack table (file-level)

Applies to both `normalized/player_identities.json` and
`normalized/roster_memberships.json` as well as to the existing files they
sit alongside.

| Field | player_identities.json | roster_memberships.json |
|---|---|---|
| snapshot_id | `nba_real_2026_preoffseason_v1` | `nba_real_2026_preoffseason_v1` |
| schema_version | TBD — propose `m10-f4-pilot-v1` (curator confirm) | same pattern |
| as_of_date (file-level) | TBD — curator to set, e.g. 2026-07-XX | same |
| generated_at (ISO-8601) | TBD — F4-B landing timestamp | same |
| source_name (file-level) | TBD — e.g. "Manual curation from NBA.com + team public roster pages" | TBD |
| source_url (file-level) | `null` (file-level; per-record URLs carry the citations) | `null` |
| source_type (file-level, E3 5-enum) | `manual_curated` (recommended; see §10 for manifest enum compatibility) | `manual_curated` (recommended) |
| stale_after_date (top-level source_manifest) | TBD — recommend `as_of_date + 14 days` (offseason, but post-FA moves require tighter window) | n/a (top-level) |
| manual_review_required | `true` (const) | `true` |
| live_eligible | `false` (const) | `false` |
| data_freshness_warning (file-level) | TBD — e.g. "Frozen as-of pilot snapshot; not a live roster; offseason only; ≤4 players." | TBD |
| limitations[] (file-level, ≥1) | TBD — must include identity-only, not-live, no-contract, as-of, no-frontend, no-Agent, no-trade-signing, pilot-scope (≤4 players) | TBD — must include membership-only, not-live, no-contract, etc. |

## 8. Field mapping table

Maps pilot fields to the E3/E4 schema requirements. F4-B JSON must use these
exact JSON keys (no renaming, no synonyms).

| JSON key | File | Required? | Schema / type | Notes |
|---|---|---|---|---|
| `schema_version` | both | required | string, minLength 1 | e.g. `m10-f4-pilot-v1` |
| `snapshot_id` | both, all records | required (const) | string, pattern `^[a-z0-9_-]+$` | Must equal `nba_real_2026_preoffseason_v1` |
| `as_of_date` | both, all records | required | string YYYY-MM-DD | Must match across all files/records |
| `generated_at` | both | optional | ISO-8601 string | Set at F4-B landing time |
| `source_name` | both, all records | required | string, minLength 1 | Non-empty; per-record cites the specific page |
| `source_url` | both, all records | required for non-manual_review | string or null | Must be non-null for F4-B (no manual_review placeholders in pilot) |
| `source_type` | both, all records | required (E3/E4 5-enum) | `manual_curated` / `public_reference` / `league_public_reference` / `team_public_reference` / `manual_review` | Record-level; see §10 for per-file enum compatibility |
| `manual_review_required` | both, all records | required (const true) | boolean = true | Enforced by schema `const: true` |
| `live_eligible` | both, all records | required (const false) | boolean = false | Enforced by schema `const: false` |
| `data_freshness_warning` | both, all records | required | string, minLength 1 | UI-mandated warning |
| `limitations` | both, all records | required (minItems 1) | array of strings (minLength 1 each) | Caveats; must not be empty |
| `players` | player_identities | required | array of player objects | 4 entries for F4-B |
| `player_id` | per player | required | pattern `^[a-z][a-z0-9_-]*$` | Stable slug; unique across file |
| `display_name` | per player | required | string, minLength 1 | e.g. "J. Doe" |
| `first_name` | per player | required | string, minLength 1 | |
| `last_name` | per player | required | string, minLength 1 | |
| `birthdate` | per player | optional | string YYYY-MM-DD or null | Recommended null for F4-B |
| `height` | per player | optional | string (minLength 1) or null | Display string; recommended null for F4-B |
| `weight` | per player | optional | string (minLength 1) or null | Display string; recommended null for F4-B |
| `position` | per player | required | E3 9-enum | PG/SG/SF/PF/C/G/F/FC/GF |
| `notes` | per player, per membership | optional | array of strings | Curator caveats only; no rumors/medical/scouting |
| `roster_memberships` | roster_memberships | required | array of membership objects | 4 entries for F4-B |
| `membership_id` | per membership | optional | pattern `^[a-z][a-z0-9_-]*$` | May be omitted (JSON key absent) or set; no runtime UUIDs |
| `team_id` | per membership | required | pattern `^nba-[A-Z]{3}$` | Must resolve to sealed teams.json |
| `player_id` | per membership | required | pattern `^[a-z][a-z0-9_-]*$` | Must resolve to player_identities entry |
| `roster_status` | per membership | required | E4 6-enum | F4-B restricted to `standard`/`two_way` |

## 9. Source conflict policy

When the three required sources (league_public_reference NBA.com team roster,
team_public_reference team official roster, public_reference Basketball
Reference / ESPN / Spotrac) disagree, F4-B must follow this resolution order:

1. **Hard disagreement on roster_status (e.g., one source says `standard` and
   another implies waived/traded) → drop the player from the pilot.** Do not
   guess; pick a different, unambiguous player. This is the preferred
   resolution because the pilot has only 4 slots and there are hundreds of
   unambiguous NBA players on standard contracts to choose from.
2. **Disagreement on optional fields (height/weight/birthdate) → set that
   field to `null`** for F4-B and note the conflict in `conflict_notes`. Do
   not pick one source's value over another without documenting why.
3. **Disagreement on position** → use the league_public_reference (NBA.com)
   value if it is within the E3 9-enum; otherwise fall back to
   public_reference. Document in `conflict_notes`. If NBA.com lists multiple
   positions, prefer the primary listed position (first on page).
4. **Disagreement on name spelling** → use the league_public_reference
   (NBA.com) spelling. If diacritics are involved, preserve them in
   `first_name`/`last_name` but use the common ASCII display form for
   `display_name` if that's how NBA.com renders it. Document in notes.
5. **Any disagreement not resolvable by rules 1–4** → drop the player from
   the pilot and pick another.

Conflict resolutions must be recorded per record in `conflict_notes` before
F4-B lands. No silent resolution is permitted.

## 10. Source manifest compatibility plan

There is a known schema enum mismatch between record-level `source_type`
(E3/E4) and file-level `per_file_sources[*].source_type` (E2). The curator
must handle this explicitly in F4-B.

### 10.1 The mismatch

- **Record-level (players[].source_type, roster_memberships[].source_type)** —
  E3/E4 schemas allow 5 values:
  `manual_curated`, `public_reference`, `league_public_reference`,
  `team_public_reference`, `manual_review`.
- **File-level (source_manifest.per_file_sources[rel].source_type)** —
  E2 `schema/source_manifest_schema.json` allows only 4 values:
  `manual_curated`, `public_reference`, `league_roster`,
  `manual_non_official_ui`.

The two enums share only `manual_curated` and `public_reference`.
`league_public_reference` and `team_public_reference` (record-level) do not
exist in the E2 per-file enum. `league_roster` (E2 per-file) does not exist in
E3/E4. `manual_non_official_ui` (E2 per-file) is intended for visual-metadata
files (palette / non-official UI assets), not for player/roster.

### 10.2 Resolution for F4-B (no schema changes)

F4-B will **not** modify the schema. Therefore:

- **Record-level source_type** uses the full E3/E4 5-enum. Pilot players'
  per-record source_type should be set to reflect the actual citation of that
  record (typically `league_public_reference` when citing NBA.com,
  `team_public_reference` when citing the team site, `public_reference` when
  citing Basketball Reference / ESPN / Spotrac, or `manual_curated` when the
  record was cross-checked across multiple sources).
- **source_manifest.data_categories** must be extended with exactly
  `"player_identities"` and `"roster_memberships"`; must NOT include
  `contracts`, `salaries`, `cap_sheets`, `injuries`, `rumors`, `live_status`,
  `scouting`, or any other category.
- **source_manifest.per_file_sources** entries for
  `normalized/player_identities.json` and `normalized/roster_memberships.json`
  must set `source_type` to **`manual_curated`** (recommended; reflects that
  the file as a whole is a cross-checked manual curation across multiple
  public sources) or `public_reference`; must NOT set it to
  `league_public_reference` or `team_public_reference` (those values fail
  the E2 enum).
- **source_manifest.per_file_sources** entries must include:
  - `source_name` (non-empty string)
  - `source_url` (non-null; cite the primary league public roster page)
  - `source_type` (`manual_curated` recommended — schema-compatible)
  - `as_of_date`
  - `manual_review_required: true`
  - `live_eligible: false`
  - `data_freshness_warning` (non-empty)
  - `limitations[]` (non-empty)
- **source_manifest.file_hashes** must be SHA-256 (see §11).
- **Do not land any `manual_review` placeholder records** in F4-B. All four
  player records and four membership records must be fully sourced and
  reviewed. `manual_review` is for curation time only and must not reach disk.

### 10.3 Future schema alignment (deferred past F4-B)

Aligning the two enums (e.g., adding `league_public_reference` and
`team_public_reference` to E2's per-file source_type) is deferred to a later
governance milestone (post-M10-F). F4-B does not require this change.

## 11. Hash plan

F4-B must compute and record SHA-256 hashes for the two new normalized files
and populate `source_manifest.file_hashes` in `sha256:<lowercase_hex>` format.

### 11.1 Commands (PowerShell, to be run after F4-B JSON is final but before commit)

```powershell
# After player_identities.json is finalized
Get-FileHash data/snapshots/nba_real_2026_preoffseason_v1/normalized/player_identities.json -Algorithm SHA256

# After roster_memberships.json is finalized
Get-FileHash data/snapshots/nba_real_2026_preoffseason_v1/normalized/roster_memberships.json -Algorithm SHA256
```

Record the hex hash from each command's `Hash` column, lowercased, and prefix
with `sha256:` when inserting into `source_manifest.file_hashes`, for example:

```json
"file_hashes": {
  "normalized/teams.json": "sha256:<existing_hash_unchanged>",
  "normalized/team_visual_metadata.json": "sha256:<existing_hash_unchanged>",
  "normalized/player_identities.json": "sha256:<lowercase_hex_from_Get-FileHash>",
  "normalized/roster_memberships.json": "sha256:<lowercase_hex_from_Get-FileHash>"
}
```

### 11.2 Mandatory hash rules

- Hashes are computed against the **exact bytes** that will be committed
  (UTF-8, no trailing whitespace, final newline as written by the curator's
  editor; be consistent).
- Any post-write edit to either file requires recomputing both hashes.
- F2's `player_roster_metadata_reader` raises `PlayerRosterHashError` on
  mismatch; this is the desired behavior and F4-B tests must verify it.
- Hashes for existing files (`teams.json`, `team_visual_metadata.json`) must
  NOT change in F4-B; any change indicates accidental modification of sealed
  files and must block landing.
- `stale_after_date` (top-level source_manifest) recommended window:
  `as_of_date + 14 days` for the July offseason / free-agency period.
- `live_eligible=false`, `manual_review_required=true` at top level.
- No fallback to demo data on hash mismatch or any other hard error.

## 12. F4-B allowed files

If (and only if) F4-A is accepted and F4-B passes its own review, F4-B is
permitted to modify exactly the following files. F4-B must not touch any
file outside this list.

Permitted in F4-B:

- `data/snapshots/nba_real_2026_preoffseason_v1/normalized/player_identities.json` — new file
- `data/snapshots/nba_real_2026_preoffseason_v1/normalized/roster_memberships.json` — new file
- `data/snapshots/nba_real_2026_preoffseason_v1/source_manifest.json` — update to add `data_categories`, `per_file_sources`, `file_hashes` per §10/§11
- `data/snapshots/nba_real_2026_preoffseason_v1/manifest.json` — minor update only if needed to reflect new normalized files, and only if it continues to validate against `schema/real_snapshot_manifest_schema.json`
- `docs/m10-f4-real-player-roster-tiny-pilot.md` — F4-B handoff / verification doc (new file)
- `backend/app/tests/test_m10f_player_roster_metadata_read_model.py` — add a tiny-pilot smoke test that loads the pilot bytes via `tmp_path` (never by importing `data/snapshots/...` at module import time) and asserts schema/hash/xref/forbidden-field/no-demo-fallback for the pilot snapshot

## 13. F4-B forbidden files and surface area

Even after F4-B is approved, the following remain forbidden:

- `backend/app/api.py` — no new endpoint (GET or otherwise); endpoint deferred
- `frontend/**` — no UI wiring
- `schema/**` — no schema changes (the §10.1 enum mismatch is worked around
  per §10.2, not fixed in F4-B)
- `backend/app/services/**` except the existing
  `player_roster_metadata_reader.py` for a strictly-bug-fix change
  justified in F4-B review; no new services, no refactors, no behavior changes
- `backend/app/snapshot_loader.py` — no changes
- `backend/app/services/orchestrator*` — no changes
- Agent-related code
- Natural-language-preview code
- Trade logic
- Signing logic
- `backend/app/models/**`
- Contracts / salaries / cap sheets (any filename)
- Injury / medical data files
- Rumors / scouting opinions files
- Live API / runtime fetch / scraping code
- LLM-as-fact generation
- POST/PUT/PATCH/DELETE endpoints
- `execute/apply/commit/mutate/write/persist/save/delete/update/submit/auto_*`
  endpoints
- Operations on `D:\DraftMind`

## 14. F4-B required tests

F4-B must run and report all of the following, all green:

### 14.1 F2 read model suite

```powershell
D:\anaconda\python.exe -m pytest backend/app/tests/test_m10f_player_roster_metadata_read_model.py -q
```

Expected at F4-B time: ≥82 tests (80 F2 tests + 2 new tiny-pilot smoke tests).

### 14.2 M10-E schema + F2 read model regression

```powershell
D:\anaconda\python.exe -m pytest `
  backend/app/tests/test_m10e_source_lineage_schema.py `
  backend/app/tests/test_m10e_player_identity_schema.py `
  backend/app/tests/test_m10e_roster_membership_schema.py `
  backend/app/tests/test_m10f_player_roster_metadata_read_model.py `
  -q
```

### 14.3 Full M10 metadata regression

```powershell
D:\anaconda\python.exe -m pytest `
  backend/app/tests/test_m10_real_snapshot_schema.py `
  backend/app/tests/test_m10c_team_metadata.py `
  backend/app/tests/test_m10c_team_visual_metadata.py `
  backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py `
  backend/app/tests/test_m10e_source_lineage_schema.py `
  backend/app/tests/test_m10e_player_identity_schema.py `
  backend/app/tests/test_m10e_roster_membership_schema.py `
  backend/app/tests/test_m10f_player_roster_metadata_read_model.py `
  -q
```

Expected baseline (from F2 seal): ≥812 tests; F4-B will add 2+ tests so the
final count must be ≥814 and all green.

### 14.4 F4-B-specific checks (must be added in the F4-B test file extension)

- **Hash validation**: load pilot bytes via tmp_path; assert SHA-256 matches
  `source_manifest.file_hashes` for both new files; tamper one byte and assert
  `PlayerRosterHashError`.
- **player_id xref**: every `roster_memberships[].player_id` resolves to
  exactly one player identity; no duplicate player_ids.
- **team_id xref**: every `roster_memberships[].team_id` resolves to exactly
  one sealed team; both team_ids are in the 2-team pilot scope.
- **Forbidden fields scan**: recursive scan over pilot bytes for every
  salary/contract/cap/injury/medical/rumor/scouting/live/depth/trade-eligibility/
  PII/media/mutation/logo key on the E3/E4 blacklist; assert zero hits.
- **Forbidden files scan**: assert `data/snapshots/nba_real_2026_preoffseason_v1/`
  contains no `contracts*.json`, `salaries*.json`, `cap_sheet*.json`,
  `injuries*.json`, `rumors*.json`, `scouting*.json` after F4-B lands.
- **No demo fallback**: for the pilot snapshot, assert missing/corrupt files
  raise typed errors (not stub/demo data).
- **Static isolation**: assert no import of `player_roster_metadata_reader`
  from Agent, NL-preview, trade, signing, frontend paths; assert no new
  POST/PUT/PATCH/DELETE route references player-roster.
- **No contracts/salaries/cap files**: explicit file-system scan as above.
- **Schema validation**: player_identities.json validates against E3;
  roster_memberships.json validates against E4; updated source_manifest
  validates against E2; updated manifest (if touched) validates against
  `real_snapshot_manifest_schema.json`.

## 15. Reviewer checklist

F4-B must not land until every item is checked off by a reviewer who is not
the curator. All items are hard requirements; "N/A" is acceptable only where
explicitly marked.

### 15.1 Source pack completeness

- [ ] §5 has 4 player rows, no `TBD` cells remain (except optional fields
      explicitly set to `null` per §5.1).
- [ ] §6 has 4 membership rows, no `TBD` cells remain.
- [ ] Every record has a non-null `source_url` pointing at a specific public
      page (not a home page / index page).
- [ ] Every `source_url` is reachable without login, without paywall at the
      time of review, and shows the fact being cited.
- [ ] Every record's `source_type` is one of the E3/E4 5-enum values; no
      `manual_review` placeholders are landed.
- [ ] `access_date` is recorded for every record.
- [ ] `as_of_date` matches across all records and file-level metadata.
- [ ] `stale_after_date` is set at the source_manifest top level within the
      recommended 7–14 day window (or an explicit exception is documented).
- [ ] `data_freshness_warning` is non-empty at file and per-record level.
- [ ] `limitations[]` is non-empty at file and per-record level.
- [ ] Curator and reviewer are both named and distinct.
- [ ] `review_status` is `approved` for every record.

### 15.2 Scope ceiling

- [ ] Exactly 2 distinct `team_id`s referenced across all pilot records.
- [ ] Exactly 4 distinct `player_id`s in player_identities.json.
- [ ] Exactly 4 roster membership records.
- [ ] Every `roster_status` is either `standard` or `two_way`.
- [ ] No salary/contract/cap fields anywhere.
- [ ] No injury/medical fields anywhere.
- [ ] No rumor/scouting/live/current/depth/minutes/role/trade-eligibility/PII/
      agent/social/media/mutation/logo fields anywhere (scan keys + note text).

### 15.3 Integrity

- [ ] All `player_id`s match `^[a-z][a-z0-9_-]*$` and are unique.
- [ ] All `team_id`s match `^nba-[A-Z]{3}$` and resolve in `teams.json`.
- [ ] Every membership's `player_id` resolves to exactly one player.
- [ ] Every membership's `team_id` resolves to exactly one sealed team.
- [ ] `snapshot_id` is `nba_real_2026_preoffseason_v1` everywhere.
- [ ] `manual_review_required=true` everywhere (file + records).
- [ ] `live_eligible=false` everywhere (file + records + per-file sources).
- [ ] Per-file source_type in source_manifest uses `manual_curated` or
      `public_reference` (E2-compatible per §10.2), not
      `league_public_reference` or `team_public_reference`.
- [ ] `file_hashes` are computed from final bytes (§11) and validate.
- [ ] Existing file hashes (teams.json, team_visual_metadata.json) are
      unchanged from the F2/F3 baseline.
- [ ] `data_categories` extended with exactly `player_identities` and
      `roster_memberships`; no forbidden categories.
- [ ] Rollback plan documented (revert F4-B commit; re-seal snapshot to
      F3 state).

### 15.4 Test readiness

- [ ] §14.1 / §14.2 / §14.3 all green.
- [ ] §14.4 F4-specific checks added and green.
- [ ] M10 full metadata regression count ≥814 and all green.

### 15.5 Surface-area isolation

- [ ] No changes to `backend/app/api.py`.
- [ ] No changes to `frontend/**`.
- [ ] No changes to `schema/**`.
- [ ] No new or modified backend services (unless a documented F2 bug fix).
- [ ] No Agent / NL-preview / trade / signing wiring.
- [ ] No new HTTP endpoints (any method).

## 16. Risk register

Inherits all risks from F3 §12 and adds F4-A-specific risks below. Mitigations
are F4-B landing controls.

### 16.1 High severity (in addition to F3 high risks)

| Risk | Why F4-A specific | F4-B mitigation |
|---|---|---|
| Curator fills in `TBD` cells without actually verifying URLs | F4-A is a template; humans may rush to fill it | Reviewer must open every URL; §15.1 requires URL reachability at review time; any unverifiable cell → HOLD |
| Per-file `source_type` set to an E2-incompatible value (e.g. `league_public_reference`) at landing | Enum mismatch is easy to miss; schema would reject | §10.2 explicitly mandates `manual_curated` or `public_reference`; F4-B test validates source_manifest against E2 schema |
| Scope creep beyond 2 teams / 4 players during landing | Easy to add "just one more player" while writing JSON | §15.2 scope ceiling is an explicit checklist; F4-B test asserts count bounds |
| Existing sealed file hashes (teams.json / team_visual_metadata.json) drift because of accidental editor whitespace | Editors sometimes trim trailing whitespace or normalize line endings | §11.2 forbids changing existing hashes; F4-B test asserts they match baseline |

### 16.2 Medium severity

| Risk | F4-B mitigation |
|---|---|
| Birthdate/height/weight disputes across sources (if curator decides to populate them) | §5.1 recommends null for F4-B; §9 sets conflict resolution to null on disagreement |
| Stale_after_date set too long, masking post-FA roster churn | §11.2 mandates 7–14 day window in July offseason; reviewer confirms per §15.1 |
| source_url rot (page moves or is taken down between F4-B and future review) | access_date recorded; snapshot frozen-as-of is still valid as a historical record even if URL later moves; future snapshot version handles URL updates |
| player_id collision or naming inconsistency between curator and reviewer | §5/§6 slot table forces planned_player_id review before landing; naming scheme documented (F1 §5.3) |
| Position disagrees across sources | §9 rule 3 resolves to league_public_reference; documented in conflict_notes |

### 16.3 Low severity

| Risk | F4-B mitigation |
|---|---|
| Typo in display name / first_name / last_name | Two-source cross-check + reviewer verification; F4-B schema validation catches missing required keys; typos corrected in future snapshot version, never in-place on sealed snapshot |
| Inconsistent null vs empty-string on optional fields | §8 field mapping specifies `null` (not empty string) for deferred optionals; schema enforces types |
| Notes[] accidentally contain prohibited content (rumors, etc.) | F2 forbidden-key scan recurses into notes values; §14.4 requires the scan in F4-B tests |
| Line-ending / encoding differences between curator OSes causing hash drift | §11.2 requires consistent UTF-8 + final newline; hash computed immediately before commit |

## 17. Final conclusion

- **M10-F4-A is docs-only / source-pack-only.** The only artifact produced by
  this milestone is `docs/m10-f4-a-real-player-roster-tiny-pilot-source-pack.md`
  (this file). No source code, schema, snapshot, or test file is modified by
  F4-A.
- **M10-F4-A does not authorize writing real JSON.** No
  `player_identities.json` or `roster_memberships.json` is created by F4-A;
  no source_manifest or manifest edits are performed by F4-A. The `TBD`
  cells in §5/§6 are placeholders for a human curator to fill from verified
  public sources before F4-B.
- **M10-F4-A verdict: framework approved, landing HOLD_FOR_SOURCE_VERIFICATION.**
  The methodology, field mapping, enum-compatibility plan, hash plan, allowed/
  forbidden file lists, test plan, checklist, and risk register defined here
  are approved for F4-B's use. Specific candidate player records, source URLs,
  access dates, and current roster statuses are not finalized in F4-A and must
  be verified by a human curator with access to public web pages before F4-B.
- **M10-F4-A must be reviewed by ChatGPT before any F4-B work starts.** F4-B
  implementation (real JSON landing) must not begin until this document is
  accepted in review.
- **F4-B remains HOLD until the source pack is fully filled and re-approved.**
  Passing F4-A does not auto-open F4-B. F4-B requires its own fresh ChatGPT
  review with (a) all `TBD` cells in §5/§6 filled, (b) all §15 checklist
  items checked off, (c) F4-B-specific tests written, and (d) a fresh
  full-regression test run.
- **This pilot is a frozen historical/as-of snapshot, not current/live NBA
  data.** Any future consumer must surface `data_freshness_warning`,
  `limitations`, `live_eligible=false`, and `manual_review_required=true`;
  the data must never be represented as current or live.
- **Contracts/salaries/cap sheets remain out of scope** for all of M10-F and
  require a future dedicated governance series.
- **No commit, tag, or push is performed by F4-A.** The working tree
  contains only this one new doc file, ready for review.
