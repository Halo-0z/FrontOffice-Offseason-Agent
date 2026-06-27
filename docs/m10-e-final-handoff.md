# M10-E Final Handoff

This document is the **final handoff** for the M10-E (Player/Roster Data
Governance + Schema) sub-series. It records what M10-E delivered, what it
explicitly did **not** deliver, the guardrails that must remain true going
forward, and the recommended next step.

Run date: 2026-06-28.
Preceding seal: M10-E Smoke Verification at commit `f8cd23f` / tag
`m10e-smoke-verification`.

## 1. Final status

**M10-E is complete and sealed.**

- This handoff is a **docs-only** milestone. It adds a single markdown file
  and does not change code, schemas, tests, data, frontend, backend, API,
  services, loaders, or snapshots.
- Baseline at start of handoff:
  - HEAD: `f8cd23f Add M10-E smoke verification`
  - Tag: `m10e-smoke-verification`
  - `git status --short`: clean (empty)
- M10-E delivered **governance rules + source/freshness/lineage envelope +
  player identity schema + roster membership schema + tests + smoke
  verification**. It did **not** deliver real player data, real roster data,
  contracts/salaries/cap sheets, a backend read model for player/roster, a
  frontend player/roster UI, or any Agent/NL-preview/trade/signing wiring.

## 2. Milestone summary

### M10-E1 — Player/Roster Data Governance Gate

- Commit: `22ca2a5`
- Tag: `m10e1-player-roster-governance-gate`
- Files:
  - `docs/m10-e-player-roster-data-governance-gate.md`
- What it delivered: a docs-only governance gate that established the
  ordering, scope boundaries, and hard prohibitions for the rest of M10-E.
- Key decisions locked:
  - M10-E cannot directly write real player data or real roster data.
  - Contracts / salaries / cap sheets are deferred to M10-F or later.
  - No NBA API, no scraping, no LLM-generated data.
  - Agent / natural-language-preview cannot use real player/roster metadata
    for trade or signing decisions.
- Validation: docs-only; governance rules validated by all subsequent E2-E4
  schema tests that enforce the named prohibitions.

### M10-E2 — Source / Freshness / Lineage Schema Patch

- Commit: `ff09f5f`
- Tag: `m10e2-source-freshness-lineage-schema`
- Files:
  - `schema/source_manifest_schema.json` (patched)
  - `backend/app/tests/test_m10e_source_lineage_schema.py`
  - `docs/m10-e2-source-freshness-lineage-schema-patch.md`
- What it delivered:
  - Added `player_identities` and `roster_memberships` to the
    `data_categories` enum.
  - Removed `contracts` and `cap_sheets` from the `data_categories` enum
    (deferred to M10-F+).
  - Extended `per_file_sources` entries with optional `source_type`,
    `manual_review_required`, `live_eligible` (const false),
    `data_freshness_warning`, and `limitations`.
  - Added constrained `source_type` enum (manual_curated / public_reference
    / league_public_reference / team_public_reference / manual_non_official_ui
    in E2; aligned to manual_review wording in E3/E4) that rejects
    `llm_generated` / `scraped_unreviewed`.
  - Extended the top-level `propertyNames` blacklist to cover
    salaries/injuries/rumors/live_status/latest_roster (defence in depth).
- Test result: **58 passed**.

### M10-E3 — Player Identity Schema

- Commit: `26883e4`
- Tag: `m10e3-player-identity-schema`
- Files:
  - `schema/player_identities_schema.json`
  - `backend/app/tests/test_m10e_player_identity_schema.py`
  - `docs/m10-e3-player-identity-schema.md`
- What it delivered:
  - New JSON Schema for future `normalized/player_identities.json` with
    strict `additionalProperties: false` at both top level and per-player.
  - Required identity fields: `player_id`, `display_name`, `first_name`,
    `last_name`, `position`, plus full lineage (source_name/source_url/
    source_type/as_of_date/manual_review_required=true/live_eligible=false/
    data_freshness_warning/snapshot_id/limitations).
  - Optional identity fields: `birthdate` (YYYY-MM-DD | null), `height`,
    `weight`, `notes`, `membership_id`-equivalent id (player_id only here).
  - Position enum: PG/SG/SF/PF/C/G/F/FC/GF.
  - Safe source_type enum: manual_curated / public_reference /
    league_public_reference / team_public_reference / manual_review.
  - 56-field propertyNames blacklist covering salary/contract/cap, medical/
    injury, PII/social/agent, rumors/opinion, live/availability/projection,
    mutation verbs, live/current naming, logos/photos.
  - `manual_review_required` const true; `live_eligible` const false.
- Test result: **178 passed**. No real player data added; synthetic fixtures
  only (`Test Player Alpha`, `p-syn-alpha`, …); content-audit test rejects
  real NBA player names appearing in any fixture string.

### M10-E4 — Roster Membership Schema

- Commit: `0b28729`
- Tag: `m10e4-roster-membership-schema`
- Files:
  - `schema/roster_memberships_schema.json`
  - `backend/app/tests/test_m10e_roster_membership_schema.py`
  - `docs/m10-e4-roster-membership-schema.md`
- What it delivered:
  - New JSON Schema for future `normalized/roster_memberships.json` with
    strict `additionalProperties: false` at both top level and
    per-membership.
  - Required membership fields: `team_id` (pattern `^nba-[A-Z]{3}$`,
    matches `teams.json`), `player_id` (pattern `^[a-z][a-z0-9_-]*$`,
    matches E3 player ids), `roster_status`, plus full lineage.
  - Optional membership fields: `membership_id`, `source_url` (string|null),
    `notes`.
  - Deliberately narrow `roster_status` enum (six low-risk values only):
    `standard`, `two_way`, `training_camp`, `unsigned_draft_rights`,
    `free_agent`, `unknown_manual_review`.
  - Forbidden roster statuses (deferred to M10-F+): inactive, waived,
    traded, injured, suspended, questionable, probable, day_to_day,
    available, unavailable, active_now, current, latest — rejected by both
    enum and propertyNames blacklist.
  - Safe source_type enum aligned with E3.
  - 78-field propertyNames blacklist covering the E3 blacklist plus
    trade_restriction / no_trade_clause / current_status / latest_status /
    active_now / starter / bench_role / rotation_role / the forbidden
    status strings themselves.
  - `manual_review_required` const true; `live_eligible` const false.
- Test result: **244 passed**. No real roster data added; synthetic
  fixtures only (`player-test-alpha` → `nba-ATL`, …); content-audit test
  rejects real NBA player names.

### M10-E Smoke Verification

- Commit: `f8cd23f`
- Tag: `m10e-smoke-verification`
- Files:
  - `docs/m10-e-smoke-verification.md`
- What it delivered: a docs-only smoke that re-ran every M10-E test and
  performed static guardrail checks.
- Test results recorded in the smoke doc:
  - E2 only: **58 passed**
  - E3 only: **178 passed**
  - E4 only: **244 passed**
  - E2 + E3 + E4: **480 passed**
  - M10 metadata full regression (B + C1 + C2 + D1 + E2 + E3 + E4):
    **732 passed**
- Static checks verified:
  - No new data files in real snapshot normalized/ (still only teams.json
    and team_visual_metadata.json).
  - No player_identities.json, roster_memberships.json, contracts.json,
    salaries.json, cap_sheet(s).json, injuries.json, rumors.json,
    scouting_opinions.json, players.json, rosters.json.
  - All six schema files present and not modified by the smoke.
  - Frontend has zero references to player_identities / roster_memberships.
  - Backend services have zero references to player_identities /
    roster_memberships (only the three E test files reference them).
  - api.py contains only pre-existing guardrail rejection lists for
    execute/apply/commit/mutate/write — no new mutation endpoints.
  - Real NBA player names appear only in the content-audit blacklists and
    audit docstrings, not in schemas or data.

## 3. Current artifacts

The following M10-E artifacts exist in the repository at the time of this
handoff. All paths are relative to the repository root.

**Docs (5):**

- `docs/m10-e-player-roster-data-governance-gate.md`
- `docs/m10-e2-source-freshness-lineage-schema-patch.md`
- `docs/m10-e3-player-identity-schema.md`
- `docs/m10-e4-roster-membership-schema.md`
- `docs/m10-e-smoke-verification.md`

**Schemas (3 produced or patched by M10-E):**

- `schema/source_manifest_schema.json` (patched in E2)
- `schema/player_identities_schema.json` (added in E3)
- `schema/roster_memberships_schema.json` (added in E4)

(Pre-existing schemas `teams_schema.json`, `team_visual_metadata_schema.json`,
and `real_snapshot_manifest_schema.json` from M10-B/C were not modified by
any E milestone, except for line-ending normalization that git reports as
a warning but not as a content diff.)

**Tests (3 added by M10-E):**

- `backend/app/tests/test_m10e_source_lineage_schema.py`
- `backend/app/tests/test_m10e_player_identity_schema.py`
- `backend/app/tests/test_m10e_roster_membership_schema.py`

**Data files: none added by M10-E.** The real snapshot
`data/snapshots/nba_real_2026_preoffseason_v1/` is unchanged from its
M10-D2 seal (manifest.json + source_manifest.json + normalized/teams.json +
normalized/team_visual_metadata.json).

## 4. What is explicitly NOT included

The following are **not** part of M10-E and must not be assumed to exist,
even though the schemas for player/roster are now defined:

- **No real player identity data.** `normalized/player_identities.json`
  does not exist.
- **No real roster membership data.** `normalized/roster_memberships.json`
  does not exist.
- **No contracts, salaries, or cap sheets.** None of these files exist;
  the `data_categories` enum actively rejects `contracts` and `cap_sheets`
  at the schema layer.
- **No injury/medical data.** No injury, medical_status, health, or
  availability fields or files.
- **No rumors / scouting opinions.** No opinion data.
- **No live/current/latest roster data.** All governance enums and
  blacklists reject live/current/latest naming and values; live_eligible
  is const false at both file and record levels.
- **No backend read model for player/roster.**
  `backend/app/services/real_snapshot_metadata_reader.py` continues to
  expose team identity + visual metadata only. No other service imports
  the new schemas.
- **No frontend player/roster UI.** The `/offseason` panel remains the
  M10-D2 team selector + abbreviation badge; no player list, no roster
  list, no player inspector.
- **No Agent integration.** The Agent, orchestrator, and intent classifier
  cannot access player/roster data.
- **No natural-language-preview integration.** The NL preview does not see
  player/roster metadata.
- **No trade/signing logic integration.** Trade simulator and signing
  logic continue to operate on demo/generated data only.
- **No NBA API integration.**
- **No scraping.**
- **No LLM-generated data.** llm_generated is rejected at the schema
  layer for both source_manifest per-file sources and the record-level
  source_type enums in E3/E4.
- **No execute/apply/commit/mutate/write/persist/save/delete/update/
  submit/auto_execute/auto_approve endpoints.** Mutation verbs are
  rejected at both the existing API guardrail layer and the new E3/E4
  schema propertyNames blacklists.

## 5. Guardrails that must remain true

These guardrails are enforced by schemas and tests today. They must not be
weakened in any future milestone without an explicit governance gate.

- **LLM cannot choose or mutate roster data.** `source_type=llm_generated`
  is rejected by the source_manifest per-file-source enum (E2) and by the
  E3/E4 record-level source_type enums. Future services must additionally
  enforce that LLM output never flows directly into real snapshot files.
- **Agent cannot use player/roster metadata for signing/trade decisions.**
  Enforced today by the absence of any service import of the new schemas
  (verified by static grep in the smoke doc). Future milestones that add a
  player/roster read model must add static-import guardrail tests that
  prevent the Agent, NL preview, and trade/signing logic from importing
  the real reader.
- **source_manifest must reject contracts / salaries / cap_sheets /
  live_status / rumors.** Enforced in E2 by the `data_categories` enum
  (contracts and cap_sheets removed; live_status/rumors/injuries/
  current_roster/latest_roster/scouting_opinions rejected by
  propertyNames) and by negative tests.
- **Player identity schema must reject salary/contract/cap, injury/medical,
  social/agent, rumors/scouting, live/availability/projection, and
  mutation fields.** Enforced in E3 by the 56-field propertyNames
  blacklist at top and per-player, plus const false/true flags, plus
  178 tests.
- **Roster membership schema must reject inactive/waived/traded/injured/
  available/current/latest and salary/contract/cap, injury, trade
  restrictions, depth/role/rotation projections, and mutation fields.**
  Enforced in E4 by the narrow 6-value roster_status enum, the 78-field
  propertyNames blacklist (which also lists the forbidden status names as
  forbidden keys), plus const false/true flags, plus 244 tests.
- **Real data must be snapshot-based, source-backed, manually reviewed,
  live_eligible=false.** Enforced across E2/E3/E4 by required lineage
  fields, `manual_review_required: const true`, `live_eligible: const false`,
  non-empty `limitations`, and non-empty `data_freshness_warning`.
- **No fallback from real snapshot to demo data.** The M10-D1 hard-error
  contract continues: schema/hash/xref/not-found errors raise typed errors
  (mapped to HTTP 500), never stub/demo data. This contract must be
  carried forward when a player/roster read model is added.

## 6. Test evidence

This final handoff **reuses the sealed smoke evidence** from
`docs/m10-e-smoke-verification.md`. It does not re-run tests and does not
modify any test file. The evidence (recorded at the E-smoke seal, commit
`f8cd23f`):

| Suite | Result |
|---|---|
| E2 `test_m10e_source_lineage_schema.py` | 58 passed |
| E3 `test_m10e_player_identity_schema.py` | 178 passed |
| E4 `test_m10e_roster_membership_schema.py` | 244 passed |
| E2 + E3 + E4 combined | 480 passed |
| M10 metadata full regression (B + C1 + C2 + D1 + E2 + E3 + E4) | 732 passed |

The pre-existing Windows-only pytest tempdir atexit `PermissionError
[WinError 5]` appears after the pytest summary line and is environmental;
it does not affect pass/fail counts and is not a regression introduced by
M10-E.

## 7. Recommended next step

**Do not jump to writing real player/roster data.** The recommended next
step is a **design gate**, not an implementation:

> **M10-F Design Gate: Real Player/Roster Data Read Model Planning**
> (alternatively: **M10-F1 Real Player/Roster Source Intake Design Gate**)

The design gate must produce a written plan covering, at minimum:

1. **Source intake workflow.** Exact manual curation steps, source URLs,
   reviewer sign-off, and how file_hashes will be produced and sealed.
2. **Scope of the first real-data drop.** Whether it covers all ~540+
   standard-roster players or a smaller pilot set, and why.
3. **Per-file governance values.** Concrete `source_type`, `as_of_date`,
   `data_freshness_warning`, `limitations[]`, and `stale_after_date` that
   will be used.
4. **Cross-reference enforcement.** How team-id xref (roster_memberships →
   teams), player-id xref (roster_memberships → player_identities), and
   id-uniqueness will be enforced at read time.
5. **Reader service plan.** Which new service module will load
   player_identities/roster_memberships, how it returns errors
   (RealSnapshotSchemaError/HashError/CrossReferenceError/NotFoundError →
   HTTP 500), and how it refuses to serve data when lineage fields are
   missing.
6. **Static-import guardrails.** New tests that prevent Agent,
   natural-language-preview, trade/signing logic, and demo data paths from
   importing the real reader.
7. **Frontend plan** (if any): whether any player/roster UI is added in
   the same milestone, or deferred. Default should be **deferred** until
   the read model is stable.
8. **Out-of-scope confirmation.** Explicitly re-confirms that contracts,
   salaries, cap sheets, injury/medical data, live/current/latest
   semantics, rumors, scouting opinions, and LLM-generated content remain
   forbidden.
9. **Hard-error policy.** Re-states that there is no fallback from real
   snapshot errors to demo/generated data.

Until M10-F design gate is approved, the following must remain true:

- Do not populate `normalized/player_identities.json`.
- Do not populate `normalized/roster_memberships.json`.
- Do not add contracts / salaries / cap sheets.
- Do not add frontend player/roster UI.
- Do not wire player/roster data into the Agent or NL preview.
- Do not connect to live APIs, scrape websites, or use LLM-generated data
  as source input.
- Do not widen the E4 `roster_status` enum to include inactive/waived/
  traded/injured/available/current/latest without a dedicated governance
  review.

## 8. Handoff instructions for the next model

- **Start from HEAD `f8cd23f`** (this smoke-verification commit). If this
  final-handoff doc is committed and tagged later, start from whatever
  commit carries the `m10e-final-handoff` tag instead.
- **Respect M10-E boundaries.** Do not write real player data, real roster
  data, contracts, salaries, cap sheets, or any of the forbidden fields
  listed in §4 and §5 without first opening a new governance gate.
- **Read E1-E4 docs before making any change.** At minimum read:
  - `docs/m10-e-player-roster-data-governance-gate.md`
  - `docs/m10-e2-source-freshness-lineage-schema-patch.md`
  - `docs/m10-e3-player-identity-schema.md`
  - `docs/m10-e4-roster-membership-schema.md`
  - `docs/m10-e-smoke-verification.md`
  - This document.
- **Use schemas + tests as guardrails.** Treat the 732-test M10 metadata
  regression as the minimum bar; any future change must keep it green.
  When adding new fields or categories, prefer tightening the schemas
  (narrower enums, more forbidden keys) over loosening them.
- **Do not operate `D:\DraftMind`.**
- **Do not mutate `data/snapshots/` without explicit design approval.** Any
  new real snapshot file must be accompanied by hash sealing, per-file
  source entries, a matching data_categories entry, manual_review_required
  true, live_eligible false, limitations, and a data_freshness_warning.
- **Do not use real NBA player data until source/freshness/manual-review
  rules are approved** in the M10-F design gate.
- **Do not widen the roster_status enum, add injury/availability fields,
  or add contracts/salaries/cap** in any M10-E follow-up; those belong to
  a later milestone series with their own governance.
- **No mutation endpoints.** Do not add execute/apply/commit/mutate/write/
  persist/save/delete/update/submit endpoints that touch real snapshot
  data.

## 9. Final conclusion

- **M10-E Final Handoff is ready for ChatGPT review.**
- **M10-E can be considered closed** after this document is committed and
  tagged.
- **Recommended tag name for this commit:** `m10e-final-handoff`.
- **Status of M10-E:** governance + schema + tests + smoke fully sealed;
  no real player/roster data shipped; all hard guardrails from E1
  enforced at the schema layer and verified by 732 regression tests; no
  frontend/backend/API/service/data wiring for player/roster has been
  added.
- **Next recommended milestone:** M10-F Design Gate (Real Player/Roster
  Data Read Model Planning) as described in §7. Do not proceed directly to
  real-data intake.
