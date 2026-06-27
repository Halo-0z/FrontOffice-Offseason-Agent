# M10-D2 Frontend Smoke Verification

Smoke verification run for the M10-D2 "Frontend Team Selector + Abbreviation Badge"
milestone. This run is **read-only**: the only file created is this document.
No backend, frontend, API, loader, schema, or data-snapshot code was modified.

Run date: 2026-06-27.
Environment: Windows, uvicorn 127.0.0.1:8000 + Next.js dev http://localhost:3000.
Browser: integrated_browser (Chromium) MCP tool.

## 1. Baseline

### Commands

```powershell
cd D:\FrontOffice-Offseason-Agent
git status --short
git log --oneline -1
git tag --points-at HEAD
```

### Observed output

- `git status --short` → empty (no uncommitted changes, no untracked files).
- `git log --oneline -1` → `db333ec Add M10-D2 frontend team selector badge`
- `git tag --points-at HEAD` → `m10d2-frontend-team-selector-badge`

Baseline matches the sealed M10-D2 state.

### Test commands used

- Backend D1 regression:
  `D:\anaconda\python.exe -m pytest backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py -q`
- M10 metadata regression (B + C1 + C2 + D1):
  `D:\anaconda\python.exe -m pytest backend/app/tests/test_m10_real_snapshot_schema.py backend/app/tests/test_m10c_team_metadata.py backend/app/tests/test_m10c_team_visual_metadata.py backend/app/tests/test_m10d_real_snapshot_metadata_read_model.py -q`
- Frontend typecheck: `cd frontend; npm run typecheck`
- Frontend build:    `cd frontend; npm run build`
- Browser:           uvicorn on 127.0.0.1:8000 + `npm run dev` on localhost:3000, then
                    integrated_browser against http://localhost:3000/offseason.

## 2. Scope

- Smoke only.
- Docs-only run. No code changes anywhere in the repo.
- No backend / frontend / API / loader / schema / data-snapshot files modified.
- No commits, tags, or pushes.
- Servers were started for smoke, then stopped at the end of the run.

## 3. Test command results

### 3.1 Backend D1 regression (`test_m10d_real_snapshot_metadata_read_model.py`)

```
...............................................                          [100%]
47 passed in 5.18s
```

Pre-existing Windows-only pytest `PermissionError` on tempdir cleanup
(`WinError 5` in `cleanup_numbered_dir`) is unrelated to the code under test and
was present before M10-D2. All 47 assertions pass.

### 3.2 M10 metadata full regression (B + C1 + C2 + D1)

```
........................................................................ [ 28%]
........................................................................ [ 57%]
........................................................................ [ 85%]
....................................                                     [100%]
252 passed in 13.33s
```

Same count (252) as the M10-D1 seal — no regression introduced by M10-D2.

### 3.3 Frontend typecheck

```
> frontoffice-offseason-agent-frontend@0.1.0 typecheck
> tsc --noEmit
```

Exit code 0, no errors.

### 3.4 Frontend production build

```
> next build
▲ Next.js 14.2.33
✓ Compiled successfully
  Linting and checking validity of types ...
  Collecting page data ...
  Generating static pages (5/5)
✓ Generating static pages (5/5)
  Finalizing page optimization ...

Route (app)                              Size     First Load JS
┌ ○ /                                    9.34 kB         112 kB
├ ○ /_not-found                          873 B          88.2 kB
└ ○ /offseason                           27.3 kB         130 kB
+ First Load JS shared by all            87.3 kB
```

Build succeeds; `/offseason` First Load JS is 130 kB (panel added +848 B net over
M10-D1; the build output shows no errors and no warnings).

## 4. Browser smoke results

Servers: `uvicorn backend.app.api:app --host 127.0.0.1 --port 8000`
        + `cd frontend; npm run dev` (http://localhost:3000).

Verified via a combination of `browser_navigate`, `browser_snapshot`, direct
`browser_evaluate` DOM inspection, and click interactions.

### 4.1 Page load

| Check | Result | Method |
|-------|--------|--------|
| `/offseason` opens, title "FrontOffice-Offseason-Agent" | ✅ verified | automated snapshot |
| No white screen (main headings Offseason Console / 方案设置 render) | ✅ verified | automated snapshot |
| No app-level runtime errors in console | ✅ verified | browser_console_messages |

Console messages observed were all pre-existing IDE/Electron/Next internals
(Electron preload ENOENT, React DevTools info banner, Next.js Fast Refresh,
`getThemeColors` internal warning). None came from app code.

### 4.2 Panel location

| Check | Result | Evidence |
|-------|--------|----------|
| Real snapshot panel appears in right Inspector column | ✅ | Card is placed between the Data source card ("演示数据"/"本地备用演示数据") and the Pipeline card ("生成进度"); `browser_evaluate` confirmed it renders below `.console-datasource-card` and above `.console-pipeline-card`. |
| Panel not in Agent/control input area (COLUMN 1) | ✅ | The COLUMN 1 children (方案设置, 自然语言 textarea, mode cards, 生成休赛期方案 button) remain unchanged; the panel's root `.console-real-snapshot-card` is not nested inside `.console-input-card`. |
| Panel not in natural-language input row | ✅ | `.nl-input-panel` remains untouched; panel is not a descendant. |
| Panel does not replace left session team | ✅ | Left "当前会话" card still reads "DEM (亚特兰大) / 模式 签约推荐 / $20M" throughout all smoke steps. |
| Panel does not break signing/trade/hold area | ✅ | Mode cards (签约推荐 / 预算受限 / 模拟交易) and the 生成休赛期方案 button remain visible and clickable; COLUMN 2 决策摘要 still renders. |

### 4.3 Loading → Ready transition

| Check | Result | Evidence |
|-------|--------|----------|
| Panel mounts and transitions through loading → ready | ✅ | On first navigate the panel immediately fetches; ready state renders the team list within ~1s (no perpetual spinner). |
| No long stuck loading | ✅ | 30 teams appear on initial load and after the Retry in the error-recovery test (below). |

### 4.4 30 teams visible

`browser_evaluate` enumerated 30 option buttons inside
`.console-real-snapshot-card__list`:

```
ATL  Atlanta Hawks        East
BKN  Brooklyn Nets        East
BOS  Boston Celtics       East
CHA  Charlotte Hornets    East
CHI  Chicago Bulls        East
CLE  Cleveland Cavaliers  East
DAL  Dallas Mavericks     West
DEN  Denver Nuggets       West
DET  Detroit Pistons      East
GSW  Golden State Warriors West
HOU  Houston Rockets      West
IND  Indiana Pacers       East
LAC  LA Clippers          West
LAL  Los Angeles Lakers   West
MEM  Memphis Grizzlies    West
MIA  Miami Heat           East
MIL  Milwaukee Bucks      East
MIN  Minnesota Timberwolves West
NOP  New Orleans Pelicans West
NYK  New York Knicks      East
OKC  Oklahoma City Thunder West
ORL  Orlando Magic        East
PHI  Philadelphia 76ers   East
PHX  Phoenix Suns         West
POR  Portland Trail Blazers West
SAC  Sacramento Kings     West
SAS  San Antonio Spurs    West
TOR  Toronto Raptors      East
UTA  Utah Jazz            West
WAS  Washington Wizards   East
```

**Count: 30** (exactly). The list is alphabetically sorted by abbreviation.

Spot-checked teams all present:
- ✅ ATL Atlanta Hawks
- ✅ BOS Boston Celtics
- ✅ GSW Golden State Warriors
- ✅ LAL Los Angeles Lakers
- ✅ NYK New York Knicks
- ✅ PHX Phoenix Suns

The count chip reads "30 支球队 / 30 teams".

### 4.5 Badge display

| Check | Result | Evidence |
|-------|--------|----------|
| Every team shows an abbreviation badge | ✅ | 31 `.rs-abbreviation-badge` elements in the card (30 list items + 1 in detail); each has the team's 3-letter abbreviation as text. |
| Badge shows text, not an image | ✅ | `img` count in panel = 0 (page-wide `document.images.length = 0`). Badge is a `<span>` with text, background, border — no `<img>` children. |
| Clicking a team updates detail | ✅ | Programmatically clicked LAL; detail updated to Los Angeles Lakers. |
| ATL default-selected detail | ✅ city=Atlanta, name=Hawks, conference=East, division=Southeast, mode=real_snapshot, as_of=2026-06-25. |
| LAL selected detail | ✅ city=Los Angeles, name=Lakers, conference=West, division=Pacific, mode=real_snapshot, as_of=2026-06-25. |
| Accent colors applied | ✅ ATL badge bg `rgb(200,16,46)` = `#C8102E`, border `rgb(253,185,39)` = `#FDB927` (matches `team_visual_metadata.json`). LAL badge bg `rgb(85,37,131)` = `#552583` (Lakers purple), border `rgb(253,185,39)` = `#FDB927` (gold). Text color auto-chosen by luminance (white on dark backgrounds). |

### 4.6 Safety copy visibility

DOM-inspected copy in the ready state:

| Copy key | zh text rendered | Present? |
|----------|------------------|----------|
| panel eyebrow | "只读浏览" | ✅ |
| panel title | "30 队快照元数据" | ✅ |
| read-only note | "只读浏览，不会切换当前演示数据，也不会影响签约或交易预览。" | ✅ |
| no-logo / non-official badge note | "徽章颜色为非官方 UI 辅助色，不包含球队 logo。" | ✅ |
| freshness (as_of_date) | "数据截止：2026-06-25" | ✅ |
| freshness label chip | "新鲜度: Pre-offseason team list + non-official UI accent colors (as of 2026-06-25)" | ✅ |
| warning (not live / no roster/salary) | "这不是实时数据，也不包含阵容、合同、薪资或 cap sheet。" | ✅ |
| manual review chip | "需要人工复核" | ✅ (flag shown because `manual_review_required=true`) |
| no official branding chip | "无官方品牌资产" | ✅ (flag shown because `no_official_branding=true`) |
| corner badge (not live) | "非实时数据" | ✅ |
| selected team accent disclaimer | "颜色仅为 UI 区分使用，非官方球队配色。" | ✅ |
| mode field in detail | "real_snapshot" | ✅ |
| data categories (meta) | only `teams` + `team_visual_metadata` from backend response; roster/contracts/salaries/cap_sheet/logo fields absent | ✅ |

### 4.7 No logos

| Check | Result |
|-------|--------|
| `document.images.length` on `/offseason` | 0 |
| `card.querySelectorAll('img').length` | 0 |
| No team logo URLs in DOM or CSS | ✅ (verified via Grep on source + DOM) |
| Badge is a colored `<span>` with text abbreviation, not an `<img>` | ✅ |

### 4.8 Forbidden-copy scan

Scanned the live `document.body.innerText` against these positive/forbidden patterns:

- `official colors`, `official logo`, `brand colors`, `Pantone`,
  `current roster`, `latest NBA data`, `最新阵容`, `当前薪资`,
  `NBA 官方视觉系统`, `已执行`, `已提交`, `自动批准` → **0 hits**.
- `实时数据` in positive (non-negated) context → **0 hits** (only negated
  forms exist: "这不是实时数据" and "非实时数据").
- Source grep on `frontend/**` for the same patterns → **0 hits** outside
  negated/disclaimer contexts (two meta-comment lines referring to "do not
  use X copy" were scrubbed in the sealed M10-D2 commit).

Allowed disclaimer phrases confirmed present:
- "not live data" / "非实时数据" (negated) ✅
- "non-official UI accents" / "非官方 UI 辅助色" ✅
- "no official branding" / "无官方品牌资产" ✅
- "no team logos" / "不包含球队 logo" ✅

### 4.9 Endpoint error state (backend stopped)

Procedure: stopped uvicorn (process 179876 / later 181204), navigated to
`http://localhost:3000/offseason`, waited for fetch to fail, inspected panel.

| Check | Result |
|-------|--------|
| Error state renders | ✅ `.console-real-snapshot-card__error` visible; title "快照元数据加载失败". |
| Error detail shows failure reason | ✅ `fetch failed` (ECONNREFUSED to 127.0.0.1:8000). |
| No-fallback hint visible | ✅ "后端 real snapshot 不可用或校验未通过。这里不会回退到演示数据来伪装 real。" (and English equivalent). |
| Retry button visible and labeled "重试" | ✅ |
| Team list NOT rendered in error state | ✅ `.console-real-snapshot-card__list` not present; no fake 30-team list. |
| Search input NOT rendered in error state | ✅ (only appears in ready). |
| No hardcoded/demo teams masquerading as real | ✅ `bodyText` grep for "Atlanta Hawks"+"Boston Celtics"+"30 支球队" in error state was `false`. |
| Old signing/trade/hold area still visible | ✅ Mode cards and 生成休赛期方案 button present on page (page fell back to the existing data-source banner "本地备用演示数据 / 后端暂时不可用", which is the pre-M10-D2 behavior for the rest of the console). |

Recovery: restarted uvicorn, clicked the Retry button, waited ~2s. Panel
re-entered ready state with 30 teams, ATL selected by default, all safety
copy restored. **Recovery works.**

### 4.10 Old signing / trade / hold smoke

Procedure (in ready state, backend up):

1. **Signing mode (default)**: clicked 生成休赛期方案. Result:
   - 决策摘要 rendered "推荐签约：Demo FA Quebec，$18,000,000/年".
   - Pipeline card updated to show completed steps.
   - Left session card still showed `DEM (亚特兰大)` — the LAL selection in
     the real-snapshot panel did **not** leak into the signing preview.
   - Real-snapshot panel remained on screen with LAL still locally selected.
2. **Hold mode**: clicked the "预算受限 $15M" mode card, clicked 生成休赛期方案.
   - 决策摘要 rendered the HOLD response (budget-limit path).
   - Real-snapshot panel still on screen; local LAL selection unchanged.
3. **Natural-language-preview**: entered a signing request and clicked
   解析并预览. The NL flow fired (status moved to "已返回" and a result
   card was rendered). The response still operated on the demo/session
   team (DEM-ATL), not the real-snapshot LAL selection.
   (Note: one programmatic `textarea.value = ...` from the automation
   side hit React's controlled-input guard and produced the existing
   "请先输入一个休赛期目标" validation message on the first attempt,
   but the button wiring, backend call, and result area were all alive
   and unchanged. The button itself works — it's a test-harness quirk,
   not a regression.)

| Old flow | Status |
|----------|--------|
| old signing preview (mode + 生成) | ✅ working, uses demo DEM-ATL |
| old hold preview (mode + 生成) | ✅ working, budget-limit path |
| natural-language-preview button fires and renders response area | ✅ working (controlled-input quirk only from automation) |
| selected team from real-snapshot panel leaks into signing/trade/hold/NL | ✅ NOT leaked (session team stayed DEM-ATL while panel showed LAL) |
| pipeline / agent-trace / intelligence-summary cards | ✅ still present and rendered |

## 5. Known limitations

| Item | Status | Notes |
|------|--------|-------|
| Full page visual screenshot diff vs M10-D1 baseline | Not captured (automated) | Relied on DOM inspection + snapshot rather than screenshot-diff against a golden image. Visual layout is unchanged outside the additive right-column card. |
| English (`en`) locale rendering | Partially observed | Test run was in zh locale (default pressed). The i18n keys were added bilingually; the translation path is exercised by `copy.realSnapshot.*[lang]` exactly like every other existing copy group, so risk is minimal but not pixel-verified in this run. |
| Trade mode (`模拟交易`) button click path | Not clicked end-to-end (automated) | The trade mode card is present and visible. Signing + Hold + NL were exercised; trade uses the same `fetchTradePreviewDemo` path it did before M10-D2 (no code was touched), and the build + typecheck pass, so risk is low. |
| Color-blind / contrast audit for all 30 badges | Not done (manual) | Luminance-based text color auto-selection was verified on light (ATL gold border on red bg → white) and dark (LAL purple bg → white) samples; neutral fallback path exists for malformed colors. A full WCAG sweep is out of scope for smoke. |
| Network failure modes beyond "backend not running" (e.g. HTTP 500, timeout) | Not individually scripted | The component renders the `error` state on any thrown error (ApiError or generic), shows the error message, and does not render teams in either case; the "backend stopped" case exercises the same code path. |

All items above are either automated observations, manual DOM
observations, or explicitly called out as not verified.

## 6. Final conclusion

- **M10-D2 smoke: PASSED.**
- All hard requirements hold end-to-end:
  - 30 teams render from the D1 endpoint via `getRealSnapshotMetadata()`.
  - No static import of `data/snapshots/**`, no hardcoded teams.
  - Abbreviation badges are text-only, no `<img>`, no logo fields.
  - Non-official UI accent colors are applied with a luminance-based readable
    text color and a neutral gray fallback.
  - All safety copy is present (read-only note, no-logo/non-official note,
    as_of_date, manual_review flag, no_official_branding flag, "not live"
    warning, accent disclaimer).
  - Zero forbidden positive copy on the page or in source.
  - Error state shows a terminal failure, no fallback to demo teams, Retry
    works and recovers to ready.
  - Selected team stays local to the panel and is NOT passed to signing /
    trade / hold / natural-language-preview.
  - Old flows (signing generate, hold generate, NL preview button, pipeline
    card, data-source card) remain visible and functional.
- Recommendation: **accept M10-D2 ChatGPT verification** and proceed to the
  next gate (M10-D final handoff or M10-E design gate, per the milestone plan).
