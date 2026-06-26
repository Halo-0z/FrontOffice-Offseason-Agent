# M9-C: Natural-Language Classify-to-Preview Flow

## Overview

M9-C adds a **deterministic, backend-only** composition endpoint that
chains:

1. **M9-B** `classify_user_intent` — pure rule-based natural-language
   classifier that returns an `AgentIntentPlan` (`resolved` /
   `needs_clarification` / `blocked`).
2. **M9-C safety gate** — a strict read-only gate that decides whether a
   preview is allowed.
3. **M8-E** `orchestrate_preview` — the existing deterministic preview
   orchestrator, called **only** when the gate allows it.

The new endpoint is `POST /api/agent/natural-language-preview`. It does
**not** replace `/api/agent/classify-intent` — the classify endpoint
remains the single-purpose classifier used by M9-B; M9-C is the
composition entry point used when the caller wants a preview "if safe".

## Deterministic / Read-Only Guarantees

M9-C is, and must remain:

- **No LLM.** No OpenAI / Anthropic / any model call.
- **No network.** No `httpx`, `requests`, `aiohttp`, `urllib`, `socket`,
  `websocket`, `selenium`, `playwright`, `scrapy`, `bs4`, `mcp`.
- **No frontend changes.** M9-C is backend-only. Frontend wiring is
  deferred to M9-D.
- **No data/snapshot mutation.** The service never writes to `data/*.json`
  or `data/snapshots/**`.
- **No direct engine calls.** The service composes two already-sealed
  services (`classify_user_intent` and `orchestrate_preview`). It does
  not import:
  - `trade_simulator`
  - `transaction_rule_engine`
  - `proposal_builder`
  - `proposal_viewer`
  - `snapshot_loader`
  - `agent_intelligence`
  - `agent_trace_builder`
- **No mutation endpoints.** There is no `/api/agent/execute`, `/apply`,
  `/commit`, `/mutate`, `/write`, `/persist`, `/save`, `/delete`,
  `/update`, or `/submit`.
- **Immutable dataclasses.** Request / result dataclasses are frozen.
- **Fixed `source` string:** `"deterministic-classify-to-preview-flow"`.

## Four-State `flow_status`

Every response has exactly one of four flow states:

| `flow_status`         | When it is returned                                          | `preview_result` | `requires_human_approval` | Orchestrator called? |
|-----------------------|--------------------------------------------------------------|------------------|---------------------------|----------------------|
| `preview_generated`   | Classifier resolved to `signing_preview` or `trade_preview_demo`, confidence ≥ 0.7, safety flags clean, no blocked reason, `needs_clarification=False`. | orchestrator `.to_dict()` verbatim | **true** | yes |
| `needs_clarification` | Classifier returned `classification_status == "needs_clarification"`. | `null` | false | **no** |
| `blocked`             | Classifier returned `classification_status == "blocked"` (dangerous language / bypass-approval / execute intent). | `null` | false | **no** |
| `preview_not_generated` | Gate-level hold (`resolved_intent == "hold"`) OR classifier produced any invalid invariant (resolved-but-no-intent, unsupported intent, low confidence, dangerous/blocked/unsafe safety flag, needs_clarification/blocked with non-null intent). | `null` | false | **no** |

Important nuance (GLM review follow-up):

- **Resolved `hold`** returns `preview_not_generated` (not `hold` and not
  `needs_clarification`). This is an intentional gate-level decision —
  the user explicitly said "don't act yet", so we do not call the
  orchestrator and we do not return a preview. The `safety_notes` array
  explains this. This avoids conflicting with the M8-F historical
  behavior where a frontend "hold" button still ran the old
  proposal-preview flow.
- **Blocked is a safety denial, not a pending approval.** Therefore
  `requires_human_approval` is **false** for blocked responses. Never
  route blocked users to a human-approval queue.
- **Low confidence is not a hold.** M9-B explicitly sets
  `resolved_intent=None` when confidence < 0.7, so M9-C's defensive gate
  sees a `resolved + intent=None` invariant and returns
  `preview_not_generated`.

## Gate Rules (exact conditions for calling the orchestrator)

The orchestrator is called **only if ALL** of the following are true:

1. `plan.classification_status == "resolved"`
2. `plan.resolved_intent in {"signing_preview", "trade_preview_demo"}`
3. `plan.resolved_intent is not None`
4. `plan.needs_clarification is False`
5. `plan.blocked_reason is None`
6. `plan.confidence >= 0.7`
7. No safety flag in `plan.safety_flags` case-insensitive-matches
   `dangerous`, `blocked`, or `unsafe`.

If any condition fails, the orchestrator is NOT called and
`preview_result` is `null`. The most specific `flow_status` wins:

- `blocked_reason is not None` → `flow_status = "blocked"`
- `needs_clarification is True` → `flow_status = "needs_clarification"`
- `resolved_intent == "hold"` → `flow_status = "preview_not_generated"`
  (gate hold note added)
- Any other invalid invariant → `flow_status = "preview_not_generated"`
  (gate invariant note added)

## `preview_result` Verbatim

When `flow_status == "preview_generated"`, `preview_result` is **exactly**
`orchestrator_result.to_dict()`:

- No fields removed.
- No fields added.
- `verdict` / `requires_human_approval` / `intelligence_summary` /
  `agent_trace` / `preview_payload` are NOT rewritten.
- Deep equality is enforced by tests.

Entities shown inside `preview_result` (player names, team names, salary
figures, `agent_trace.run_id`, etc.) belong to the deterministic demo
payload and are intentionally part of the preview. The "no-echo" rule
applies to the **M9-C envelope** (`flow_status`, `classification`,
`safety_notes`, `source`) — that layer must never echo the raw
`user_text`, never leak user-supplied player/team/salary strings, and
never contain execution language.

## Classification Safe Projection

The `classification` field in the response is **not**
`AgentIntentPlan.to_dict()`. It is a strict subset
(`ClassificationProjection`) that contains only:

- `classification_status`
- `resolved_intent`
- `confidence`
- `needs_clarification`
- `safety_flags`
- `blocked_reason`
- `clarification_questions`
- `approval_note`
- `source`

Explicitly **excluded**:

- `objective` — may contain user-supplied text.
- `constraints` — may contain user-supplied text.
- raw `user_text` — never echoed.

## Request Shape

The request body is identical to M9-B `/api/agent/classify-intent`:

```json
{
  "user_text": "string (required, 1-500 chars, no control / zero-width chars)",
  "team_id": "string (optional, default 'DEM-ATL')",
  "locale": "string (optional, default 'zh-CN')",
  "constraints": "object | array (optional, recursively scanned)",
  "metadata": "object (optional, recursively scanned)"
}
```

Input validation is **reused**, not rewritten:

- Pydantic enforces `user_text` length and forbidden characters
  (HTTP 422 on violation).
- The HTTP layer calls the existing `_find_forbidden_metadata_key` and
  `_find_forbidden_value` helpers on **both** `metadata` and
  `constraints`, rejecting forbidden mutation keys/values with HTTP 400.

## Metadata Pass-Through

If the gate allows preview generation, `request.metadata` is forwarded
verbatim to `AgentOrchestrationRequest.metadata`. A deep-equality test
verifies this pass-through.

## Response Envelope

```json
{
  "flow_status": "preview_generated | needs_clarification | blocked | preview_not_generated",
  "classification": {
    "classification_status": "resolved | needs_clarification | blocked",
    "resolved_intent": "signing_preview | trade_preview_demo | hold | null",
    "confidence": 0.85,
    "needs_clarification": false,
    "safety_flags": ["preview_only"],
    "blocked_reason": null,
    "clarification_questions": [],
    "approval_note": "只读预览，需人工确认，不会自动执行。",
    "source": "deterministic-rule-classifier"
  },
  "preview_result": null,
  "requires_human_approval": false,
  "safety_notes": [
    "Only resolved signing/trade plans may generate preview.",
    "Needs-clarification, blocked, hold, and low-confidence plans do not call the orchestrator.",
    "Preview results are read-only and require human approval."
  ],
  "source": "deterministic-classify-to-preview-flow"
}
```

Rules:

- `preview_result` is `null` for every state except `preview_generated`.
- `requires_human_approval` is `true` **only** when `flow_status ==
  "preview_generated"`.
- `safety_notes` always contains the three default notes, plus any
  extra note (hold / blocked / invariant violation) when applicable.

## Files Added / Modified

Added:

- [models/agent_natural_language_preview.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/models/agent_natural_language_preview.py) — frozen dataclasses for request, classification projection, result.
- [services/agent_natural_language_preview.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/services/agent_natural_language_preview.py) — the classify-to-preview service.
- [tests/test_agent_natural_language_preview.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/tests/test_agent_natural_language_preview.py) — service-level tests.
- [tests/test_agent_natural_language_preview_api.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/tests/test_agent_natural_language_preview_api.py) — HTTP-layer tests.
- [m9-c-natural-language-preview-flow.md](file:///D:/FrontOffice-Offseason-Agent/docs/m9-c-natural-language-preview-flow.md) (this document).
- [m9-c-natural-language-preview-api-smoke-runbook.md](file:///D:/FrontOffice-Offseason-Agent/docs/m9-c-natural-language-preview-api-smoke-runbook.md) — smoke runbook.

Modified:

- [api.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/api.py) — added the new endpoint (aliased Pydantic model + reused scanner).
- [test_agent_guardrails.py](file:///D:/FrontOffice-Offseason-Agent/backend/app/tests/test_agent_guardrails.py) — added M9-C guardrail section.

Explicitly **not** modified (frozen per scope):

- `frontend/**`
- `data/**`, `data/snapshots/**`
- `backend/app/services/agent_orchestrator.py`
- `backend/app/services/agent_intent_classifier.py`
- `backend/app/services/agent_intelligence.py`
- `backend/app/services/agent_trace_builder.py`
- `backend/app/services/transaction_rule_engine.py`
- `backend/app/services/trade_simulator.py`
- `backend/app/services/proposal_builder.py`
- `backend/app/services/proposal_viewer.py`
- `backend/app/services/snapshot_loader.py`

## What's Next (M9-D)

M9-D will add frontend wiring: a natural-language input box that calls
`/api/agent/natural-language-preview`, renders the four flow states,
and for `preview_generated` reuses the existing preview card /
verdict / trace components. The backend flow delivered here is
sufficient for that frontend work; no backend changes are required in
M9-D beyond possible envelope tweaks discovered during integration.
