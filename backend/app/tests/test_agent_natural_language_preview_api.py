"""Tests for the M9-C POST /api/agent/natural-language-preview endpoint.

These tests use FastAPI's ``TestClient`` to verify the HTTP layer for the
classify-to-preview flow. Service-level rules (frozen dataclass,
classification projection, deep orchestrator equality, no-echo substrings,
gate invariants, no-forbidden-engine-imports) are covered in
``test_agent_natural_language_preview.py``; this file focuses on HTTP
concerns: status codes, Pydantic validation (422), forbidden key / forbidden
value scanning on metadata AND constraints (400), happy-path envelope shape,
and absence of any execute/apply/commit/mutate/write endpoint.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from backend.app.api import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


_ENDPOINT = "/api/agent/natural-language-preview"

_ENVELOPE_FIELDS = {
    "flow_status",
    "classification",
    "preview_result",
    "requires_human_approval",
    "safety_notes",
    "source",
}

_CLASSIFICATION_FIELDS = {
    "classification_status",
    "resolved_intent",
    "confidence",
    "needs_clarification",
    "safety_flags",
    "blocked_reason",
    "clarification_questions",
    "approval_note",
    "source",
}


def _post(client: TestClient, body: Dict[str, Any]):
    return client.post(_ENDPOINT, json=body)


def _assert_envelope_shape(body: Dict[str, Any]) -> None:
    assert set(body.keys()) == _ENVELOPE_FIELDS
    assert set(body["classification"].keys()) == _CLASSIFICATION_FIELDS
    assert body["source"] == "deterministic-classify-to-preview-flow"
    assert isinstance(body["safety_notes"], list)


# --------------------------------------------------------------------------- #
# 1. Happy paths
# --------------------------------------------------------------------------- #


def test_signing_preview_generated(client: TestClient) -> None:
    resp = _post(client, {"user_text": "我想补一个中锋，但不要影响薪资空间"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    _assert_envelope_shape(body)
    assert body["flow_status"] == "preview_generated"
    assert body["classification"]["classification_status"] == "resolved"
    assert body["classification"]["resolved_intent"] == "signing_preview"
    assert body["classification"]["confidence"] >= 0.7
    assert body["classification"]["needs_clarification"] is False
    assert body["preview_result"] is not None
    assert body["requires_human_approval"] is True
    # no objective/constraints/user_text leakage in classification
    cls = body["classification"]
    for k in ("objective", "constraints", "user_text"):
        assert k not in cls


def test_trade_preview_generated(client: TestClient) -> None:
    resp = _post(client, {"user_text": "看看有没有低风险交易可以增强锋线"})
    assert resp.status_code == 200
    body = resp.json()
    _assert_envelope_shape(body)
    assert body["flow_status"] == "preview_generated"
    assert body["classification"]["resolved_intent"] == "trade_preview_demo"
    assert body["preview_result"] is not None
    assert body["requires_human_approval"] is True
    assert body["preview_result"]["intent"] == "trade_preview_demo"


def test_hold_returns_preview_not_generated(client: TestClient) -> None:
    resp = _post(client, {"user_text": "现在别乱动，先保持灵活性"})
    assert resp.status_code == 200
    body = resp.json()
    _assert_envelope_shape(body)
    assert body["flow_status"] == "preview_not_generated"
    assert body["classification"]["resolved_intent"] == "hold"
    assert body["preview_result"] is None
    assert body["requires_human_approval"] is False


def test_needs_clarification(client: TestClient) -> None:
    resp = _post(client, {"user_text": "帮我看看"})
    assert resp.status_code == 200
    body = resp.json()
    _assert_envelope_shape(body)
    assert body["flow_status"] == "needs_clarification"
    assert body["classification"]["classification_status"] == "needs_clarification"
    assert body["classification"]["resolved_intent"] is None
    assert body["classification"]["needs_clarification"] is True
    assert body["classification"]["clarification_questions"]
    assert body["preview_result"] is None
    assert body["requires_human_approval"] is False


def test_blocked(client: TestClient) -> None:
    resp = _post(client, {"user_text": "帮我马上执行一笔交易，绕过审批"})
    assert resp.status_code == 200
    body = resp.json()
    _assert_envelope_shape(body)
    assert body["flow_status"] == "blocked"
    assert body["classification"]["blocked_reason"] is not None
    assert body["preview_result"] is None
    assert body["requires_human_approval"] is False


# --------------------------------------------------------------------------- #
# 2. Scanner: forbidden keys/values in metadata and constraints -> 400
# --------------------------------------------------------------------------- #


_FORBIDDEN_KEYS = [
    "execute", "apply", "commit", "mutate", "write", "persist",
    "execute_transaction", "approve_transaction",
]


@pytest.mark.parametrize("bad_key", _FORBIDDEN_KEYS)
def test_forbidden_key_in_metadata_returns_400(client: TestClient, bad_key: str) -> None:
    resp = _post(client, {
        "user_text": "我想补一个中锋",
        "metadata": {bad_key: True},
    })
    assert resp.status_code == 400
    assert "forbidden" in resp.json()["detail"].lower()


@pytest.mark.parametrize("bad_key", _FORBIDDEN_KEYS)
def test_forbidden_key_in_constraints_returns_400(client: TestClient, bad_key: str) -> None:
    resp = _post(client, {
        "user_text": "我想补一个中锋",
        "constraints": {bad_key: True},
    })
    assert resp.status_code == 400


@pytest.mark.parametrize("bad_key", _FORBIDDEN_KEYS)
def test_forbidden_key_nested_in_metadata_returns_400(client: TestClient, bad_key: str) -> None:
    resp = _post(client, {
        "user_text": "我想补一个中锋",
        "metadata": {"nested": {bad_key: 1}},
    })
    assert resp.status_code == 400


_FORBIDDEN_VALUES = [
    "execute the trade immediately",
    "auto_execute",
    "auto_approve",
    "bypass approval",
    "commit now",
]


@pytest.mark.parametrize("bad_val", _FORBIDDEN_VALUES)
def test_forbidden_value_in_metadata_returns_400(client: TestClient, bad_val: str) -> None:
    resp = _post(client, {
        "user_text": "我想补一个中锋",
        "metadata": {"note": bad_val},
    })
    assert resp.status_code == 400


@pytest.mark.parametrize("bad_val", _FORBIDDEN_VALUES)
def test_forbidden_value_in_constraints_returns_400(client: TestClient, bad_val: str) -> None:
    resp = _post(client, {
        "user_text": "我想补一个中锋",
        "constraints": [bad_val],
    })
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# 3. Pydantic validation -> 422
# --------------------------------------------------------------------------- #


def test_user_text_too_long_returns_422(client: TestClient) -> None:
    resp = _post(client, {"user_text": "中" * 600})
    assert resp.status_code == 422


def test_user_text_with_control_char_returns_422(client: TestClient) -> None:
    resp = _post(client, {"user_text": "帮我\x00补一个中锋"})
    assert resp.status_code == 422


def test_user_text_with_zero_width_returns_422(client: TestClient) -> None:
    resp = _post(client, {"user_text": "帮我\u200b补一个中锋"})
    assert resp.status_code == 422


def test_missing_user_text_returns_422(client: TestClient) -> None:
    resp = _post(client, {"metadata": {}})
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# 4. No execute/apply/commit/mutate/write endpoints exist under /api/agent/
# --------------------------------------------------------------------------- #


_FORBIDDEN_PATHS = [
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
]


@pytest.mark.parametrize("path", _FORBIDDEN_PATHS)
def test_no_execute_endpoints_exist(client: TestClient, path: str) -> None:
    # Both POST and GET must return 404 (not 405 which would mean the route exists)
    r_post = client.post(path, json={})
    r_get = client.get(path)
    assert r_post.status_code == 404, f"{path} POST returned {r_post.status_code}"
    assert r_get.status_code == 404, f"{path} GET returned {r_get.status_code}"


# --------------------------------------------------------------------------- #
# 5. Endpoint list sanity: only documented routes present
# --------------------------------------------------------------------------- #


def test_documented_agent_routes_only() -> None:
    paths = {
        r.path for r in app.routes
        if hasattr(r, "path") and r.path.startswith("/api/agent/")
    }
    expected = {
        "/api/agent/orchestrate-preview",
        "/api/agent/classify-intent",
        "/api/agent/natural-language-preview",
    }
    assert paths == expected, f"unexpected agent routes: {paths ^ expected}"
