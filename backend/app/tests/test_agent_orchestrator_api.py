"""Tests for the M8-E5-B agent orchestrator API endpoint.

These tests use FastAPI's ``TestClient`` (backed by ``httpx``) to verify
the new ``POST /api/agent/orchestrate-preview`` endpoint. All tests are
read-only; no real server is started and no network is touched.

Coverage:
1. signing_preview intent returns 200 with correct shape.
2. Response contains preview_payload, agent_trace, requires_human_approval=true.
3. trade_preview_demo preserves deterministic trade validation status.
4. hold returns hold/blocked result with requires_human_approval=true.
5. Unsupported intent is blocked/hold, never guessed as signing/trade.
6. Metadata with forbidden mutation keys returns 400.
7. Nested metadata forbidden keys also return 400.
8. Response does not expose execute/apply/commit/mutate fields.
9. API call does not mutate data JSON files.
10. Demo/sample/historical labeling is never reported as current/live NBA data.
11. App does not expose /execute /apply /commit /mutate endpoints.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from backend.app.api import app


REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _hash_data_files() -> Dict[str, str]:
    snapshot: Dict[str, str] = {}
    for name in (
        "teams.json",
        "players.json",
        "contracts.json",
        "free_agents.json",
        "evidence_notes.json",
        "cap_config.json",
    ):
        path = DATA_DIR / name
        if path.exists():
            snapshot[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


# --------------------------------------------------------------------------- #
# 1. signing_preview returns 200
# --------------------------------------------------------------------------- #


def test_signing_preview_returns_200(client: TestClient) -> None:
    resp = client.post(
        "/api/agent/orchestrate-preview",
        json={
            "intent": "signing_preview",
            "team_id": "DEM-ATL",
            "objective": "补强大个子",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "signing_preview"
    assert body["status"] == "awaiting_human_approval"


# --------------------------------------------------------------------------- #
# 2. Response shape: preview_payload, agent_trace, requires_human_approval=true
# --------------------------------------------------------------------------- #


def test_signing_preview_response_shape(client: TestClient) -> None:
    resp = client.post(
        "/api/agent/orchestrate-preview",
        json={
            "intent": "signing_preview",
            "team_id": "DEM-ATL",
            "objective": "补强大个子",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["requires_human_approval"] is True
    assert "preview_payload" in body
    assert "agent_trace" in body
    assert body["agent_trace"]["requires_human_approval"] is True
    assert body["preview_payload"]["requires_human_approval"] is True
    assert len(body["agent_trace"]["steps"]) == 5
    assert body["agent_trace"]["steps"][4]["tool_name"] == "request_human_approval"
    assert body["agent_trace"]["steps"][4]["requires_human_review"] is True


# --------------------------------------------------------------------------- #
# 3. trade_preview_demo preserves deterministic validation status
# --------------------------------------------------------------------------- #


def test_trade_preview_demo_preserves_validation(client: TestClient) -> None:
    # First get the deterministic trade preview directly via the existing
    # GET endpoint for comparison.
    direct = client.get("/api/offseason/trade-preview-demo")
    assert direct.status_code == 200
    direct_body = direct.json()
    direct_vr = direct_body["preview"]["validation_result"]

    resp = client.post(
        "/api/agent/orchestrate-preview",
        json={"intent": "trade_preview_demo"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "trade_preview_demo"
    assert body["requires_human_approval"] is True

    orch_vr = body["preview_payload"]["preview"]["validation_result"]
    assert orch_vr["status"] == direct_vr["status"]
    assert orch_vr["is_valid"] == direct_vr["is_valid"]


# --------------------------------------------------------------------------- #
# 4. hold returns hold/blocked result with requires_human_approval=true
# --------------------------------------------------------------------------- #


def test_hold_returns_hold_result(client: TestClient) -> None:
    resp = client.post(
        "/api/agent/orchestrate-preview",
        json={"intent": "hold"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["intent"] == "hold"
    assert body["status"] == "hold"
    assert body["requires_human_approval"] is True
    assert body["preview_payload"]["status"] == "hold"


# --------------------------------------------------------------------------- #
# 5. unsupported intent blocked, not guessed
# --------------------------------------------------------------------------- #


def test_unsupported_intent_blocked_not_guessed(client: TestClient) -> None:
    bad_intents = [
        "execute_trade",
        "sign_player",
        "auto_execute",
        "trade_player_now",
        "commit_deal",
    ]
    for intent in bad_intents:
        resp = client.post(
            "/api/agent/orchestrate-preview",
            json={"intent": intent},
        )
        assert resp.status_code == 200, (
            f"unsupported intent={intent!r} should still 200 (service blocks)"
        )
        body = resp.json()
        assert body["status"] == "blocked", (
            f"unsupported intent={intent!r} should be blocked, got {body['status']}"
        )
        assert body["requires_human_approval"] is True
        # Must NOT have invoked signing/trade preview (no proposal/trade_transaction keys).
        assert "proposal" not in body["preview_payload"]
        assert "trade_transaction" not in body["preview_payload"]


# --------------------------------------------------------------------------- #
# 6. metadata forbidden keys -> 400
# --------------------------------------------------------------------------- #


_FORBIDDEN_TOP_LEVEL = [
    "execute",
    "executed",
    "apply",
    "applied",
    "commit",
    "committed",
    "mutate",
    "mutated",
    "write",
    "persist",
    "approve_transaction",
    "execute_transaction",
    "execute_signing",
    "roster_update",
    "contract_update",
    "snapshot_write",
]


@pytest.mark.parametrize("forbidden_key", _FORBIDDEN_TOP_LEVEL)
def test_metadata_forbidden_key_returns_400(
    client: TestClient, forbidden_key: str
) -> None:
    resp = client.post(
        "/api/agent/orchestrate-preview",
        json={
            "intent": "signing_preview",
            "team_id": "DEM-ATL",
            "metadata": {forbidden_key: True},
        },
    )
    assert resp.status_code == 400, (
        f"metadata with key {forbidden_key!r} should return 400"
    )
    detail = resp.json().get("detail", "")
    assert "forbidden" in detail.lower() or "preview-only" in detail.lower()


# --------------------------------------------------------------------------- #
# 7. nested metadata forbidden key also returns 400
# --------------------------------------------------------------------------- #


def test_nested_metadata_forbidden_key_returns_400(client: TestClient) -> None:
    nested_cases = [
        {"options": {"execute": True}},
        {"options": {"nested": {"commit": "yes"}}},
        {"steps": [{"apply": True}]},
        {"deep": {"deeper": {"deepest": {"mutate": True}}}},
        {"EXECUTE": True},
        {"CommitTransaction": "now"},
    ]
    for meta in nested_cases:
        resp = client.post(
            "/api/agent/orchestrate-preview",
            json={
                "intent": "signing_preview",
                "team_id": "DEM-ATL",
                "metadata": meta,
            },
        )
        assert resp.status_code == 400, (
            f"nested metadata {meta} should return 400"
        )


def test_clean_metadata_passes(client: TestClient) -> None:
    """Metadata with benign keys must not be blocked."""
    resp = client.post(
        "/api/agent/orchestrate-preview",
        json={
            "intent": "signing_preview",
            "team_id": "DEM-ATL",
            "metadata": {
                "source": "ui",
                "user_role": "viewer",
                "debug": False,
                "options": {"dry_run": True},
            },
        },
    )
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# 8. response does not expose mutation capability fields
# --------------------------------------------------------------------------- #


_FORBIDDEN_RESPONSE_TERMS = {
    "auto_executed",
    "transaction_executed",
    "signed_automatically",
    "trade_executed",
    "wrote_snapshot",
    "roster_modified",
    "contracts_modified",
}


def test_response_contains_no_mutation_fields(client: TestClient) -> None:
    for intent in ("signing_preview", "trade_preview_demo", "hold"):
        body_data: Dict[str, Any] = {"intent": intent}
        if intent == "signing_preview":
            body_data["team_id"] = "DEM-ATL"
        resp = client.post("/api/agent/orchestrate-preview", json=body_data)
        assert resp.status_code == 200
        serialized = json.dumps(resp.json(), ensure_ascii=False).lower()
        for term in _FORBIDDEN_RESPONSE_TERMS:
            assert term not in serialized, (
                f"{intent} response contains forbidden term {term!r}"
            )


# --------------------------------------------------------------------------- #
# 9. API call does not mutate data JSON files
# --------------------------------------------------------------------------- #


def test_api_call_does_not_mutate_data_files(client: TestClient) -> None:
    before = _hash_data_files()
    for intent in ("signing_preview", "trade_preview_demo", "hold"):
        body_data: Dict[str, Any] = {"intent": intent}
        if intent == "signing_preview":
            body_data["team_id"] = "DEM-ATL"
        client.post("/api/agent/orchestrate-preview", json=body_data)
    after = _hash_data_files()
    assert before == after, "API call must not mutate data/*.json files"


# --------------------------------------------------------------------------- #
# 10. demo/sample labeling never claims current/live NBA data
# --------------------------------------------------------------------------- #


_FORBIDDEN_LIVE_LABELS = {"current nba", "live nba", "real-time nba", "real time nba"}


def test_demo_label_not_misrepresented_as_live(client: TestClient) -> None:
    for intent in ("signing_preview", "trade_preview_demo"):
        body_data: Dict[str, Any] = {"intent": intent}
        if intent == "signing_preview":
            body_data["team_id"] = "DEM-ATL"
        resp = client.post("/api/agent/orchestrate-preview", json=body_data)
        assert resp.status_code == 200
        body = resp.json()
        serialized = json.dumps(body, ensure_ascii=False).lower()

        # Must have a sample/demo/historical label.
        has_label = (
            "sample_data" in serialized
            or "演示数据" in body["agent_trace"].get("data_source_label", "")
            or "历史数据样本" in body["agent_trace"].get("data_source_label", "")
        )
        assert has_label, f"{intent} response missing demo/sample/historical label"

        # Must NOT claim to be live/current/real-time.
        for label in _FORBIDDEN_LIVE_LABELS:
            assert label not in serialized, (
                f"{intent} response must not be labeled as {label!r}"
            )


# --------------------------------------------------------------------------- #
# 11. app does not expose /execute /apply /commit /mutate endpoints
# --------------------------------------------------------------------------- #


def test_no_execution_endpoints_exist(client: TestClient) -> None:
    forbidden_paths = [
        ("/api/execute", "POST"),
        ("/api/apply", "POST"),
        ("/api/commit", "POST"),
        ("/api/mutate", "POST"),
        ("/api/write-snapshot", "POST"),
        ("/api/agent/execute", "POST"),
        ("/api/agent/apply", "POST"),
        ("/api/agent/commit", "POST"),
    ]
    # Hit each forbidden path and assert we get 404 or 405, never 200.
    for path, method in forbidden_paths:
        if method == "POST":
            resp = client.post(path, json={})
        else:
            resp = client.get(path)
        assert resp.status_code in (404, 405), (
            f"endpoint {method} {path} must not exist (got {resp.status_code})"
        )


# --------------------------------------------------------------------------- #
# 12. (extra) required field intent missing -> 422
# --------------------------------------------------------------------------- #


def test_missing_intent_returns_422(client: TestClient) -> None:
    resp = client.post(
        "/api/agent/orchestrate-preview",
        json={"team_id": "DEM-ATL"},
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# 13. (extra) metadata with case-variants of forbidden keys also blocked
# --------------------------------------------------------------------------- #


def test_case_insensitive_metadata_block(client: TestClient) -> None:
    resp = client.post(
        "/api/agent/orchestrate-preview",
        json={
            "intent": "hold",
            "metadata": {"EXECUTE": True},
        },
    )
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# 14. (extra) response final_message is read-only disclaimer
# --------------------------------------------------------------------------- #


def test_response_final_message_is_read_only(client: TestClient) -> None:
    resp = client.post(
        "/api/agent/orchestrate-preview",
        json={"intent": "hold"},
    )
    body = resp.json()
    msg = body["agent_trace"]["final_message"]
    assert "只读" in msg
    assert "不会自动执行" in msg
