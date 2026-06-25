# M8-D3 Snapshot Mode Smoke Runbook

## 任务名称

M8-D3 Snapshot Mode Smoke Runbook

## 当前 snapshot_id

```
nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25
```

## 概述

本 runbook 验证 backend 在 `DATA_MODE=snapshot` 下能正确识别并报告 M8-D2 新增的 2025-26 历史 source-backed NBA snapshot。本轮**不改变推荐逻辑**，`proposal-preview` / `trade-preview-demo` 暂时仍保持 demo flow。snapshot 是 2025-26 historical source-backed，**不是** 2026 offseason current state。

## 前置条件

1. 项目路径: `D:\FrontOffice-Offseason-Agent`
2. Python: `D:\anaconda\python.exe` (3.12.7)
3. 已封口里程碑:
   - M8-B (snapshot validator / loader)
   - M8-C1/C2 (data source resolver / /api/health metadata)
   - M8-D1 (frontend console shell)
   - M8-D2 (historical NBA snapshot)
4. snapshot 目录存在:
   ```
   data/snapshots/nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25/
   ```
5. 端口 8000 未被占用。

## Step 1: 验证 snapshot CLI

### 1a. 用 --path 验证

```powershell
cd D:\FrontOffice-Offseason-Agent
D:\anaconda\python.exe backend/scripts/validate_snapshot.py --path data/snapshots/nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25
```

### 1b. 用 --snapshot-id + --data-root 验证

```powershell
D:\anaconda\python.exe backend/scripts/validate_snapshot.py --snapshot-id nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25 --data-root data/snapshots
```

### 预期输出

```json
{
  "snapshot_id": "nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25",
  "manifest_status": "ok",
  "is_valid": true,
  "errors": [],
  "warnings": [
    "player 'nba-phx-dillon-brooks' has no contract on file",
    "teams 'nba-GSW' has manual_review_required=true",
    ...
  ],
  "row_counts": {
    "teams": 2,
    "players": 10,
    "contracts": 9,
    "free_agents": 0,
    "cap_config": 1,
    "evidence_notes": 5
  }
}
```

exit code: 0

### 可接受 warnings

- `player 'nba-phx-dillon-brooks' has no contract on file` — Dillon Brooks 因 source pack 标注 cap hit/incentive 映射冲突，刻意不写入 contracts.json
- `manual_review_required=true` — 所有 row 均为 provisional source-backed 数据，manual_review_required=true 是预期行为

### 不可接受错误

- `is_valid: false`
- `errors` 非空
- `snapshot_id` 不匹配
- `manifest_status` 非 `ok`

## Step 2: 设置 PowerShell 环境变量

```powershell
$env:DATA_MODE="snapshot"
$env:DATA_SNAPSHOT_ID="nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25"
$env:DATA_ROOT="data/snapshots"
```

### 环境变量说明

| 变量 | 值 | 说明 |
|------|-----|------|
| `DATA_MODE` | `snapshot` | 启用 snapshot mode |
| `DATA_SNAPSHOT_ID` | `nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25` | 要加载的 snapshot id |
| `DATA_ROOT` | `data/snapshots` | snapshot 根目录（相对项目根） |

注意: `SNAPSHOT_ALLOW_TEST_FIXTURE` 不需要设置。M8-D2 snapshot 的 `snapshot_type` 是 `historical_source_backed`，不是 `test_fixture`，因此不受此 flag 限制。

## Step 3: 启动 snapshot mode backend

```powershell
cd D:\FrontOffice-Offseason-Agent
D:\anaconda\python.exe -m uvicorn backend.app.api:app --host 127.0.0.1 --port 8000 --reload
```

### 预期启动日志

```
INFO:     Will watch for changes in these directories: ['D:\\FrontOffice-Offseason-Agent']
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [...]
INFO:     Started server process [...]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

## Step 4: 检查 /api/health

另开一个 PowerShell 窗口:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health | ConvertTo-Json -Depth 8
```

### 预期输出

```json
{
  "status": "ok",
  "sample_data": false,
  "service": "frontoffice-offseason-agent",
  "data_mode": "snapshot",
  "active_data_source": "snapshot:nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25",
  "snapshot_id": "nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25",
  "snapshot_valid": true,
  "snapshot_is_fixture": false,
  "snapshot_type": "historical_source_backed",
  "snapshot_warnings": [
    "player 'nba-phx-dillon-brooks' has no contract on file",
    "teams 'nba-GSW' has manual_review_required=true",
    ...
  ],
  "fallback_reason": null,
  "strict_snapshot": false
}
```

### 必须检查的字段

| 字段 | 预期值 | 说明 |
|------|--------|------|
| `status` | `ok` | snapshot 加载成功，不 degraded |
| `sample_data` | `false` | 当前是 real/source-backed snapshot，非 demo |
| `data_mode` | `snapshot` | snapshot mode 生效 |
| `active_data_source` | `snapshot:nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25` | 数据源标签 |
| `snapshot_id` | `nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25` | 必须匹配 |
| `snapshot_valid` | `true` | snapshot 通过 validator |
| `snapshot_is_fixture` | `false` | 非 test_fixture |
| `snapshot_type` | `historical_source_backed` | snapshot 类型 |
| `fallback_reason` | `null` | 无 fallback |
| `strict_snapshot` | `false` | 非 strict mode |

### 不可接受情况

- `datasource` 仍显示 `demo`
- `snapshot_id` 不匹配
- `sample_data` 被误报为 `true`
- `is_valid` / `snapshot_valid` 为 `false`
- `fallback_reason` 非空（除非刻意测试 fallback 场景）

## Step 5: 可选 — 检查业务 API 不被误改

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/offseason/scenarios | ConvertTo-Json -Depth 8
Invoke-RestMethod http://127.0.0.1:8000/api/offseason/trade-preview-demo | ConvertTo-Json -Depth 8
```

### 预期行为

- endpoint 不崩溃，返回 200
- `scenarios` 返回 demo scenarios（signing_recommendation / strict_budget_hold / trade_preview_demo）
- `trade-preview-demo` 返回 demo trade data（DEM-ATL <-> DEM-PDX）
- 这些 endpoint **仍然使用 demo flow**，不使用 snapshot 数据。这是 M8-D3 阶段可接受的行为，snapshot 接入业务流程留待后续里程碑。

## Step 6: 停止 backend

在运行 uvicorn 的 PowerShell 窗口按 `Ctrl+C`，或关闭窗口。

## 明确说明

1. **M8-D3 不改变推荐逻辑**: `proposal-preview` / `trade-preview-demo` / agent orchestrator 仍读 demo data。
2. **proposal-preview / trade-preview-demo 暂时仍可保持 demo flow**: snapshot 数据接入业务流程留待后续里程碑。
3. **snapshot 是 2025-26 historical source-backed，不是 2026 offseason current state**: 这是第一份小型 provisional snapshot，用于验证数据管线，非完整 roster/payroll。
4. **manual_review_required=true 是预期行为**: 所有 row 均为 third-party 整理数据，需要人工核验。

## 可接受 warnings 汇总

| Warning | 原因 |
|---------|------|
| `player 'nba-phx-dillon-brooks' has no contract on file` | Dillon Brooks 因 source pack cap hit/incentive 映射冲突，刻意不写入 contracts.json |
| `manual_review_required=true` (所有 row) | provisional source-backed snapshot，所有数据需人工核验 |

## 不可接受错误汇总

| 错误 | 含义 |
|------|------|
| `is_valid: false` | snapshot 校验失败 |
| `errors` 非空 | 有 fatal error |
| `snapshot_id` 不匹配 | 加载了错误的 snapshot |
| `datasource` 仍显示 `demo` | snapshot mode 未生效 |
| `sample_data` 被误报为 `true` | snapshot 被误判为 demo data |

## 测试命令

```powershell
cd D:\FrontOffice-Offseason-Agent

D:\anaconda\python.exe -m pytest backend/app/tests/test_data_source_resolver.py -v
D:\anaconda\python.exe -m pytest backend/app/tests/test_api_health_datasource.py -v
D:\anaconda\python.exe -m pytest backend/app/tests/test_validate_snapshot_cli.py -v
D:\anaconda\python.exe -m pytest backend/app/tests/test_snapshot_loader.py -v
D:\anaconda\python.exe -m pytest backend/app/tests/test_snapshot_validator.py -v
D:\anaconda\python.exe -m pytest backend/app/tests

cd D:\FrontOffice-Offseason-Agent\frontend
npm run typecheck
npm run build
```

## 参考

- M8-B: snapshot validator / loader (`backend/app/services/snapshot_validator.py`, `snapshot_loader.py`)
- M8-C1/C2: data source resolver (`backend/app/services/data_source_resolver.py`)
- M8-D2: historical NBA snapshot (`data/snapshots/nba_2025_26_hist_gsw_phx_sourcepack_2026_06_25/`)
- API endpoints: `backend/app/api.py`
