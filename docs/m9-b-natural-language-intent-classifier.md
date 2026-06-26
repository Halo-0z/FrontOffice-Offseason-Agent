# M9-B: Natural-Language Intent Classifier

> Milestone M9, step B — deterministic / fake / rule-based intent
> classifier that sits **upstream** of the orchestrator (M8-E).

## 1. What this module does

`POST /api/agent/classify-intent` accepts one sentence of natural
language from a GM user and returns a single **intent plan** describing
what the user roughly wants to do next. It is a triage step only.

```
user text ──► classifier ──► intent plan (resolved / needs_clarification / blocked)
                                │
                                ▼
                      (future M9-C, gated separately)
                      optional preview orchestration
```

## 2. What it explicitly does NOT do

To keep the boundary tight and auditable (this is the single most
important rule of M9-B):

- **No LLM.** The classifier is 100% rule-based; no OpenAI / Anthropic /
  vLLM / any model call. No network I/O at all.
- **No preview payload.** It never builds a signing preview or a trade
  package, never picks concrete players, never constructs salary
  numbers, never touches `proposal_builder` / `proposal_viewer`.
- **No orchestrator calls.** It never imports or calls
  `agent_orchestrator`; it never POSTs to
  `/api/agent/orchestrate-preview`; it never consumes a `run_id`.
- **No mutation.** It never writes to disk, never touches
  `data/snapshots/`, never mutates `data/*.json`, never mutates the
  input request dict.
- **No execution endpoints.** Adding the classifier endpoint must NOT
  cause `/api/agent/execute`, `/api/agent/apply`, `/api/agent/commit`,
  `/api/agent/mutate`, `/api/agent/write`, `/api/agent/save`,
  `/api/agent/delete`, `/api/agent/update`, or `/api/agent/submit` to
  exist.
- **No player / team / salary echoes.** The classifier never names
  specific players, teams, or dollar amounts in its output. Specific
  nouns are always abstracted into generic positional/directional
  language ("补强前场位置", "explore trade direction",
  "需要澄清具体目标").
- **No user-text echo.** `blocked_reason`, `clarification_questions`,
  and `objective` must never copy the raw `user_text` back into the
  response.

The "no downstream coupling" rule is enforced at test time by
`test_agent_guardrails.py::test_m9b_classifier_modules_no_upstream_engine_imports`
and `test_m9b_classifier_works_without_engine_imports`, which monkeypatch
every engine/orchestrator module out of `sys.modules` and assert the
classifier still works.

## 3. Files

New in M9-B:

| Path | Purpose |
|------|---------|
| `backend/app/models/agent_intent_classifier.py` | Frozen dataclasses `AgentIntentClassificationRequest` and `AgentIntentPlan`. |
| `backend/app/services/agent_intent_classifier.py` | Pure-function rule-based classifier `classify_user_intent()`. |
| `backend/app/tests/test_agent_intent_classifier.py` | Service-level unit tests (keyword coverage, state invariants, echo ban, output sanitisation). |
| `backend/app/tests/test_agent_intent_classifier_api.py` | HTTP-level tests for the new endpoint (status codes, forbidden-key scanning, input validation, absence of execution endpoints). |
| `docs/m9-b-natural-language-intent-classifier.md` | This document. |

Modified in M9-B:

| Path | Change |
|------|--------|
| `backend/app/api.py` | Adds `POST /api/agent/classify-intent`; adds two helpers: `_contains_forbidden_key_recursive` (re-used for metadata **and** constraints, keys and values) and `_find_forbidden_value`. The existing `POST /api/agent/orchestrate-preview` endpoint is untouched. |
| `backend/app/tests/test_agent_guardrails.py` | Adds M9-B-specific guardrail tests (no LLM/network imports, no upstream-engine imports, frozen dataclass, no data-file mutation, no execution endpoints, cross-state invariants). |

The classifier must never import:

```
backend/app/services/agent_orchestrator.py
backend/app/services/transaction_rule_engine.py
backend/app/services/trade_simulator.py
backend/app/services/snapshot_loader.py
backend/app/services/proposal_builder.py
backend/app/services/proposal_viewer.py
backend/app/services/agent_intelligence.py
backend/app/services/agent_trace_builder.py
```

It also must never import `openai`, `anthropic`, `mcp`, `requests`,
`httpx`, `aiohttp`, `urllib`, `socket`, `selenium`, `playwright`,
`bs4`/`beautifulsoup`, `scrapy`, or `websocket`.

## 4. API contract

### 4.1 Request — `POST /api/agent/classify-intent`

```json
{
  "user_text": "我想补一个中锋，但不要影响薪资空间",
  "team_id": "DEM-ATL",
  "locale": "zh-CN",
  "constraints": {"preserve_cap_flexibility": true},
  "metadata": {"source": "console"}
}
```

Field rules:

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `user_text` | string | yes | 1–500 chars; no ASCII/Unicode control characters (Cc category); no zero-width characters (`\u200b`, `\u200c`, `\u200d`, `\ufeff`). Violations return **422**. |
| `team_id` | string | no (default `"DEM-ATL"`) | Not used by the rule-based classifier today; accepted for forward compatibility. |
| `locale` | string | no (default `"zh-CN"`) | Not used to switch models; Chinese/English keywords are always active. |
| `constraints` | object / list | no (default `{}`) | Recursively scanned for forbidden mutation keys **and** values. Violations return **400**. |
| `metadata` | object / list | no (default `{}`) | Recursively scanned for forbidden mutation keys **and** values. Violations return **400**. |

Forbidden keys anywhere under `metadata` or `constraints` (matched
case-insensitively against leaf keys, with camelCase / snake_case /
kebab-case split):

```
execute, apply, commit, mutate, write, persist, save, delete,
update, submit, transaction_executed, auto_execute, auto_approve,
force, override, bypass, skip_approval, bypass_validation,
bypass_approval, force_through
```

Forbidden values anywhere under `metadata` or `constraints` (checked
case-insensitively):

- Phrases (substring match):
  `transaction_executed`, `auto_execute`, `auto_approve`,
  `skip_approval`, `bypass_validation`, `bypass_approval`,
  `force_through`, `execute_trade`, `commit_transaction`, `commit_trade`,
  `apply_trade`, `modify_contract`, `write_roster`, `update_snapshot`,
  `update_roster`, `without_approval`, plus their joined/space variants
  (e.g. `skip approval`, `bypassValidation`, `auto approve`).
- Single words (after tokenising on non-alphanumerics + camelCase /
  snake_case):
  `execute`, `executed`, `apply`, `applied`, `commit`, `committed`,
  `mutate`, `mutated`, `write`, `persist`, `save`, `delete`, `update`,
  `submit`.

### 4.2 Response — `AgentIntentPlan`

```json
{
  "classification_status": "resolved",
  "resolved_intent": "signing_preview",
  "confidence": 0.9,
  "needs_clarification": false,
  "objective": "希望补强前场位置并保持薪资灵活性",
  "constraints": {"preserve_cap_flexibility": true},
  "safety_flags": [],
  "blocked_reason": null,
  "clarification_questions": [],
  "approval_note": "本结果为只读意图识别，任何后续签约或交易预览均需经过规则引擎校验并由人工确认后方可推进。",
  "source": "deterministic-rule-classifier"
}
```

Fields:

| Field | Type | Notes |
|-------|------|-------|
| `classification_status` | `"resolved"` / `"needs_clarification"` / `"blocked"` | Three-state result. |
| `resolved_intent` | `"signing_preview"` / `"trade_preview_demo"` / `"hold"` / `null` | **Must be `null` when status is `needs_clarification` or `blocked`.** Must be one of the three preview/hold constants when status is `resolved`. |
| `confidence` | float in [0.0, 1.0] | `0.0` for blocked; `>= 0.7` for resolved; `< 0.7` for needs_clarification. |
| `needs_clarification` | bool | Mirrors the status but always present for UI convenience. |
| `objective` | string / `null` | Generic Chinese description, never a verbatim echo of `user_text`, never contains a concrete player/team/salary. `null` for blocked. |
| `constraints` | object | Pass-through of a shallow sanitized copy of the request constraints (always `{}` today). |
| `safety_flags` | list of strings | e.g. `["dangerous_language_blocked"]`, `["mixed_intent"]`, `["low_confidence"]`. Empty for resolved. |
| `blocked_reason` | string / `null` | Generic Chinese text; **never** echoes `user_text`. `null` except when `classification_status == "blocked"`. |
| `clarification_questions` | list of strings | Generic Chinese follow-up questions; **never** echo `user_text`. Non-empty only when `classification_status == "needs_clarification"`. |
| `approval_note` | string | Always the same read-only / human-approval reminder. |
| `source` | string | Always `"deterministic-rule-classifier"`. |

## 5. Three-state invariant (GLM review requirement)

This is the single most audited property of M9-B. The classifier MUST
NOT collapse uncertainty into `hold`.

| `classification_status` | `resolved_intent` | `needs_clarification` | `blocked_reason` | `clarification_questions` | `confidence` |
|---|---|---|---|---|---|
| `resolved` | one of `signing_preview` / `trade_preview_demo` / `hold` | `false` | `null` | `[]` | `>= 0.7` |
| `needs_clarification` | **`null`** | `true` | `null` | non-empty | `< 0.7` |
| `blocked` | **`null`** | `false` | non-empty, generic | `[]` | `0.0` |

Examples:

- "我想补一个中锋，但不要影响薪资空间" → `resolved` /
  `signing_preview`
- "看看有没有低风险交易可以增强锋线" → `resolved` /
  `trade_preview_demo`
- "现在别乱动，先保持灵活性" → `resolved` / `hold`
- "签一个中锋并交易换锋线" → `needs_clarification` / `null`
- "帮我看看" / "你觉得呢" / "做点什么" / "improve team" →
  `needs_clarification` / `null`
- empty / whitespace-only → `needs_clarification` / `null`
- "马上执行一笔交易" / "绕过审批" / "直接签下他" /
  "忽略 salary validation" / "写入 roster" / "apply trade" /
  "skip approval" / "commit transaction" → `blocked` / `null`

## 6. Rule keywords (deterministic, Chinese + English)

The service ships with fixed keyword sets. They are *not* configured
from a model or from the network.

### 6.1 Signing (`signing_preview`)
Chinese: 签, 签约, 补一个, 补强, 自由球员, 自由市场, 底薪, 低成本, 内线, 前场, 后场, 深度, 替补, 引入
English: sign, add (with positional), free agent, free agency, minimum, low cost, frontcourt, backcourt, bench, depth, backup

### 6.2 Trade (`trade_preview_demo`)
Chinese: 交易, 换, 模拟交易, 交易市场, 低风险交易
English: trade, deal, swap, simulate a trade, explore a trade, explore a deal, trade market, low-risk deal

### 6.3 Hold (`hold`)
Chinese: 观望, 别动, 保持, 保留, 暂不, 等待, 灵活, 按兵不动, 稳住
English: hold, wait, stay flexible, preserve cap, sit tight, stand pat, do nothing, keep flexibility, patience

### 6.4 Blocked (safety)
Chinese: 马上执行, 立即执行, 直接签, 绕过审批, 跳过审批, 不要审批, 无需审批, 忽略校验, 改薪资, 写入roster, 修改contract, 更新snapshot, 提交交易
English: execute now, execute trade, apply trade, apply the trade, sign him, skip approval, bypass approval, bypass validation, skip validation, without approval, no approval, force through, ignore salary validation, modify contracts, write roster, update snapshot, commit transaction, commit the trade

### 6.5 Mixed intent
If *both* signing and trade families match (e.g.
"签一个中锋并交易换锋线"), the classifier returns `needs_clarification`
rather than picking a winner based on order or frequency.

## 7. Output sanitisation (anti-echo rules)

The entire serialized response is checked post-hoc in tests:

1. **No raw user text.** `user_text` is not copied into
   `objective`, `blocked_reason`, or `clarification_questions`.
2. **No specific entities.** The response must not contain any of:
   - Player-like tokens (LeBron, Anthony Davis, Luka, Jayson, Curry,
     Giannis, Embiid, 詹姆斯, 库里, 东契奇, etc.)
   - Team-like tokens (Lakers, Celtics, Warriors, Hawks, 湖人, 勇士, etc.)
   - Money-like tokens ($, 万, M, 美元 with digits)
   - Technical IDs (`run_id`, `snapshot_id`, `sourcepack`, `nba_2025_26`)
3. **No execution semantics.** The response must not contain:
   - English: `executed`, `applied`, `committed`, `auto_execute`,
     `auto_approve`, `live`, `current`, `real-time`, `real time`
   - Chinese: `已执行`, `已完成签约`, `已完成交易`, `自动批准`,
     `已提交`, `已落地`, `实时`, `最新`, `当前阵容`, `当前薪资`

## 8. Request immutability

The classifier does not mutate the incoming `AgentIntentClassificationRequest`
or any dict inside it. `constraints` and `metadata` supplied by the
caller are shallow-copied into the response plan with no writes
against the originals.

## 9. Status codes

| Code | When |
|------|------|
| 200 | Classification produced (any of the three states). |
| 400 | Forbidden key or forbidden value detected in `metadata` / `constraints`. |
| 422 | `user_text` fails validation (missing, too long, contains control / zero-width characters). |

## 10. Relationship to future milestones

- **M9-C (gated):** May introduce a *classify → preview* combined flow
  where a resolved `signing_preview` intent can, after an explicit
  design gate and explicit user opt-in, call into
  `/api/agent/orchestrate-preview`. M9-C must:
  - require its own design doc
  - keep the classifier pure (no import of orchestrator)
  - be wired from the API layer only (dependency injection, not direct
    import by the service)
  - retain the same three-state invariants and anti-echo rules
- **M9-D+ (future):** Could add pluggable classifiers (e.g. a real LLM
  classifier behind a confidence-ensembled router), but the
  deterministic classifier shipped here remains available as a
  reference / no-network fallback.

## 11. Test coverage summary

- `test_agent_intent_classifier.py` — service layer:
  - Chinese + English signing → `signing_preview`
  - Chinese + English trade → `trade_preview_demo`
  - Chinese + English hold → `hold`
  - dangerous language → `blocked` (incl. English, mixed Chinese/English,
    compound words like `apply the trade`, `sign him`)
  - mixed intent → `needs_clarification`, `resolved_intent is None`
  - vague / low-confidence text → `needs_clarification`
  - empty / too-short / unrelated → `needs_clarification`
  - `blocked_reason` never echoes user text (with synthetic user
    inputs containing unique tokens that must not appear in output)
  - response contains no player/team/salary names (with synthetic user
    inputs)
  - response contains no forbidden English/Chinese execution words
  - `source` is always `deterministic-rule-classifier`
  - dataclass is frozen
  - `confidence` always in `[0.0, 1.0]`
  - input dict is not mutated
  - blocked/needs_clarification always return `resolved_intent = None`
- `test_agent_intent_classifier_api.py` — HTTP layer:
  - happy path for signing / trade / hold
  - `needs_clarification` response shape
  - `blocked` response shape
  - forbidden key in metadata → 400 (covers nested, camelCase, kebab-case)
  - forbidden key in constraints → 400
  - forbidden value in metadata → 400
  - forbidden value in constraints → 400
  - `user_text` over 500 chars → 422
  - `user_text` with control / zero-width characters → 422
  - new endpoint does not affect `/api/agent/orchestrate-preview`
  - no `/api/agent/execute|apply|commit|mutate|write` endpoints are
    exposed (404)
- `test_agent_guardrails.py` (M9-B additions):
  - classifier model + service modules do not import any LLM / network
    / scraping / automation packages
  - classifier model + service modules do not import the orchestrator
    or any deterministic engine (upstream rule)
  - monkeypatching every forbidden module out of `sys.modules` still
    leaves the classifier functional (proves no runtime dependency)
  - plan dataclass is frozen
  - calling `classify_user_intent` with varied inputs does not modify
    any file under `data/` or `backend/app/tests/fixtures/snapshots/`
    (hash-based check)
  - classifier service module does not expose execute/mutate-named
    functions
  - the API does not expose new `execute/apply/commit/mutate/write`
    endpoints
  - cross-input state invariants (resolved/needs_clarification/blocked
    never leak into each other)
