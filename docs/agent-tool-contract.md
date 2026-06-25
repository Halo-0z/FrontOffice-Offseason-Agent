# Agent Tool Contract

> Milestone: M8-E1 (docs-only)
>
> Status: Contract / boundary freeze. No runtime code in this milestone.
>
> Scope: This document is the **FrontOffice Agent tool contract**. It
> defines what the Agent and any backing LLM may do, what they may not
> do, the unified tool result envelope, and the per-tool contract for
> the 11 tools that make up the Agent's read-only/sim-only action
> surface.

---

## 0. 项目定位

FrontOffice-Offseason-Agent 的重心是 **Agent**，不是 NBA 数据库。

- 真实 snapshot 只是 Agent 的**数据燃料**，不是项目本体。
- Agent 可以**规划、调用只读工具、解释结果**。
- Agent **不能执行签约、交易、阵容修改、真实数据写入**。
- LLM 只能**解释和组织结果**，不能覆盖确定性工具结果。
- 所有模拟结果都是**只读预览**，必须经人工确认后才允许进入下一步。

统一文案贯穿全文：

> **这是只读预览，不会自动执行。**

---

## 1. Agent 权限边界

### 1.1 Agent / LLM 可以

- 理解用户目标
- 拆解任务
- 选择只读工具
- 调用确定性模拟工具
- 汇总工具结果
- 生成解释
- 标注风险
- 请求人工确认

### 1.2 Agent / LLM 不可以

- 修改 roster
- 修改 contract / cap state
- 写入 snapshot
- 执行 signing / trade
- 自己发明薪资数据
- 绕过 salary validation
- 把 demo data 说成真实数据
- 把 historical snapshot 说成当前实时 NBA 数据
- 没有人类确认就推进操作

> 任何超出上述白名单的能力都不属于 Agent，必须由确定性服务在
> 人工确认后执行。Agent 永远不是 autonomous trade executor。

---

## 2. 统一 Tool Result Envelope

所有工具的返回必须套用以下结构。确定性服务产出 `status` /
`artifacts` / `technical_details`；LLM 只能填充 `summary` /
`next_actions` 等解释字段，不能改写 status 或 artifacts。

```jsonc
{
  // 工具名，必须与第 4 节契约中的 tool_name 一致
  "tool_name": "simulate_signing",

  // 确定性裁决，LLM 不可覆盖
  "status": "success | warning | blocked | error",

  // 一句话人话总结（可由 LLM 生成，但不得与 status 冲突）
  "summary": "签约后 GSW 薪资仍低于第一 apron。",

  // 确定性服务产出的警告列表
  "warnings": [
    "snapshot 'nba-...' has manual_review_required=true"
  ],

  // 建议的下一步（仅建议，不自动执行）
  "next_actions": [
    "request_human_approval"
  ],

  // 逻辑引用，不得放文件路径或原始大对象
  "artifacts": {
    "proposal_id": "prop-2025-001",
    "preview_id": "prev-2025-001",
    "evidence_ids": ["ev-2526-cap-levels"]
  },

  // 是否需要人工复核（manual review 数据 / warning 状态必为 true）
  "requires_human_review": true,

  // 数据源上下文，由 resolver 生成，工具不得篡改
  "source_context": {
    "data_source_id": "demo",
    "data_source_label": "演示数据",
    "sample_data": true,
    "snapshot_id": null,
    "snapshot_type": null,
    "manual_review_required": false
  },

  // 调试用技术详情，前端默认折叠
  "technical_details": {
    "resolver_kind": "demo | snapshot | offline",
    "validator_warnings_count": 0,
    "rule_engine_version": "m6-v1"
  }
}
```

### 2.1 约束

- `artifacts` 只能放 `proposal_id`、`preview_id`、`evidence_id` 等
  **逻辑引用**，不允许放文件路径或原始 JSON 大对象。
- **不允许工具接受任意文件路径作为 Agent 参数。** 所有数据访问
  必须通过 resolver / service 句柄。
- `data_source_id` 必须是 resolver 生成的**只读句柄**，工具不得
  自行构造或篡改。
- `status` 由确定性工具产生，LLM 不得改写。
- `source_context` 由 resolver 注入，工具不得覆盖。

---

## 3. Human Approval Contract

### 3.1 只需要展示（无需确认即可查看）

- 数据源说明
- 球队上下文
- 候选列表
- 校验失败原因
- evidence notes
- HOLD 建议

### 3.2 必须人工确认

- 所有 signing proposal
- 所有 trade proposal
- 所有 projected roster / depth chart
- 使用 manual-review 数据形成的建议
- 从 warning 状态继续比较或规划

### 3.3 永远不能自动执行

- 修改 roster
- 修改 contract / cap state
- 写入 snapshot
- 执行 signing / trade
- 将 preview 标记为正式交易
- 绕过 rule engine

### 3.4 统一文案

所有需要确认的输出必须带：

> 这是只读预览，不会自动执行。

人工确认后的最大状态是 `approved_preview`，**不等于**真实交易或
签约已获批。`approved_preview` 只表示“用户已看过并同意继续”，
真正的执行不在本系统范围内。

---

## 4. 11 个工具契约

每个工具契约包含以下字段：

- `tool_name`
- `purpose`
- `allowed_inputs`
- `output_schema`
- `reads`
- `writes`
- `deterministic_or_llm`
- `failure_modes`
- `fallback_behavior`
- `user_visible_trace_label`
- `human_approval_required`
- `safety_notes`

---

### 4.1 `load_active_data_source`

| 字段 | 值 |
|------|-----|
| `purpose` | 读取当前数据源状态，返回 demo / snapshot / offline fallback、人话 label、warnings。 |
| `allowed_inputs` | 无（读取 resolver 缓存）。 |
| `output_schema` | envelope，`artifacts` 无；`source_context` 为核心载荷。 |
| `reads` | data_source_resolver 缓存 |
| `writes` | 无 |
| `deterministic_or_llm` | deterministic |
| `failure_modes` | resolver 缓存未初始化；snapshot load 失败。 |
| `fallback_behavior` | offline → 返回 demo fallback + offline label。 |
| `user_visible_trace_label` | 「读取当前数据」 |
| `human_approval_required` | 否 |
| `safety_notes` | **不能把 historical snapshot 说成 current/live。** snapshot_type=historical_source_backed 必须在 label 中体现「历史样本」。 |

---

### 4.2 `inspect_team_context`

| 字段 | 值 |
|------|-----|
| `purpose` | 读取球队薪资、阵容、位置缺口。 |
| `allowed_inputs` | `team_id`（必须存在于当前数据源）。 |
| `output_schema` | envelope，`artifacts` 含 team_id；salary summary、roster list、position gaps。 |
| `reads` | cap_sheet_service、roster_need_service |
| `writes` | 无 |
| `deterministic_or_llm` | deterministic |
| `failure_modes` | team_id 不存在；跨数据源拼接。 |
| `fallback_behavior` | team 不在当前数据源 → blocked，不跨源拼接。 |
| `user_visible_trace_label` | 「分析球队现状」 |
| `human_approval_required` | 否 |
| `safety_notes` | **不得跨数据源拼接球队上下文。** demo 数据中的球队不得到 snapshot 里找合同。 |

---

### 4.3 `find_candidate_players`

| 字段 | 值 |
|------|-----|
| `purpose` | 按位置、预算、角色筛候选。 |
| `allowed_inputs` | `position`、`max_salary`、`role`、`team_id`。 |
| `output_schema` | envelope，`artifacts` 含 candidate player_ids 列表。 |
| `reads` | free_agent_service |
| `writes` | 无 |
| `deterministic_or_llm` | deterministic |
| `failure_modes` | 无候选；候选薪资缺失。 |
| `fallback_behavior` | 候选薪资缺失 → 从候选集中移除，并在 warnings 中标注。 |
| `user_visible_trace_label` | 「查找候选球员」 |
| `human_approval_required` | 否 |
| `safety_notes` | **缺失薪资的候选不能进入 signing simulation。** 不允许 LLM 猜测薪资。 |

---

### 4.4 `simulate_signing`

| 字段 | 值 |
|------|-----|
| `purpose` | 生成签约后的只读预览。 |
| `allowed_inputs` | `team_id`、`player_id`、`salary`（来自合同/FA 服务，非 LLM 自报）。 |
| `output_schema` | envelope，`artifacts` 含 proposal_id / preview_id；projected cap state、depth chart。 |
| `reads` | cap_sheet_service、depth_chart_projector |
| `writes` | 无（只生成 preview 对象，不落盘） |
| `deterministic_or_llm` | deterministic |
| `failure_modes` | player_id 不存在；salary 与服务不一致。 |
| `fallback_behavior` | salary 不一致 → blocked，要求使用服务返回的 salary。 |
| `user_visible_trace_label` | 「模拟签约方案」 |
| `human_approval_required` | 是（preview 生成后必须人工确认才能继续） |
| `safety_notes` | **只模拟，不执行。** 不写入 roster / contract。 |

---

### 4.5 `simulate_trade`

| 字段 | 值 |
|------|-----|
| `purpose` | 生成两队交易后的只读预览。 |
| `allowed_inputs` | `team_a_id`、`team_b_id`、`players_a`、`players_b`（player_id 列表）。 |
| `output_schema` | envelope，`artifacts` 含 proposal_id / preview_id；salary matching、roster impact。 |
| `reads` | trade_simulator、cap_sheet_service |
| `writes` | 无 |
| `deterministic_or_llm` | deterministic |
| `failure_modes` | player 不在指定队；salary matching 失败。 |
| `fallback_behavior` | salary matching 失败 → blocked。 |
| `user_visible_trace_label` | 「模拟交易方案」 |
| `human_approval_required` | 是 |
| `safety_notes` | **salary 由合同服务读取，不接受 LLM 自报金额作为事实。** |

---

### 4.6 `validate_salary_rules`

| 字段 | 值 |
|------|-----|
| `purpose` | 唯一的薪资和交易规则裁决工具。 |
| `allowed_inputs` | `proposal_id` 或完整 proposal 对象。 |
| `output_schema` | envelope，`status` = PASS / WARNING / BLOCKED；rule violations 列表。 |
| `reads` | transaction_rule_engine、cap rule config |
| `writes` | 无 |
| `deterministic_or_llm` | **deterministic only** |
| `failure_modes` | proposal 结构非法；cap config 缺失。 |
| `fallback_behavior` | cap config 缺失 → error，不继续。 |
| `user_visible_trace_label` | 「检查薪资规则」 |
| `human_approval_required` | 否（裁决本身不需要确认，但基于裁决的下一步需要） |
| `safety_notes` | **PASS / WARNING / BLOCKED 只能由确定性规则产生，LLM 不能覆盖。** 这是项目最核心的确定性边界。 |

---

### 4.7 `validate_roster_balance`

| 字段 | 值 |
|------|-----|
| `purpose` | 检查人数、位置深度、阵容风险。 |
| `allowed_inputs` | `team_id`、projected roster。 |
| `output_schema` | envelope，roster size、position depth、risk flags。 |
| `reads` | roster_need_service、depth_chart_projector |
| `writes` | 无 |
| `deterministic_or_llm` | deterministic（启发式） |
| `failure_modes` | roster 数据不完整。 |
| `fallback_behavior` | 数据不完整 → warning，标注「阵容信息不完整」。 |
| `user_visible_trace_label` | 「检查阵容影响」 |
| `human_approval_required` | 否 |
| `safety_notes` | **这是启发式阵容风险，不是教练结论。** 不得表述为「教练建议」。 |

---

### 4.8 `validate_data_quality`

| 字段 | 值 |
|------|-----|
| `purpose` | 检查结果是否受 demo / snapshot / manual review 影响。 |
| `allowed_inputs` | 当前 source_context + artifacts。 |
| `output_schema` | envelope，data_quality_flags（is_demo / is_historical_snapshot / has_manual_review / is_offline_fallback）。 |
| `reads` | data_source_resolver |
| `writes` | 无 |
| `deterministic_or_llm` | deterministic |
| `failure_modes` | resolver 状态未初始化。 |
| `fallback_behavior` | 未初始化 → 视为 offline fallback。 |
| `user_visible_trace_label` | 「核对数据质量」 |
| `human_approval_required` | 否 |
| `safety_notes` | **historical snapshot 不能包装成实时数据。** must surface `is_historical_snapshot=true` 到 user-visible label。 |

---

### 4.9 `collect_evidence`

| 字段 | 值 |
|------|-----|
| `purpose` | 收集 evidence notes、source URLs、confidence。 |
| `allowed_inputs` | `team_id`、`player_ids`、`topics`。 |
| `output_schema` | envelope，`artifacts` 含 evidence_ids 列表；evidence notes 数组。 |
| `reads` | evidence_service |
| `writes` | 无 |
| `deterministic_or_llm` | deterministic |
| `failure_modes` | 无匹配 evidence。 |
| `fallback_behavior` | 无匹配 → warning「未找到支持证据」，不编造。 |
| `user_visible_trace_label` | 「整理支持证据」 |
| `human_approval_required` | 否 |
| `safety_notes` | **不得生成不存在的 evidence_id 或 URL。** LLM 不得补全 evidence。 |

---

### 4.10 `generate_recommendation_explanation`

| 字段 | 值 |
|------|-----|
| `purpose` | 把工具结果整理成人话建议。 |
| `allowed_inputs` | 全部上游 envelope（proposal、validation、evidence、data_quality）。 |
| `output_schema` | envelope，recommendation text、risk summary、next_actions。 |
| `reads` | 上游 envelopes |
| `writes` | 无 |
| `deterministic_or_llm` | M8-E 初期 **deterministic template**；未来可引入 LLM 解释层。 |
| `failure_modes` | 上游 envelope 缺失关键字段。 |
| `fallback_behavior` | 缺失 → 使用保守模板「数据不足，建议人工复核」。 |
| `user_visible_trace_label` | 「生成建议」 |
| `human_approval_required` | 是（建议本身需展示，执行需确认） |
| `safety_notes` | **未来即使用 LLM，也只能解释，不能改金额、verdict、evidence IDs。** LLM 输出不得覆盖 `validate_salary_rules` 的 status。 |

---

### 4.11 `request_human_approval`

| 字段 | 值 |
|------|-----|
| `purpose` | 构造不可跳过的人工确认 gate。 |
| `allowed_inputs` | recommendation envelope + proposal_id。 |
| `output_schema` | envelope，`status` = awaiting_human_approval；approval_state=pending。 |
| `reads` | 上游 recommendation |
| `writes` | 无（只设置 approval_state，不执行） |
| `deterministic_or_llm` | deterministic |
| `failure_modes` | 上游 recommendation 缺失。 |
| `fallback_behavior` | 缺失 → blocked，不允许进入 approval gate。 |
| `user_visible_trace_label` | 「等待人工确认」 |
| `human_approval_required` | **是（这就是确认 gate 本身）** |
| `safety_notes` | **不能返回 transaction executed。** 确认后最多进入 `approved_preview`，不等于真实交易或签约获批。 |

---

## 5. 工具调用顺序约束

工具不是任意可组合的。以下顺序约束必须遵守：

1. `load_active_data_source` 必须在任何读取工具之前调用。
2. `inspect_team_context` 必须在 `find_candidate_players` 之前。
3. `simulate_signing` / `simulate_trade` 必须在 `validate_salary_rules` 之前。
4. `validate_salary_rules` 必须在 `validate_roster_balance` 之前。
5. `validate_data_quality` 必须在 `generate_recommendation_explanation` 之前。
6. `collect_evidence` 必须在 `generate_recommendation_explanation` 之前。
7. `request_human_approval` 必须是最后一步，不可跳过。

`validate_salary_rules` 是**唯一**的薪资裁决工具。任何其他工具
不得产出 PASS / WARNING / BLOCKED 的薪资结论。

---

## 6. LLM 边界总表

| 能力 | Agent/LLM | 确定性服务 | 人工 |
|------|-----------|------------|------|
| 理解目标 | ✅ | — | — |
| 拆解任务 | ✅ | — | — |
| 选只读工具 | ✅ | — | — |
| 读取数据 | — | ✅ | — |
| 模拟签约/交易 | — | ✅ | — |
| 薪资裁决 | — | ✅（唯一） | — |
| 生成解释 | ✅（模板/LLM） | — | — |
| 标注风险 | ✅ | — | — |
| 改金额/verdict | ❌ | ✅ | — |
| 执行交易/签约 | ❌ | ❌ | ❌（本系统外） |
| 人工确认 | — | — | ✅ |

---

## 7. 本文档不涉及

- 真实 NBA API 接入
- 30 队数据扩展
- runtime API scraping
- 自动落库 / 自动执行 / 真实交易执行
- LLM 直接调用 OpenAI API（M8-E 不接 OpenAI）

---

## 8. 后续实现拆分

- **M8-E1**（本文档）：docs-only Agent tool contract，不改代码。
- **M8-E2**：backend trace schema 扩展。
- **M8-E3**：frontend trace display。
- **M8-E4**：guardrail tests。
- **M8-E5**：optional orchestrator stub（仍不接 OpenAI API，只做只读 stub）。

M8-E1 只写文档；M8-E2 才开始扩展 trace schema；M8-E5 也不接
OpenAI API，只做只读 orchestrator stub。
