# M8-E5 Orchestrator Preview API Smoke Runbook

## 当前基线

```
commit: dba518b Add M8-E5 orchestrator preview API
tag:    m8e5-orchestrator-preview-api
endpoint: POST /api/agent/orchestrate-preview
```

## 这份 Runbook 的目的

本 runbook 用白话说明如何本地验证 `POST /api/agent/orchestrate-preview` 是一个**安全的 preview-only API**。

具体要确认的是：

1. 这个 endpoint 只会生成**只读预览**，不会执行任何签约或交易。
2. 它不会修改 roster、contracts、cap state，也不会写入 snapshot 文件。
3. 它不连接 LLM、不连接真实 NBA API、不做 scraping。
4. 所有响应的 `requires_human_approval` 字段始终为 `true`。
5. 不支持的 intent 会被阻断返回 hold/blocked，不会被猜成 signing 或 trade。
6. metadata 中出现 execute/apply/commit/mutate/write/persist 等 mutation 语义字段时，会直接返回 HTTP 400。

这不是完整的自主 Agent，不是执行系统，这只是一层很薄的 HTTP adapter，把已有的 deterministic preview 能力暴露出来。

---

## Step 0: 前置条件

1. 项目路径：`D:\FrontOffice-Offseason-Agent`
2. Python：`D:\anaconda\python.exe`
3. 端口 8000 未被占用。
4. 已封口里程碑：M8-E5-A（service orchestrator stub）、M8-E5-B（API exposure）。

---

## Step 1: 启动后端

PowerShell：

```powershell
cd D:\FrontOffice-Offseason-Agent
D:\anaconda\python.exe -m uvicorn backend.app.api:app --host 127.0.0.1 --port 8000 --reload
```

预期：看到 `Uvicorn running on http://127.0.0.1:8000`，无报错。

---

## Step 2: signing_preview smoke test

PowerShell（使用 `Invoke-RestMethod`）：

```powershell
$body = @{
    intent     = "signing_preview"
    team_id    = "DEM-ATL"
    locale     = "zh-CN"
    objective  = "Add frontcourt help"
    metadata   = @{ source = "smoke_runbook" }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/agent/orchestrate-preview" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body | ConvertTo-Json -Depth 10
```

**预期结果：**

- HTTP 状态码：**200**
- 顶层字段包含：`intent`、`status`、`requires_human_approval`、`preview_payload`、`agent_trace`、`warnings`、`limitations`
- `intent` = `"signing_preview"`
- `requires_human_approval` = **`true`**（必须，不可为 false）
- `preview_payload` 存在，且是签约预览结果（包含 `proposal` 或 `actions` 字段）
- `agent_trace` 存在，且包含 5 个步骤：`intake_request` → `route_intent` → `run_deterministic_preview` → `summarize_validation_and_evidence` → `request_human_approval`
- `status` 是 `"awaiting_human_approval"`（preview-only 状态，不是 executed/approved）
- 整个响应 JSON（序列化后）中**不应该出现**以下字符串：`executed`、`applied`、`committed`、`transaction_executed`、`auto_executed`、`signed_automatically`、`roster_modified`、`contracts_modified`、`wrote_snapshot`
- `agent_trace.data_source_label` 是 `"演示数据"` 或 `"历史数据样本"`，**不应**出现 `"current NBA"`、`"live NBA"`、`"real-time NBA"` 等字样。

---

## Step 3: trade_preview_demo smoke test

```powershell
$body = @{
    intent     = "trade_preview_demo"
    locale     = "zh-CN"
    metadata   = @{ source = "smoke_runbook" }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/agent/orchestrate-preview" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body | ConvertTo-Json -Depth 10
```

**预期结果：**

- HTTP 状态码：**200**
- `intent` = `"trade_preview_demo"`
- `requires_human_approval` = **`true`**
- `preview_payload` 中包含 `trade_transaction`、`preview` 等交易预览字段
- `preview_payload.preview.validation_result.status` 是 deterministic 结果（当前实现下为 `"PASS"`），**不应**被 API 层改写
- 整个响应中**不应该出现** `executed`、`applied`、`committed` 等执行态词汇
- `agent_trace.final_message` 应包含"只读"、"不会自动执行"字样。

---

## Step 4: hold smoke test

```powershell
$body = @{
    intent     = "hold"
    locale     = "zh-CN"
    objective  = "Do not make a move yet"
    metadata   = @{ source = "smoke_runbook" }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/agent/orchestrate-preview" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body | ConvertTo-Json -Depth 10
```

**预期结果：**

- HTTP 状态码：**200**
- `intent` = `"hold"`
- `status` 是 `"hold"`（hold/blocked 语义，不是 awaiting_human_approval）
- `requires_human_approval` = **`true`**
- `preview_payload.status` = `"hold"`，且包含 `hold_reason`
- `agent_trace.steps[2].tool_name` = `"hold_without_execution"`
- **不应调用**签约/交易执行能力：`preview_payload` 中不包含 `proposal`、`trade_transaction` 字段。

---

## Step 5: unsupported intent smoke test

```powershell
$body = @{
    intent     = "execute_trade"
    metadata   = @{ source = "smoke_runbook" }
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/agent/orchestrate-preview" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body | ConvertTo-Json -Depth 10
```

**预期结果：**

- HTTP 状态码：**200**（API 本身接受请求，由 service 层阻断）
- `status` = `"blocked"`（不是 awaiting_human_approval）
- `requires_human_approval` = **`true`**
- **不被猜测**成 `signing_preview` 或 `trade_preview_demo`：`preview_payload` 中不包含 `proposal`、`trade_transaction` 字段
- `preview_payload.hold_reason` 中说明 intent 不被支持
- **不执行任何交易**：响应中无执行标记。

同样可验证其他不受支持的 intent，例如：`"sign_player"`、`"auto_execute"`、`"trade_player_now"`、`"commit_deal"`，都应被阻断。

---

## Step 6: forbidden metadata smoke test

### 6a. 顶层 forbidden key

```powershell
$body = @{
    intent     = "signing_preview"
    team_id    = "DEM-ATL"
    metadata   = @{ execute = $true }
} | ConvertTo-Json -Depth 5

try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/agent/orchestrate-preview" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body
} catch {
    $_.Exception.Response.StatusCode.value__
    $_.ErrorDetails.Message
}
```

**预期结果：**

- HTTP 状态码：**400**
- 响应 detail 中包含 `forbidden` 或 `preview-only` 字样，原因是 metadata 中包含 forbidden mutation key `execute`。

### 6b. 嵌套 metadata forbidden key（camelCase）

```powershell
$body = @{
    intent     = "hold"
    metadata   = @{ nested = @{ commitTransaction = $true } }
} | ConvertTo-Json -Depth 5

try {
    Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/agent/orchestrate-preview" `
        -Method POST `
        -ContentType "application/json" `
        -Body $body
} catch {
    $_.Exception.Response.StatusCode.value__
    $_.ErrorDetails.Message
}
```

**预期结果：**

- HTTP 状态码：**400**
- 递归扫描发现嵌套的 `commitTransaction`（驼峰式），被识别为 `commit` 禁止根动词，直接拒绝。

同样以下 metadata 字段也应被 400 拒绝（递归、大小写不敏感、支持 snake_case/camelCase）：

- `executed`、`apply`、`applied`、`commit`、`committed`
- `mutate`、`mutated`、`write`、`persist`
- `approve_transaction`、`execute_transaction`、`execute_signing`
- `roster_update`、`contract_update`、`snapshot_write`
- 任意嵌套层级中的上述字段（含 list 内对象）。

---

## Step 7: 安全边界 Checklist

逐项打勾：

| 检查项 | 必须为 |
|--------|--------|
| 不接 LLM（无 openai/anthropic 导入和调用） | ✅ |
| 不接真实 NBA API | ✅ |
| 不做 runtime scraping | ✅ |
| 不执行交易 | ✅ |
| 不执行签约 | ✅ |
| 不修改 roster/contracts/cap/snapshot（data/*.json 文件哈希不变） | ✅ |
| 所有响应 `requires_human_approval` = `true` | ✅ |
| 响应中不出现 `executed`/`applied`/`committed` 等执行态字段 | ✅ |
| metadata forbidden key（含递归嵌套/驼峰）返回 400 | ✅ |
| 不支持的 intent 返回 blocked/hold，不猜测 | ✅ |
| demo/sample/historical 数据不被误标为 current/live NBA data | ✅ |
| 不存在 `/execute`、`/apply`、`/commit`、`/mutate` 等端点 | ✅ |

---

## Step 8: 回归测试命令

所有 smoke 步骤通过后，跑一遍全量后端回归测试：

```powershell
cd D:\FrontOffice-Offseason-Agent
D:\anaconda\python.exe -m pytest backend/app/tests/test_agent_orchestrator_api.py -q
D:\anaconda\python.exe -m pytest backend/app/tests/test_agent_orchestrator.py -q
D:\anaconda\python.exe -m pytest backend/app/tests/test_agent_guardrails.py -q
D:\anaconda\python.exe -m pytest backend/app/tests/test_api_endpoints.py -q
D:\anaconda\python.exe -m pytest backend/app/tests -q
```

**预期结果：**

- 5 条命令全部 exit code 0
- 全量测试全部 passed（M8-E5-B 封口基线为 541 passed）
- 无失败、无错误、无跳过的核心守卫测试。

---

## Step 9: 封口前检查

```powershell
cd D:\FrontOffice-Offseason-Agent
git status --short
git diff --stat
```

**预期结果：**

- `git status --short` 只显示 `?? docs/m8-e5-orchestrator-api-smoke-runbook.md`（本轮只新增 docs 文件，不修改 backend/frontend/data/tests 任何文件）。
- `git diff --stat` 无输出（因为新增的是 untracked 文件）。

如果 diff 中出现 backend/、frontend/、data/ 下的文件被修改，说明本轮有意外改动，需要在封口前排查回滚。

---

## 注意事项

- 本 runbook 中的所有 `Invoke-RestMethod` 命令均为只读调用，不会修改服务器数据。
- 如果你更喜欢用 curl（例如在 Git Bash 或 WSL 中），可把 PowerShell 命令转换为等价的 `curl -X POST -H "Content-Type: application/json" -d '<body>' http://127.0.0.1:8000/api/agent/orchestrate-preview`。
- 不要在生产环境暴露 `--reload` 模式；runbook 中使用 `--reload` 仅为本地 smoke 测试方便。
- 若端口 8000 被占用，可换用其他端口（如 8001），相应替换命令中的端口号即可。
