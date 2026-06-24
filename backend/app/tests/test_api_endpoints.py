"""Tests for the M7-A backend API endpoints.

These tests use FastAPI's ``TestClient`` (backed by ``httpx``) so no
real server is started and no network is touched. They verify:

- health endpoint shape
- proposal-preview recommended path ($20M -> RECOMMENDED + SIGNING)
- proposal-preview strict-budget path ($15M -> NO_ACTION + HOLD)
- requires_human_approval is always true
- sample_data is always true
- no data file mutation after API calls
- trade-preview-demo endpoint shape + PASS + human approval
- invalid team_id returns a 4xx client error
- invalid target position returns a 4xx client error
- scenarios endpoint lists the three demo modes

Run:

    python -m pytest backend/app/tests/test_api_endpoints.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api import app


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


@pytest.fixture(scope="module")
def client() -> TestClient:
    """A module-scoped TestClient. The API is read-only so sharing is safe."""
    return TestClient(app)


def _hash_data_files() -> dict:
    """Snapshot the SHA-256 of every data JSON file for mutation checks."""
    import hashlib

    snapshot: dict = {}
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
# Health
# --------------------------------------------------------------------------- #


def test_health_endpoint(client: TestClient) -> None:
    """GET /api/health returns status=ok, sample_data=true, service name."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["sample_data"] is True
    assert body["service"] == "frontoffice-offseason-agent"


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #


def test_scenarios_endpoint(client: TestClient) -> None:
    """GET /api/offseason/scenarios lists the three demo modes."""
    resp = client.get("/api/offseason/scenarios")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_data"] is True
    ids = {s["id"] for s in body["scenarios"]}
    assert ids == {
        "signing_recommendation",
        "strict_budget_hold",
        "trade_preview_demo",
    }
    # Each scenario must advertise its endpoint + method.
    for s in body["scenarios"]:
        assert s["endpoint"].startswith("/api/offseason/")
        assert s["method"] in {"GET", "POST"}


# --------------------------------------------------------------------------- #
# Proposal preview — recommended path ($20M)
# --------------------------------------------------------------------------- #


def test_proposal_preview_recommended_path(client: TestClient) -> None:
    """$20M budget -> RECOMMENDED proposal with a SIGNING action that passes."""
    resp = client.post(
        "/api/offseason/proposal-preview",
        json={
            "team_id": "DEM-ATL",
            "objective": "Add frontcourt help",
            "target_positions": ["C"],
            "max_salary": 20000000,
            "max_candidates": 2,
            "evidence_query": "center need cap flexibility",
        },
    )
    assert resp.status_code == 200
    body = resp.json()

    # Top-level contract invariants.
    assert body["requires_human_approval"] is True
    assert body["sample_data"] is True

    # Proposal should be RECOMMENDED with at least one SIGNING action.
    proposal = body["proposal"]
    assert proposal["status"] == "RECOMMENDED"
    assert proposal["team_id"] == "DEM-ATL"
    assert len(proposal["recommended_actions"]) >= 1

    action = proposal["recommended_actions"][0]
    assert action["action_type"] == "SIGNING"
    assert action["validation_status"] == "PASS"
    assert action["is_valid"] is True
    assert action["requires_human_approval"] is True

    # Evaluation should PASS (sample_data_only INFO is allowed).
    evaluation = body["evaluation"]
    assert evaluation["status"] == "PASS"


# --------------------------------------------------------------------------- #
# Proposal preview — strict-budget path ($15M)
# --------------------------------------------------------------------------- #


def test_proposal_preview_strict_budget_hold_path(client: TestClient) -> None:
    """$15M budget -> NO_ACTION proposal with a HOLD action."""
    resp = client.post(
        "/api/offseason/proposal-preview",
        json={
            "team_id": "DEM-ATL",
            "objective": "Add frontcourt help",
            "target_positions": ["C"],
            "max_salary": 15000000,
            "max_candidates": 2,
            "evidence_query": "center need cap flexibility",
        },
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["requires_human_approval"] is True
    assert body["sample_data"] is True

    proposal = body["proposal"]
    assert proposal["status"] == "NO_ACTION"
    assert len(proposal["recommended_actions"]) >= 1

    action = proposal["recommended_actions"][0]
    assert action["action_type"] == "HOLD"


# --------------------------------------------------------------------------- #
# Proposal preview — guardrails
# --------------------------------------------------------------------------- #


def test_proposal_preview_requires_human_approval(client: TestClient) -> None:
    """requires_human_approval must be true at every level."""
    resp = client.post(
        "/api/offseason/proposal-preview",
        json={
            "team_id": "DEM-ATL",
            "objective": "Add frontcourt help",
            "target_positions": ["C"],
            "max_salary": 20000000,
            "max_candidates": 2,
            "evidence_query": "center need cap flexibility",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["requires_human_approval"] is True
    assert body["proposal"]["requires_human_approval"] is True
    for action in body["proposal"]["recommended_actions"]:
        assert action["requires_human_approval"] is True


def test_proposal_preview_sample_data_true(client: TestClient) -> None:
    """sample_data must be true at the top level."""
    resp = client.post(
        "/api/offseason/proposal-preview",
        json={
            "team_id": "DEM-ATL",
            "objective": "Add frontcourt help",
            "target_positions": ["C"],
            "max_salary": 20000000,
            "max_candidates": 2,
            "evidence_query": "center need cap flexibility",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["sample_data"] is True
    assert body["proposal"]["sample_data"] is True


def test_proposal_preview_no_data_mutation(client: TestClient) -> None:
    """Calling the endpoint must not mutate any data JSON file."""
    before = _hash_data_files()
    client.post(
        "/api/offseason/proposal-preview",
        json={
            "team_id": "DEM-ATL",
            "objective": "Add frontcourt help",
            "target_positions": ["C"],
            "max_salary": 20000000,
            "max_candidates": 2,
            "evidence_query": "center need cap flexibility",
        },
    )
    after = _hash_data_files()
    assert before == after


# --------------------------------------------------------------------------- #
# Proposal preview — error handling
# --------------------------------------------------------------------------- #


def test_invalid_team_returns_client_error(client: TestClient) -> None:
    """Unknown team_id must return 4xx, not 500."""
    resp = client.post(
        "/api/offseason/proposal-preview",
        json={
            "team_id": "DEM-XXX-DOES-NOT-EXIST",
            "objective": "Add frontcourt help",
            "target_positions": ["C"],
            "max_salary": 20000000,
            "max_candidates": 2,
            "evidence_query": "center need cap flexibility",
        },
    )
    assert 400 <= resp.status_code < 500
    body = resp.json()
    # FastAPI HTTPException detail is a string under "detail".
    assert "detail" in body


def test_invalid_target_position_returns_client_error(client: TestClient) -> None:
    """An invalid position string must return 4xx."""
    resp = client.post(
        "/api/offseason/proposal-preview",
        json={
            "team_id": "DEM-ATL",
            "objective": "Add frontcourt help",
            "target_positions": ["XX"],  # not a valid position
            "max_salary": 20000000,
            "max_candidates": 2,
            "evidence_query": "center need cap flexibility",
        },
    )
    assert 400 <= resp.status_code < 500
    body = resp.json()
    assert "detail" in body


def test_missing_team_id_returns_client_error(client: TestClient) -> None:
    """Omitting team_id must trigger Pydantic validation -> 422."""
    resp = client.post(
        "/api/offseason/proposal-preview",
        json={
            "objective": "Add frontcourt help",
            "target_positions": ["C"],
            "max_salary": 20000000,
            "max_candidates": 2,
        },
    )
    assert resp.status_code == 422


# --------------------------------------------------------------------------- #
# Trade preview demo
# --------------------------------------------------------------------------- #


def test_trade_preview_demo_endpoint(client: TestClient) -> None:
    """GET /api/offseason/trade-preview-demo returns the demo trade payload."""
    resp = client.get("/api/offseason/trade-preview-demo")
    assert resp.status_code == 200
    body = resp.json()

    # Top-level invariants.
    assert body["sample_data"] is True
    assert body["requires_human_approval"] is True

    # Trade transaction identity.
    tx = body["trade_transaction"]
    assert tx["transaction_id"] == "tx-trade-demo-001"
    assert tx["team_a_id"] == "DEM-ATL"
    assert tx["team_b_id"] == "DEM-PDX"
    assert len(tx["outgoing_from_a"]) >= 1
    assert len(tx["outgoing_from_b"]) >= 1

    # Preview validation result.
    preview = body["preview"]
    vr = preview["validation_result"]
    assert vr["status"] == "PASS"
    assert vr["is_valid"] is True
    assert vr["requires_human_approval"] is True

    # Salary matching both sides pass.
    sm = body["salary_matching"]
    assert sm["team_a"]["passed"] is True
    assert sm["team_b"]["passed"] is True


def test_trade_preview_demo_requires_human_approval(client: TestClient) -> None:
    """requires_human_approval must be true at every level of the trade payload."""
    resp = client.get("/api/offseason/trade-preview-demo")
    assert resp.status_code == 200
    body = resp.json()
    assert body["requires_human_approval"] is True
    assert body["trade_transaction"]["requires_human_approval"] is True
    assert body["preview"]["requires_human_approval"] is True
    assert body["preview"]["validation_result"]["requires_human_approval"] is True


def test_trade_preview_demo_status_pass(client: TestClient) -> None:
    """validation_result.status must be PASS for the demo trade."""
    resp = client.get("/api/offseason/trade-preview-demo")
    body = resp.json()
    assert body["preview"]["validation_result"]["status"] == "PASS"


def test_trade_preview_demo_no_data_mutation(client: TestClient) -> None:
    """Calling the trade endpoint must not mutate any data JSON file."""
    before = _hash_data_files()
    client.get("/api/offseason/trade-preview-demo")
    after = _hash_data_files()
    assert before == after


def test_trade_preview_demo_matches_cli_output(client: TestClient) -> None:
    """The API payload must equal the CLI script's JSON output (no drift)."""
    import subprocess
    import sys

    cli_path = REPO_ROOT / "backend" / "scripts" / "run_trade_preview_demo.py"
    result = subprocess.run(
        [sys.executable, str(cli_path), "--format", "json"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    cli_payload = json.loads(result.stdout)

    api_resp = client.get("/api/offseason/trade-preview-demo")
    api_payload = api_resp.json()

    # The API and CLI must produce identical payloads (same keys, same values).
    assert api_payload == cli_payload


# --------------------------------------------------------------------------- #
# Schema consistency with CLI (proposal preview)
# --------------------------------------------------------------------------- #


def test_proposal_preview_schema_matches_cli(client: TestClient) -> None:
    """The API proposal payload must have the same top-level keys as the CLI."""
    import subprocess
    import sys

    cli_path = REPO_ROOT / "backend" / "scripts" / "run_offseason_demo.py"
    result = subprocess.run(
        [
            sys.executable,
            str(cli_path),
            "--format",
            "json",
            "--team-id",
            "DEM-ATL",
            "--objective",
            "Add frontcourt help",
            "--target-position",
            "C",
            "--max-salary",
            "20000000",
            "--max-candidates",
            "2",
            "--evidence-query",
            "center need cap flexibility",
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    cli_payload = json.loads(result.stdout)

    api_resp = client.post(
        "/api/offseason/proposal-preview",
        json={
            "team_id": "DEM-ATL",
            "objective": "Add frontcourt help",
            "target_positions": ["C"],
            "max_salary": 20000000,
            "max_candidates": 2,
            "evidence_query": "center need cap flexibility",
        },
    )
    api_payload = api_resp.json()

    # Top-level keys must match so M7-B can swap static -> API seamlessly.
    assert set(api_payload.keys()) == set(cli_payload.keys())
    # Nested proposal + evaluation keys must match too.
    assert set(api_payload["proposal"].keys()) == set(cli_payload["proposal"].keys())
    assert set(api_payload["evaluation"].keys()) == set(cli_payload["evaluation"].keys())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
