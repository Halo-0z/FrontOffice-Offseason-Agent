# M9-C Natural-Language-Preview API Smoke Verification

**Date:** 2026-06-27
**Endpoint under test:** `POST /api/agent/natural-language-preview`
**Baseline:** HEAD `41fda77` (tag `m9c-natural-language-preview-flow`)
**Scope:** Read-only API smoke. No code changes beyond this docs file. No commit/tag/push.
**Driver:** `fastapi.testclient.TestClient` (in-process, no network, no LLM).

## Result: **PASS (83/83 smoke checks, 158/158 pytest)**

All five main-path flows, all four error paths, the classification safe
projection, forbidden-word / no-echo checks, and the orchestrator
call-boundary check passed. Pre-existing pytest suites also passed
unmodified.

## Preconditions

- `git status --short` → empty before smoke.
- `git rev-parse --short HEAD` → `41fda77`.
- `git tag --points-at HEAD` → `m9c-natural-language-preview-flow`.
- `D:\DraftMind` not touched.
- No frontend, data, snapshot, or sealed-service file was modified.

## Smoke Script Method

A temporary TestClient script exercised the endpoint directly. For each
case the script asserted:

1. HTTP status code.
2. Envelope shape: `flow_status`, `classification`, `preview_result`,
   `requires_human_approval`, `safety_notes`, `source` all present;
   `source == "deterministic-classify-to-preview-flow"`.
3. `flow_status ∈ {preview_generated, preview_not_generated, needs_clarification, blocked}`.
4. Classification field set is exactly the 9 allowed fields; `objective`,
   `constraints`, `user_text`, `raw_text` are absent.
5. For `preview_generated`: `preview_result` non-null, `requires_human_approval == true`,
   preview_result has orchestrator shape (`intent/status/requires_human_approval/
   preview_payload/agent_trace/warnings/limitations`),
   `preview_result.status == "awaiting_human_approval"` (read-only),
   `preview_result.intent` matches `classification.resolved_intent`.
6. For non-`preview_generated`: `preview_result is null`,
   `requires_human_approval == false`.
7. For `needs_clarification`: `clarification_questions` non-empty,
   `resolved_intent is null`.
8. For `blocked`: `blocked_reason` non-empty, `resolved_intent is null`,
   `requires_human_approval == false` (safety denial, not pending approval).
9. Forbidden execution words (`executed/applied/committed/auto_execute/
   auto_approve/已执行/已完成签约/已完成交易/自动批准/已提交/已落地`) are
   absent from the M9-C-owned envelope (top-level + `classification` +
   `safety_notes` + `source`).
10. Forbidden tech IDs (`snapshot_id`, `sourcepack`, `nba_2025_26`) are
    absent from the entire response.
11. For non-generated responses, no 6-character substring of the raw
    `user_text` appears in the serialized envelope.
12. Mutation endpoints (`/api/agent/{execute,apply,commit,mutate,write,
    persist,save,delete,update,submit}`) all return HTTP 404 for both
    POST and GET.
13. Orchestrator call-boundary: monkeypatching
    `backend.app.services.agent_orchestrator.orchestrate_preview` to
    raise `AssertionError("ORCHESTRATOR_CALLED")` does not break
    hold / needs_clarification / blocked / compound-intent requests —
    proving the orchestrator is never entered for those flows.

## Case-by-Case Results

### 1. Signing → `preview_generated`

Request:
```json
{
  "user_text": "我想补一个中锋，但不要影响薪资空间",
  "team_id": "DEM-ATL", "locale": "zh-CN",
  "constraints": {"preserve_cap_flexibility": true},
  "metadata": {"source": "m9c-smoke"}
}
```
Result:
- HTTP **200** ✓
- `flow_status = "preview_generated"` ✓
- `classification.classification_status = "resolved"` ✓
- `classification.resolved_intent = "signing_preview"` ✓
- `preview_result` non-null ✓
- `requires_human_approval = true` ✓
- `preview_result.status = "awaiting_human_approval"` (read-only) ✓
- `preview_result.intent = "signing_preview"` (matches classification) ✓

### 2. Trade → `preview_generated`

Request:
```json
{
  "user_text": "看看有没有低风险交易可以增强锋线",
  "team_id": "DEM-ATL", "locale": "zh-CN",
  "constraints": {"risk_tolerance": "low"},
  "metadata": {"source": "m9c-smoke"}
}
```
Result:
- HTTP **200** ✓
- `flow_status = "preview_generated"` ✓
- `classification.classification_status = "resolved"` ✓
- `classification.resolved_intent = "trade_preview_demo"` ✓
- `preview_result` non-null ✓
- `requires_human_approval = true` ✓
- `preview_result.status = "awaiting_human_approval"` ✓
- `preview_result` carries the verbatim orchestrator structure
  (`intent/status/requires_human_approval/preview_payload/agent_trace/
  warnings/limitations/intelligence_summary`) — no M9-C reshape detected. ✓

### 3. Hold → `preview_not_generated` (gate-level)

Request:
```json
{
  "user_text": "现在别乱动，先保持灵活性",
  "team_id": "DEM-ATL", "locale": "zh-CN",
  "constraints": {"preserve_cap_flexibility": true},
  "metadata": {"source": "m9c-smoke"}
}
```
Result:
- HTTP **200** ✓
- `flow_status = "preview_not_generated"` ✓
- `classification.classification_status = "resolved"` ✓
- `classification.resolved_intent = "hold"` ✓
- `preview_result = null` ✓
- `requires_human_approval = false` ✓
- Orchestrator NOT called (verified by monkeypatching orchestrator to
  raise; request still returned 200 with `preview_not_generated`) ✓

### 4. Needs Clarification (compound signing + trade)

Request:
```json
{
  "user_text": "签一个中锋并交易换锋线",
  "team_id": "DEM-ATL", "locale": "zh-CN",
  "constraints": {},
  "metadata": {"source": "m9c-smoke"}
}
```
Result:
- HTTP **200** ✓
- `flow_status = "needs_clarification"` ✓
- `classification.classification_status = "needs_clarification"` ✓
- `classification.resolved_intent = null` ✓
- `preview_result = null` ✓
- `requires_human_approval = false` ✓
- `clarification_questions` non-empty ✓
- Did NOT fall back to hold ✓
- Orchestrator NOT called ✓

### 5. Blocked (bypass-approval)

Request:
```json
{
  "user_text": "帮我马上执行一笔交易，绕过审批",
  "team_id": "DEM-ATL", "locale": "zh-CN",
  "constraints": {},
  "metadata": {"source": "m9c-smoke"}
}
```
Result:
- HTTP **200** ✓
- `flow_status = "blocked"` ✓
- `classification.classification_status = "blocked"` ✓
- `classification.resolved_intent = null` ✓
- `preview_result = null` ✓
- `requires_human_approval = false` (safety denial, not a pending approval) ✓
- `blocked_reason` non-empty ✓
- Orchestrator NOT called ✓

### 6. Metadata forbidden key → HTTP 400

`{"user_text": "我想补一个中锋", "metadata": {"executeTrade": true}}` →
**HTTP 400**, detail mentions "forbidden mutation-semantic key at
'executeTrade'". ✓

### 7. Constraints forbidden nested key → HTTP 400

`{"user_text": "我想补一个中锋", "constraints": {"nested": {"autoExecute": true}}}`
→ **HTTP 400**, detail mentions "forbidden mutation-semantic key at
'nested.autoExecute'". ✓

### 8. user_text too long → HTTP 422

`user_text = "中" * 600` → **HTTP 422** (`string_too_long`,
max_length=500). ✓

### 9. user_text control / zero-width chars → HTTP 422

- `"帮我\x00补一个中锋"` → **HTTP 422** ✓
- `"帮我\u200b补一个中锋"` → **HTTP 422** ✓

## Cross-cutting Safety Checks (all pass)

| Check | Result |
|---|---|
| Envelope contains no exec words (EN + ZH) for all 5 cases | PASS |
| Envelope contains no forbidden tech IDs (`snapshot_id`, `sourcepack`, `nba_2025_26`) for all 5 cases | PASS |
| Full response contains no forbidden tech IDs (same set) for all 5 cases | PASS |
| Non-generated responses contain no 6-char substring of raw user_text | PASS |
| `/api/agent/execute, apply, commit, mutate, write, persist, save, delete, update, submit` all 404 for POST and GET | PASS |
| Classification field-set exactly = 9 allowed fields (no objective/constraints/user_text/raw_text) | PASS |
| preview_result for signing/trade has all orchestrator-mandatory keys | PASS |
| preview_result.requires_human_approval = true (not rewritten) | PASS |
| preview_result.intent matches classification.resolved_intent | PASS |
| Hold / clarify / blocked orchestrator NOT invoked (monkeypatch-to-raise proof) | PASS |

### Note on `run_id`

`run_id` is present inside `preview_result.agent_trace` for the two
`preview_generated` cases. This is the verbatim orchestrator trace
field (M8-E design) and per the M9-C spec must not be stripped —
`preview_result` is the orchestrator's `to_dict()` verbatim. The M9-C
envelope itself (top-level fields + classification + safety_notes +
source) does not contain `run_id`, which is the intended boundary.

## Pytest Regression (post-smoke)

```
D:\anaconda\python.exe -m pytest \
    backend/app/tests/test_agent_natural_language_preview.py \
    backend/app/tests/test_agent_natural_language_preview_api.py \
    backend/app/tests/test_agent_guardrails.py -q
158 passed in 3.33s
```

No test failures; no test files were modified during this smoke.

## Git Diff / Status After Smoke

Only this docs file is added (untracked). No modifications to:
- `frontend/`
- `data/` or `data/snapshots/`
- sealed services (`agent_orchestrator.py`, `agent_intent_classifier.py`,
  `agent_intelligence.py`, `agent_trace_builder.py`,
  `transaction_rule_engine.py`, `trade_simulator.py`,
  `proposal_builder.py`, `proposal_viewer.py`, `snapshot_loader.py`)
- API or model files under `backend/app/`

## Recommendation

**Proceed to ChatGPT acceptance.** The M9-C API behaves exactly as
specified:

1. Four flow states (`preview_generated` / `preview_not_generated` /
   `needs_clarification` / `blocked`) are implemented correctly.
2. Only resolved signing/trade with clean safety flags and
   confidence ≥ 0.7 generates a preview; hold / needs_clarification /
   blocked / low-confidence / invalid invariants do not call the
   orchestrator and return `preview_result = null`.
3. Hold is correctly implemented as a gate-level `preview_not_generated`
   (not `needs_clarification`, not its own state), avoiding the M8-F
   frontend hold conflict called out in the design.
4. Blocked correctly returns `requires_human_approval = false` —
   treated as a safety denial, not a pending approval.
5. The `classification` projection is safe (no objective / constraints /
   raw user text).
6. `preview_result` is the verbatim orchestrator `to_dict()` — no
   reshape, no verdict/requires_human_approval/intelligence_summary/
   agent_trace/preview_payload rewrite.
7. Input validation (length, control/zero-width chars, forbidden
   metadata/constraints keys and values) is enforced and returns the
   correct HTTP status codes.
8. No execute/apply/commit/mutate/write/persist/save/delete/update/submit
   endpoints exist under `/api/agent/`.
9. No user-text echo, no execution language, no forbidden tech IDs in
   the M9-C envelope.
