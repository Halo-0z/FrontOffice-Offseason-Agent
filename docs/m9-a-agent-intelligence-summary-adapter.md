# M9-A — Agent Evidence/Risk Summary Adapter (Deterministic/Fake)

## Status: Implemented (backend-only, additive)

## Goal

Add a plain-language "intelligence summary" field to every
`POST /api/agent/orchestrate-preview` response. The summary is a **read-only
explainer** for the deterministic preview payload that the orchestrator already
produced. It does **not** make decisions, does **not** call any LLM or network
service, and does **not** modify the payload or verdict.

## Non-goals (explicitly out of scope for M9-A)

- No real LLM integration (no OpenAI / Anthropic / MCP calls).
- No network / scraping / browser use.
- No frontend rendering (M9-A-FE will add UI separately; the field is present
  in the API response but the existing frontend ignores it).
- No execute / apply / commit / mutate / write capability of any kind.
- No changes to the deterministic engines (`transaction_rule_engine`,
  `trade_simulator`, `snapshot_loader`, `proposal_builder`, `proposal_evaluator`,
  `agent_trace_builder`, `evidence_service`, `offseason_agent`).
- No claims of live / real-time / current NBA data.
- No overruling of the deterministic `validation_result.verdict` or
  `requires_human_approval` flag.
- No changes under `data/` or `data/snapshots/`.

## What was added

### New files

- `backend/app/models/agent_intelligence.py`
  - Frozen dataclass `AgentIntelligenceSummary` with the following JSON-serializable fields:
    - `summary_title: str` — short Chinese title reflecting the result status
    - `plain_language_summary: str` — 1–2 sentence Chinese description of what
      the preview contains (or why the request was blocked / held)
    - `deterministic_verdict: str` — human-readable verdict derived strictly from
      `status` + the existing `validation_status` / `is_valid` values
    - `evidence_summary: List[str]` — bulleted evidence (player/position/salary,
      validation result, evidence count, cap deltas, HOLD reason, etc.)
    - `risk_summary: List[str]` — bulleted risks (rule issues, cap impact,
      data caveats)
    - `approval_note: str` — fixed reminder that this is read-only and requires
      human approval
    - `data_limitations: List[str]` — fixed disclosure that data is demo /
      historical sample, not a real NBA CBA calculator, not to be used as
      live advice
    - `next_review_questions: List[str]` — suggested questions for a human
      reviewer (health, cap space, luxury tax, etc.)
    - `source: str` — always `"deterministic-fake-adapter"` so downstream code
      can see at a glance this is not an LLM response

- `backend/app/services/agent_intelligence.py`
  - Public entry point:
    `build_intelligence_summary(*, intent, status, requires_human_approval,
    preview_payload, agent_trace=None, warnings=None, limitations=None)
    -> AgentIntelligenceSummary`
  - The function:
    1. Reads **only** the already-built `preview_payload` / `agent_trace` /
       `warnings` / `limitations` passed in by the orchestrator.
    2. Branches **on `status`**, not on `intent`:
       - `blocked` → "安全拦截" summary; explicitly says no plan was generated.
       - `hold` → "暂不行动" summary; no signing/trade recommendation.
       - `awaiting_human_approval` + `signing_preview` → signing summary derived
         from the first action in `preview_payload.actions`.
       - `awaiting_human_approval` + `trade_preview_demo` → trade summary
         derived from `preview_payload.trade_transaction` and
         `preview_payload.preview.validation_result`.
       - Any other combination → generic read-only fallback summary.
    3. Sanitizes any caller/payload-sourced strings (hold_reason, warnings,
       cap_impact_summary, matched_need, intent passed from caller) so that
       forbidden words/phrases like `executed`, `auto_execute`, `live`,
       `current`, `real-time`, `实时`, `最新`, `当前阵容`, `当前薪资`,
       `run_id`, `snapshot_id`, `sourcepack`, `nba_2025_26` can never leak
       into the natural-language summary even if the payload contains them.
    4. Runs a defensive post-build `_validate_no_forbidden_text(...)` self-check
       that raises `AssertionError` if any developer edit accidentally
       reintroduces a forbidden snippet — this is a build-time guard, not a
       runtime cost for hot paths.
  - The module imports **only** stdlib (`dataclasses`, `typing`) and
    project-internal model types; it does **not** import
    `transaction_rule_engine`, `trade_simulator`, `snapshot_loader`,
    `proposal_builder`, `proposal_evaluator`, `agent_trace_builder`,
    `evidence_service`, or any LLM / network / scraping / browser library
    (openai, anthropic, mcp, requests, httpx, aiohttp, urllib, socket,
    selenium, playwright, bs4, beautifulsoup4, scrapy, websocket).

- `backend/app/tests/test_agent_intelligence_summary.py`
  - 22 tests covering:
    - `intelligence_summary` is present for all four intents
      (signing / trade / hold / blocked)
    - Old response fields (`intent`, `status`, `requires_human_approval`,
      `preview_payload`, `agent_trace`, `warnings`, `limitations`) preserved
    - `AgentOrchestratorResult` still constructs/serializes cleanly when
      `intelligence_summary=None` (backward-compat)
    - JSON round-trip of the full response works
    - `preview_payload` is deep-equal (via `copy.deepcopy` +
      `json.dumps(sort_keys=True)`) before/after calling
      `build_intelligence_summary`, for all four status paths
    - **Status drives the summary, not intent**:
      - `intent=signing_preview, status=blocked` → blocked summary, no signing
        recommendation
      - `intent=trade_preview_demo, status=hold` → hold summary, no trade
        recommendation
    - Blocked summary says "安全拦截", contains no player/team/amount
      recommendation, and contains no execution-semantic words
      (`executed`, `applied`, `committed`, `auto_execute`, `auto_approve`,
      `已执行`, `已完成签约`, `已完成交易`, `自动批准`, `已提交`, `已落地`)
    - Forbidden-word scans (English + Chinese + technical IDs) across all
      intents, including adversarial inputs that inject forbidden words via
      `warnings`, `hold_reason`, `matched_need`, `cap_impact_summary`
    - `source == "deterministic-fake-adapter"`
    - Every summary discloses demo/historical data and read-only / human
      approval nature
    - Forbidden-import scan for both `agent_intelligence` service and model
    - The service does not import deterministic engines
    - Data-file hash check: calling `build_intelligence_summary` does not
      mutate `data/*.json`, `data/snapshots/**`, or
      `backend/app/tests/fixtures/snapshots/**`
    - Field shape of `AgentIntelligenceSummary.to_dict()` is contractual

### Modified files

- `backend/app/models/agent_orchestrator.py`
  - `AgentOrchestratorResult` now has an **additive** field
    `intelligence_summary: Optional[Any] = None`.
  - `to_dict()` includes `intelligence_summary` only when it is not `None`,
    calling `.to_dict()` on the summary if that method exists (for the
    `AgentIntelligenceSummary` dataclass) or passing through dict-like values.
  - All existing fields, semantics, defaults, and frozen-ness are unchanged.

- `backend/app/services/agent_orchestrator.py`
  - Minimal change: after constructing the original `AgentOrchestratorResult`
    exactly as before, the service calls `build_intelligence_summary(...)`
    with the result's existing fields and returns a **new**
    `AgentOrchestratorResult` that is identical except for the populated
    `intelligence_summary` field.
  - No routing logic was changed. No deterministic engine calls were added.
    The summary step reads only already-computed state.

- `backend/app/tests/test_agent_orchestrator.py`
  - Added additive assertions that the four existing happy-path tests also
    receive a populated `intelligence_summary` with
    `source == "deterministic-fake-adapter"`.
  - Added a `@pytest.mark.parametrize` test that asserts the new
    `agent_intelligence` modules contain no forbidden LLM / network / engine
    imports.

- `backend/app/tests/test_agent_orchestrator_api.py`
  - Added a shared `_assert_intelligence_summary_shape(body)` helper and call
    it from the signing / trade / hold / blocked API tests.
  - Verifies all seven legacy fields remain present in the JSON response and
    that `intelligence_summary` is present with the contractual 9-field shape
    and discloses read-only / human-approval semantics.
  - Verifies blocked API responses contain a "拦截" summary and no
    signing/trade recommendation text.

- `backend/app/tests/test_agent_guardrails.py`
  - Added an M9-A section at the bottom with:
    - Forbidden-import scans (LLM, network, browser, scraping libs) for both
      new modules
    - Forbidden-engine-import scans (`transaction_rule_engine`,
      `trade_simulator`, `snapshot_loader`) for the service module
    - `AgentIntelligenceSummary` is a frozen dataclass
    - API-level scan: serialized `intelligence_summary` across all four intents
      contains no execution-semantic words (English or Chinese)
    - Scan: summary never claims live/real-time/current data
    - Scan: `agent_intelligence` module exposes no `execute` / `apply` /
      `commit` / `mutate` / `write` / `sign_player` / `trade_player` /
      `save_snapshot` callables

## API response shape (additive)

The response of `POST /api/agent/orchestrate-preview` now has one extra key
alongside the existing seven keys. Example (signing_preview):

```json
{
  "intent": "signing_preview",
  "status": "awaiting_human_approval",
  "requires_human_approval": true,
  "preview_payload": { "...": "unchanged" },
  "agent_trace": { "...": "unchanged" },
  "warnings": ["...unchanged..."],
  "limitations": ["...unchanged..."],
  "intelligence_summary": {
    "summary_title": "签约预览：Demo FA Quebec（中锋）补强方案",
    "plain_language_summary": "系统为球队 DEM-ATL 生成了一个只读签约预览：以 $1M、1 年合同签下 Demo FA Quebec（中锋）。该方案通过了项目样例薪资与阵容规则检查，但仍然只是预览。",
    "deterministic_verdict": "规则检查通过",
    "evidence_summary": [
      "阵容需求匹配：... (sanitized)",
      "球员位置：中锋；报价：$1M / 1 年",
      "规则校验：PASS",
      "关联证据条数：N"
    ],
    "risk_summary": [
      "薪资影响：... (sanitized)",
      "签约不会自动执行，需要管理层、薪资帽团队和队医人工复核。"
    ],
    "approval_note": "这是只读预览，不会自动执行任何操作。所有建议动作都必须由人工复核并确认后才可采取。",
    "data_limitations": [
      "当前数据基于仓库内置的演示/历史样本，不是官方 NBA 数据流，也不会自动刷新。",
      "薪资与交易规则为项目样例规则（例如薪资配平 incoming ≤ outgoing × 125% + $100,000），不等于真实 NBA CBA。",
      "所有结果仅供预览和规则演示，不作为真实交易/签约建议。"
    ],
    "next_review_questions": [
      "候选球员的合同状态、伤病情况是否与样本数据一致？是否需要人工二次核实？",
      "球队薪资空间、帽下余额是否与公开信息核对过？",
      "交易/签约是否会触发奢侈税、硬工资帽或其他 CBA 条款？"
    ],
    "source": "deterministic-fake-adapter"
  }
}
```

## Design rules enforced in code (and tests)

1. **The summary is an explainer, not a decider.** It never flips
   `status`, `requires_human_approval`, `validation_result.status`,
   `validation_result.is_valid`, or anything inside `preview_payload`.
2. **`status` is the source of truth.** Even if the caller passes
   `intent=signing_preview`, if the orchestrator returns `status=blocked`
   or `status=hold`, the summary is a blocked/hold summary — never a
   recommendation to sign or trade.
3. **No fabrication.** The only numbers, player names, team IDs, and cap
   figures that appear in the summary are taken from the deterministic
   `preview_payload` (and sanitized). The adapter never invents amounts,
   players, teams, or PASS/FAIL verdicts.
4. **No live-data claims.** Phrases like "live", "real-time", "current NBA",
   "实时", "最新", "当前阵容", "当前薪资" are forbidden in the summary's own
   templates and stripped from passthrough text.
5. **No execution semantics.** Phrases like "executed", "applied",
   "committed", "auto_execute", "auto_approve", "已执行", "已完成签约",
   "已完成交易", "自动批准", "已提交", "已落地" are forbidden in the summary
   and stripped from passthrough text.
6. **No technical IDs in natural language.** `run_id`, `snapshot_id`,
   `sourcepack`, `nba_2025_26` are stripped from passthrough text. The raw
   IDs can still appear inside `preview_payload` / `agent_trace` (which the
   adapter does not modify), but not in the human-readable summary.
7. **No LLM / network / scraping.** Enforced by import-scan tests and by
   the fact that the module imports only stdlib + project models.
8. **No engine coupling.** The adapter does not import or call
   `transaction_rule_engine`, `trade_simulator`, or `snapshot_loader`; the
   engines run before it and pass their results in.
9. **No data mutation.** Enforced by file-hash tests that compare
   `data/*.json`, `data/snapshots/**`, and test fixture snapshots before and
   after calling `build_intelligence_summary` / `orchestrate_preview`.
10. **No new execute/apply/commit/mutate/write surface.** Enforced by
    module-attribute scan tests.
11. **Defensive self-check.** `_validate_no_forbidden_text(...)` runs on the
    summary's own fields at build time and raises `AssertionError` if any
    template text accidentally contains a forbidden snippet — a belt-and-braces
    guard against regressions when developers edit the adapter later.
12. **Backend-only in M9-A.** The frontend is intentionally untouched. It
    will receive the new field in the JSON response but ignore it until
    M9-A-FE.

## Why `source = "deterministic-fake-adapter"`

The field is a hard-coded label so that any future UI, log aggregator, or
eval harness can tell at a glance whether the summary came from this
rule-based adapter or from a future real LLM. When a real LLM is ever wired
in, it must:

1. Use a different `source` value (e.g. `"llm:<model>"`).
2. Go through a separate design gate (not this module).
3. Be subject to its own prompt-injection / factuality / PII guardrails.

## Path to a real LLM (future, NOT done in M9-A)

A future milestone (post M9-B design gate) may replace this adapter with an
LLM-based one. When that happens, the following must be true:

- It lives behind a new interface (so we can A/B the deterministic adapter
  vs the LLM adapter).
- It is still **read-only**: it receives the already-built
  `preview_payload` + `agent_trace` and returns an
  `AgentIntelligenceSummary`-shaped object. It must not modify the payload.
- It is gated behind an explicit feature flag; the deterministic adapter
  remains the default / fallback.
- It must still pass every guardrail test in
  `test_agent_intelligence_summary.py` and the M9-A section of
  `test_agent_guardrails.py` (no execution language, no live-data claims,
  no technical IDs, disclosure of human-approval requirement).
- All network / credential / retry / budget / PII concerns of an LLM call
  are addressed separately; M9-A intentionally takes zero dependency on
  any of that.

## Test commands

```powershell
cd D:\FrontOffice-Offseason-Agent
D:\anaconda\python.exe -m pytest backend/app/tests/test_agent_intelligence_summary.py -q
D:\anaconda\python.exe -m pytest backend/app/tests/test_agent_orchestrator.py -q
D:\anaconda\python.exe -m pytest backend/app/tests/test_agent_orchestrator_api.py -q
D:\anaconda\python.exe -m pytest backend/app/tests/test_agent_guardrails.py -q
D:\anaconda\python.exe -m pytest backend/app/tests -q
```
