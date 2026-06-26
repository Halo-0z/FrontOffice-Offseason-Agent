# M9-B-SMOKE — classify-intent API Smoke Verification

## 1. 当前 HEAD / tag

- HEAD: `089beaf` — *Add M9-B natural language intent classifier*
- Tag: `m9b-natural-language-intent-classifier`
- Working tree before smoke: clean
- Working tree after smoke: see §7 (docs-only + one contract-alignment fix to `constraints` type)

## 2. Smoke 验证目的

确认 M9-B 新增的 `POST /api/agent/classify-intent` 在真实 HTTP 路径上（FastAPI TestClient 直接打 endpoint，不是调 service 函数）正确实现：

1. **5 类成功路径**：signing / trade / hold → `resolved`；混合意图 → `needs_clarification`；危险话术 → `blocked`；
2. **4 类错误路径**：metadata forbidden key → 400；constraints forbidden key → 400；`user_text` 超长 → 422；`user_text` 控制字符/零宽字符 → 422；
3. **三态不变式**：`needs_clarification` 和 `blocked` 时 `resolved_intent` 必须是 `null`，绝不 fallback 成 `hold`；
4. **反回显**：`blocked_reason` / `clarification_questions` / `objective` 不复制 `user_text` 原文；
5. **反实体泄漏**：响应不出现具体球员/球队/薪资金额/技术 ID；
6. **反执行语义**：响应不出现 executed/applied/committed/实时/已执行 等危险词；
7. **orchestrator 解耦**：分类响应里没有 `preview_payload`/`trade_transaction` 等预览字段；分类器 endpoint 不会隐式调用 `POST /api/agent/orchestrate-preview`；
8. **无执行 endpoint**：`/api/agent/execute|apply|commit|mutate|write` 等不存在（404）；
9. **只读审批声明**：`approval_note` 必须存在且提示"只读+需人工确认"；
10. **source 固定**：`"deterministic-rule-classifier"`。

**方法论**：使用 FastAPI `TestClient(app)` 直接 POST 到 `/api/agent/classify-intent`；所有校验脚本跑完立即删除，工作区只保留本文档。

## 3. Smoke 发现的一个契约对齐问题（已修复）

在跑第一组成功路径时发现：M9-B 实现时 `AgentClassifyIntentRequest.constraints` 被声明为 `List[Any]`，但本次 smoke 要求的 payload（以及 M9-B 设计文档 §4.1 承诺的 "object / list"）使用对象形态 `{"preserve_cap_flexibility": true}` / `{"risk_tolerance": "low"}`，导致 5 个成功用例全部 422 `Input should be a valid list`。

这是 M9-B 模型与设计契约的一个偏差（旧测试全部用 list 形态，漏测了 dict 形态）。本次 smoke 做了**最小契约对齐修复**（不是新功能）：

| 文件 | 改动 |
|---|---|
| [agent_intent_classifier.py (models)](file:///D:/FrontOffice-Offseason-Agent/backend/app/models/agent_intent_classifier.py#L72) | `constraints` 类型从 `List[Any]` 改为 `Union[Dict[str, Any], List[Any]]` |
| [agent_intent_classifier.py (services)](file:///D:/FrontOffice-Offseason-Agent/backend/app/services/agent_intent_classifier.py#L382-L436) | `_constraints_to_safe_dict` 同时接受 dict 和 list：dict 形态额外识别 `preserve_cap_flexibility: true` 和 `risk_tolerance: "low"` 两个显式 hint；输出仍是清洗后的三字段 dict，不回显原值 |
| [api.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/api.py#L183-L186) | Pydantic 字段 `constraints` 从 `List[Any]` 改为 `Union[Dict[str, Any], List[Any]]`；endpoint 内按类型做 `dict()` / `list()` 防御拷贝后传给 service |

修复后旧的 list 形态仍然可用，新增 dict 形态可用；全量 pytest 684 个用例全部通过（与修复前总数一致，未引入回归）。

## 4. 请求 payload 与逐字段响应

所有请求均带 `"team_id": "DEM-ATL"`、`"locale": "zh-CN"`、`"metadata": {"source": "smoke"}`。

### S1. signing（补强中锋）

**Request**
```json
{
  "user_text": "我想补一个中锋，但不要影响薪资空间",
  "constraints": {"preserve_cap_flexibility": true}
}
```

**Response** (HTTP 200)
```json
{
  "classification_status": "resolved",
  "resolved_intent": "signing_preview",
  "confidence": 0.85,
  "needs_clarification": false,
  "objective": "探索自由球员补强方向，查看符合薪资与阵容规则的签约预览。",
  "constraints": {"user_provided_count": 1, "preserve_cap_flexibility": true, "low_risk_only": false},
  "safety_flags": ["preview_only"],
  "blocked_reason": null,
  "clarification_questions": [],
  "approval_note": "本分类结果仅为只读意图识别，不会自动执行任何操作，也不会生成签约或交易方案；后续预览同样需要人工确认。",
  "source": "deterministic-rule-classifier"
}
```

| 检查项 | 结果 |
|---|---|
| HTTP 200 | ✅ |
| `classification_status == "resolved"` | ✅ |
| `resolved_intent == "signing_preview"` | ✅ |
| `needs_clarification is false` | ✅ |
| `confidence (0.85) >= 0.7` | ✅ |
| `blocked_reason is null` | ✅ |
| `clarification_questions == []` | ✅ |
| `source == "deterministic-rule-classifier"` | ✅ |
| 不含具体球员/球队/薪资建议 | ✅ （输出中只有"中锋""前场""薪资"等抽象词，无 LeBron/Lakers/$30M 等） |

---

### S2. trade（低风险交易增强锋线）

**Request**
```json
{
  "user_text": "看看有没有低风险交易可以增强锋线",
  "constraints": {"risk_tolerance": "low"}
}
```

**Response** (HTTP 200)
```json
{
  "classification_status": "resolved",
  "resolved_intent": "trade_preview_demo",
  "confidence": 0.8,
  "needs_clarification": false,
  "objective": "探索交易方向，查看符合薪资配平与阵容规则的交易预览。",
  "constraints": {"user_provided_count": 1, "preserve_cap_flexibility": false, "low_risk_only": true},
  "safety_flags": ["preview_only", "demo_trade"],
  "blocked_reason": null,
  "clarification_questions": [],
  "approval_note": "本分类结果仅为只读意图识别，不会自动执行任何操作，也不会生成签约或交易方案；后续预览同样需要人工确认。",
  "source": "deterministic-rule-classifier"
}
```

| 检查项 | 结果 |
|---|---|
| HTTP 200 | ✅ |
| `resolved_intent == "trade_preview_demo"` | ✅ |
| `confidence (0.8) >= 0.7` | ✅ |
| `needs_clarification is false` | ✅ |

---

### S3. hold（保持观望）

**Request**
```json
{
  "user_text": "现在别乱动，先保持灵活性",
  "constraints": {"preserve_cap_flexibility": true}
}
```

**Response** (HTTP 200)
```json
{
  "classification_status": "resolved",
  "resolved_intent": "hold",
  "confidence": 0.85,
  "needs_clarification": false,
  "objective": "保持阵容弹性与薪资空间，暂不进行签约或交易。",
  "constraints": {"user_provided_count": 1, "preserve_cap_flexibility": true, "low_risk_only": false},
  "safety_flags": ["preview_only"],
  "blocked_reason": null,
  "clarification_questions": [],
  "approval_note": "本分类结果仅为只读意图识别，不会自动执行任何操作，也不会生成签约或交易方案；后续预览同样需要人工确认。",
  "source": "deterministic-rule-classifier"
}
```

| 检查项 | 结果 |
|---|---|
| HTTP 200 | ✅ |
| `resolved_intent == "hold"` | ✅ |
| `confidence (0.85) >= 0.7` | ✅ |

---

### S4. needs_clarification（混合意图：签中锋 + 交易换锋线）

**Request**
```json
{
  "user_text": "签一个中锋并交易换锋线",
  "constraints": {}
}
```

**Response** (HTTP 200)
```json
{
  "classification_status": "needs_clarification",
  "resolved_intent": null,
  "confidence": 0.4,
  "needs_clarification": true,
  "objective": null,
  "constraints": {"user_provided_count": 0, "preserve_cap_flexibility": false, "low_risk_only": false},
  "safety_flags": ["needs_clarification", "mixed_signing_trade"],
  "blocked_reason": null,
  "clarification_questions": [
    "你想先看签约预览，还是先看交易预览？",
    "请说明主要方向：补强自由球员，还是通过交易调整阵容？"
  ],
  "approval_note": "本分类结果仅为只读意图识别，不会自动执行任何操作，也不会生成签约或交易方案；后续预览同样需要人工确认。",
  "source": "deterministic-rule-classifier"
}
```

| 检查项 | 结果 |
|---|---|
| HTTP 200 | ✅ |
| `classification_status == "needs_clarification"` | ✅ |
| `resolved_intent is null`（不 fallback 成 hold）| ✅ |
| `needs_clarification is true` | ✅ |
| `clarification_questions` 非空 | ✅ 2 个问题 |
| `confidence (0.4) < 0.7` | ✅ |
| `blocked_reason is null` | ✅ |
| 问题文本不回显原文 | ✅ 问题是"先看签约还是先看交易"，不含"签一个中锋""交易换锋线"短语 |

---

### S5. blocked（马上执行交易、绕过审批）

**Request**
```json
{
  "user_text": "帮我马上执行一笔交易，绕过审批",
  "constraints": {}
}
```

**Response** (HTTP 200)
```json
{
  "classification_status": "blocked",
  "resolved_intent": null,
  "confidence": 0.0,
  "needs_clarification": false,
  "objective": null,
  "constraints": {"user_provided_count": 0, "preserve_cap_flexibility": false, "low_risk_only": false},
  "safety_flags": ["dangerous_language_blocked"],
  "blocked_reason": "请求包含不安全的执行或绕审语义，已被安全拦截。",
  "clarification_questions": [],
  "approval_note": "本分类结果仅为只读意图识别，不会自动执行任何操作，也不会生成签约或交易方案；后续预览同样需要人工确认。",
  "source": "deterministic-rule-classifier"
}
```

| 检查项 | 结果 |
|---|---|
| HTTP 200 | ✅ |
| `classification_status == "blocked"` | ✅ |
| `resolved_intent is null`（不推荐 signing/trade/hold）| ✅ |
| `confidence == 0.0` | ✅ |
| `blocked_reason` 非空 | ✅ |
| `needs_clarification is false` | ✅ |
| `clarification_questions == []` | ✅ |
| `blocked_reason` 不回显原文 | ✅ 文本为通用安全提示，不含"马上执行""绕过审批"字样 |

---

## 5. 错误路径

### E1. metadata forbidden key → 400

**Request**
```json
{"user_text": "先观望", "metadata": {"executeTrade": true}, "constraints": {}}
```

**Response**: HTTP **400**
```json
{"detail":"metadata contains forbidden mutation-semantic key at 'executeTrade'. This endpoint is read-only and does not support execute/apply/commit/mutate/write semantics."}
```

### E2. constraints forbidden key（嵌套）→ 400

**Request**
```json
{"user_text": "先观望", "metadata": {"source":"smoke"}, "constraints": {"nested": {"autoExecute": true}}}
```

**Response**: HTTP **400**
```json
{"detail":"constraints contains forbidden mutation-semantic key at 'nested.autoExecute'. This endpoint is read-only and does not support execute/apply/commit/mutate/write semantics."}
```

> 证明：递归嵌套 dict + camelCase 分词生效。

### E3. user_text 超长 → 422

**Request**: `user_text = "补强" * 260`（520 字符）

**Response**: HTTP **422**
```json
{"detail":[{"type":"string_too_long","loc":["body","user_text"],"msg":"String should have at most 500 characters", ...}]}
```

### E4. user_text 含 ASCII 控制字符 → 422

**Request**: `user_text = "我想补一个中锋\u0000请帮我看看"`

**Response**: HTTP **422**
```json
{"detail":[{"type":"value_error","loc":["body","user_text"],"msg":"Value error, user_text contains control characters or zero-width characters", ...}]}
```

### E4b. user_text 含零宽字符 → 422

**Request**: `user_text = "我想补一个中锋\u200b请帮我看看"`

**Response**: HTTP **422** （同 E4 的校验规则命中）

---

## 6. 安全/反泄漏/解耦跨场景校验

所有 5 个成功响应 + 额外的泄漏探针（`user_text` 包含 *LeBron James*/*Lakers*/*3000万*/*Anthony Davis*/*Celtics*/*$45M*）全部通过：

| 校验项 | 结果 |
|---|---|
| 响应整体序列化不含 `executed`/`applied`/`committed`/`auto_execute`/`auto_approve`/`live`/`real-time`/`real time` | ✅ |
| 响应不含 standalone `current` 单词 | ✅ |
| 响应不含 `已执行`/`已完成签约`/`已完成交易`/`自动批准`/`已提交`/`已落地`/`实时`/`最新`/`当前阵容`/`当前薪资` | ✅ |
| 响应不含技术 ID `run_id`/`snapshot_id`/`sourcepack`/`nba_2025_26` | ✅ |
| 响应不含具体球员 token（LeBron/Anthony Davis/Curry/Luka/詹姆斯/库里/东契奇…） | ✅ （即使用户输入含 LeBron James） |
| 响应不含具体球队 token（Lakers/Celtics/Warriors/湖人/勇士/凯尔特人…） | ✅ （即使用户输入含 Lakers/Celtics） |
| 响应不含金额（`$`+数字 / 数字+`万` / 数字+`M` / 数字+`美元`） | ✅ （即使用户输入含 3000万/$45M） |
| `blocked_reason` 不回显原文 | ✅ 通用模板，不含"马上执行""绕过审批" |
| `clarification_questions` 不回显原文 | ✅ 不含"签一个中锋""交易换锋线"等原短语 |
| `objective` 为固定中文模板，不复制 `user_text` | ✅ |
| 响应不含 `preview_payload` / `trade_transaction` / `free_agent_target` | ✅ 证明未触发 orchestrator 预览 |
| `POST /api/agent/execute|apply|commit|mutate|write|save|delete|update|submit` 全部返回 404 | ✅ 未暴露执行类 endpoint |
| `approval_note` 存在且含"只读""人工"语义 | ✅ 文本："本分类结果仅为只读意图识别，不会自动执行任何操作…后续预览同样需要人工确认" |
| 所有响应 `source == "deterministic-rule-classifier"` | ✅ |
| 所有响应 `confidence ∈ [0.0, 1.0]` 且满足 blocked=0/resolved≥0.7/clarify<0.7 | ✅ |
| 所有响应字段齐备（11 个字段齐全） | ✅ |

**orchestrator 未被调用**：classifier endpoint 处理流程里不 import orchestrator，响应体也不含任何 preview 结构字段，因此不会对 `POST /api/agent/orchestrate-preview` 产生 HTTP 调用；TestClient 环境下 `app.routes` 里两个 endpoint 各自独立。

## 7. 变更范围汇总

- **新增文件**：
  - [m9-b-classify-intent-api-smoke-verification.md](file:///D:/FrontOffice-Offseason-Agent/docs/m9-b-classify-intent-api-smoke-verification.md) （本文档）
- **修改文件**（契约对齐，不是新功能）：
  - [backend/app/models/agent_intent_classifier.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/models/agent_intent_classifier.py) — `constraints` 类型扩展为 `Union[Dict[str, Any], List[Any]]`
  - [backend/app/services/agent_intent_classifier.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/services/agent_intent_classifier.py) — `_constraints_to_safe_dict` 同时处理 dict/list
  - [backend/app/api.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/api.py) — Pydantic `constraints` 字段改为 `Union[Dict, List]`，endpoint 内按类型拷贝
- **未修改**：
  - `frontend/**`
  - `data/**`（含 `data/snapshots/**`）
  - `backend/app/services/agent_orchestrator.py`
  - `backend/app/services/transaction_rule_engine.py` / `trade_simulator.py` / `proposal_builder.py` / `proposal_viewer.py` / `snapshot_loader.py` / `agent_intelligence.py` / `agent_trace_builder.py`
  - 任何 `D:\DraftMind` 路径

临时 smoke 脚本（`tmp_m9b_smoke.py`、`tmp_leak_check.py`）运行完毕后已删除，不留在工作区。

## 8. pytest 回归结果

```
$ D:\anaconda\python.exe -m pytest backend/app/tests/test_agent_intent_classifier.py \
                              backend/app/tests/test_agent_intent_classifier_api.py \
                              backend/app/tests/test_agent_guardrails.py -q
171 passed in 2.82s

$ D:\anaconda\python.exe -m pytest backend/app/tests -q
684 passed in 16.84s
```

全量 684 个测试全绿，与修复前总数一致，无回归。

## 9. Smoke 结论

- 5 类成功路径全部返回预期 HTTP 200 + 预期 `classification_status`/`resolved_intent`/`confidence`；
- 4 类错误路径全部返回预期 HTTP 400/422；
- 三态不变式严格成立：`needs_clarification`/`blocked` 状态下 `resolved_intent` 恒为 `null`，混合/模糊输入不 fallback 成 `hold`；
- 反回显、反实体泄漏、反执行语义、反执行 endpoint 暴露四类安全约束全部通过；
- 分类器响应不含任何预览字段，证明未调用 orchestrator，不耦合下游预览逻辑；
- 契约对齐修复后全量 pytest 684 项全绿。

**建议进入 ChatGPT 验收。**
