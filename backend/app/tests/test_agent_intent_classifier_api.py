"""Tests for the M9-B POST /api/agent/classify-intent endpoint.

These tests use FastAPI's ``TestClient`` to verify the HTTP layer for the
natural-language intent classifier. Service-level rules (classification
accuracy, frozen dataclass, no-echo, no-forbidden-snippets, input-mutation
guards) are covered in ``test_agent_intent_classifier.py``; this file
focuses on HTTP concerns: status codes, field validation (422), forbidden
key / forbidden value scanning (400), endpoint independence from the
orchestrator, and absence of any new execute/apply/commit/mutate/write
endpoints.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from backend.app.api import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


_PLAN_FIELDS = [
    "classification_status",
    "resolved_intent",
    "confidence",
    "needs_clarification",
    "objective",
    "constraints",
    "safety_flags",
    "blocked_reason",
    "clarification_questions",
    "approval_note",
    "source",
]


def _post(client: TestClient, body: Dict[str, Any]):
    return client.post("/api/agent/classify-intent", json=body)


def _assert_plan_shape(body: Dict[str, Any]) -> None:
    for f in _PLAN_FIELDS:
        assert f in body, f"response missing field {f!r}"
    assert body["source"] == "deterministic-rule-classifier"


# --------------------------------------------------------------------------- #
# 1. Happy paths: signing / trade / hold
# --------------------------------------------------------------------------- #


def test_signing_happy_path(client: TestClient) -> None:
    resp = _post(client, {"user_text": "我想补一个中锋，但不要影响薪资空间"})
    assert resp.status_code == 200
    body = resp.json()
    _assert_plan_shape(body)
    assert body["classification_status"] == "resolved"
    assert body["resolved_intent"] == "signing_preview"
    assert body["needs_clarification"] is False
    assert body["confidence"] >= 0.7
    assert body["blocked_reason"] is None
    assert body["clarification_questions"] == []


def test_trade_happy_path(client: TestClient) -> None:
    resp = _post(client, {"user_text": "看看有没有低风险交易可以增强锋线"})
    assert resp.status_code == 200
    body = resp.json()
    _assert_plan_shape(body)
    assert body["classification_status"] == "resolved"
    assert body["resolved_intent"] == "trade_preview_demo"
    assert body["needs_clarification"] is False
    assert body["confidence"] >= 0.7


def test_hold_happy_path(client: TestClient) -> None:
    resp = _post(client, {"user_text": "现在别乱动，先保持灵活性"})
    assert resp.status_code == 200
    body = resp.json()
    _assert_plan_shape(body)
    assert body["classification_status"] == "resolved"
    assert body["resolved_intent"] == "hold"
    assert body["needs_clarification"] is False
    assert body["confidence"] >= 0.7


# --------------------------------------------------------------------------- #
# 2. needs_clarification and blocked responses
# --------------------------------------------------------------------------- #


def test_needs_clarification_response(client: TestClient) -> None:
    resp = _post(client, {"user_text": "帮我看看"})
    assert resp.status_code == 200
    body = resp.json()
    _assert_plan_shape(body)
    assert body["classification_status"] == "needs_clarification"
    assert body["resolved_intent"] is None
    assert body["needs_clarification"] is True
    assert body["confidence"] < 0.7
    assert body["blocked_reason"] is None
    assert len(body["clarification_questions"]) >= 1


def test_blocked_response(client: TestClient) -> None:
    resp = _post(client, {"user_text": "帮我马上执行一笔交易"})
    assert resp.status_code == 200
    body = resp.json()
    _assert_plan_shape(body)
    assert body["classification_status"] == "blocked"
    assert body["resolved_intent"] is None
    assert body["needs_clarification"] is False
    assert body["confidence"] == 0.0
    assert body["blocked_reason"] is not None
    assert body["clarification_questions"] == []
    # blocked_reason must NOT contain the user's verbatim dangerous phrase.
    assert "马上执行" not in body["blocked_reason"]


# --------------------------------------------------------------------------- #
# 3. metadata forbidden key -> 400
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "metadata",
    [
        {"execute_trade": True},
        {"nested": {"commitTransaction": True}},
        {"items": [{"apply_changes": True}]},
        {"auto_execute": True},
    ],
)
def test_metadata_forbidden_key_returns_400(
    client: TestClient, metadata: Dict[str, Any]
) -> None:
    resp = _post(client, {
        "user_text": "先观望",
        "metadata": metadata,
    })
    assert resp.status_code == 400
    assert "forbidden" in resp.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# 4. constraints forbidden key -> 400
# --------------------------------------------------------------------------- #


def test_constraints_forbidden_key_returns_400(client: TestClient) -> None:
    resp = _post(client, {
        "user_text": "先观望",
        "constraints": [{"execute": True}],
    })
    assert resp.status_code == 400
    assert "forbidden" in resp.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# 5. metadata / constraints forbidden value -> 400
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "payload",
    [
        {"user_text": "先观望", "metadata": {"note": "please execute trade"}},
        {"user_text": "先观望", "metadata": {"flags": ["auto_approve"]}},
        {"user_text": "先观望", "constraints": ["skip approval please"]},
        {"user_text": "先观望", "constraints": ["bypassValidation"]},
    ],
)
def test_forbidden_value_returns_400(client: TestClient, payload: Dict[str, Any]) -> None:
    resp = _post(client, payload)
    assert resp.status_code == 400
    assert "forbidden" in resp.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# 6. user_text length / control-char / zero-width validation -> 422
# --------------------------------------------------------------------------- #


def test_user_text_too_long_returns_422(client: TestClient) -> None:
    resp = _post(client, {"user_text": "a" * 501})
    assert resp.status_code == 422


def test_user_text_control_char_returns_422(client: TestClient) -> None:
    resp = _post(client, {"user_text": "abc\x00def"})
    assert resp.status_code == 422


def test_user_text_zero_width_returns_422(client: TestClient) -> None:
    resp = _post(client, {"user_text": "sign a center\u200b now"})
    assert resp.status_code == 422


def test_user_text_required_returns_422(client: TestClient) -> None:
    resp = _post(client, {})
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# 7. Endpoint independence: new endpoint does not affect the orchestrator
# --------------------------------------------------------------------------- #


def test_orchestrator_endpoint_still_works_unchanged(client: TestClient) -> None:
    resp = client.post(
        "/api/agent/orchestrate-preview",
        json={"intent": "hold", "team_id": "DEM-ATL"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # orchestrator response must NOT have classify-intent fields
    assert "classification_status" not in body
    # orchestrator response must still have all original M9-A fields
    for f in (
        "intent", "status", "requires_human_approval",
        "preview_payload", "agent_trace", "warnings", "limitations",
        "intelligence_summary",
    ):
        assert f in body


def test_classify_endpoint_does_not_return_preview_payload(client: TestClient) -> None:
    """The classifier MUST NOT build previews."""
    resp = _post(client, {"user_text": "模拟一笔交易"})
    assert resp.status_code == 200
    body = resp.json()
    for f in ("preview_payload", "agent_trace", "status", "warnings", "limitations"):
        assert f not in body, (
            f"classify-intent response must not contain preview-only field {f!r}"
        )


# --------------------------------------------------------------------------- #
# 8. No execute/apply/commit/mutate/write endpoints exposed
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path",
    [
        "/api/agent/execute",
        "/api/agent/apply",
        "/api/agent/commit",
        "/api/agent/mutate",
        "/api/agent/write",
        "/api/agent/save",
        "/api/agent/delete",
        "/api/agent/update",
        "/api/agent/submit",
    ],
)
def test_no_execution_endpoints_exposed(client: TestClient, path: str) -> None:
    resp = client.post(path, json={})
    assert resp.status_code in (404, 405), (
        f"endpoint {path} must not exist; got {resp.status_code}"
    )


# --------------------------------------------------------------------------- #
# 9. Response does not echo raw user text (names/amounts)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "user_text",
    [
        "我想签LeBron James",
        "trade for Anthony Davis",
        "用3000万签一个人",
        "找Lakers做交易",
    ],
)
def test_response_never_echoes_concrete_entities(
    client: TestClient, user_text: str
) -> None:
    resp = _post(client, {"user_text": user_text})
    assert resp.status_code == 200
    blob = json.dumps(resp.json(), ensure_ascii=False).lower()
    for bad in ("lebron", "anthony davis", "lakers", "3000万", "$30m", "$30000000"):
        assert bad not in blob, f"response leaked concrete entity {bad!r}"


# --------------------------------------------------------------------------- #
# 10. Locale / team_id are accepted but do not crash
# --------------------------------------------------------------------------- #


def test_locale_and_team_id_accepted(client: TestClient) -> None:
    resp = _post(client, {
        "user_text": "先观望",
        "team_id": "DEM-ATL",
        "locale": "zh-CN",
    })
    assert resp.status_code == 200
    body = resp.json()
    _assert_plan_shape(body)
    assert body["classification_status"] == "resolved"
    assert body["resolved_intent"] == "hold"


def test_constraints_recursive_scan_nested(client: TestClient) -> None:
    """Forbidden key inside nested dict in constraints must 400."""
    resp = _post(client, {
        "user_text": "先观望",
        "constraints": [{"ok": 1}, {"nested": [{"write_file": True}]}],
    })
    assert resp.status_code == 400
