# Final API Console Smoke Runbook (M7-D)

This runbook is the canonical "show me the final M7 system" path. It
covers the full release surface after M7-A / M7-B / M7-C: the FastAPI
backend, the Next.js API-first console, the static fallback, the
two-team trade preview, and every safety boundary the project enforces.

It is **display / verification only**. It does not add features, does
not call any LLM, does not call any MCP, does not call any real NBA
API, does not write any data file, and does not approve or execute any
transaction.

> Companion documents:
> - [demo-runbook.md](demo-runbook.md) — original M5-B CLI-only runbook.
> - [architecture.md](architecture.md) — layered architecture.
> - [agent-workflow.md](agent-workflow.md) — agent tool orchestration.
> - [final-release-snapshot.md](final-release-snapshot.md) — M5-D snapshot.

---

## 1. Current Project Capabilities

After M7-A / M7-B / M7-C, the system supports:

| Capability | Status |
|---|---|
| Sample / simulation data only (not real NBA data) | ✅ |
| FastAPI backend (`backend/app/api.py`) | ✅ |
| Next.js frontend (`frontend/`) | ✅ |
| API-first Agent Console (`/offseason`) | ✅ |
| Static fallback when backend is unavailable | ✅ |
| Signing recommendation (default scenario) | ✅ |
| Strict-budget HOLD fallback scenario | ✅ |
| Two-team trade preview (DEM-ATL ⇄ DEM-PDX) | ✅ |
| Two-team post-trade cap / roster need / depth chart | ✅ |
| Chinese / English bilingual UI | ✅ |
| No real NBA API | ✅ (boundary enforced) |
| No LLM / OpenAI API calls | ✅ (boundary enforced) |
| No MCP | ✅ (boundary enforced) |
| No data writes (`data/*.json` never mutated) | ✅ (boundary enforced) |
| Preview only — every action requires human approval | ✅ (boundary enforced) |

The system is a **deterministic, sample-data, preview-only advisor**.
It is not a real NBA tool, not a CBA simulator, not a transaction
approval system, and not a source of confirmed NBA transactions.

---

## 2. Install Dependencies

### 2.1 Backend

The project ships a minimal `requirements.txt` (FastAPI + uvicorn +
pydantic + httpx + pytest + pytest-asyncio). No LLM, no MCP, no NBA
API, no database dependencies.

```powershell
cd D:\FrontOffice-Offseason-Agent
D:\anaconda\python.exe -m pip install -r requirements.txt
```

### 2.2 Frontend

The frontend uses Next.js 14 + React 18 + TypeScript 5. No additional
dependencies need to be added — `package.json` is frozen for M7.

```powershell
cd D:\FrontOffice-Offseason-Agent\frontend
npm install
```

---

## 3. Backend Verification Commands

Run these from the repo root on Windows PowerShell. All commands are
deterministic and offline.

```powershell
cd D:\FrontOffice-Offseason-Agent

# 3.1 Full deterministic test suite
D:\anaconda\python.exe -m pytest backend/app/tests

# 3.2 Offseason CLI demo (default recommendation scenario)
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py --format json

# 3.3 Trade preview CLI demo (two-team trade with Team A + Team B post-trade)
D:\anaconda\python.exe backend/scripts/run_trade_preview_demo.py --format json

# 3.4 API import smoke (FastAPI app loads, title is correct)
D:\anaconda\python.exe -c "from backend.app.api import app; print(app.title)"
```

### Expected results

| Command | Expected |
|---|---|
| `pytest backend/app/tests` | `372 passed` (a known Windows `PermissionError` from pytest's atexit cleanup may appear after the session — it does **not** mean tests failed) |
| `run_offseason_demo.py --format json` | Valid JSON with `proposal.status: RECOMMENDED`, `evaluation.status: PASS`, `requires_human_approval: true`, `sample_data: true` |
| `run_trade_preview_demo.py --format json` | Valid JSON with `team_a_post_trade` and `team_b_post_trade` blocks; DEM-ATL cap $74M → $78M; DEM-PDX cap $74M → $70M; `requires_human_approval: true` |
| `from backend.app.api import app; print(app.title)` | `FrontOffice-Offseason-Agent API` |

---

## 4. Start the Backend API

Because port `8000` may be occupied or blocked by Windows permissions,
this runbook uses **port 8010** as the default. The frontend smoke
checks in Section 6 assume 8010.

```powershell
cd D:\FrontOffice-Offseason-Agent
D:\anaconda\python.exe -m uvicorn backend.app.api:app --host 127.0.0.1 --port 8010
```

### Health check (separate PowerShell window)

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/health
```

**Expected**:

```powershell
status      sample_data
------      -----------
ok                True
```

Leave the uvicorn process running for Sections 5–8.

---

## 5. Start the Frontend

Open a **second** PowerShell window. The frontend dev server reads
`NEXT_PUBLIC_API_BASE_URL` at startup, so it must be set before
`npm run dev`.

```powershell
cd D:\FrontOffice-Offseason-Agent\frontend
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8010"
npm run dev
```

Open in a browser:

```
http://localhost:3000/offseason
```

---

## 6. Frontend Smoke Check (API success path)

With the backend running on 8010, manually verify each scenario. The
"current data source" badge is the single most important indicator —
it must read **"当前数据来源：后端 API"** (zh) / **"Data source:
backend API"** (en) for every scenario.

| # | Action | Expected |
|---|---|---|
| 6.1 | Load `/offseason`, default language | Page renders in Chinese; hero, mode cards, input panel visible |
| 6.2 | Click the `English` toggle | All UI copy switches to English; switching back to `中文` works |
| 6.3 | Select **默认推荐 / Default Recommendation**, click **生成休赛期方案 / Generate offseason plan** | Status badge: `RECOMMENDED` + `PASS`; data source badge: `backend API`; a `SIGNING` action for `Demo FA Quebec` (C) appears |
| 6.4 | Select **严格预算 / Strict-Budget Fallback**, click **生成** | Status badge: `NO_ACTION`; a `HOLD` action appears; data source badge: `backend API` |
| 6.5 | Select **模拟交易 / Trade Preview**, click **生成** | Data source badge: `backend API`; trade teams `DEM-ATL ⇄ DEM-PDX`; salary matching `PASS` on both sides |
| 6.6 | On the trade preview, look at the **两队交易后视图 / Two-team post-trade view** section | Two cards side by side: **交易后影响（DEM-ATL）** and **交易后影响（DEM-PDX）**, each with cap / roster / depth-chart impact summaries |
| 6.7 | Expand **查看交易审计详情 / View trade audit details** | Audit sections for **both** teams appear: `DEM-ATL: cap_summary_before / cap_summary_after`, `DEM-ATL: depth_chart_after`, `DEM-ATL: roster_need_after`, `DEM-PDX: cap_summary_before / cap_summary_after`, `DEM-PDX: depth_chart_after`, `DEM-PDX: roster_need_after` |
| 6.8 | Check the risk list on the trade preview | Risks include `riskSgGap` (ATL SG gap), `riskSalaryUp` (ATL salary up), `riskTeamBCGap` (PDX C gap), `riskTeamBSalaryDown` (PDX salary down), `riskSampleData`. The old `riskTeamBDeferred` text must **not** appear |
| 6.9 | Resize the browser to ~375px width | No horizontal overflow; the two-team grid collapses to a single column |
| 6.10 | Check the footer / hero badges | `sample data`, `preview only`, `requires human approval`, `no real NBA prediction`, `no transaction execution`, `no LLM · no MCP · no external API` all visible |

If any scenario shows a blank screen, a console error, or the
`fallback` data-source badge while the backend is running, stop and
re-run Section 3.

---

## 7. Fallback Smoke Check (API unavailable path)

This verifies the static fallback payloads still render correctly when
the backend is down. The fallback is **not** the primary data source —
it only activates when the API call fails or times out (8s).

### 7.1 Stop the backend

In the uvicorn PowerShell window, press `Ctrl+C` to stop the server.
Do **not** stop the frontend `npm run dev` process.

### 7.2 Refresh and re-generate

In the browser:

1. Refresh `http://localhost:3000/offseason`.
2. For each of the three modes (default recommendation, strict-budget,
   trade preview), click **生成 / Generate**.

### 7.3 Expected fallback indicators

| Indicator | Expected value |
|---|---|
| Data source badge | **当前数据来源：本地 fallback 样例** / **Data source: local fallback sample** |
| Fallback banner | **后端 API 不可用，当前显示本地静态样例结果。** / **Backend API unavailable; showing local static sample payload.** |
| Default recommendation | `RECOMMENDED` + `PASS`, `SIGNING` action for `Demo FA Quebec` (C) |
| Strict-budget fallback | `NO_ACTION`, `HOLD` action, `no_matching_candidate` risk |
| Trade preview | Two-team view still shows both `DEM-ATL` and `DEM-PDX` post-trade cards; audit details still show both teams' cap / depth / roster need |
| Page | No blank screen, no uncaught exception, no horizontal overflow |

The fallback payloads are a **snapshot** of the CLI JSON output. They
are sample / simulation data — not real NBA data, not a prediction, not
an approved transaction.

### 7.4 Restart the backend (optional, for continued testing)

```powershell
# In the uvicorn PowerShell window
D:\anaconda\python.exe -m uvicorn backend.app.api:app --host 127.0.0.1 --port 8010
```

Refresh `/offseason` and click **生成** again — the data source badge
should flip back to **backend API**.

---

## 8. API Endpoints Reference

All endpoints are read-only, sample-data, preview-only. None of them
writes to `data/`, calls an LLM, calls MCP, or calls any external NBA
API.

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Liveness probe — returns `{"status": "ok", "sample_data": true}` |
| GET | `/api/offseason/scenarios` | Lists the three demo scenarios (default, strict-budget, trade) |
| POST | `/api/offseason/proposal-preview` | Generates a proposal preview (wraps `build_demo_payload`) |
| GET | `/api/offseason/trade-preview-demo` | Fixed two-team trade preview (wraps `run_trade_preview_demo`); includes `team_a_post_trade` and `team_b_post_trade` |

### 8.1 `proposal-preview` PowerShell example

```powershell
$body = @{
    team_id = "DEM-ATL"
    objective = "Add frontcourt help"
    target_positions = @("C")
    max_salary = 20000000
    max_candidates = 2
    evidence_query = "center need cap flexibility"
} | ConvertTo-Json

Invoke-RestMethod `
    -Method Post `
    -Uri http://127.0.0.1:8010/api/offseason/proposal-preview `
    -ContentType "application/json" `
    -Body $body
```

**Expected**: a JSON object with `proposal.status: RECOMMENDED`,
`evaluation.status: PASS`, `requires_human_approval: true`,
`sample_data: true`, at least one `SIGNING` action for `fa-005`
(`Demo FA Quebec`, C, $18M).

### 8.2 `trade-preview-demo` PowerShell example

```powershell
Invoke-RestMethod http://127.0.0.1:8010/api/offseason/trade-preview-demo
```

**Expected**: a JSON object with:

- `trade_transaction.transaction_id: "tx-trade-demo-001"`
- `trade_transaction.team_a_id: "DEM-ATL"`, `team_b_id: "DEM-PDX"`
- `salary_matching.team_a.passed: true`, `team_b.passed: true`
- `team_a_post_trade.team_id: "DEM-ATL"`,
  `team_a_post_trade.cap_summary_before.total_salary: 74000000`,
  `team_a_post_trade.cap_summary_after.total_salary: 78000000`
- `team_b_post_trade.team_id: "DEM-PDX"`,
  `team_b_post_trade.cap_summary_before.total_salary: 74000000`,
  `team_b_post_trade.cap_summary_after.total_salary: 70000000`
- `requires_human_approval: true`, `sample_data: true`

### 8.3 API ↔ CLI zero-drift guarantee

The API `trade-preview-demo` endpoint calls the same
`build_trade_preview_payload()` function as
`run_trade_preview_demo.py --format json`. The test
`test_trade_preview_demo_matches_cli_output` in
`backend/app/tests/test_api_endpoints.py` asserts the two outputs are
byte-identical. If a future change drifts them, that test fails.

---

## 9. Release Boundaries

This release is bounded by the following hard guardrails. They are
enforced by code, by tests (`test_agent_guardrails.py`), and by the
no-mutation tests. If any of these is violated, the test suite fails.

| Boundary | Status |
|---|---|
| Not a real-time NBA tool | ✅ |
| Not a complete CBA simulator (MVP salary matching only) | ✅ |
| Not a transaction approval system | ✅ |
| Does not write to `data/` files | ✅ |
| Does not call any external NBA API | ✅ |
| Does not call any LLM / OpenAI API | ✅ |
| Does not call any MCP tool | ✅ |
| All players / contracts / evidence are sample / simulation data | ✅ |
| Every action has `requires_human_approval: true` | ✅ |

A `PASS` / `RECOMMENDED` status from the evaluator or the rule engine
is **not** an approval. It only means the preview passed deterministic
guardrail checks. A human must still approve every transaction outside
the system.

---

## 10. Next Milestones (not implemented in M7-D)

M7-D is a release-polish / smoke-runbook milestone. It does not add
features. The next planned milestones are:

| Milestone | Focus | Status |
|---|---|---|
| M8-A | Real NBA Data Ingestion Design (design only — no real data connection) | not started |
| M8-B | Small Real Snapshot Import (a small, frozen, on-disk snapshot — still no live API) | not started |

M8 is **not** implemented in this release. The system still uses
sample / simulation data only. Connecting to a real NBA data source
requires a separate milestone with its own guardrail review.

---

## 11. Known Windows Notes

- **pytest atexit `PermissionError`**: on Windows, pytest may print
  `Exception ignored in atexit callback` with a `PermissionError` on
  `C:\Users\<user>\AppData\Local\Temp\pytest-of-<user>\pytest-current`
  after the test session ends. This is a known pytest cleanup issue on
  Windows and does **not** affect test results. As long as pytest
  reports `N passed`, the run is healthy.
- **Git LF → CRLF warnings**: Windows `core.autocrlf` may print
  `warning: in the working copy of '...', LF will be replaced by CRLF`
  on `git diff` / `git status`. This is expected Windows behavior and
  does not affect functionality.
- **Port 8000 may be blocked**: this runbook uses port 8010 to avoid
  conflicts. If 8010 is also unavailable, pick any free port above
  1024 and update `NEXT_PUBLIC_API_BASE_URL` accordingly.

---

## 12. Quick Verification Checklist

Use this checklist when reviewing the project on a fresh clone.

```powershell
# 1. Backend tests
cd D:\FrontOffice-Offseason-Agent
D:\anaconda\python.exe -m pytest backend/app/tests
# Expected: 372 passed

# 2. CLI demos
D:\anaconda\python.exe backend/scripts/run_offseason_demo.py --format json
# Expected: RECOMMENDED + PASS + requires_human_approval: true

D:\anaconda\python.exe backend/scripts/run_trade_preview_demo.py --format json
# Expected: team_a_post_trade + team_b_post_trade blocks present

# 3. API import
D:\anaconda\python.exe -c "from backend.app.api import app; print(app.title)"
# Expected: FrontOffice-Offseason-Agent API

# 4. Frontend
cd D:\FrontOffice-Offseason-Agent\frontend
npm run typecheck   # Expected: no errors
npm run build       # Expected: Compiled successfully

# 5. Manual smoke (browser)
# Start backend on 8010, start frontend with NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8010
# Open http://localhost:3000/offseason
# Verify: Chinese default, English toggle, three modes, two-team trade view, audit details
# Stop backend, verify fallback banner + fallback data source badge
```

If every step above passes, the M7 release is healthy and ready for
demo.
