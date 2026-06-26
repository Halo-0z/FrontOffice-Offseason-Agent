# M8-E Agent Orchestrator Handoff Summary

> 本文档是 M8-E 里程碑封口后的新会话接管文档。任何新会话、其他模型、或未来的自己在接手项目时，请先读本文件，再动手改代码。

---

## 1. 当前仓库状态

```
HEAD:       e22889f Add M8-E5 orchestrator API smoke runbook
branch:     main
origin/main: 已同步
git status: clean
```

### 当前重要 tags（按时间顺序）

| Tag | Commit | 说明 |
|-----|--------|------|
| `m8e1-agent-tool-contract-docs` | `e93e6d6` | M8-E1 Agent tool contract 文档 |
| `m8e2-backend-agent-trace-schema` | `63301a2` | M8-E2 后端 agent trace schema |
| `m8e3-frontend-agent-trace-display` | `831e0ef` | M8-E3 前端 agent trace 展示 |
| `m8e4-agent-guardrail-tests` | `1cbb0f4` | M8-E4 Agent guardrail 测试 |
| `m8e5-service-orchestrator-stub` | `68d2fa9` | M8-E5-A service-only orchestrator stub |
| `m8e5-orchestrator-preview-api` | `dba518b` | M8-E5-B preview-only orchestrator API |
| `m8e5-orchestrator-api-smoke-runbook` | `e22889f` | M8-E5-C API smoke runbook 文档 |
| `m8e5-orchestrator-api-smoke-verification` | `e22889f` | M8-E5-D 人工 smoke 验证完成（无新 commit，仅打 tag） |

---

## 2. 项目定位

**FrontOffice-Offseason-Agent 的核心不是 NBA 数据库，而是 NBA 休赛期前台决策支持 Agent。**

真实 NBA snapshot 只是 Agent 的燃料，不是项目本体。

项目最终要体现的完整链路是：

1. 用户输入休赛期目标
2. Agent 拆解任务
3. 检索 / 读取球队数据
4. 调用工具模拟签约或交易
5. 薪资规则和阵容风险校验（deterministic，不可覆盖）
6. 给出带证据的建议
7. **人工确认后才允许进入下一步**

截止 M8-E 封口，项目已经完成了 1-6 步的 preview-only 闭环。第 7 步是 human approval gate，永远在前端/人工侧完成，Agent 不具备自动执行能力。

---

## 3. 当前 Agent 能做什么

M8-E 封口时，Agent 可以：

- 理解**显式 intent**（signing_preview / trade_preview_demo / hold）
- 读取现有 demo/snapshot 数据（只读）
- 调用 deterministic preview service（不重算、不覆盖 verdict）
- 生成两层 agent_trace：
  - **orchestrator 层**（5 步）：intake → route → preview/hold → summarize → approval gate
  - **inner 层**（8 步，签约/交易）：具体工具调用链，由 `agent_trace_builder` 生成
- 返回 proposal/trade/hold preview 结果
- 给出 evidence / warnings / limitations
- **始终要求人类确认**（`requires_human_approval = true`）
- 通过 API (`POST /api/agent/orchestrate-preview`) 对外暴露只读预览能力

---

## 4. 当前 Agent 不能做什么（硬边界）

以下是不可违反的硬边界，所有测试和代码都在保护这些边界：

- ❌ 不自动执行签约
- ❌ 不自动执行交易
- ❌ 不修改 roster
- ❌ 不修改 contracts / cap state
- ❌ 不写 snapshot
- ❌ 不接 OpenAI API
- ❌ 不接真实 NBA API（无 runtime scraping）
- ❌ 不绕过 salary validation
- ❌ 不让 LLM 覆盖 deterministic verdict
- ❌ 不把 demo data 说成真实数据
- ❌ 不把 historical snapshot 说成 current/live NBA data
- ❌ 不支持自由文本自动推断任意交易（只支持显式 allowlisted intent）
- ❌ unsupported intent 不能猜测成 signing_preview 或 trade_preview_demo
- ❌ metadata 中出现 execute/apply/commit/mutate/write/persist 等字段必须被 400 拒绝

---

## 5. M8-E1 到 M8-E5-D 每一步总结

### M8-E1: Agent Tool Contract Docs

- **Commit**: `e93e6d6` Add M8-E1 agent tool contract docs
- **Tag**: `m8e1-agent-tool-contract-docs`
- **修改范围**: `docs/agent-tool-contract.md`、`docs/agent-decision-flow.md`、`docs/agent-workflow.md`
- **做成了什么**: 定义了 Agent 工具契约，明确了 preview-only 边界、8 步 trace 结构、deterministic tool 序列、human approval gate。
- **没做什么**: 没有代码改动，纯设计文档。

### M8-E2: Backend Agent Trace Schema

- **Commit**: `63301a2` Add M8-E2 backend agent trace schema
- **Tag**: `m8e2-backend-agent-trace-schema`
- **修改范围**:
  - 新增 `backend/app/models/agent_trace.py`（frozen dataclass：AgentTrace / AgentTraceStep）
  - 新增 `backend/app/services/agent_trace_builder.py`（build_proposal_agent_trace / build_trade_agent_trace）
  - 修改 `backend/app/api.py` 为现有 proposal-preview / trade-preview-demo 端点**附加**（additive）agent_trace
- **做成了什么**: 后端能为签约/交易 preview 生成 8 步结构化 agent_trace，步骤状态严格从 deterministic verdict 派生，不发明裁决。
- **没做什么**: 没有改 salary validation，没有改 signing/trade 结果，没有接 LLM。

### M8-E3: Frontend Agent Trace Display

- **Commit**: `831e0ef` Add M8-E3 frontend agent trace display
- **Tag**: `m8e3-frontend-agent-trace-display`
- **修改范围**: 前端 Next.js 页面（右侧 Inspector 面板）
- **做成了什么**:
  - 前端右侧 Inspector 能显示后端返回的 agent_trace
  - 初始状态显示 Agent Trace 空卡片
  - signing/proposal preview 后显示 signing Agent 链路
  - trade-preview-demo 后显示 trade Agent 链路
  - technical_details 默认折叠
  - 主界面不铺 raw JSON
  - 不显示"已执行交易/已完成签约"等误导文案
  - 修复 trade-preview-demo 指标区"人工确认"误显示"不需要"的问题，正确显示"需要"
- **没做什么**: 没有改后端 API 契约，没有新增 endpoint，没有自动执行能力。

### M8-E4: Agent Guardrail Tests

- **Commit**: `1cbb0f4` Add M8-E4 agent guardrail tests
- **Tag**: `m8e4-agent-guardrail-tests`
- **修改范围**: 扩展 `backend/app/tests/test_agent_guardrails.py`（52 个测试）
- **做成了什么**: 补了 23 个守卫测试保护 Agent 边界——验证无 LLM/MCP 导入、无数据写入、trace 步骤顺序正确、final_message 固定、requires_human_approval 始终 true、approval_state 无执行状态、无 executed/applied/committed 标记、薪资步骤状态严格从 verdict 派生、API 无 execute 端点、AgentTrace/AgentTraceStep 是 frozen dataclass。
- **没做什么**: 没有改业务逻辑、前端、数据文件或快照。M8-E4 封口时全量后端测试 491 passed。

### M8-E5-A: Service-only Orchestrator Stub

- **Commit**: `68d2fa9` Add M8-E5 service orchestrator stub
- **Tag**: `m8e5-service-orchestrator-stub`
- **修改范围**:
  - 新增 `backend/app/models/agent_orchestrator.py`（frozen dataclass：AgentOrchestratorRequest / AgentOrchestratorResult / OrchestratorTrace / OrchestratorTraceStep）
  - 新增 `backend/app/services/agent_orchestrator.py`（`orchestrate_preview()` 函数）
  - 新增 `backend/app/tests/test_agent_orchestrator.py`（20 个测试）
- **做成了什么**: 实现了一个薄的 deterministic intent routing 层，把现有 signing preview、trade preview demo、hold 三种能力包成统一的 `orchestrate_preview()` 入口，生成 5 步 orchestrator trace。支持显式 allowlisted intent（signing_preview / trade_preview_demo / hold），unsupported intent 返回 blocked/hold。
- **没做什么**: 没有接 API，没有接前端，没有接 LLM，没有新的 mutation 能力，没有改任何已有业务逻辑或 deterministic 结果。

### M8-E5-B: Preview-only Orchestrator API

- **Commit**: `dba518b` Add M8-E5 orchestrator preview API
- **Tag**: `m8e5-orchestrator-preview-api`
- **修改范围**:
  - 修改 `backend/app/api.py`（新增 `AgentOrchestratePreviewRequest` Pydantic model、递归 metadata forbidden-key 扫描、`POST /api/agent/orchestrate-preview` endpoint）
  - 新增 `backend/app/tests/test_agent_orchestrator_api.py`（30 个测试）
- **做成了什么**: 新增安全的 preview-only API 端点，metadata 递归扫描禁止 execute/apply/commit/mutate/write/persist 等键（支持 snake_case/camelCase/嵌套/大小写变体），直接透传 `AgentOrchestratorResult.to_dict()`，不重塑、不覆盖、不重算。
- **没做什么**: 没有在 API 层重新实现 signing/trade 逻辑，没有重新计算 salary validation，没有新增 execute/apply/commit endpoint，没有改前端。

### M8-E5-C: API Smoke Runbook

- **Commit**: `e22889f` Add M8-E5 orchestrator API smoke runbook
- **Tag**: `m8e5-orchestrator-api-smoke-runbook`
- **修改范围**: 新增 `docs/m8-e5-orchestrator-api-smoke-runbook.md`
- **做成了什么**: 一份可复制的 PowerShell smoke runbook，覆盖 signing_preview / trade_preview_demo / hold / unsupported intent / forbidden metadata（顶层+嵌套）6 个场景，含安全边界 checklist 和回归测试命令。
- **没做什么**: 没有任何代码改动，纯文档。

### M8-E5-D: API Smoke Verification

- **Commit**: 无新 commit（在 `e22889f` 上打 verification tag）
- **Tag**: `m8e5-orchestrator-api-smoke-verification`
- **修改范围**: 无代码改动，无文件改动
- **做成了什么**: 人工按照 runbook 逐项验证了 6 个 smoke 场景，全部通过。验证结果详见第 10 节。
- **没做什么**: 没有改代码，没有改文档，只打了一个 verification tag。

---

## 6. 当前关键文件

### 文档（docs/）

| 文件 | 作用 |
|------|------|
| [agent-tool-contract.md](file:///D:/FrontOffice-Offseason-Agent/docs/agent-tool-contract.md) | M8-E1 Agent 工具契约定义 |
| [agent-decision-flow.md](file:///D:/FrontOffice-Offseason-Agent/docs/agent-decision-flow.md) | Agent 决策流程图 |
| [agent-workflow.md](file:///D:/FrontOffice-Offseason-Agent/docs/agent-workflow.md) | Agent 工作流说明 |
| [m8-e5-orchestrator-api-smoke-runbook.md](file:///D:/FrontOffice-Offseason-Agent/docs/m8-e5-orchestrator-api-smoke-runbook.md) | M8-E5-C API 本地 smoke 验证手册 |
| [architecture.md](file:///D:/FrontOffice-Offseason-Agent/docs/architecture.md) | 项目架构总览 |
| [demo-runbook.md](file:///D:/FrontOffice-Offseason-Agent/docs/demo-runbook.md) | Demo 运行手册 |

### 后端模型（backend/app/models/）

| 文件 | 作用 |
|------|------|
| [agent_trace.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/models/agent_trace.py) | M8-E2 frozen dataclass：AgentTrace / AgentTraceStep（inner 8 步 trace） |
| [agent_orchestrator.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/models/agent_orchestrator.py) | M8-E5-A frozen dataclass：AgentOrchestratorRequest / AgentOrchestratorResult / OrchestratorTrace / OrchestratorTraceStep（orchestrator 5 步 trace） |
| [agent.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/models/agent.py) | OffseasonGoal 等核心 model |
| [transaction.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/models/transaction.py) | 交易 model（禁止修改） |

### 后端服务（backend/app/services/）

| 文件 | 作用 |
|------|------|
| [agent_trace_builder.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/services/agent_trace_builder.py) | M8-E2：构建 inner 8 步 agent_trace |
| [agent_orchestrator.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/services/agent_orchestrator.py) | M8-E5-A：`orchestrate_preview()` 薄编排层 |
| [proposal_viewer.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/services/proposal_viewer.py) | 签约 demo payload 构建（禁止修改） |
| [proposal_builder.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/services/proposal_builder.py) | proposal 构建管线（禁止修改） |
| [proposal_evaluator.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/services/proposal_evaluator.py) | proposal 评估（禁止修改） |
| [transaction_rule_engine.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/services/transaction_rule_engine.py) | 薪资规则引擎（禁止修改） |
| [trade_simulator.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/services/trade_simulator.py) | 交易模拟器（禁止修改） |
| [data_source_resolver.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/services/data_source_resolver.py) | 数据源解析（禁止修改） |

### 后端 API

| 文件 | 作用 |
|------|------|
| [api.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/api.py) | FastAPI 应用，包含所有 API endpoint |

### 后端测试（backend/app/tests/）

| 文件 | 测试数量 | 作用 |
|------|---------|------|
| [test_agent_guardrails.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/tests/test_agent_guardrails.py) | 52 | M8-E4 Agent 边界守卫测试 |
| [test_agent_orchestrator.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/tests/test_agent_orchestrator.py) | 20 | M8-E5-A service 层测试 |
| [test_agent_orchestrator_api.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/tests/test_agent_orchestrator_api.py) | 30 | M8-E5-B API 层测试 |
| [test_api_endpoints.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/tests/test_api_endpoints.py) | 22 | 原有 API endpoint 测试 |

### 前端

| 文件 | 作用 |
|------|------|
| [page.tsx](file:///D:/FrontOffice-Offseason-Agent/frontend/app/offseason/page.tsx) | Offseason console 主页面（含 Inspector 面板） |
| [apiClient.ts](file:///D:/FrontOffice-Offseason-Agent/frontend/lib/apiClient.ts) | 前端 API client |

---

## 7. 当前关键 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 + data source metadata |
| GET | `/api/offseason/scenarios` | 列出支持的 demo 场景 |
| POST | `/api/offseason/proposal-preview` | 签约 preview（直接调用 build_demo_payload，附加 inner 8 步 trace） |
| GET | `/api/offseason/trade-preview-demo` | 固定 demo 交易 preview（附加 inner 8 步 trace） |
| **POST** | **`/api/agent/orchestrate-preview`** | **M8-E5 新增：preview-only orchestrator 统一入口。这是 preview endpoint，不是 execute endpoint。** |

### POST /api/agent/orchestrate-preview 重点说明

- **这是 preview-only endpoint**，不执行任何签约或交易。
- Request body: `{ intent, team_id?, locale?, objective?, metadata? }`
- 允许的 intent：`signing_preview`、`trade_preview_demo`、`hold`
- `metadata` 递归扫描禁止 mutation 语义键（execute/apply/commit/mutate/write/persist 等 16 个键，支持 snake_case/camelCase/嵌套/大小写变体），出现即返回 HTTP 400
- Response: 直接返回 `AgentOrchestratorResult.to_dict()`，不重塑、不覆盖
- 所有响应 `requires_human_approval = true`
- unsupported intent 返回 `status: "blocked"`，不猜测成 signing/trade

---

## 8. 当前测试基线

M8-E 封口（M8-E5-D 验证通过后）全量后端测试：

| 测试套件 | 通过数 |
|---------|--------|
| test_agent_guardrails.py（M8-E4） | 52 passed |
| test_agent_orchestrator.py（M8-E5-A） | 20 passed |
| test_agent_orchestrator_api.py（M8-E5-B） | 30 passed |
| test_api_endpoints.py（原有） | 22 passed |
| 其他后端测试 | 417 passed |
| **全量合计** | **541 passed** |

运行全量测试命令：

```powershell
cd D:\FrontOffice-Offseason-Agent
D:\anaconda\python.exe -m pytest backend/app/tests -q
```

---

## 9. M8-E5-D Smoke Verification 结果

M8-E5-D 人工按照 [m8-e5-orchestrator-api-smoke-runbook.md](file:///D:/FrontOffice-Offseason-Agent/docs/m8-e5-orchestrator-api-smoke-runbook.md) 逐项验证，结果如下：

| 场景 | 结果 |
|------|------|
| signing_preview (DEM-ATL, "Add frontcourt help") | ✅ HTTP 200，requires_human_approval=true，5 步 trace 完整，无 executed/applied/committed |
| trade_preview_demo | ✅ HTTP 200，requires_human_approval=true，trade preview 信息完整，validation_result 未被改写 |
| hold | ✅ HTTP 200，status=hold，不调用 signing/trade |
| unsupported intent (execute_trade) | ✅ HTTP 200 + status=blocked，不猜测成 signing/trade，不执行交易 |
| forbidden metadata 顶层 (execute: true) | ✅ HTTP 400 |
| forbidden metadata 嵌套 (commitTransaction) | ✅ HTTP 400（递归+驼峰扫描生效） |
| requires_human_approval 始终为 true | ✅ 所有场景验证通过 |
| git status clean | ✅ smoke 前后无文件变化 |

---

## 10. 下一步建议

M8-E 封口后，建议的候选下一步（按优先级）：

1. **M8-F Frontend Orchestrator API Wiring（推荐优先）**
   - 把前端 Inspector / console 主流程从直接调用 `/api/offseason/proposal-preview` 和 `/api/offseason/trade-preview-demo`，切换为统一调用 `/api/agent/orchestrate-preview`
   - 利用 orchestrator 返回的 5 步高层 trace 展示意图路由过程
   - 保持只读，不添加 execute 按钮或自动执行逻辑
   - 完成后前端体验从"两个独立 demo 按钮"升级为"统一的 Agent 预览入口"

2. **M9 Data Expansion Schema Gap Audit**
   - 审计当前数据模型在扩展到 30 队真实数据时的 schema gap
   - 设计数据扩展的迁移路径（不实际执行扩展）
   - 明确哪些字段是 demo 专用的，哪些字段需要适配真实 snapshot

3. **M8-F2 Orchestrator Compare/Hold Scenario Enhancement**
   - 丰富 hold 路径的证据展示（为什么推荐 hold）
   - 考虑增加 compare intent（比较多个方案），仍保持 preview-only

### 明确不建议立即做的事

- ❌ **不要马上接 LLM**。当前 deterministic 链路是稳定的安全网，接 LLM 前必须先完成前端 wiring 和数据审计。
- ❌ **不要马上做真实 NBA API**。runtime scraping 和外部 API 调用会打破当前的确定性和安全边界。
- ❌ **不要马上扩 30 队数据**。先做 schema gap audit，再决定扩展路径。
- ❌ **不要添加 execute/apply/commit 按钮或端点**。Human approval gate 是硬边界。

---

## 11. 后续执行原则

无论谁接手项目，请遵守以下原则：

1. **小步封口**：每个 milestone 控制在可验证范围内，先测试、再 smoke、再封口。
2. **每步先验收再 commit/tag/push**：每步完成后跑全量测试，确认 guardrail tests 不退化。
3. **不操作 D:\DraftMind**：另一个项目，不要碰。
4. **不让执行模型自行 commit/tag/push**：这些操作由 ChatGPT 验收后人工执行。
5. **ChatGPT 做最终验收 gate**：每个 milestone 完成后发报告给 ChatGPT，由 ChatGPT 判断是否能封口。
6. **改代码前先读 guardrail tests**：test_agent_guardrails.py 是 Agent 边界的法典，新功能不能让任何守卫测试失败。
7. **新增功能必须加守卫测试**：任何新能力如果能突破现有边界，必须先加对应的 guardrail test。
8. **demo/sample/historical 永远是 demo/sample/historical**：不要误标为 live/current/real-time。

---

## 12. 快速接管 checklist

新会话启动时：

- [ ] 读本文档（handoff summary）
- [ ] 读 [agent-tool-contract.md](file:///D:/FrontOffice-Offseason-Agent/docs/agent-tool-contract.md)
- [ ] 运行 `git status --short` 确认工作区 clean
- [ ] 运行 `D:\anaconda\python.exe -m pytest backend/app/tests -q` 确认 541 tests passed
- [ ] 确认不碰 D:\DraftMind
- [ ] 确认不接 LLM / 真实 NBA API / scraping
- [ ] 确认不添加 execute/apply/commit/mutation 能力
- [ ] 动手前先写 todo list
- [ ] 完成后跑全量测试 + git status 检查
- [ ] 发报告给 ChatGPT 验收
