# M8-F Frontend Orchestrator API Wiring Summary

## 1. 当前仓库状态

- **HEAD**: `c74e523` — *Wire frontend to orchestrator preview API*
- **Tag**: `m8f-frontend-orchestrator-api-wiring`
- **origin/main**: 已同步
- **工作区**: `git status` clean，无未提交变更

M8-F 是 FrontOffice-Offseason-Agent 在 M8 里程碑的封口轮次，核心工作是把前端签约/交易两条主路径接入后端已有的 Agent 编排入口，并完成前端产品语言降噪。

---

## 2. M8-F 用白话解决了什么问题

后端在 M8-E 阶段已经搭好了统一的 Agent 编排入口 `POST /api/agent/orchestrate-preview`，它负责：

1. 接收前端意图（签约预览 / 交易预览 / 观望）；
2. 路由到对应的确定性预览能力；
3. 产出只读的 preview payload；
4. 产出 5 步 agent trace（intake → route → preview → summarize → approval gate）；
5. 在最后一步强制走人工确认闸门，不自动执行任何动作。

但在 M8-F 之前，前端签约/交易页面还在直接调用旧的 `proposal-preview` / `trade-preview-demo` demo API，用户看到的 trace 是旧的 8 步内部工具链步骤，标签里还混着 `transaction_id`、`validation_result` 这类工程字段名，整体像是给开发者看的控制台，不像一个给普通用户看的产品。

M8-F 做了两件事：

- **接线**：让前端 signing / trade 两个场景优先打到新的 orchestrator preview API，旧 API 保留作为 fallback，本地 static sample 作为最终兜底；
- **降噪**：把主界面所有残留的工程词（PASS、PLAYER_CONTRACT、IN/OUT、post-trade total salary、sample/demo、`C: have 0, target 2`、`校验状态：PASS` 等）替换成普通用户能读懂的中文/英文产品语言。

M8-F 保持系统**只读、安全、可回退**，没有引入任何新的执行能力、LLM、真实 NBA 数据或外部抓取。

---

## 3. 当前前端请求路径

### 3.1 signing / 签约推荐

- 入口：`POST /api/agent/orchestrate-preview`
- `intent = "signing_preview"`
- 前端把后端返回的 `response.preview_payload`（形状与旧 proposal-preview 响应一致）喂给已有的 `ProposalViewer` 组件渲染签约结果；
- 把 `response.agent_trace`（5 步 orchestrator trace）喂给右侧"方案生成过程"卡片渲染步骤；
- `response.warnings` / `response.limitations` 作为提醒/限制文案展示。

### 3.2 trade / 模拟交易

- 入口：`POST /api/agent/orchestrate-preview`
- `intent = "trade_preview_demo"`
- 前端把 `response.preview_payload`（形状与旧 trade-preview-demo 响应一致）喂给已有的 `TradePreviewViewer` 组件渲染交易结果；
- 把 `response.agent_trace`（5 步 orchestrator trace）喂给右侧"方案生成过程"卡片；
- 薪资配平、交易后薪资/深度图、双方交易后视图沿用已有组件，只把展示文案做了降噪。

### 3.3 hold / 预算受限、暂不行动

- **没有迁移到 orchestrator hold**。
- 继续走旧接口 `POST /api/offseason/proposal-preview`。
- 原因：orchestrator 返回的 hold payload 是一个"薄"hold 响应，只包含阻断原因，不等于旧 API 返回的完整 proposal payload（含 actions、evaluation、depth_chart_summary 等字段），直接切换会让 UI 丢字段。hold 迁移需要单独做 payload 适配，留给后续里程碑。

### 3.4 fallback 链路

signing 与 trade 两条路径遵循同一个三层 fallback：

1. **第一层**：`POST /api/agent/orchestrate-preview`（orchestrator 新接口）；
2. **第二层**：如果 orchestrator 失败（网络错误、5xx、返回 blocked 且非预期），回落到旧 API：
   - signing → `POST /api/offseason/proposal-preview`
   - trade → `POST /api/offseason/trade-preview-demo`
3. **第三层**：如果旧 API 也失败，回落到本地 static sample payload（`demoProposalPayload.ts` / `demoTradePreviewPayload.ts`），页面仍可展示。

旧 API 不删除，作为兼容层保留，方便回滚与对比。

---

## 4. 修改文件

M8-F 共涉及 4 个前端文件，没有修改后端、数据、快照或测试。

### 4.1 `frontend/lib/apiClient.ts`

- 新增 `OrchestratorPreviewRequest` / `OrchestratorPreviewResponse` TypeScript 类型；
- 新增 `fetchOrchestratorPreview(req)` 函数，封装 `POST /api/agent/orchestrate-preview`；
- 把 `AgentTrace` 接口的 `intent_type` / `current_state` / `approval_state` 改为可选字段（orchestrator trace 不返回这些字段，只返回 `intent` 和 `overall_status`），保证渲染层做 defensive fallback 时不崩溃；
- 注释明确标注：orchestrator 是 preview-only，永远不 execute/mutate。

### 4.2 `frontend/app/offseason/page.tsx`

主页面组件，是 M8-F 的主要改动点：

- 新增 orchestrator 调用分支：signing/trade 优先调用 `fetchOrchestratorPreview`，失败后回落旧 API，再失败回落 local sample；
- 新增 `sanitizeStepSummary` 函数，正则清洗后端 `plain_language_summary` 中的工程词（`校验状态：PASS`、`薪资规则裁决结果：PASS`、`intent=signing_preview`、`allowlist` 等），替换为用户可读文案；
- 新增 `mapStepSummary` 调用 sanitize 并按步骤索引生成产品语言 fallback 文案；
- 新增 `positionCodeLabel` 函数（C/PG/SG/SF/PF → 中锋/控卫/分卫/小前锋/大前锋）；
- 新增 `translateMatchedNeed` 函数，把 `"C: have 0, target 2 (priority=high)"` 翻译成"中锋：现有 0，目标 2（优先级：高）"；
- 新增 `getUserFacingValidationStatus` 函数，把 `PASS/FAIL/WARNING/BLOCKED` 映射为"通过/未通过/需注意/已拦截"；
- 主界面关键指标卡片直接使用映射后的中文/英文标签（"规则检查"/"Rule check"、"薪资配平"/"Salary match"、"通过"/"Pass"）；
- 底部免责文案从 "sample/demo 数据" 改为 "演示数据 / demo data"；
- 右侧"方案生成过程"卡片对 orchestrator 5 步 trace 与 legacy 8 步 trace 做统一映射，所有步骤标题与摘要都是产品语言。

### 4.3 `frontend/components/TradePreviewViewer.tsx`

交易预览主组件：

- 资产卡片方向徽章：`OUT` → "送出"/"Sending out"，`IN` → "得到"/"Receiving"；
- 资产类型：`PLAYER_CONTRACT` → "球员合同"/"Player contract"；
- 薪资配平卡片：`PASS/FAIL` 徽章使用 i18n 标签"通过/Pass"、"未通过/Fail"；
- 薪资配平规则：从硬编码英文公式替换为本土化解释"规则：得到薪资 ≤ 送出薪资 × 125% + $100,000（样例规则，非真实 CBA）"；
- 交易后 summary 文本（`cap_impact_summary` / `roster_impact_summary` / `depth_chart_impact_summary`）通过三个翻译辅助函数从英文硬编码文本解析重构为中文/英文产品语言（"DEM-ATL 交易后总薪资 $XX，薪资空间 $XX" 等）；
- 需求等级：`high/medium/low` → "高/中/低" / "High/Medium/Low"；
- i18n 字段标签：全部从 snake_case（`transaction_id`、`asset_type`、`outgoing_salary`）改为 plain English（"Transaction ID"、"Asset type"、"Sending salary"）。

### 4.4 `frontend/data/i18n.ts`

国际化文案表：

- 新增徽章标签：`outBadge` / `inBadge` / `passBadge` / `failBadge` / `playerContractType` / `priorityHigh/Medium/Low`；
- trade 字段标签全部从 snake_case 改为 plain English（如 `fit_score` → "Fit score"，`cap_impact` → "Cap impact"）；
- agent trace 标题从工程化的 "Agent Execution Steps" / "Pipeline" 改为产品语言 "方案生成过程" / "How this preview was built" / "生成进度" / "Generation progress"；
- `blocked` 状态标签从"已阻断"改为"已安全拦截"/"Safely blocked"，强调安全语义；
- demo 数据免责文案把 "sample/demo" 统一替换为"演示数据"/"demo data"；
- 控制台区块标题："Key Metrics" → "Key metrics"、"Data Source" → "Data source" 等英文大小写风格统一。

---

## 5. 产品语言规则

### 5.1 主界面允许出现的语言

主界面（用户默认可见区域，不展开"查看技术详情"/"查看完整审计详情"时看到的所有内容）使用普通用户能读懂的产品语言，例如：

- 功能区块：方案生成过程、生成进度、补强位置、送出 / 得到、交易后总薪资、薪资空间、球员合同、阵容深度；
- 状态标签：通过、未通过、需注意、已安全拦截、需要人工确认、只读预览；
- 位置名称：中锋、控卫、分卫、小前锋、大前锋（英文：Center / Point guard / Shooting guard / Small forward / Power forward）；
- 数字表达：现有 X，目标 Y，缺口 Z；送出薪资、得到薪资、配平阈值；
- 数据来源说明：演示数据、快照数据（非实时）、本地静态样例；
- 动作提示：需要你确认后才会采取任何行动、不代表真实 NBA 数据。

### 5.2 主界面不允许出现的内容

以下工程字段/术语**禁止**出现在主界面：

- 原始状态码：`PASS` / `FAIL` / `BLOCKED` / `WARNING` / `RECOMMENDED` / `NO_ACTION` / `HOLD`（必须映射为中文/英文产品词）；
- snake_case 字段名：`transaction_id`、`validation_result`、`validation_status`、`asset_type`、`tool_name`、`tool_call_trace`、`intent_type`、`current_state`、`approval_state`、`metadata`、`orchestrator`、`payload`、`pipeline`、`router`、`allowlist`、`deterministic`、`fixture` 等；
- 原始位置代码作为唯一标签（`C: have 0, target 2` 这类必须翻译）；
- 英文硬编码句子（`post-trade total salary`、`cap space`、`players with starter`、`sample/demo data` 这类必须翻译）；
- 误导性动作文案：**严禁**出现"已执行交易"、"已完成签约"、"自动批准"、"已提交"、"自动执行"、"已批准"这类暗示系统已经做了真实动作的措辞。

### 5.3 技术详情折叠区

所有技术字段（`tool_name`、`inputs_summary`、`outputs_summary`、`technical_details`、`evidence_ids`、原始 `transaction_id`、原始 `validation_status`、raw payload 切片等）**只允许**出现在以下两种折叠区域，默认收起：

- 右侧 trace 步骤的"查看技术详情"（每个步骤一个 `<details>`）；
- 签约/交易卡片底部的"查看完整审计详情"/"View full audit details"（整个审计区块一个 `<details>`）。

折叠区内允许保留原始英文字段名和原始状态码（方便开发者排错），但仍需做基础格式化（不直接打印 `[object Object]`，对象/数组 pretty-print，null/undefined 显示"（空）"/"(empty)"）。

---

## 6. 安全边界

M8-F 严格维持以下边界，任何后续改动不得突破：

- **不接 LLM**：所有建议、评估、trace 文案都来自确定性代码和预置文案，没有调用任何大语言模型；
- **不接真实 NBA API**：所有球员、薪资、合同数据来自仓库内置 snapshot / demo JSON，不访问任何外部 NBA 数据接口；
- **不做 scraping**：没有任何网络爬取逻辑；
- **不新增 execute / apply / commit / mutate 能力**：orchestrator 端点是 preview-only，永远返回 `requires_human_approval: true`；前端没有任何"执行交易"/"确认签约"/"提交"按钮能触发写操作；
- **不自动执行交易**，**不自动执行签约**，用户在 UI 上看到的一切都是预览；
- **不改 deterministic verdict**：前端只做展示层 mapping，不篡改后端 `validation_result.status`、salary matching 结果、evaluation issues 等核心判定；
- **不改 salary / trade validation result**：所有规则判定在后端完成，前端只做文案翻译；
- **不改 data / snapshot**：`data/`、`backend/app/tests/fixtures/snapshots/` 目录本轮零改动，后续任何改动必须走单独的 data gate；
- **不把 demo / historical 数据说成 live / current NBA data**：底部始终显示"演示数据，不代表真实 NBA 数据"的免责声明；snapshot 模式显示"快照数据，非实时"。

---

## 7. 已验证内容

M8-F 封口前已完成以下验证：

| 验证项 | 结果 |
|--------|------|
| `cd frontend && npm run typecheck` | ✅ 通过（tsc --noEmit 无错误） |
| `cd frontend && npm run build` | ✅ 通过（Next.js production build，5/5 static pages） |
| `pytest backend/app/tests/test_agent_orchestrator_api.py -q` | ✅ 30 passed |
| `pytest backend/app/tests/test_api_endpoints.py -q` | ✅ 22 passed |
| 人工截图验收（signing 页面） | ✅ trace 主界面不再显示 PASS；"C: have 0, target 2" 已改为"中锋：现有 0，目标 2" |
| 人工截图验收（trade 页面） | ✅ PASS → 通过；PLAYER_CONTRACT → 球员合同；IN/OUT → 送出/得到；post-trade salary → 交易后总薪资；cap space → 薪资空间；sample/demo → 演示数据 |
| commit 后 git status | ✅ clean |

后端测试套件（含 test_agent_guardrails.py、test_agent_trace.py、test_offseason_agent.py 等）在 M8-E 阶段已经通过，M8-F 不修改后端，因此不需要重跑。

---

## 8. 后续注意事项

1. **不要直接删除旧 API**。`/api/offseason/proposal-preview` 和 `/api/offseason/trade-preview-demo` 目前仍是 signing/trade 的 fallback 层，也是 hold 场景的唯一通道；删除前必须先完成 hold 迁移和充分的回归测试。
2. **不要贸然接 orchestrator hold**。orchestrator 的 hold payload 是薄阻断响应，不含 actions/evaluation/depth_chart 等字段，直接切换会让 UI 缺内容。迁移前先设计 payload 适配层，决定 UI 是降级展示还是维持旧路径。
3. **如果要接 LLM，必须先做设计 gate**。LLM 接入会改变建议来源、可审计性和输出稳定性，需要单独设计：prompt 契约、输出 schema 校验、确定性回退路径、成本/延迟预算、失败降级策略，不能在当前代码里直接加 fetch。
4. **如果要接真实 NBA 数据，也必须先做数据来源和 freshness gate**。真实数据涉及：数据版权、更新频率、字段映射一致性、snapshot 与 live 数据的切换开关、用户可见的数据来源标识，不能静默替换 demo JSON。
5. **前端继续保持"用户语言主界面 + 技术折叠详情"的双层规则**。后续加任何新字段/卡片时，默认把工程字段放进 `<details>` 折叠区，主界面只放产品语言；新增英文硬编码前必须走 i18n；新增状态码必须加 `getUserFacing*` 映射函数。

---

## 9. 下一步建议

M8-F 封口后，仓库处于一个稳定可演示的状态。下一步建议按以下顺序考虑，**不要直接接 LLM，不要直接接真实 NBA API**：

1. **M8-G Frontend Orchestrator Smoke Runbook / Acceptance Notes**（推荐优先）
   写一份面向验收/演示的 runbook，覆盖 signing/trade/hold 三条路径的点击步骤、预期页面状态、已知限制，方便团队成员和验收方快速走通流程，也作为后续回归测试的蓝本。

2. **M9 Data Expansion Gate（设计先行）**
   在引入新赛季/更多球队 snapshot 前，先做数据扩展设计：snapshot 目录命名约定、manifest 字段扩展、前端 snapshot 选择器 UI、snapshot 与 demo 模式的边界。

3. **M9 LLM Integration Design Gate（设计先行，不实现）**
   输出一份 LLM 接入设计文档，覆盖模型选择、prompt 契约、输出 schema 校验、确定性回退、审计日志、成本控制；文档 review 通过后才进入实现阶段。

当前更稳的路径是先做 **M8-G**（巩固验收基础），再做 **M9 Data Expansion Gate** 或 **M9 LLM Integration Design Gate** 的设计工作，任何代码层面的 LLM / 真实数据接入都应排在设计 gate 之后。
