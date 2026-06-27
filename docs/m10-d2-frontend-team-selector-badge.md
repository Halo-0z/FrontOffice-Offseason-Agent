# M10-D2 Frontend Team Selector + Abbreviation Badge

Additive, read-only frontend wiring that sits in the `/offseason` page's right-hand
Inspector column and lets a user browse 30-team identity metadata returned by the
M10-D1 endpoint `GET /api/snapshots/metadata?snapshot_mode=real_snapshot`.

This milestone is **frontend-only**. It does not touch backend, loaders, schema,
snapshot data, or any of the M8/M9 signing/trade/hold/natural-language-preview
flows.

## 1. UI location

- Page: `/offseason`
- Column: COLUMN 3 — right-hand Inspector column (`console-grid` → third flex child)
- Position: directly below the M8-D4 "Data source" card (`console-datasource-card`)
  and above the existing M8-F2 "Pipeline" card (`console-pipeline-card`).
- Component: `frontend/components/RealSnapshotTeamSelector.tsx`, default-exported.
- NOT placed in:
  - COLUMN 1 input configuration area (no interference with team/objective/position/natural-language inputs)
  - COLUMN 2 signing/trade/hold control area (no overlap with old preview buttons)
  - The natural-language textarea row
  - The agent-trace / intelligence-summary / result area

## 2. Endpoint

- `GET /api/snapshots/metadata?snapshot_mode=real_snapshot`
- Exposed to frontend via `getRealSnapshotMetadata()` in `frontend/lib/apiClient.ts`.
- Request has no body; `snapshot_mode=real_snapshot` is mandatory.
- Backend enforces:
  - `demo`/`live`/`current`/`latest` are rejected with HTTP 400.
  - Missing files, schema mismatch, hash mismatch, xref mismatch → HTTP 500.
  - No fallback to demo.
  - Response projection excludes `roster`, `contracts`, `salaries`,
    `cap_sheet`, `free_agents`, `draft_assets`, `logo`, file hashes, and
    file-system paths.

## 3. States

The panel has four explicit states, all rendered inside the card:

| State     | Trigger                              | UI                                                                  |
| --------- | ------------------------------------ | ------------------------------------------------------------------- |
| `loading` | In-flight GET request                | Shows `stateLoading` copy, no list/detail.                          |
| `ready`   | Successful 2xx response with `teams` | Safety meta → search → team list → selected-team detail.            |
| `error`   | Network error or non-2xx response    | `stateError` title, error detail, `errorHint` (no-fallback note), and a `retry` button. |
| `idle`    | Pre-mount (transitioned immediately) | Briefly shown before request fires.                                 |

The component auto-fetches on mount and exposes a "Retry" button in the error state.

## 4. Safety copy (bilingual)

All copy is centralized in `frontend/data/i18n.ts` under `copy.realSnapshot`:

- `panelTitle` — "30 队快照元数据" / "30-team snapshot metadata"
- `readOnlyNote` — "只读浏览，不会切换当前演示数据，也不会影响签约或交易预览。" /
  "Read-only browser. This does not switch the active demo data or affect signing/trade previews."
- `safetyNote` — "徽章颜色为非官方 UI 辅助色，不包含球队 logo。" /
  "Badge colors are non-official UI accents. No team logos are included."
- `freshness` — "数据截止：{date}" / "As of {date}" (interpolated from `as_of_date`)
- `warning` — "这不是实时数据，也不包含阵容、合同、薪资或 cap sheet。" /
  "This is not live data and does not include rosters, contracts, salaries, or cap sheets."
- `manualReview` — "需要人工复核" / "Manual review required"
- `noOfficialBranding` — "无官方品牌资产" / "No official branding"
- `notLive` — "非实时数据" / "Not live data" (corner badge)
- `accentDisclaimer` — "颜色仅为 UI 区分使用，非官方球队配色。" /
  "Colors are for UI differentiation only and are not official team colors."
- `errorHint` — explains that there is **no fallback to demo data**.

## 5. Non-official UI accent badge / no logo

- Each team is rendered with an `AbbreviationBadge` that shows the team's three-letter
  `abbreviation` as text inside a small colored chip.
- Colors come from `visual_metadata.accent_color` (background) and
  `visual_metadata.secondary_accent_color` (border). These are treated as
  **non-official UI accents only**.
- The text color is chosen automatically for readability (relative-luminance check
  on the background → black or white).
- If a color is missing, empty, or not a valid `#RRGGBB` hex value, the badge falls
  back to neutral gray (`#6B7280` bg, `#9CA3AF` border).
- **No `<img>` tags, no logo URLs, no references to logo fields anywhere in the
  component.** The backend also strips `logo` from the response.
- We never use the words "official colors", "brand colors", "Pantone",
  "official logo", "official visual system", "current roster", "latest NBA data",
  "实时数据", "最新阵容", "当前薪资", or "NBA 官方视觉系统".
- The word "live" only appears in the **negative**: "not live data" / "非实时数据".

## 6. Selected team is local to this panel

- Selected team id is stored in **component-local `useState` only**.
- It is **NOT** lifted to the page, **NOT** written to any context, **NOT** passed
  as a prop to any other component, and **NOT** included in any request body.
- It does not:
  - change which team drives signing previews
  - change which team drives trade previews
  - change the hold button behavior
  - change the natural-language-preview request
  - change the `selectedPlayer`/`objective`/`position`/`candidates` inputs
  - trigger an orchestrator call
- Clicking a team only updates the detail card inside the same panel.

## 7. Error behavior — no demo fallback

- On fetch failure the panel renders the `error` state with the backend error
  message and an explicit "no fallback to demo" hint.
- The component does **not** import `data/snapshots/**` statically.
- It does **not** hardcode 30 teams.
- It does **not** fall back to demo data, hardcoded team lists, or
  `data/demoProposalPayload` and relabel that as "real".
- The Retry button simply re-issues the GET request.

## 8. Smoke checklist

Before closing M10-D2, verify in the browser:

- [ ] `/offseason` loads without console errors.
- [ ] A new card "30 队快照元数据 / 30-team snapshot metadata" appears in the
      right Inspector column, between the Data source card and the Pipeline card.
- [ ] On initial load the card shows `stateLoading`, then transitions to `ready`
      (or `error` if the backend is unavailable).
- [ ] In the `ready` state:
  - [ ] The "not live / 非实时数据" corner badge is visible.
  - [ ] `readOnlyNote`, `safetyNote`, and `warning` are all visible.
  - [ ] `as_of_date` is shown in the freshness row.
  - [ ] When `manual_review_required` is true, a "Manual review required"
        chip is shown.
  - [ ] When `no_official_branding` is true, a "No official branding" chip
        is shown.
  - [ ] The search input filters teams by city/name/abbreviation/division/conference.
  - [ ] The team list shows 30 teams when the search box is empty
        (count chip reads "30 teams" / "30 支球队").
  - [ ] Each team row shows a colored abbreviation badge (text = abbreviation,
        no `<img>`).
  - [ ] Clicking a team row updates the selected-team detail card below the list.
  - [ ] The selected-team detail shows abbreviation badge, city+name,
        conference (translated East/West), division, snapshot mode, and as_of date.
  - [ ] The "Colors are non-official UI accents…" disclaimer is visible under
        the detail grid.
- [ ] In the `error` state:
  - [ ] The card shows the error message, the "no fallback to demo" hint,
        and a Retry button.
  - [ ] No team list is rendered and no fake/hardcoded data is shown.
- [ ] Forbidden-copy scan — the page and source files do NOT contain
      (in positive/descriptive context):
      - "已执行", "已提交", "自动批准"
      - "official colors", "official logo", "brand colors", "Pantone",
        "NBA official visual system", "current roster", "latest NBA data"
      - "实时数据" (positive), "最新阵容", "当前薪资", "NBA 官方视觉系统"
  - The phrase "not live data" / "非实时数据" is allowed only as a negation.
- [ ] Old flows unchanged:
  - [ ] The signing preview (`DemoSigningPreview`) button still fires `fetchProposalPreview`.
  - [ ] The trade preview (`DemoTradePreview`) button still fires `fetchTradePreviewDemo`.
  - [ ] The Hold button still shows the hold block message.
  - [ ] The natural-language preview textarea + button still fires
        `fetchNaturalLanguagePreview` and renders its result.
  - [ ] The Pipeline card, Agent Trace card, and Intelligence Summary still
        render exactly as before.
  - [ ] The left "Session Team" (ATL / DEM) display still reads from the
        demo default (`DEM_PROPOSAL_REQUESTS[0]`) and is not mutated.

## 9. Old flows must remain unchanged

This milestone is strictly additive. The following invariants must hold:

- `POST /api/agent/proposal-preview-demo` is unchanged.
- `POST /api/agent/trade-preview-demo` is unchanged.
- `GET /api/health` is unchanged.
- `POST /api/agent/natural-language-preview` is unchanged.
- The demo-preset buttons (Signing preview / Trade preview / Hold) use the same
  hardcoded request payloads they used before M10-D2.
- `DEMO_PROPOSAL_REQUESTS[0].team_id` (ATL) remains the "session team" for all
  existing demo preview flows.
- No new mutation, execution, apply, or commit capability is introduced.
- The orchestrator is not called from the new panel.

## 10. Files touched

- `frontend/lib/apiClient.ts` — adds `RealSnapshotTeamVisualMetadata`,
  `RealSnapshotTeamMetadata`, `RealSnapshotMetadataResponse`, and
  `getRealSnapshotMetadata()`.
- `frontend/components/RealSnapshotTeamSelector.tsx` — new component.
- `frontend/app/offseason/page.tsx` — imports and renders
  `<RealSnapshotTeamSelector lang={lang} />` in COLUMN 3.
- `frontend/data/i18n.ts` — adds `copy.realSnapshot` (bilingual).
- `frontend/app/globals.css` — adds section 27 styles scoped to
  `.console-real-snapshot-card*` and `.rs-abbreviation-badge`.
- `docs/m10-d2-frontend-team-selector-badge.md` — this file.

No backend/API/schema/loader/snapshot-data files are modified.
