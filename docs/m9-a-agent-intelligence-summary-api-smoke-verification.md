# M9-A-SMOKE — Agent Intelligence Summary API Smoke Verification

## 1. 当前 HEAD / tag

- HEAD: `0d8b97e` — *Add M9-A agent intelligence summary adapter*
- Tag: `m9a-agent-intelligence-summary-adapter`
- Working tree: clean (no pre-existing modifications before smoke)

## 2. Smoke 验证目的

确认 M9-A 新增的 `intelligence_summary` 字段真实出现在 `POST /api/agent/orchestrate-preview` 的 HTTP 响应里，并且：

- 旧 7 个字段保留且语义未变；
- `requires_human_approval` 始终为 `true`；
- signing / trade 场景 summary 明确标注"只读预览"，没有任何执行语义；
- hold 场景 summary 明确说"暂不行动"，不被写成签约或交易推荐；
- blocked 场景 summary 明确说"安全拦截/未生成方案"，不伪装成可执行方案；
- intelligence_summary 内不出现英文/中文危险词和技术 ID。

**方法论**：使用 FastAPI `TestClient` 直接打 HTTP 接口（不是直接调 service 函数），逐字段做断言。所有校验脚本跑完立即删除，工作区只保留本文档。

## 3. 请求 payload

共测 5 个请求（按 task 要求 4 类场景，另补一个 `DEM-ATL` 的 signing 场景用来验证真实签约预览路径，因为 `ATL` 不在 demo 白名单里会被安全降级到 HOLD）：

| # | intent | team_id | objective |
|---|--------|---------|-----------|
| S1 | `signing_preview` | `ATL` | add frontcourt help |
| S1a | `signing_preview` | `DEM-ATL` | add frontcourt help |
| S2 | `trade_preview_demo` | `ATL` | explore a demo trade |
| S3 | `hold` | `ATL` | preserve flexibility |
| S4 | `execute_trade` | `ATL` | execute a trade now |

所有请求都带 `"locale": "zh-CN"` 和 `constraints` 数组。

## 4. 每种请求的关键返回结果

### S1. signing_preview (team_id=ATL) — 安全降级到 HOLD

| 字段 | 值 |
|------|----|
| HTTP | 200 |
| `intent` | `signing_preview` |
| `status` | **`hold`** |
| `requires_human_approval` | `true` |
| `preview_payload` 存在 | ✅ keys: `evidence, hold_reason, intent, limitations, recommended_actions, requires_human_approval, sample_data, status, tool_trace` |
| `agent_trace.steps` 数量 | 5 |
| `intelligence_summary` 存在 | ✅ |
| `summary_title` | **暂不行动：当前条件下建议保持观望** |
| `deterministic_verdict` | 建议暂不行动（hold） |
| `source` | `deterministic-fake-adapter` |

> 观察：`team_id="ATL"` 不在 demo 白名单，orchestrator 安全降级到 HOLD；summary 按 status 输出"暂不行动"而不是"签约预览"——**这恰好验证了"status 优先于 intent"的安全逻辑**。

### S1a. signing_preview (team_id=DEM-ATL) — 真实签约预览路径

| 字段 | 值 |
|------|----|
| HTTP | 200 |
| `intent` | `signing_preview` |
| `status` | **`awaiting_human_approval`** |
| `requires_human_approval` | `true` |
| `preview_payload` 存在 | ✅ |
| `agent_trace.steps` 数量 | 5 |
| `intelligence_summary` 存在 | ✅ |
| `summary_title` | **签约预览：Demo FA Quebec（中锋）补强方案** |
| `deterministic_verdict` | 规则检查通过 |
| `plain_language_summary` | "系统为球队 DEM-ATL 生成了一个只读签约预览：以 $18M、1 年合同签下 Demo FA Quebec（中锋）。该方案通过了项目样例薪资与阵容规则检查，但仍然只是预览。" |
| `source` | `deterministic-fake-adapter` |

### S2. trade_preview_demo (team_id=ATL) — 交易 demo

| 字段 | 值 |
|------|----|
| HTTP | 200 |
| `intent` | `trade_preview_demo` |
| `status` | **`awaiting_human_approval`** |
| `requires_human_approval` | `true` |
| `preview_payload` 存在 | ✅ keys: `cap_impact_summary, depth_chart_impact_summary, preview, requires_human_approval, roster_impact_summary, salary_matching, sample_data, team_a_post_trade, team_b_post_trade, trade_transaction` |
| `agent_trace.steps` 数量 | 5 |
| `intelligence_summary` 存在 | ✅ |
| `summary_title` | **交易预览：DEM-ATL ↔ DEM-PDX 双方交易方案** |
| `deterministic_verdict` | 规则检查通过 |
| `source` | `deterministic-fake-adapter` |

### S3. hold

| 字段 | 值 |
|------|----|
| HTTP | 200 |
| `intent` | `hold` |
| `status` | **`hold`** |
| `requires_human_approval` | `true` |
| `preview_payload` 存在 | ✅ keys: `evidence, hold_reason, intent, limitations, recommended_actions, requires_human_approval, sample_data, status, tool_trace` |
| `agent_trace.steps` 数量 | 5 |
| `intelligence_summary` 存在 | ✅ |
| `summary_title` | **暂不行动：当前条件下建议保持观望** |
| `deterministic_verdict` | 建议暂不行动（hold） |
| `source` | `deterministic-fake-adapter` |
| 反推荐签约校验 | ✅ 未出现"补强方案"、"双方交易"字样 |

### S4. execute_trade (blocked)

| 字段 | 值 |
|------|----|
| HTTP | 200 |
| `intent` | `execute_trade` |
| `status` | **`blocked`** |
| `requires_human_approval` | `true` |
| `preview_payload` 存在 | ✅ keys: `evidence, hold_reason, intent, limitations, recommended_actions, requires_human_approval, sample_data, status, tool_trace` |
| `agent_trace.steps` 数量 | 5 |
| `intelligence_summary` 存在 | ✅ |
| `summary_title` | **安全拦截：该请求类型未被允许** |
| `deterministic_verdict` | 请求已被安全拦截，未生成方案 |
| `source` | `deterministic-fake-adapter` |
| 反可执行方案校验 | ✅ 未出现"补强方案/双方交易/推荐交易/推荐签约/已执行"字样 |

## 5. 危险词检查结果

对每个场景的 `intelligence_summary` 做字典扫描（英文大小写不敏感；中文精确匹配；技术 ID 大小写不敏感），所有 5 个场景的命中数**全部为 0**：

| 危险词组 | S1 (ATL→hold) | S1a (signing) | S2 (trade) | S3 (hold) | S4 (blocked) |
|----------|:-:|:-:|:-:|:-:|:-:|
| 英文（executed/applied/committed/auto_execute/auto_approve/live/current/real-time/real time） | 0 | 0 | 0 | 0 | 0 |
| 中文（已执行/已完成签约/已完成交易/自动批准/已提交/已落地/实时/最新/当前阵容/当前薪资） | 0 | 0 | 0 | 0 | 0 |
| 技术 ID（run_id/snapshot_id/sourcepack/nba_2025_26） | 0 | 0 | 0 | 0 | 0 |

另外 `approval_note` 在所有场景下都包含"只读"与"人工"字样，确认披露了只读预览 + 人工复核语义；`data_limitations` 也在所有场景下固定披露"演示/历史样本"属性。

## 6. 旧字段兼容检查结果

所有 5 个 HTTP 响应都包含完整的旧 7 个字段，无缺失、无改名、无类型变化：

- ✅ `intent`：字符串，与请求一致（S1/S1a 为 `signing_preview`，S2 为 `trade_preview_demo`，S3 为 `hold`，S4 为 `execute_trade`）
- ✅ `status`：字符串，取值在 `awaiting_human_approval` / `hold` / `blocked` 之间
- ✅ `requires_human_approval`：5/5 个场景均为 `true`
- ✅ `preview_payload`：dict，signing/trade 场景包含对应的 proposal/trade_transaction 结构，hold/blocked 场景包含 hold_reason
- ✅ `agent_trace`：dict，`steps` 固定为 5 个编排步骤，`requires_human_approval` 内层也是 `true`
- ✅ `warnings`：list，存在
- ✅ `limitations`：list，存在，固定 5 条数据/规则限制说明

`intelligence_summary` 自身的 9 个字段（summary_title / plain_language_summary / deterministic_verdict / evidence_summary / risk_summary / approval_note / data_limitations / next_review_questions / source）在 5/5 场景全部齐整。

## 7. 结论

| 项 | 结果 |
|----|------|
| 4 种指定场景（signing / trade / hold / blocked）都返回 intelligence_summary | ✅ 通过 |
| signing 场景（DEM-ATL）summary 标题为"签约预览"、裁定为"规则检查通过"、明确标注只读预览 | ✅ 通过 |
| trade 场景 summary 标题为"交易预览"、裁定为"规则检查通过"、明确标注只读预览 | ✅ 通过 |
| hold 场景 summary 为"暂不行动"，不写成签约或交易推荐 | ✅ 通过 |
| blocked 场景 summary 为"安全拦截"，不伪装成可执行方案 | ✅ 通过 |
| `requires_human_approval` 外层 + 内层（agent_trace / preview_payload）均为 true | ✅ 通过 |
| 英文/中文/技术 ID 危险词扫描 0 命中 | ✅ 通过 |
| 旧 7 字段完整保留 | ✅ 通过 |
| 非 demo 球队（ATL）signing 场景安全降级到 HOLD，summary 按 status 输出（status 优先于 intent） | ✅ 通过（附加验证） |
| 工作区未改任何 frontend/backend 业务代码/data/snapshot | ✅ 通过 |

**Smoke 结论：通过，建议进入 ChatGPT 验收。**
