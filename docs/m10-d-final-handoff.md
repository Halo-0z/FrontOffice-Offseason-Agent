# M10-D Final Handoff

M10-D "Real Snapshot Metadata Read Model + Frontend Team Selector + Abbreviation Badge"
closes with this handoff. This document is docs-only; it does not modify any code,
schema, loader, snapshot data, or backend/frontend behavior.

Run date: 2026-06-27.
Status tag pending: `m10d-final-handoff` (to be applied by the reviewer after ChatGPT
acceptance).

## 1. Baseline

### Current sealed commit
- **Commit:** `5c50a08 Add M10-D2 frontend smoke verification`
- **Tag:** `m10d2-frontend-smoke-verification`
- **`git status --short`:** empty (no uncommitted changes, no untracked files beyond
  this document at write time).
- **Remote:** `origin/main` synced; `m10d1-*` and `m10d2-*` tags pushed and confirmed
  in prior milestones.

### M10-D stage goal
Add an additive, **read-only** real-snapshot metadata path from backend to frontend
that:
1. Exposes 30-team identity metadata and non-official UI accent visual metadata
   through a hardened GET endpoint.
2. Renders a read-only team selector + abbreviation badge in the `/offseason`
   Inspector column.
3. Does **not** switch the default data source, does **not** touch
   rosters/contracts/salaries/cap sheets/logos, does **not** connect to the
   Agent/orchestrator/natural-language-preview decision chain, and does
   **not** add any mutation/execute/apply/commit/write capability.

M10-D was split into three sub-milestones and a docs-only smoke run:
- **M10-D1** — Backend read model (`GET /api/snapshots/metadata?snapshot_mode=real_snapshot`).
- **M10-D2** — Frontend team selector + abbreviation badge (additive `/offseason` panel).
- **M10-D2 Smoke** — End-to-end browser + regression smoke verification (docs only).
- **M10-D Final Handoff** — this document.

## 2. M10-D1 summary (Backend Read Model)

### Endpoint
```
GET /api/snapshots/metadata?snapshot_mode=real_snapshot
```
- HTTP method: **GET only**. No POST/PUT/PATCH/DELETE under `/api/snapshots/`.
- Query parameter `snapshot_mode` is **required**.
- The only accepted value is `real_snapshot`.

### Explicit opt-in / mode rejection
`demo`, `live`, `current`, `latest`, empty string, and any other value are rejected
with HTTP 400 at the HTTP layer before any disk I/O. A missing `snapshot_mode` is
rejected by FastAPI's `Query(...)` as 422. This forms a double guard (HTTP + service
`mode` pre-check).

### Hard error, no demo fallback
All failure modes raise typed errors mapped to HTTP 500 and **never** fall back to
the demo snapshot:

| Failure | Error type |
|---|---|
| real snapshot directory missing | `RealSnapshotNotFoundError` |
| `manifest.json` / `source_manifest.json` / `normalized/teams.json` / `normalized/team_visual_metadata.json` missing | `RealSnapshotNotFoundError` |
| JSON parse failure | `RealSnapshotSchemaError` |
| JSON Schema validation failure | `RealSnapshotSchemaError` |
| SHA-256 mismatch vs `source_manifest.file_hashes` | `RealSnapshotHashError` |
| Cross-reference mismatch (unknown team_id, missing team, abbreviation mismatch, team count ≠ 30, `no_official_branding != true`) | `RealSnapshotCrossReferenceError` |
| `live_eligible != false` or `manual_review_required != true` | `RealSnapshotSchemaError` |

### Files read (defence-in-depth)
Service reads exactly four files:
- `manifest.json`
- `source_manifest.json`
- `normalized/teams.json`
- `normalized/team_visual_metadata.json`

It does **not** read `players.json`, `contracts.json`, `cap_sheet*.json`,
`free_agents.json`, `draft_assets.json`, any image files, any brand/Pantone data,
or any network resource. The `normalized/` directory currently contains only the
two JSON files above; the service does not directory-walk.

### Response projection
Top-level response: `snapshot_id`, `snapshot_mode` (fixed `"real_snapshot"`),
`snapshot_type`, `season`, `as_of_date`, `freshness_label` (currently `"frozen"`),
`data_freshness_warning`, `source_name`, `manual_review_required` (fixed `true`),
`live_eligible` (fixed `false`), `no_official_branding` (fixed `true`),
`data_categories` (currently `["teams", "team_visual_metadata"]`), `limitations`,
and `teams[]` (30 entries).

Each `teams[]` entry: `team_id`, `city`, `name`, `abbreviation`, `conference`,
`division`, `visual_metadata { accent_color, secondary_accent_color, badge_style, no_official_branding }`.

### Forbidden fields (recursive scan before response)
The endpoint recursively scans the response and raises HTTP 500 if any of these
fields appear at any level:
- Data fields: `roster`, `players`, `contracts`, `salaries`, `cap_sheet`,
  `free_agents`, `draft_assets`.
- Branding: `logo_path`, `logo_url`, `official_logo`, `nba_logo`, `team_logo`,
  `mascot_image`, `official_branding`, `official_colors`, `brand_colors`,
  `pantone`, `brand_guidelines`.
- Execution: `execute`, `apply`, `commit`, `mutate`, `write`, `persist`, `save`,
  `delete`, `update`, `submit`, `auto_execute`, `auto_approve`.
- Internals: `file_hashes`, `per_file_sources`, file paths, `source_url`,
  `schema_version`.

### Unchanged existing behavior
- `snapshot_loader.py` was **not modified** and does not import the real-snapshot
  reader; it continues to load the demo historical snapshot independently.
- `data_source_resolver.py` was **not modified**.
- `/api/health`, `/api/offseason/proposal-preview`,
  `/api/offseason/trade-preview-demo`, `/api/agent/orchestrate-preview`,
  `/api/agent/classify-intent`, `/api/agent/natural-language-preview` behavior is
  unchanged and continues to use demo data.
- Default `data_mode` remains `demo`, `sample_data=true`.
- No environment-variable or loader change activates real snapshot by default.
- The endpoint is not wired into the Agent, orchestrator, natural-language-preview,
  proposal builder, trade simulator, or transaction rule engine. It does not call
  any LLM, MCP, external NBA API, or network resource.

### Test results
- M10-D1 dedicated (`test_m10d_real_snapshot_metadata_read_model.py`):
  **47 passed** (14 service positive, 6 API positive, 8 API negative, 11 hard-error
  with tmp_path isolation, 6 regression).
- M10 metadata full regression (B + C1 + C2 + D1): **252 passed** (matches the
  sealed M10-D1 count; no regression).

## 3. M10-D2 summary (Frontend Team Selector + Abbreviation Badge)

M10-D2 is additive, frontend-only, and sits inside the existing `/offseason` page.

### UI placement
- Page: `/offseason`.
- Column: COLUMN 3 (right-hand Inspector, third flex child of `.console-grid`).
- Position: between the M8-D4 "Data source" card and the existing M8-F2 "Pipeline"
  card.
- Not placed in COLUMN 1 input area, not in the natural-language textarea row, not
  in COLUMN 2 signing/trade/hold control area, not in the agent-trace/result area.
- Does not replace or move the left "session team" (DEM-ATL demo default).

### Endpoint consumption
- Exposed to frontend via `getRealSnapshotMetadata()` in `frontend/lib/apiClient.ts`.
- Sends `GET /api/snapshots/metadata?snapshot_mode=real_snapshot` (no body).
- **No static import** of `data/snapshots/**`.
- **No hardcoded 30-team list**.
- **No fallback** to `data/demoProposalPayload` or demo teams on error.

### States
Four explicit states, rendered inside the card:
- `idle` — briefly shown before the request fires.
- `loading` — in-flight GET, shows loading copy; no list/detail yet.
- `ready` — 2xx with `teams`; renders safety meta → search → team list →
  selected-team detail.
- `error` — network error or non-2xx; shows error title, error detail, explicit
  "no fallback to demo" hint, and a Retry button that re-issues the GET.

### UI content in `ready` state
- Read-only title ("30 队快照元数据" / "30-team snapshot metadata") with a "只读浏览" eyebrow.
- Read-only note: "只读浏览，不会切换当前演示数据，也不会影响签约或交易预览。"
- Safety/nologo note: "徽章颜色为非官方 UI 辅助色，不包含球队 logo。"
- Freshness row: "数据截止：{as_of_date}" (e.g. 2026-06-25) + freshness label chip.
- Warning: "这不是实时数据，也不包含阵容、合同、薪资或 cap sheet。"
- Flag chips: "需要人工复核" (`manual_review_required=true`), "无官方品牌资产"
  (`no_official_branding=true`).
- Corner badge: "非实时数据" / "Not live data".
- Search input that filters teams by city/name/abbreviation/division/conference.
- Count chip: "30 支球队 / 30 teams".
- Team list: 30 rows (alphabetical by abbreviation), each with a colored
  abbreviation badge + city/name + conference label.
- Selected-team detail: abbreviation badge, `{city} {name}`, conference
  (translated East/West), division, snapshot mode (`real_snapshot`), as-of date,
  and an "颜色仅为 UI 区分使用，非官方球队配色" disclaimer.

### Abbreviation badge / no logo
- Each team is rendered as an `AbbreviationBadge` `<span>` with the team's
  three-letter `abbreviation` as text. Background = `accent_color`,
  border = `secondary_accent_color`, text color chosen by a relative-luminance
  check (black/white) for readability.
- Invalid/missing hex → neutral gray fallback (`#6B7280` bg, `#9CA3AF` border).
- **No `<img>` tags, no logo URLs, no logo-field reads.**
- The component never uses positive/descriptive references to "official colors",
  "brand colors", "Pantone", "official logo", "NBA official visual system",
  "current roster", "latest NBA data", "实时数据" (positive), "最新阵容",
  "当前薪资", or "NBA 官方视觉系统".
- The word "live" appears only in negation: "not live data" / "非实时数据".

### Selected-team isolation
- Selected team lives **only** in component-local `useState`.
- Not lifted to the page, not written to any React context, not passed as a prop
  to any other component, not included in any request body.
- Does not change which team drives signing previews, trade previews, hold
  behavior, or the natural-language-preview request.
- Clicking a team only updates the detail card inside the same panel.

### Error behavior
- Renders the `error` state with backend error message and explicit no-fallback
  hint ("后端 real snapshot 不可用或校验未通过。这里不会回退到演示数据来伪装 real。").
- No team list, no search box, no fake data rendered in error state.
- Retry button re-issues the GET.

### Files touched (additive only)
- `frontend/lib/apiClient.ts` — added `RealSnapshotTeamVisualMetadata`,
  `RealSnapshotTeamMetadata`, `RealSnapshotMetadataResponse`, and
  `getRealSnapshotMetadata()`.
- `frontend/components/RealSnapshotTeamSelector.tsx` — new component.
- `frontend/app/offseason/page.tsx` — imports and renders
  `<RealSnapshotTeamSelector lang={lang} />` in COLUMN 3.
- `frontend/data/i18n.ts` — added `copy.realSnapshot` (bilingual).
- `frontend/app/globals.css` — added styles scoped to `.console-real-snapshot-card*`
  and `.rs-abbreviation-badge`.
- `docs/m10-d2-frontend-team-selector-badge.md` — D2 design doc.

No backend/API/loader/schema/snapshot-data files were modified in M10-D2.

## 4. M10-D2 smoke summary

Smoke was executed as a docs-only run (`docs/m10-d2-frontend-smoke-verification.md`).
Servers were started temporarily (`uvicorn` on 127.0.0.1:8000 + `npm run dev` on
localhost:3000) and stopped after the run. No code was modified.

### Test command results
| Command | Result |
|---|---|
| M10-D1 dedicated pytest (`test_m10d_real_snapshot_metadata_read_model.py`) | **47 passed** |
| M10 metadata full regression (B + C1 + C2 + D1) | **252 passed** |
| `npm run typecheck` | ✅ exit 0, no errors |
| `npm run build` | ✅ Next.js 14.2.33 compile success; `/offseason` First Load JS 130 kB |

### Browser smoke results (integrated_browser + DOM inspection)
- **Page load** ✅ `/offseason` opens, title correct, no white screen, no app-level
  runtime errors (only pre-existing IDE/Next internals in console).
- **Panel location** ✅ in right Inspector between Data source and Pipeline cards;
  not in input/NL/control areas; left session team `DEM (亚特兰大)` untouched.
- **Loading → Ready** ✅ transitions through loading to ready within ~1s; no
  perpetual spinner.
- **30 teams visible** ✅ listbox contains exactly 30 team options sorted by
  abbreviation; spot-checks passed for ATL, BOS, GSW, LAL, NYK, PHX.
- **Badge visible** ✅ 31 `.rs-abbreviation-badge` elements (30 list + 1 detail),
  all text-only `<span>`; `document.images.length === 0` inside the panel.
- **Selected team detail updates** ✅ ATL by default → clicking LAL updates detail
  to "Los Angeles Lakers / West / Pacific" with LAL's purple/gold accent colors.
- **Safety copy** ✅ read-only eyebrow+note, no-logo/non-official note, as_of_date,
  freshness label chip, warning, manual-review chip, no-official-branding chip,
  "非实时数据" corner badge, non-official accent disclaimer — all rendered.
- **No logo** ✅ zero `<img>` elements page-wide; badge is text-only.
- **Forbidden-copy scan** ✅ positive/descriptive hits for
  `official colors` / `official logo` / `brand colors` / `Pantone` /
  `current roster` / `latest NBA data` / `最新阵容` / `当前薪资` /
  `NBA 官方视觉系统` / `已执行` / `已提交` / `自动批准` = **0**;
  `实时数据` appears only in negated form.
- **Endpoint error state** ✅ stopping backend and reloading shows the error card,
  the no-fallback hint, and the Retry button; team list and search are NOT
  rendered; no hardcoded/demo 30 teams masquerade as real; old signing/trade/hold
  controls remain visible; restarting backend + clicking Retry recovers to ready
  with 30 teams.
- **Old signing preview** ✅ default signing mode + 生成休赛期方案 still returns
  the demo "推荐签约：Demo FA Quebec, $18M" response; left session team stays on
  DEM-ATL while the panel may show LAL locally (no leakage).
- **Old hold preview** ✅ budget-limit hold path still works; panel selection
  still isolated.
- **Natural-language-preview** ✅ button still fires the NL endpoint and renders
  the response area; the request uses the demo session team and ignores the
  panel's local selection.
- **Selected team does not leak** ✅ verified end-to-end by selecting LAL in the
  panel while signing/Hold/NL flows continued to operate on DEM-ATL.

### Known limitations noted in smoke
- English (`en`) locale rendering was not pixel-verified (run was in zh default);
  copy keys are added bilingually following the existing i18n pattern.
- Trade mode card (`模拟交易`) was not clicked end-to-end; signing + hold + NL
  were exercised. Trade uses the unchanged `fetchTradePreviewDemo` path; typecheck
  and build pass.
- Network-failure permutations beyond "backend not running" (HTTP 500, timeout)
  were not individually scripted; they exercise the same `error` branch.

## 5. Current security boundaries

These invariants hold at the M10-D seal and must not be weakened by any follow-on
milestone without an explicit design gate:

- **Demo mode remains the default.** `/api/health` still reports
  `data_mode="demo", sample_data=true`. No environment flag or loader change
  auto-enables real snapshot.
- **Real snapshot is read-only metadata only.** It exposes team identity and
  non-official UI accent colors. It does **not** include or imply any live data,
  player, roster, contract, salary, cap-sheet, draft-asset, free-agent, or logo
  payload.
- **Real snapshot does not participate in trades/signings.** No proposal, trade,
  hold, or natural-language-preview path reads from or writes to the real-snapshot
  endpoint.
- **The Agent / LLM does not use real snapshot for decisions.** The endpoint is
  not wired into `agent_orchestrator`, `agent_intent_classifier`,
  `agent_natural_language_preview`, `proposal_builder`, `trade_simulator`, or
  `transaction_rule_engine`, and it does not call any LLM or external API.
- **No trades or signings are executed.** All preview paths remain read-only as
  sealed in M9; M10-D does not add any execution path.
- **No roster/contract/salary/cap-sheet mutation.** M10-D does not read or write
  any of these structures.
- **No logos.** No team logo image, NBA logo, mascot image, or logo URL is read,
  projected, or rendered. Badge is a text abbreviation on a non-official accent
  color.
- **No official colors / brand colors / Pantone.** Accent colors are explicitly
  labeled "non-official UI accents" in both backend limitations and frontend copy;
  the recursive response scan rejects any `official_colors` / `brand_colors` /
  `pantone` fields.
- **No live/current/latest/real-time claim.** `live_eligible=false` is enforced at
  the schema and response level; freshness label is `frozen`; UI shows "非实时数据"
  and "这不是实时数据" prominently.
- **No execute/apply/commit/mutate/write endpoint.** `/api/snapshots/` exposes only
  `GET /api/snapshots/metadata`; OpenAPI confirms no other method; recursive
  response scanning rejects any execution-named field.
- **Manual review required.** `manual_review_required=true` is enforced at the
  schema level and surfaced in the UI as a chip.
- **No official branding.** `no_official_branding=true` is enforced at the schema
  level (both per-team and top-level) and surfaced as a chip.

## 6. Key file inventory

### M10-D1 (backend read model)
- [real_snapshot_metadata_reader.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/services/real_snapshot_metadata_reader.py) — service
  that loads, validates, hash-checks, cross-references, and projects the real
  snapshot metadata; defines `RealSnapshotMetadataError` / `NotFoundError` /
  `SchemaError` / `HashError` / `CrossReferenceError`; implements forbidden-field
  recursive scan and DTO projection.
- [test_m10d_real_snapshot_metadata_read_model.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py)
  — 47 tests covering service positive, API positive, API negative, hard-error,
  and regression cases.
- Design doc: [m10-d-real-snapshot-metadata-read-model.md](file:///D:/FrontOffice-Offseason-Agent/docs/m10-d-real-snapshot-metadata-read-model.md).

Supporting (pre-existing, not modified in M10-D1/D2):
- `backend/app/api.py` — adds the `GET /api/snapshots/metadata` route that
  delegates to the reader.
- `data/snapshots/nba_real_2026_preoffseason_v1/manifest.json`
- `data/snapshots/nba_real_2026_preoffseason_v1/source_manifest.json`
- `data/snapshots/nba_real_2026_preoffseason_v1/normalized/teams.json`
- `data/snapshots/nba_real_2026_preoffseason_v1/normalized/team_visual_metadata.json`
- Regression tests carried over from M10-B/C1/C2 (schema, team metadata, team
  visual metadata).

### M10-D2 (frontend selector + badge)
- [apiClient.ts](file:///D:/FrontOffice-Offseason-Agent/frontend/lib/apiClient.ts) —
  adds `RealSnapshotTeamVisualMetadata`, `RealSnapshotTeamMetadata`,
  `RealSnapshotMetadataResponse`, and `getRealSnapshotMetadata()`.
- [RealSnapshotTeamSelector.tsx](file:///D:/FrontOffice-Offseason-Agent/frontend/components/RealSnapshotTeamSelector.tsx)
  — new `"use client"` component implementing idle/loading/ready/error states,
  search, abbreviation badge with luminance text color + neutral fallback,
  local-only selected team, and retry-on-error.
- [page.tsx](file:///D:/FrontOffice-Offseason-Agent/frontend/app/offseason/page.tsx)
  — imports and renders `<RealSnapshotTeamSelector lang={lang} />` in COLUMN 3;
  no other behavior change.
- [i18n.ts](file:///D:/FrontOffice-Offseason-Agent/frontend/data/i18n.ts) — adds
  `copy.realSnapshot` (bilingual) covering panel title, read-only note, safety
  note, freshness, warning, manual review, no official branding, not-live corner
  badge, accent disclaimer, states, and error hints.
- [globals.css](file:///D:/FrontOffice-Offseason-Agent/frontend/app/globals.css) —
  adds styles scoped to `.console-real-snapshot-card*` and `.rs-abbreviation-badge`.
- Design doc: [m10-d2-frontend-team-selector-badge.md](file:///D:/FrontOffice-Offseason-Agent/docs/m10-d2-frontend-team-selector-badge.md).

### Smoke
- [m10-d2-frontend-smoke-verification.md](file:///D:/FrontOffice-Offseason-Agent/docs/m10-d2-frontend-smoke-verification.md)
  — end-to-end browser + regression smoke log (47/252 backend tests, typecheck,
  build, browser checks for load/panel location/loading-30 teams/badge/safety
  copy/no-logo/forbidden copy/error fallback/old signing+hold+NL flows).

## 7. Verification commands

To reproduce the M10-D seal locally:

```powershell
cd D:\FrontOffice-Offseason-Agent

# 1. Baseline
git status --short
git log --oneline -1
git tag --points-at HEAD

# 2. Backend M10-D1 dedicated regression
D:\anaconda\python.exe -m pytest backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py -q

# 3. Backend M10 metadata full regression (B + C1 + C2 + D1)
D:\anaconda\python.exe -m pytest backend/app/tests/test_m10_real_snapshot_schema.py backend/app/tests/test_m10c_team_metadata.py backend/app/tests/test_m10c_team_visual_metadata.py backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py -q

# 4. Frontend typecheck
cd frontend
npm run typecheck

# 5. Frontend production build
npm run build
cd ..

# 6. Browser smoke checklist (manual/automated against http://localhost:3000/offseason)
#    a. Start servers:
#       D:\anaconda\python.exe -m uvicorn backend.app.api:app --host 127.0.0.1 --port 8000
#       cd frontend; npm run dev
#    b. /offseason loads without white screen or console errors.
#    c. Right Inspector shows "30 队快照元数据" card between Data source and Pipeline.
#    d. Card transitions loading → ready; "非实时数据" corner badge visible.
#    e. Safety copy visible: read-only note, no-logo/non-official note, as_of_date,
#       warning, manual-review chip, no-official-branding chip, accent disclaimer.
#    f. 30 teams listed; abbreviation badges are colored text chips (no <img>);
#       clicking a team updates the detail card.
#    g. Forbidden-copy scan (manual grep on body text and frontend/** source):
#       official colors / official logo / brand colors / Pantone / current roster /
#       latest NBA data / 最新阵容 / 当前薪资 / NBA 官方视觉系统 / 已执行 / 已提交 /
#       自动批准 must have 0 positive hits; "实时数据" must only appear negated.
#    h. Stop backend → reload → panel shows error + no-fallback hint + Retry;
#       no fake team list; signing/trade/hold controls remain visible; restart
#       backend + Retry → recovers to ready with 30 teams.
#    i. Generate signing preview, hold preview, NL preview; confirm panel's
#       locally selected team does not leak into demo flows (session team stays DEM-ATL).
```

## 8. Known limitations (at M10-D close)

- **Team metadata only.** Roster (players), contracts, salaries, cap sheets,
  free agents, and draft assets are out of scope. The real-snapshot endpoint
  returns none of these fields and actively rejects them.
- **Non-official UI accent badge only.** Badge colors are labeled as non-official
  UI accents, not team/brand colors. There are no logos, no mascot images, no
  Pantone/brand-guideline data.
- **Snapshot metadata, not live data.** `freshness_label="frozen"`,
  `live_eligible=false`, `as_of_date=2026-06-25`. UI shows "非实时数据" prominently.
- **Selected team is panel-local.** It does not drive any proposal, trade, hold,
  natural-language-preview, or Agent decision; selection does not leave the
  component.
- **No real players, contracts, salaries, cap sheets.** No real player identities,
  contract terms, salary figures, or cap-sheet numbers are loaded, projected, or
  rendered anywhere in the app under M10-D. The demo roster/salary data is
  unchanged and remains sample/demo only.
- **No mutation surface.** `/api/snapshots/` exposes GET only. No execute, apply,
  commit, mutate, write, persist, save, delete, update, or submit endpoint exists
  on this path.
- **English locale rendering** was not pixel-verified in smoke (run was in zh
  default); copy keys are present bilingually.
- **Trade mode button** was not clicked end-to-end in smoke; signing + hold + NL
  were exercised and passed.

## 9. Recommended next steps (M10-E Design Gate)

M10-D closes with a minimal, hardened, read-only metadata path. **M10-E must
NOT jump directly into real roster/salary code.** It must open with a
**design gate** that decides whether and how to extend the real-snapshot surface.

Required M10-E design-gate agenda:

1. **Player identity schema.** Whether to add a `players.json` (or
   `player_identities.json`) normalized file under the real snapshot, what fields
   are allowed (player_id, name, position, height/weight, college/country, draft,
   etc.), and what fields remain forbidden (e.g. biometric/PII beyond standard
   basketball-reference identity).
2. **Roster schema.** Whether to add `rosters.json` (team → player_id[] with
   role/status), the schema for contract-status flags (two-way, Exhibit 10, etc.),
   and how to cross-reference against `players.json`.
3. **Contracts/salaries schema.** Whether and how to model contracts and
   cap-sheet figures; this is the highest-risk surface and must have its own
   `manual_review_required=true`, `live_eligible=false`, source-name, and
   freshness-label contract, plus a recursive forbidden-field scan and
   per-file hash checks mirroring M10-D1.
4. **Docs/schema-first continuation.** M10-E should continue the
   docs/schema/loader order used in M10-B/C/D: schema doc → normalized JSON seed
   → loader unit tests → service read model → frontend panel. No code-first data
   files.
5. **GPT-5.5 design gate.** Run the M10-E design gate through GPT-5.5 to decide:
   - Whether to take player identity + roster first, defer contracts/salaries.
   - Whether to introduce additional snapshot modes (e.g. `real_roster`,
     `real_contracts`) as separate GET endpoints rather than extending the
     metadata endpoint.
   - Whether to require a `data_category` allowlist per endpoint.
6. **GLM risk review.** After GPT-5.5 signs off, run a GLM risk review focused on:
   - Branding/logo regressions (ensuring `no_official_branding=true` and the
     recursive forbidden-field scan stay intact when new files are added).
   - Forbidden-copy regressions in any new UI copy.
   - No accidental mutation surface being added alongside new read endpoints.
   - Agent/LLM isolation — new real endpoints must remain read-only metadata and
     must not be auto-wired into orchestrator/proposal/trade paths without an
     explicit future milestone gate.
   - Demo-mode default invariant — no env/loader change flips default to real.

Until M10-E design gate completes, M10-D remains the authoritative real-snapshot
surface: **team identity + non-official UI accent metadata only, GET-only, no
fallback, no mutation, no Agent coupling, no roster/salary/logo exposure.**

## 10. Final conclusion

- **M10-D is closed.**
- **M10-D1** (backend read model) is sealed at commit `7e36cb3` / tag
  `m10d1-real-snapshot-metadata-read-model`; 47 dedicated tests pass and 252 M10
  metadata regression tests pass.
- **M10-D2** (frontend team selector + abbreviation badge) is sealed at commit
  `db333ec` / tag `m10d2-frontend-team-selector-badge`; typecheck and production
  build pass.
- **M10-D2 Smoke** is sealed at commit `5c50a08` / tag
  `m10d2-frontend-smoke-verification`; browser smoke confirms load, panel
  location, loading→ready, 30 teams, abbreviation badge (text-only, no logo),
  safety copy, forbidden-copy cleanliness, error fallback with no demo masquerade,
  and unchanged signing/hold/natural-language-preview flows with selected-team
  isolation.
- Security boundaries hold: demo default, real snapshot is read-only metadata
  only, no Agent/LLM coupling, no trades/signings executed, no
  roster/contracts/salary/cap-sheet reads or writes, no logos, no
  official/brand/Pantone colors, no live/current/latest claim, no
  execute/apply/commit/mutate/write endpoint.

**Reviewer next step:** run ChatGPT acceptance against this document and the
sealed commits; after acceptance, commit this handoff document and apply tag
`m10d-final-handoff`. Do **not** open M10-E code work until the M10-E design
gate (Section 9) is complete.
