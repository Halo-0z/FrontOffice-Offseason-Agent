# M8-A: Real NBA Data Ingestion Design

> Milestone: M8-A (Design only — no implementation)
> Status: Design complete
> Scope: Directory structure, schema, manifest, validation, fallback, human guardrails, task breakdown
> Boundary: **No real data import. No code changes. No API calls. No LLM. No MCP.**

---

## 1. Why real data cannot go directly into `data/*.json`

The current `data/` directory holds immutable **demo/sample/simulation** JSON files. Every loader and service assumes `sample_data: true` and treats the files as a stable, known-good fixture set. Dropping real NBA data into those files would break multiple invariants:

| Problem | Why it matters |
|---|---|
| **Sample vs real isolation** | All current tests assert `sample_data: true`. Mixing real data into the same directory would silently invalidate guardrail tests and make demo mode undependable. |
| **No provenance** | Demo data has no `source`, `as_of_date`, `confidence`, or license fields. Real salary/contract data must carry attribution or it is unverifiable. |
| **Expiry** | NBA contracts, cap holds, and free-agent status change daily during the offseason. A static JSON file treated as "truth" becomes stale within weeks and produces misleading previews. |
| **No verification chain** | Real contracts often have option years, partial guarantees, trade kickers, and cap holds that require human review before the system trusts them. Demo data has none of this complexity and is 100% guaranteed. |
| **No fallback path** | If real data is incomplete or a file is missing, the system must gracefully fall back to demo data or the latest verified snapshot. Without an explicit mode switch, failure is silent. |
| **Agent cannot guess** | The LLM/agent must never fabricate or interpolate missing contract figures, cap holds, or option statuses. Missing fields must be flagged for human review, not guessed. |

**Core principle:** Demo data and real snapshots live in separate directory trees, are selected via an explicit runtime config, and are never mutated or mixed.

---

## 2. Recommended data directory structure

M8-B and beyond will evolve the `data/` directory into a three-layer layout. **M8-A does not move any existing files** — existing `data/*.json` remains in place as the implicit demo set during the transition.

```
data/
├── demo/                                # Current demo/sample/simulation data (M8-B moves files here)
│   ├── manifest.json                    # Demo manifest (sample_data: true, no validation needed)
│   ├── teams.json
│   ├── players.json
│   ├── contracts.json
│   ├── free_agents.json
│   ├── cap_config.json
│   └── evidence_notes.json
│
├── snapshots/                           # Immutable, timestamped real-data snapshots
│   └── 2026-07-01/                      # Example: first real snapshot (M8-B creates this)
│       ├── manifest.json                # Snapshot manifest (see §6)
│       ├── source_notes.md              # Human-written provenance notes
│       ├── raw/                         # Optional: raw source extracts (never read by runtime)
│       │   └── (manual extracts from public sources)
│       └── normalized/                  # Normalized, validated JSON consumed by the backend
│           ├── teams.json
│           ├── players.json
│           ├── contracts.json
│           ├── free_agents.json
│           ├── cap_config.json
│           └── evidence_notes.json
│
└── normalized/
    └── latest/                          # Symlink or copy: pointer to the most recent validated snapshot
        ├── teams.json
        ├── players.json
        ├── contracts.json
        ├── free_agents.json
        ├── cap_config.json
        └── evidence_notes.json
```

### Migration notes for M8-B

- Existing `data/*.json` files are moved into `data/demo/` (or kept in place with a compatibility shim during M8-B to avoid breaking tests).
- The loader gains a `data_mode` parameter (`"demo"` | `"snapshot"`) and a `data_snapshot_id` parameter.
- When `data_mode="demo"`, it reads from `data/demo/` (or legacy `data/` for backward compatibility in M8-B).
- When `data_mode="snapshot"`, it reads from `data/snapshots/<id>/normalized/` after validating the manifest.
- `data/normalized/latest/` is only used as a convenience pointer; runtime code must always resolve through the explicit snapshot ID.

---

## 3. Data source strategy

The system **never fetches data live at runtime**. All real data enters the system as a **manually curated local snapshot**. This is a hard constraint for M8 and the foreseeable future.

### Source tiers

| Tier | Description | M8-B use? | Network access |
|---|---|---|---|
| **Manual snapshot** | Human-curated, hand-entered JSON in `data/snapshots/<id>/raw/` + `normalized/`. Most reliable, fully auditable. | **Yes — primary source** | None |
| **Public reference** | Publicly available NBA reference sites (NBA.com team pages, official press releases) used *only* by a human during snapshot creation to cross-check rosters and basic player info. Never scraped automatically. | Cross-check only (human in loop) | Human uses browser; no code fetches |
| **Paid/API source** | Commercial NBA data APIs (e.g., Sports Reference, Spotrac, official NBA stats API). **Not required for MVP**. If added later, data is always pulled offline by a human/script and committed as a snapshot, never fetched at request time. | No | Offline only |
| **Local cached snapshot** | The `normalized/` output of a validated snapshot. This is the *only* thing the runtime backend reads. | Yes (exclusive runtime source) | None |

### Rules (hard constraints)

1. **No live fetch at runtime.** The backend never makes HTTP calls to external data sources during API requests or CLI runs.
2. **First real data = local verified snapshot.** M8-B imports a manually prepared, human-verified snapshot of ~2 teams and ~10-20 players.
3. **Every record carries provenance.** See §4 schema for required `source`, `source_name`, `source_url`, `as_of_date`, `verified_by`, `manual_review_required` fields.
4. **Conflicts are flagged, not resolved silently.** If two sources disagree on a salary or contract status, the record is marked `manual_review_required: true` and the system shows a warning instead of guessing.
5. **No automatic overwrite of snapshots.** Snapshots are immutable once created. A new date directory is created for updated data; old snapshots remain for audit.

### Candidate reference sources (for human cross-checking only — not auto-fetched)

These are listed for human researchers preparing snapshots. **No code in this repository will automatically fetch from these sources in M8.**

- NBA.com official team rosters (player names, positions, jersey numbers)
- Official NBA league announcements (salary cap figures for each season)
- Publicly reported contract details from widely cited sports journalism outlets
- Team official press releases for signings/trades

All require **human verification** before data enters a snapshot. License/attribution requirements must be documented in `source_notes.md` per snapshot.

---

## 4. Normalized schema design

All normalized JSON files follow the same top-level wrapper pattern. Every entity includes provenance fields and a `sample_data` flag.

### 4.1 Top-level wrapper (every file)

```jsonc
{
  "schema_version": "1.0",
  "data_mode": "snapshot",          // "demo" | "snapshot"
  "sample_data": false,             // false for snapshots, true for demo
  "snapshot_id": "2026-07-01",      // matches directory name; null for demo
  "season": "2026-2027",
  "as_of_date": "2026-07-01",
  "source": "manual_snapshot",
  "source_name": "M8-B initial real snapshot",
  "source_url": null,               // optional: URL of primary reference
  "verified_by": "human_researcher",
  "manual_review_required": false,  // top-level: any record needs review?
  "entities": [ ... ]               // teams / players / contracts / free_agents / evidence_notes
}
```

The cap_config wrapper is similar but contains a single object instead of an array:

```jsonc
{
  "schema_version": "1.0",
  "data_mode": "snapshot",
  "sample_data": false,
  "snapshot_id": "2026-07-01",
  "season": "2026-2027",
  "as_of_date": "2026-07-01",
  "source": "manual_snapshot",
  "verified_by": "human_researcher",
  "cap_config": { ... }
}
```

### 4.2 Team entity

```jsonc
{
  "team_id": "nba-ATL",             // Internal stable ID (namespaced, not demo prefix)
  "nba_team_id": 1610612737,        // Optional: official NBA team ID (integer)
  "abbreviation": "ATL",
  "name": "Atlanta Hawks",
  "market": "Atlanta",
  "conference": "East",             // Optional
  "division": "Southeast",          // Optional
  "season": "2026-2027",
  "source": "nba_com_roster",
  "source_name": "NBA.com team roster",
  "source_url": "https://www.nba.com/hawks/roster",  // Optional, for human reference
  "as_of_date": "2026-07-01",
  "verified_by": "human_researcher",
  "sample_data": false,
  "manual_review_required": false
}
```

### 4.3 Player entity

```jsonc
{
  "player_id": "p-201938",          // Internal stable ID
  "nba_player_id": 201938,          // Optional: official NBA player ID
  "name": "Trae Young",
  "position": "PG",
  "secondary_positions": [],        // e.g., ["SG"] for combo guards
  "team_id": "nba-ATL",             // Nullable; null = unsigned free agent
  "age": 27,                        // Optional
  "height_inches": 73,              // Optional
  "weight_lbs": 164,                // Optional
  "source": "nba_com_roster",
  "source_name": "NBA.com team roster",
  "source_url": null,
  "as_of_date": "2026-07-01",
  "verified_by": "human_researcher",
  "sample_data": false,
  "manual_review_required": false
}
```

### 4.4 Contract entity

```jsonc
{
  "contract_id": "ct-p-201938-2026",
  "player_id": "p-201938",
  "team_id": "nba-ATL",
  "season": "2026-2027",
  "salary": 42800000,               // Current-season cap hit (USD integer)
  "guaranteed_salary": 42800000,    // Optional: guaranteed portion
  "years_remaining": 3,
  "contract_type": "standard",      // "standard" | "rookie" | "minimum" | "two_way" | "extension" | "option"
  "player_option": false,
  "team_option": false,
  "no_trade_clause": false,
  "partial_guarantee": false,       // Optional
  "trade_kicker": false,            // Optional
  "source": "public_reports",
  "source_name": "Publicly reported contract details",
  "source_url": null,
  "as_of_date": "2026-07-01",
  "verified_by": "human_researcher",
  "sample_data": false,
  "manual_review_required": true    // Contracts almost always need review due to option complexity
}
```

### 4.5 FreeAgent entity

```jsonc
{
  "free_agent_id": "fa-p-XXXXX",
  "player_id": "p-XXXXX",           // Nullable if player not in players.json (e.g., unsigned rookies)
  "name": "Player Name",
  "position": "SF",
  "secondary_positions": [],
  "previous_team_id": "nba-XXX",    // Optional
  "free_agent_type": "unrestricted",// "unrestricted" | "restricted" | "unsigned_draft_pick"
  "expected_salary": 15000000,      // Optional: market estimate (clearly marked as estimate)
  "market_tier": "starter",         // Optional: "star" | "starter" | "rotation" | "bench" | "minimum"
  "source": "manual_market_estimate",
  "source_name": "Manual market estimate",
  "source_url": null,
  "as_of_date": "2026-07-01",
  "verified_by": "human_researcher",
  "sample_data": false,
  "manual_review_required": true    // FA estimates are inherently uncertain
}
```

### 4.6 CapConfig entity

```jsonc
{
  "season": "2026-2027",
  "salary_cap": 140588000,
  "luxury_tax": 170864000,
  "first_apron": 178864000,
  "second_apron": 189864000,
  "roster_min": 14,
  "roster_max": 15,
  "minimum_salary": 1195286,        // Scale by years of service in future; flat for MVP
  "mid_level_exception": 12864000,  // Non-taxpayer MLE
  "source": "nba_official_announcement",
  "source_name": "NBA official salary cap announcement",
  "source_url": null,
  "as_of_date": "2026-07-01",
  "verified_by": "human_researcher",
  "sample_data": false
}
```

### 4.7 EvidenceNote entity

```jsonc
{
  "evidence_id": "ev-real-001",
  "title": "Team need: frontcourt scoring",
  "body": "Human-curated note about team needs. Can reference reporting but must be summarized, not copy-pasted.",
  "source": "manual_analyst_note",
  "source_name": "Local analyst note",
  "source_url": null,               // Optional: link to an article for human reference
  "evidence_type": "roster_context",
  "team_ids": ["nba-ATL"],
  "player_ids": [],
  "topics": ["frontcourt", "scoring", "need"],
  "confidence": 0.75,
  "as_of_date": "2026-07-01",
  "verified_by": "human_researcher",
  "sample_data": false,
  "manual_review_required": false,
  "metadata": []
}
```

### Schema evolution notes

- All existing demo models (`PlayerContract`, `RosterPlayer`, `EvidenceNote`, etc.) gain new optional fields to accommodate these provenance attributes.
- The existing `sample_data: bool` field is preserved and extended to be `False` for snapshots.
- New fields (`source`, `as_of_date`, `verified_by`, `manual_review_required`) have sensible defaults so existing demo data does not break.
- The M8-B loader maps normalized JSON to the existing (slightly extended) dataclasses; no service-layer logic changes are needed in M8-B beyond data loading.

---

## 5. Data mode / runtime switch

### Environment variables

| Variable | Values | Default | Purpose |
|---|---|---|---|
| `DATA_MODE` | `demo` \| `snapshot` | `demo` | Selects which data tree to read from |
| `DATA_SNAPSHOT_ID` | e.g. `2026-07-01` | `latest` (resolved to most recent valid snapshot) | Which snapshot to load when `DATA_MODE=snapshot` |
| `DATA_DIR` | absolute path | auto-detected repo root `/data` | Override for testing / alternate data roots |

### Resolution logic

```
if DATA_MODE == "demo":
    data_dir = <DATA_DIR>/demo  (with fallback to <DATA_DIR> for backward compat in M8-B)
    validate manifest exists? demo manifest is optional; skip strict validation
elif DATA_MODE == "snapshot":
    snapshot_id = DATA_SNAPSHOT_ID or <latest valid snapshot ID>
    snapshot_dir = <DATA_DIR>/snapshots/<snapshot_id>/normalized
    manifest_path = <DATA_DIR>/snapshots/<snapshot_id>/manifest.json
    validate manifest (see §6) — FAIL FAST if manifest missing or invalid
    validate all required files exist — FAIL FAST if missing
    data_dir = snapshot_dir
```

### Backend API health response extension

The `/api/health` endpoint is extended to return data source metadata:

```json
{
  "status": "ok",
  "sample_data": false,
  "data_mode": "snapshot",
  "data_source": "verified local snapshot",
  "snapshot_id": "2026-07-01",
  "snapshot_date": "2026-07-01",
  "season": "2026-2027",
  "service": "frontoffice-offseason-agent"
}
```

### Frontend display requirement

The frontend console **must** always show a visible data source indicator:

- **Demo mode**: Yellow/grey badge "DEMO SAMPLE DATA" — existing behavior preserved.
- **Snapshot mode**: Green badge "VERIFIED LOCAL SNAPSHOT" with snapshot date (e.g., "as of 2026-07-01").
- **Fallback mode** (snapshot load failed, fell back to demo): Red/orange badge "SNAPSHOT FAILED — USING DEMO DATA" with error reason.
- **Manual review pending**: Orange warning badge "DATA PENDING REVIEW — some contracts may be inaccurate" if any record has `manual_review_required: true`.

### Mode selection safety

- **Default is always `demo`**. If `DATA_MODE` is unset, malformed, or the requested snapshot does not exist, the system must either (a) fall back to demo mode with a logged warning, or (b) fail fast per the failure policy table in §8.
- Tests run in `demo` mode by default. New snapshot-specific tests explicitly set `DATA_MODE=snapshot` and use a test fixture snapshot directory.
- **No automatic mode switching.** The mode is fixed at process startup; changing `DATA_MODE` requires a restart.

---

## 6. Manifest design

Every snapshot directory contains a `manifest.json` that describes the snapshot's contents, validity, and limitations. The demo directory may optionally contain a trivial manifest; the manifest is strictly validated only for snapshots.

```jsonc
{
  "manifest_version": "1.0",
  "snapshot_id": "2026-07-01",
  "snapshot_type": "real_snapshot",    // "demo" | "real_snapshot"
  "season": "2026-2027",
  "created_at": "2026-07-01T12:00:00Z",
  "as_of_date": "2026-07-01",

  "source_summary": {
    "primary_sources": ["nba_com_roster", "nba_official_cap_announcement", "manual_contract_entry"],
    "notes": "M8-B initial small real snapshot. Two teams, hand-verified."
  },

  "files": {
    "teams": { "path": "normalized/teams.json", "row_count": 2, "checksum": "sha256:..." },
    "players": { "path": "normalized/players.json", "row_count": 15, "checksum": "sha256:..." },
    "contracts": { "path": "normalized/contracts.json", "row_count": 15, "checksum": "sha256:..." },
    "free_agents": { "path": "normalized/free_agents.json", "row_count": 5, "checksum": "sha256:..." },
    "cap_config": { "path": "normalized/cap_config.json", "row_count": 1, "checksum": "sha256:..." },
    "evidence_notes": { "path": "normalized/evidence_notes.json", "row_count": 4, "checksum": "sha256:..." }
  },

  "row_counts": {
    "teams": 2,
    "players": 15,
    "contracts": 15,
    "free_agents": 5,
    "evidence_notes": 4
  },

  "required_files": ["teams", "players", "contracts", "free_agents", "cap_config"],
  "optional_files": ["evidence_notes"],

  "validation_status": "validated",    // "pending" | "validated" | "failed"
  "validation_errors": [],
  "validation_warnings": [
    "3 contracts marked manual_review_required due to option year uncertainty"
  ],

  "known_limitations": [
    "Only 2 teams included (M8-B minimal scope)",
    "No draft picks included",
    "Free agent expected salaries are estimates only",
    "Two-way contracts not modeled"
  ],

  "manual_review_status": {
    "teams_reviewed": true,
    "players_reviewed": true,
    "contracts_reviewed": false,
    "cap_config_reviewed": true,
    "free_agents_reviewed": false,
    "notes": "Contract option years and FA salary estimates require further review."
  },

  "checksum": "sha256:...",            // Checksum of the manifest itself (computed after all other fields)
  "schema_version": "1.0"
}
```

### Manifest validation rules

1. `manifest.json` must exist and be valid JSON.
2. `snapshot_id` must match the directory name.
3. All `required_files` entries must exist as files in the snapshot's `normalized/` directory.
4. `row_counts` must match the actual number of entities in each file.
5. If `validation_status` is `"failed"`, the snapshot must not be loaded — fail fast.
6. If `validation_status` is `"pending"` and `DATA_MODE=snapshot`, behavior is controlled by §8 (warning + allow, or block — configurable). Default: warn and allow, but frontend shows "pending review" badge.
7. Checksums (optional in M8-B, recommended in M8-C) are verified if present; mismatch → fail fast.

---

## 7. Validation / QA rules

Before a snapshot is accepted (either during manual import or at load time), the following validations run:

### File-level validation

| Rule | Severity |
|---|---|
| All required files exist (manifest `required_files`) | FAIL |
| All files are valid JSON | FAIL |
| All files have `schema_version`, `data_mode`, `sample_data: false`, `snapshot_id`, `season`, `as_of_date` | FAIL |
| `snapshot_id` in each file matches the manifest's `snapshot_id` | FAIL |
| `season` is consistent across all files | FAIL |
| Normalized output is deterministic (sorted keys, sorted entity arrays by ID) | WARNING |

### Schema validation

| Rule | Severity |
|---|---|
| Every team has `team_id`, `abbreviation`, `name`, `source`, `as_of_date`, `sample_data: false` | FAIL |
| Every player has `player_id`, `name`, `position`, `source`, `as_of_date`, `sample_data: false` | FAIL |
| Every contract has `contract_id`, `player_id`, `team_id`, `season`, `salary`, `source`, `as_of_date`, `sample_data: false` | FAIL |
| Every free agent has `name`, `position`, `source`, `as_of_date`, `sample_data: false` | FAIL |
| `cap_config` has `season`, `salary_cap`, `luxury_tax`, `first_apron`, `second_apron`, `roster_min`, `roster_max` | FAIL |
| All IDs are unique within their entity type (no duplicate `team_id`, `player_id`, `contract_id`, `evidence_id`) | FAIL |
| No entity has `sample_data: true` in a snapshot | FAIL |

### Referential integrity

| Rule | Severity |
|---|---|
| Every `contract.team_id` references an existing team | FAIL |
| Every `contract.player_id` references an existing player | FAIL |
| Every `player.team_id` (non-null) references an existing team | FAIL |
| Every `evidence_note.team_ids` entry references an existing team | WARNING |
| Every `evidence_note.player_ids` entry references an existing player | WARNING |
| Free agents with a `player_id` reference an existing player or are explicitly marked as new/unsigned | WARNING |
| Free agents must not have an active contract for the same team+season unless marked as a known exception (e.g., renegotiation) | WARNING |

### Value validation

| Rule | Severity |
|---|---|
| All salary values are non-negative integers | FAIL |
| `salary_cap < luxury_tax < first_apron < second_apron` | FAIL |
| `years_remaining >= 0` | FAIL |
| `roster_min <= roster_max` | FAIL |
| `confidence` is in [0.0, 1.0] for evidence notes | FAIL |

### Process rules (enforced by convention and tests)

- **No write to original source files.** The normalization step reads from `raw/` and writes to `normalized/`; it never mutates files in `raw/` or in another snapshot.
- **Normalized output is deterministic.** Entity arrays are sorted by their primary ID; JSON is serialized with sorted keys and consistent indentation. This ensures two normalizations of the same input produce byte-identical output.
- **The raw/ directory is never read by the runtime backend.** Only `normalized/` files are loaded during API/CLI operation.

### Where validation runs

1. **Import time** (M8-C): A `scripts/validate_snapshot.py` script validates a snapshot before it can be marked `validation_status: "validated"`.
2. **Load time** (M8-C): The backend loader re-runs critical validations (file existence, referential integrity for contracts/teams) as a defense-in-depth check.
3. **Tests**: A test suite covers both valid snapshots and intentionally corrupt snapshots to verify the validator rejects bad data.

---

## 8. Failure handling and fallback

The system must never silently produce a transaction preview from bad data. Each failure mode has a defined response:

| Failure scenario | Detection | Response | Frontend signal |
|---|---|---|---|
| **Missing required file** | Manifest validation / loader | **Fail fast** if `DATA_MODE=snapshot` and `STRICT_SNAPSHOT=true` (default for production); **fallback to demo** if `STRICT_SNAPSHOT=false` (dev default). Error logged. | Red badge: "SNAPSHOT INCOMPLETE — using demo data" |
| **Stale snapshot** (as_of_date older than configurable threshold, e.g., 30 days during season) | Manifest check at load | **WARNING** — load succeeds, but all responses carry a `data_stale: true` flag. | Orange badge: "SNAPSHOT STALE — data as of <date>" |
| **Invalid salary** (negative, non-integer, or zero where expected) | Schema/value validation | **Fail fast** for that file; if the file is required, fall back to demo per strict mode setting. | Red badge |
| **Duplicate player/team/contract ID** | Uniqueness check | **Fail fast** for that file; fallback to demo per strict mode. | Red badge |
| **Source conflict** (two sources for same entity with disagreeing values) | Manual review flag / validator | Mark entity `manual_review_required: true`. Load succeeds, but entity is flagged. Contract validation warnings are elevated to the response. | Orange badge: "DATA PENDING REVIEW" |
| **Player/team mismatch** (player's team_id doesn't match contract's team_id, or team doesn't exist) | Referential integrity check | **Fail fast** for the offending contract; contract excluded with warning. If too many contracts fail, fallback to demo. | Orange/red badge depending on count |
| **API/source unavailable** | Not applicable at runtime (no live fetch); during manual snapshot creation, human researcher notes the gap | Snapshot creation documents the gap in `known_limitations`; affected entities marked `manual_review_required: true`. | Orange badge if gaps exist |
| **Partial snapshot** (some optional files missing, e.g., no evidence_notes) | Manifest validation | **WARNING** — load succeeds, missing features are disabled (e.g., evidence panel shows "no evidence available for this snapshot"). Cap/roster/trade functionality still works. | Yellow info badge: "Limited data: evidence notes not available" |
| **Manual review required** | Any entity has `manual_review_required: true` | **Load succeeds**, but every API response includes a `warnings` array listing pending review items. Transaction previews are still generated but carry a warning banner. | Orange badge: "DATA PENDING REVIEW — previews may be inaccurate" |
| **Snapshot validation_status: failed** | Manifest check | **Fail fast** — never load a failed snapshot; fallback to demo. | Red badge |
| **Unknown DATA_MODE value** | Config parsing | **Fallback to demo** with a logged warning. | Grey badge "DEMO MODE (config error)" |

### Global fallback priority

When a failure triggers fallback:

1. **Try requested snapshot** → if valid, use it.
2. **Try latest validated snapshot** (if different from requested) → if valid, use it with a stale/wrong-ID warning.
3. **Fall back to demo mode** → use demo data, show clear "using demo data" badge.

All fallback events are logged with a clear reason. The health endpoint reports the active mode and any fallback reasons.

### Transaction preview blocking

Even when data loads successfully, certain data quality issues should **block** transaction previews (return a 409 or a structured error rather than a misleading preview):

- If `cap_config` is missing or invalid → **block all previews** (cannot compute cap hits).
- If a team's roster has zero contracts and the team is in the snapshot → **warning, not block** (may be an expansion team or data gap; allow preview but show warning).
- If a contract has `manual_review_required: true` and is involved in the proposed transaction → **warning on preview**, not a block; the human must explicitly acknowledge the uncertainty.

---

## 9. Human approval boundary (unchanged but reinforced)

Real data does not change any of the existing guardrails. All existing hard boundaries remain in force:

| Guardrail | With real data |
|---|---|
| **No auto-approved transactions** | ✅ Unchanged. Every preview is a proposal; `requires_human_approval` is always `true`. |
| **No roster writes** | ✅ Unchanged. The system never mutates roster state; all previews are pure computations returning new objects. |
| **No bypassing human approval** | ✅ Unchanged. There is no code path that skips the approval gate. |
| **Unverified data degrades proposals** | New: If any data used in a proposal has `manual_review_required: true`, the proposal's evaluation includes a `DATA_QUALITY_WARNING` issue and the frontend shows an orange banner. The proposal can still be viewed, but the human is explicitly warned. |
| **LLM never fills missing fields** | ✅ Unchanged. If a player's position, a contract's salary, or a cap figure is missing, the system does not ask an LLM to guess. It either fails validation or marks the entity as requiring manual review. |
| **Agent is advisor only** | ✅ Unchanged. The agent orchestrates tools and explains outputs; it does not declare transactions valid, does not set salaries, and does not approve signings. |
| **Sample data still works** | ✅ `DATA_MODE=demo` is always available and is the default. Demo mode is never removed. |

### Additional real-data guardrails

1. **No impersonation of official NBA sources.** The UI must not present estimates or manually entered salaries as "official NBA data." All non-official figures must be labeled as estimates or unverified.
2. **Attribution required.** If a snapshot uses a specific source for contract data, the source must be named in the manifest and visible to users via the data source badge (hover/tooltip or "About this data" panel).
3. **No legal advice.** The system does not provide legal advice on CBA compliance. It computes cap math and rule checks; humans must verify legality.

---

## 10. M8-B minimal implementation recommendation

M8-B is the **Small Real Snapshot Import** milestone. It should be narrowly scoped to minimize risk while proving the full pipeline works end-to-end.

### M8-B scope (do these)

1. **Create snapshot directory** `data/snapshots/2026-07-01/` with:
   - `manifest.json` (with `validation_status: "validated"` for the small scope)
   - `source_notes.md` documenting sources and manual verification
   - `normalized/teams.json` — **2 real teams** (choose two small-market teams with relatively stable rosters for simplicity)
   - `normalized/players.json` — **10-20 players** across those two teams
   - `normalized/contracts.json` — **10-20 contracts** (one per player; mark option-year contracts as `manual_review_required: true`)
   - `normalized/free_agents.json` — **0-5 free agents** relevant to those teams (can be a small set)
   - `normalized/cap_config.json` — **1 cap config** for the 2026-2027 season (use publicly announced figures; mark source)
   - `normalized/evidence_notes.json` — **3-5 evidence notes** (manually written, properly attributed)

2. **Add a snapshot loader module** (new file, e.g., `backend/app/services/snapshot_loader.py`):
   - `load_snapshot(snapshot_id: str, data_dir: Path) -> SnapshotBundle`
   - Validates manifest
   - Loads and validates normalized JSON
   - Returns a typed bundle containing teams, players, contracts, free_agents, cap_config, evidence_notes
   - On failure, raises `SnapshotLoadError` (or returns a result with fallback info)

3. **Add a snapshot validator module** (e.g., `backend/app/services/snapshot_validator.py`):
   - Validates a snapshot directory per §7 rules
   - Returns a `SnapshotValidationResult` with errors and warnings
   - CLI entry point: `python backend/scripts/validate_snapshot.py --snapshot 2026-07-01`

4. **Extend the data loading layer** to accept `data_mode` and `snapshot_id` parameters:
   - Existing services (`cap_sheet_service`, `roster_need_service`, etc.) already accept a `data_dir` parameter
   - M8-B adds a thin resolver that maps `(data_mode, snapshot_id)` → resolved `data_dir` Path
   - Demo mode continues to work exactly as before (backward compatible)

5. **Extend dataclasses/models** with optional provenance fields:
   - Add `source: str = ""`, `as_of_date: str = ""`, `verified_by: str = ""`, `manual_review_required: bool = False` to relevant dataclasses
   - All default to empty/false so existing demo data works unchanged
   - `sample_data` stays; snapshot data sets it to `False`

6. **Add snapshot-specific tests**:
   - Test that a valid snapshot loads correctly
   - Test that a corrupted snapshot fails validation
   - Test that fallback to demo works when snapshot is invalid
   - Test that demo mode is unaffected

7. **Add `DATA_MODE` and `DATA_SNAPSHOT_ID` env var parsing** in the API/app startup:
   - Default: `DATA_MODE=demo`
   - API startup logs which mode is active

### M8-B scope (do NOT do these)

- ❌ No real-time API fetching
- ❌ No automatic data scraping
- ❌ No frontend snapshot badge (that's M8-D)
- ❌ No data migration of existing demo files (keep `data/*.json` working as-is in M8-B; move to `data/demo/` in M8-C if needed)
- ❌ No full-league data (30 teams) — 2 teams is enough to prove the pipeline
- ❌ No multi-snapshot comparison or history UI
- ❌ No checksum verification (optional; can be added in M8-C)
- ❌ No LLM-assisted data entry or gap filling

---

## 11. Task breakdown for M8-B, M8-C, M8-D

### M8-B: Small Real Snapshot Schema + Loader (minimal working pipeline)

**Goal:** A validated 2-team real snapshot can be loaded by the backend; demo mode is unaffected.

| # | Task | Type |
|---|---|---|
| 1 | Create `data/snapshots/2026-07-01/` directory with normalized JSON files (2 teams, ~15 players/contracts, cap config, a few evidence notes, manifest) | Data (manual) |
| 2 | Write `source_notes.md` for the snapshot documenting all sources | Docs |
| 3 | Add provenance fields (`source`, `as_of_date`, `verified_by`, `manual_review_required`) to existing dataclasses with safe defaults | Backend model |
| 4 | Create `snapshot_validator.py` with file-level, schema, referential integrity checks | Backend service |
| 5 | Create `snapshot_loader.py` that loads a validated snapshot into model instances | Backend service |
| 6 | Add `resolve_data_dir(data_mode, snapshot_id)` helper | Backend config |
| 7 | Add env var parsing (`DATA_MODE`, `DATA_SNAPSHOT_ID`) to API startup | Backend config |
| 8 | Add `/api/health` extension returning `data_mode`, `sample_data`, `snapshot_id` | Backend API |
| 9 | Add `scripts/validate_snapshot.py` CLI tool | Backend script |
| 10 | Add tests for validator (valid + invalid snapshots), loader, fallback | Backend tests |
| 11 | Verify existing 372 tests still pass in demo mode | Test |

**Exit criteria:**
- `DATA_MODE=snapshot DATA_SNAPSHOT_ID=2026-07-01 python backend/scripts/run_offseason_demo.py --team-id <real-team-id>` produces a valid proposal preview with `sample_data: false`
- `DATA_MODE=demo` (default) produces identical results to M7-C
- All 372 existing tests pass
- Validator correctly rejects intentionally corrupt snapshots

### M8-C: Snapshot Mode Backend Wiring (full backend integration)

**Goal:** All existing services and API endpoints work transparently in both demo and snapshot mode; snapshot selection is robust; demo data is migrated to its own directory.

| # | Task | Type |
|---|---|---|
| 1 | Move existing `data/*.json` into `data/demo/` (with backward-compat shim or update all loaders) | Data/refactor |
| 2 | Create `data/demo/manifest.json` (simple demo manifest) | Data |
| 3 | Update all service loaders to use `resolve_data_dir()` instead of hardcoded `"data"` path | Backend refactor |
| 4 | Wire snapshot data into `proposal-preview` and `trade-preview-demo` endpoints (accept team IDs from the active snapshot) | Backend API |
| 5 | Add `GET /api/offseason/teams` endpoint listing teams in the active data mode | Backend API |
| 6 | Add `GET /api/offseason/data-source` endpoint returning manifest info + validation warnings | Backend API |
| 7 | Implement fallback chain (requested snapshot → latest snapshot → demo) with warning propagation | Backend service |
| 8 | Add stale-snapshot detection (configurable age threshold) | Backend config |
| 9 | Add strict mode (`STRICT_SNAPSHOT=true`) for production-like environments | Backend config |
| 10 | Add transaction preview blocking when `cap_config` is invalid/missing (§8) | Backend guardrail |
| 11 | Add data quality warnings to `ValidationResult` when contracts/players are `manual_review_required` | Backend service |
| 12 | Update all tests to work with new directory structure | Test |
| 13 | Add integration tests covering both modes | Test |

**Exit criteria:**
- Both demo and snapshot modes work for all endpoints
- API returns correct data source metadata
- Fallback behavior is tested and documented
- Frontend can fetch teams list for the active mode (will be used in M8-D)

### M8-D: Frontend Snapshot Data Source Badge + Guardrails

**Goal:** The frontend clearly communicates which data mode is active, shows snapshot metadata, and warns about data quality issues.

| # | Task | Type |
|---|---|---|
| 1 | Add data source badge component (demo/snapshot/fallback/review-pending states) | Frontend component |
| 2 | Fetch `/api/health` (or `/api/offseason/data-source`) on page load to determine mode | Frontend logic |
| 3 | Display snapshot date in the badge | Frontend UI |
| 4 | Show orange warning banner when `manual_review_required` items exist | Frontend UI |
| 5 | Show red banner when in fallback-to-demo mode due to snapshot failure | Frontend UI |
| 6 | Update team selection to dynamically populate from `/api/offseason/teams` (instead of hardcoded DEM-ATL/DEM-PDX/DEM-CHI) | Frontend logic |
| 7 | Disable or warn on transaction preview when data quality warnings are present (with user acknowledgment) | Frontend guardrail |
| 8 | Add "About this data" tooltip/panel showing source, as_of_date, known_limitations from manifest | Frontend UI |
| 9 | Update frontend fallback to handle "snapshot mode but backend returned demo fallback" gracefully | Frontend logic |
| 10 | Ensure frontend typecheck/build passes with the new types | Frontend build |
| 11 | Visual/UI smoke test across all four badge states | Frontend QA |

**Exit criteria:**
- Frontend correctly shows data source in all states
- Users cannot confuse demo data with real snapshot data
- Team selection works for both demo and snapshot modes
- Bilingual (CN/EN) badge labels are added to i18n
- Build passes, no type errors

### Alternative: Merging M8-C and M8-D

If velocity is high after M8-B, M8-C and M8-D can be combined into a single milestone ("M8-C/D: Full Snapshot Integration") since they are tightly coupled — the backend needs to expose the metadata that the frontend badge consumes. However, keeping them separate reduces risk: M8-C can be fully tested via CLI/API tests before any UI changes are made.

---

## 12. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | **Source freshness** — snapshots become stale quickly during free agency, leading to misleading previews | High (during offseason) | Medium | Stale-snapshot detection (§8), as_of_date displayed prominently, warning banner for snapshots older than threshold |
| R2 | **Contract accuracy** — NBA contracts have complex guarantees, options, trade bonuses, and cap holds that are hard to model correctly | High | High | All real contracts default to `manual_review_required: true`; warnings on previews involving unverified contracts; limit M8-B to 2 teams with simpler contract situations |
| R3 | **Salary/cap figure mismatch** — cap figures change annually; using wrong year's cap number invalidates all cap math | Medium | High | cap_config is a separate, explicitly versioned file; season field must match across all files; validator enforces cap/tax/apron ordering |
| R4 | **Player ID mapping** — linking players across sources (NBA.com ID, internal ID, future sources) can create duplicates or mismatches | Medium | Medium | Internal IDs are namespaced (`p-<nba_id>` when available); duplicate ID rejection in validator; cross-reference checks during manual snapshot creation |
| R5 | **Free agent status stale** — a player listed as a free agent may have signed, or a signed player may have been waived | High | Medium | as_of_date displayed; free agent list is expected to be stale; FA expected salaries are always marked as estimates with `manual_review_required: true` |
| R6 | **Legal/license/attribution** — scraping or reproducing contract data from paid sources may violate terms of service | Medium | High | No automatic scraping; all snapshots are manually curated; sources documented in manifest and source_notes.md; no large-scale reproduction of copyrighted content; evidence notes are summarized, not copy-pasted |
| R7 | **Pretending sample data is real** — a misconfiguration could serve demo data labeled as real, or vice versa | Low (with M8-C/D guardrails) | High | `sample_data` flag is explicitly checked and displayed; badge color coding; health endpoint always reports data_mode; tests verify badge states |
| R8 | **Overfitting to one data source** — relying on a single source for contracts leads to systemic bias/errors | Medium | Medium | Source fields required on every record; manifest documents all sources; future snapshots should cross-reference multiple sources; M8-B uses conservative, publicly verifiable data only |
| R9 | **Breaking demo mode** — refactoring data loading for snapshots accidentally breaks the existing demo pipeline | Medium (during M8-C) | Medium | Demo mode is the default; all existing tests run in demo mode; backward-compatible data directory resolution; M8-B does NOT move existing demo files |
| R10 | **UI misleading users** — the frontend presents previews as more authoritative than they are, especially with `manual_review_required` data | Medium | Medium | Prominent data source badge; warning banners for pending review; all transaction previews keep `requires_human_approval: true`; "About this data" panel shows limitations |
| R11 | **Partial snapshot creating false confidence** — a snapshot loads but is missing critical data (e.g., no contracts for a team), producing wrong cap numbers | Medium | High | Validator checks for contracts per team; zero-contract teams generate a warning; cap_config is required; referential integrity is enforced; missing required files → fail fast or fallback |
| R12 | **Schema evolution breaking old snapshots** — future schema changes (M9+) break M8-B snapshots | Low | Low | Schema version field in every file; loader handles known schema versions; old snapshots are immutable and can be re-normalized if needed |

---

## 13. Open questions / unresolved items

These are not blocking M8-B but should be resolved in later milestones:

1. **Two-way contracts and Exhibit 10 deals** — The current `PlayerContract` model does not handle two-way contracts, Exhibit 10, or 10-day contracts. These should be added as `contract_type` values when the snapshot includes enough two-way players to matter (likely M9 or later).
2. **Draft picks** — Draft pick assets and rookie scale contracts are not modeled. Trade preview does not support pick swaps or draft pick compensation. This is a known limitation documented in the manifest.
3. **Bird rights and cap holds** — The current rule engine does not model Bird rights, Early Bird, non-Bird free agent cap holds, or renouncement. These significantly affect cap space calculations and will require a dedicated milestone.
4. **Multi-year salary projection** — The current model tracks only `years_remaining` and a single `salary` figure. Multi-year contracts with escalating/decreasing salaries need per-year salary breakdowns for accurate future cap projections.
5. **Trade kickers and trade bonuses** — These affect outgoing salary in trades and are not modeled. The `trade_kicker` field exists in the schema but is not used by the trade simulator.
6. **Automated snapshot refresh cadence** — How often should new snapshots be created? This is a process question, not a code question. The system supports arbitrary snapshot frequency; the cadence is determined by the operator.
7. **Data editor UI** — Long-term, a simple UI for editing/correcting snapshot data (with audit trail) would reduce manual JSON editing. Not in M8 scope.
8. **League-wide snapshot** — M8-B uses 2 teams. The eventual goal of all 30 teams requires significantly more manual data entry and verification. This is likely M9+ work.

---

## Appendix A: File change summary for M8-B (planned, not executed in M8-A)

M8-A **does not implement** any of these. They are listed here for planning purposes only.

**New files (M8-B):**
- `data/snapshots/2026-07-01/manifest.json`
- `data/snapshots/2026-07-01/source_notes.md`
- `data/snapshots/2026-07-01/normalized/teams.json`
- `data/snapshots/2026-07-01/normalized/players.json`
- `data/snapshots/2026-07-01/normalized/contracts.json`
- `data/snapshots/2026-07-01/normalized/free_agents.json`
- `data/snapshots/2026-07-01/normalized/cap_config.json`
- `data/snapshots/2026-07-01/normalized/evidence_notes.json`
- `backend/app/services/snapshot_loader.py`
- `backend/app/services/snapshot_validator.py`
- `backend/app/tests/test_snapshot_loader.py`
- `backend/app/tests/test_snapshot_validator.py`
- `backend/scripts/validate_snapshot.py`

**Modified files (M8-B):**
- `backend/app/models/cap.py` — add provenance fields to `PlayerContract`, `SalaryCapConfig`
- `backend/app/models/roster.py` — add provenance fields to `RosterPlayer`, `FreeAgentFit`
- `backend/app/models/evidence.py` — add provenance fields to `EvidenceNote`
- `backend/app/api.py` — add data mode env parsing, extend health endpoint
- `backend/app/services/cap_sheet_service.py` — support data_dir resolution (minimal change)

**Files NOT modified in M8-B:**
- No frontend files (M8-D)
- No existing demo data files (moved in M8-C)
- No business logic in rule engine, trade simulator, depth chart projector (operate on loaded contracts/rosters regardless of source)
- No proposal builder, evaluator, or agent orchestrator
