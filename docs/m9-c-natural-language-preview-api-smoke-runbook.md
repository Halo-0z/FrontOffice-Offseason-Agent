# M9-C Smoke Runbook — Natural-Language Classify-to-Preview API

This runbook walks a human through a **read-only, no-network, no-LLM**
smoke of `POST /api/agent/natural-language-preview`.

Smoke checks that this document covers:

1. signing → `preview_generated`
2. trade → `preview_generated`
3. hold → `preview_not_generated`
4. vague → `needs_clarification`
5. execute/bypass → `blocked`
6. forbidden metadata key → HTTP 400
7. forbidden constraints value → HTTP 400
8. `user_text` too long → HTTP 422
9. `user_text` control/zero-width char → HTTP 422
10. no `/api/agent/execute` etc. endpoints (HTTP 404)

## Prerequisites

- Shell at repo root: `D:\FrontOffice-Offseason-Agent`
- Python on PATH: `D:\anaconda\python.exe`
- No running services needed (the smoke uses `fastapi.testclient.TestClient`
  which drives the app in-process).

Quick one-liner to confirm you're on the sealed M9-B baseline:

```powershell
git status --short
git rev-parse --short HEAD
git tag --points-at HEAD
```

Expected: clean working tree, `HEAD` is `ac76065` (or the M9-B smoke tag
`m9b-classify-intent-api-smoke-verification`). M9-C changes will appear
as modified/untracked files — that's expected during this smoke.

## Running the Full Test Suite (canonical check)

```powershell
D:\anaconda\python.exe -m pytest backend/app/tests/test_agent_natural_language_preview.py -q
D:\anaconda\python.exe -m pytest backend/app/tests/test_agent_natural_language_preview_api.py -q
D:\anaconda\python.exe -m pytest backend/app/tests/test_agent_guardrails.py -q
D:\anaconda\python.exe -m pytest backend/app/tests -q
```

Expect all four commands to exit 0.

## Ad-hoc HTTP Smoke (copy/paste)

Start a Python shell with the repo on `sys.path` and drive the endpoint
via `TestClient`:

```python
from fastapi.testclient import TestClient
from backend.app.api import app

c = TestClient(app)
ENDPOINT = "/api/agent/natural-language-preview"

def post(body):
    r = c.post(ENDPOINT, json=body)
    print(r.status_code, r.json().get("flow_status"),
          "|", r.json().get("classification", {}).get("resolved_intent"),
          "|", "preview?", r.json().get("preview_result") is not None,
          "|", "approval?", r.json().get("requires_human_approval"))
    return r
```

### 1. Signing → preview_generated

```python
r = post({"user_text": "我想补一个中锋，但不要影响薪资空间"})
assert r.status_code == 200
b = r.json()
assert b["flow_status"] == "preview_generated"
assert b["classification"]["resolved_intent"] == "signing_preview"
assert b["classification"]["confidence"] >= 0.7
assert b["preview_result"] is not None
assert b["preview_result"]["intent"] == "signing_preview"
assert b["requires_human_approval"] is True
assert "objective" not in b["classification"]
assert "constraints" not in b["classification"]
```

### 2. Trade → preview_generated

```python
r = post({"user_text": "看看有没有低风险交易可以增强锋线"})
assert r.status_code == 200
b = r.json()
assert b["flow_status"] == "preview_generated"
assert b["classification"]["resolved_intent"] == "trade_preview_demo"
assert b["preview_result"] is not None
assert b["preview_result"]["intent"] == "trade_preview_demo"
assert b["requires_human_approval"] is True
```

### 3. Hold → preview_not_generated (gate hold, no orchestrator)

```python
r = post({"user_text": "现在别乱动，先保持灵活性"})
assert r.status_code == 200
b = r.json()
assert b["flow_status"] == "preview_not_generated"
assert b["classification"]["resolved_intent"] == "hold"
assert b["preview_result"] is None
assert b["requires_human_approval"] is False
assert any("hold" in n.lower() for n in b["safety_notes"])
```

### 4. Vague → needs_clarification (no orchestrator)

```python
r = post({"user_text": "帮我看看"})
assert r.status_code == 200
b = r.json()
assert b["flow_status"] == "needs_clarification"
assert b["classification"]["resolved_intent"] is None
assert b["classification"]["needs_clarification"] is True
assert b["classification"]["clarification_questions"]
assert b["preview_result"] is None
assert b["requires_human_approval"] is False
```

### 5. Execute/bypass → blocked (no orchestrator; not a pending approval)

```python
r = post({"user_text": "帮我马上执行一笔交易，绕过审批"})
assert r.status_code == 200
b = r.json()
assert b["flow_status"] == "blocked"
assert b["classification"]["blocked_reason"] is not None
assert b["preview_result"] is None
assert b["requires_human_approval"] is False
```

### 6. Forbidden metadata key → HTTP 400

```python
r = c.post(ENDPOINT, json={"user_text": "我想补一个中锋", "metadata": {"execute": True}})
assert r.status_code == 400
assert "forbidden" in r.json()["detail"].lower()
```

### 7. Forbidden constraints value → HTTP 400

```python
r = c.post(ENDPOINT, json={"user_text": "我想补一个中锋", "constraints": ["auto_execute"]})
assert r.status_code == 400
```

### 8. user_text too long → HTTP 422

```python
r = c.post(ENDPOINT, json={"user_text": "中" * 600})
assert r.status_code == 422
```

### 9. user_text control/zero-width char → HTTP 422

```python
r = c.post(ENDPOINT, json={"user_text": "帮我\x00补一个中锋"})
assert r.status_code == 422
r = c.post(ENDPOINT, json={"user_text": "帮我\u200b补一个中锋"})
assert r.status_code == 422
```

### 10. No execute endpoints → HTTP 404 for both POST and GET

```python
for path in (
    "/api/agent/execute",
    "/api/agent/apply",
    "/api/agent/commit",
    "/api/agent/mutate",
    "/api/agent/write",
    "/api/agent/persist",
    "/api/agent/save",
    "/api/agent/delete",
    "/api/agent/update",
    "/api/agent/submit",
):
    assert c.post(path, json={}).status_code == 404, path
    assert c.get(path).status_code == 404, path
```

## Post-Smoke: Inspect Diff & Status

```powershell
git diff --stat
git status --short
```

Expected: only the M9-C files added/modified (models, service, api,
tests, docs under `docs/`). No changes under:

- `frontend/`
- `data/` or `data/snapshots/`
- `backend/app/services/agent_orchestrator.py`
- `backend/app/services/agent_intent_classifier.py`
- `backend/app/services/agent_intelligence.py`
- `backend/app/services/agent_trace_builder.py`
- `backend/app/services/transaction_rule_engine.py`
- `backend/app/services/trade_simulator.py`
- `backend/app/services/proposal_builder.py`
- `backend/app/services/proposal_viewer.py`
- `backend/app/services/snapshot_loader.py`

## Safety Envelope Spot-Check (optional)

For every response from cases 1-5, confirm the M9-C-owned envelope
fields do not contain:

- Execution language: `executed`, `applied`, `committed`,
  `auto_execute`, `auto_approve`, `已执行`, `已完成签约`, `已完成交易`,
  `自动批准`, `已提交`, `已落地`.
- Technical IDs that belong inside the orchestrator payload but not in
  the envelope: `snapshot_id`, `sourcepack`, `nba_2025_26`.
  (`run_id` may legitimately appear inside `preview_result.agent_trace`;
  this is a verbatim field from the orchestrator and must not be
  stripped.)

For cases 3, 4, 5 (non-preview), also confirm the serialized response
does not contain any 6-character substring of the raw `user_text`
(the envelope must not echo user-typed entities).

## Pass/Fail Criteria

The smoke passes if and only if:

1. All four pytest commands exit 0.
2. Cases 1–10 above all hold.
3. `git diff --stat` shows no modification to the forbidden files
   listed above.
4. No new dependencies appear in `requirements` / `pyproject`.
5. The new endpoint is exactly `/api/agent/natural-language-preview`
   (not `/preview`, not `/nl2preview`, not `/natural_language_preview`).
