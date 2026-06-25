"""Tests for the M8-E2 agent trace schema and builders.

Covers:
- proposal-preview returns agent_trace with the 8 contracted steps
- strict-budget hold path returns agent_trace (HOLD not RECOMMEND)
- trade-preview-demo returns agent_trace with simulate_trade step
- backward compatibility (old fields still present)
- no mutation / no execution flags in the trace
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.api import app


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


_DEMO_PROPOSAL_REQUEST = {
    "team_id": "DEM-ATL",
    "objective": "Add frontcourt help",
    "target_positions": ["C"],
    "max_salary": 20000000,
    "max_candidates": 2,
    "evidence_query": "center need cap flexibility",
}

_STRICT_BUDGET_REQUEST = {
    "team_id": "DEM-ATL",
    "objective": "Add frontcourt help",
    "target_positions": ["C"],
    "max_salary": 15000000,
    "max_candidates": 2,
    "evidence_query": "center need cap flexibility",
}


# --------------------------------------------------------------------------- #
# Proposal-preview agent_trace
# --------------------------------------------------------------------------- #


def test_proposal_preview_has_agent_trace(client: TestClient) -> None:
    """proposal-preview must return an agent_trace top-level key."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    assert resp.status_code == 200
    body = resp.json()
    assert "agent_trace" in body
    trace = body["agent_trace"]
    assert isinstance(trace, dict)


def test_proposal_trace_has_required_top_level_fields(client: TestClient) -> None:
    """agent_trace must contain the contracted run-level fields."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    trace = resp.json()["agent_trace"]
    for key in (
        "run_id",
        "intent_type",
        "overall_status",
        "current_state",
        "data_source_label",
        "steps",
        "requires_human_approval",
        "approval_state",
        "final_message",
    ):
        assert key in trace, f"missing run-level field: {key}"


def test_proposal_trace_steps_non_empty(client: TestClient) -> None:
    """agent_trace.steps must be a non-empty list."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    steps = resp.json()["agent_trace"]["steps"]
    assert isinstance(steps, list)
    assert len(steps) == 8


def test_proposal_trace_contains_load_active_data_source(client: TestClient) -> None:
    """Step 1 must be load_active_data_source."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    steps = resp.json()["agent_trace"]["steps"]
    tool_names = [s["tool_name"] for s in steps]
    assert "load_active_data_source" in tool_names


def test_proposal_trace_contains_simulate_signing(client: TestClient) -> None:
    """A step must use simulate_signing."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    steps = resp.json()["agent_trace"]["steps"]
    tool_names = [s["tool_name"] for s in steps]
    assert "simulate_signing" in tool_names


def test_proposal_trace_contains_validate_salary_rules(client: TestClient) -> None:
    """A step must use validate_salary_rules."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    steps = resp.json()["agent_trace"]["steps"]
    tool_names = [s["tool_name"] for s in steps]
    assert "validate_salary_rules" in tool_names


def test_proposal_trace_contains_request_human_approval(client: TestClient) -> None:
    """The last step must be request_human_approval."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    steps = resp.json()["agent_trace"]["steps"]
    assert steps[-1]["tool_name"] == "request_human_approval"


def test_proposal_trace_requires_human_approval_true(client: TestClient) -> None:
    """agent_trace.requires_human_approval must be True."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    trace = resp.json()["agent_trace"]
    assert trace["requires_human_approval"] is True


def test_proposal_trace_final_message_read_only(client: TestClient) -> None:
    """final_message must mention read-only / 只读预览."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    final = resp.json()["agent_trace"]["final_message"]
    assert "只读预览" in final or "read-only" in final.lower()


def test_proposal_trace_step_fields_complete(client: TestClient) -> None:
    """Each step must have all contracted step-level fields."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    steps = resp.json()["agent_trace"]["steps"]
    required = {
        "step_id", "sequence", "status", "title",
        "plain_language_summary", "tool_name",
        "inputs_summary", "outputs_summary",
        "warnings", "evidence_ids", "requires_human_review",
        "technical_details", "started_at", "finished_at",
    }
    for s in steps:
        assert required.issubset(set(s.keys())), f"step missing fields: {s}"


def test_proposal_trace_salary_step_status_matches_verdict(client: TestClient) -> None:
    """The salary-rules step status must be derived from the validation verdict."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    body = resp.json()
    trace = body["agent_trace"]
    steps = trace["steps"]
    # The primary action's validation_status drives the salary step.
    primary_vstatus = body["actions"][0]["validation_status"]
    salary_step = next(s for s in steps if s["tool_name"] == "validate_salary_rules")
    if primary_vstatus == "PASS":
        assert salary_step["status"] == "completed"
    elif primary_vstatus == "WARNING":
        assert salary_step["status"] == "warning"
    elif primary_vstatus == "FAIL":
        assert salary_step["status"] == "blocked"


def test_proposal_trace_human_approval_step_requires_review(client: TestClient) -> None:
    """The final approval step must have requires_human_review=True."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    steps = resp.json()["agent_trace"]["steps"]
    approval_step = steps[-1]
    assert approval_step["requires_human_review"] is True


def test_proposal_trace_does_not_expose_long_snapshot_id_in_summary(
    client: TestClient,
) -> None:
    """plain_language_summary must not contain long snapshot_id strings."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    steps = resp.json()["agent_trace"]["steps"]
    for s in steps:
        summary = s["plain_language_summary"]
        # A long snapshot id is > 20 chars and contains "sourcepack" or similar.
        assert "sourcepack" not in summary
        assert "nba_2025_26" not in summary


# --------------------------------------------------------------------------- #
# Strict-budget hold path
# --------------------------------------------------------------------------- #


def test_strict_budget_hold_trace_exists(client: TestClient) -> None:
    """The HOLD path must still return an agent_trace."""
    resp = client.post("/api/offseason/proposal-preview", json=_STRICT_BUDGET_REQUEST)
    assert resp.status_code == 200
    body = resp.json()
    assert "agent_trace" in body
    assert len(body["agent_trace"]["steps"]) == 8


def test_strict_budget_hold_does_not_become_recommend(client: TestClient) -> None:
    """HOLD must not be upgraded to RECOMMENDED by the trace."""
    resp = client.post("/api/offseason/proposal-preview", json=_STRICT_BUDGET_REQUEST)
    body = resp.json()
    assert body["proposal"]["status"] == "NO_ACTION"
    # The trace intent should be hold, not signing.
    assert body["agent_trace"]["intent_type"] == "hold"


def test_strict_budget_hold_requires_human_approval(client: TestClient) -> None:
    """HOLD path still requires human approval / read-only disclaimer."""
    resp = client.post("/api/offseason/proposal-preview", json=_STRICT_BUDGET_REQUEST)
    trace = resp.json()["agent_trace"]
    assert trace["requires_human_approval"] is True
    assert "只读预览" in trace["final_message"]


# --------------------------------------------------------------------------- #
# Trade-preview-demo agent_trace
# --------------------------------------------------------------------------- #


def test_trade_preview_has_agent_trace(client: TestClient) -> None:
    """trade-preview-demo must return an agent_trace top-level key."""
    resp = client.get("/api/offseason/trade-preview-demo")
    assert resp.status_code == 200
    body = resp.json()
    assert "agent_trace" in body
    trace = body["agent_trace"]
    assert isinstance(trace, dict)
    assert len(trace["steps"]) == 8


def test_trade_trace_contains_simulate_trade(client: TestClient) -> None:
    """A step must use simulate_trade."""
    resp = client.get("/api/offseason/trade-preview-demo")
    steps = resp.json()["agent_trace"]["steps"]
    tool_names = [s["tool_name"] for s in steps]
    assert "simulate_trade" in tool_names


def test_trade_trace_contains_validate_salary_rules(client: TestClient) -> None:
    """A step must use validate_salary_rules (salary matching)."""
    resp = client.get("/api/offseason/trade-preview-demo")
    steps = resp.json()["agent_trace"]["steps"]
    tool_names = [s["tool_name"] for s in steps]
    assert "validate_salary_rules" in tool_names


def test_trade_trace_contains_request_human_approval(client: TestClient) -> None:
    """The last step must be request_human_approval."""
    resp = client.get("/api/offseason/trade-preview-demo")
    steps = resp.json()["agent_trace"]["steps"]
    assert steps[-1]["tool_name"] == "request_human_approval"


def test_trade_trace_does_not_change_business_fields(client: TestClient) -> None:
    """The trade business fields must be unchanged by the trace."""
    resp = client.get("/api/offseason/trade-preview-demo")
    body = resp.json()
    assert body["trade_transaction"]["transaction_id"] == "tx-trade-demo-001"
    assert body["preview"]["validation_result"]["status"] == "PASS"
    assert body["salary_matching"]["team_a"]["passed"] is True
    assert body["salary_matching"]["team_b"]["passed"] is True
    assert body["requires_human_approval"] is True


def test_trade_trace_intent_is_trade(client: TestClient) -> None:
    """The trade trace intent_type must be 'trade'."""
    resp = client.get("/api/offseason/trade-preview-demo")
    trace = resp.json()["agent_trace"]
    assert trace["intent_type"] == "trade"


# --------------------------------------------------------------------------- #
# Backward compatibility
# --------------------------------------------------------------------------- #


def test_proposal_old_fields_still_present(client: TestClient) -> None:
    """Old proposal-preview fields must still exist alongside agent_trace."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    body = resp.json()
    for key in (
        "proposal", "evaluation", "actions", "evidence",
        "tool_trace", "limitations",
        "requires_human_approval", "sample_data",
    ):
        assert key in body, f"old field missing: {key}"


def test_trade_old_fields_still_present(client: TestClient) -> None:
    """Old trade-preview-demo fields must still exist alongside agent_trace."""
    resp = client.get("/api/offseason/trade-preview-demo")
    body = resp.json()
    for key in (
        "trade_transaction", "preview", "salary_matching",
        "team_a_post_trade", "team_b_post_trade",
        "requires_human_approval", "sample_data",
    ):
        assert key in body, f"old field missing: {key}"


# --------------------------------------------------------------------------- #
# No mutation / no execution
# --------------------------------------------------------------------------- #


def test_trace_has_no_executed_flag(client: TestClient) -> None:
    """No trace step may claim execution (executed=true)."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    trace = resp.json()["agent_trace"]
    for s in trace["steps"]:
        td = s.get("technical_details", {})
        assert td.get("executed") is not True
        assert td.get("applied") is not True
        assert td.get("committed") is not True


def test_trace_has_no_mutation_tools(client: TestClient) -> None:
    """No step tool_name may be a mutation/execution tool."""
    forbidden = {
        "apply_transaction", "commit", "mutate_roster",
        "execute_signing", "execute_trade", "write_snapshot",
    }
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    steps = resp.json()["agent_trace"]["steps"]
    for s in steps:
        assert s["tool_name"] not in forbidden


def test_trade_trace_has_no_executed_flag(client: TestClient) -> None:
    """No trade trace step may claim execution."""
    resp = client.get("/api/offseason/trade-preview-demo")
    trace = resp.json()["agent_trace"]
    for s in trace["steps"]:
        td = s.get("technical_details", {})
        assert td.get("executed") is not True
        assert td.get("applied") is not True


def test_trace_approval_is_preview_only(client: TestClient) -> None:
    """approval_state must not be a real execution state."""
    resp = client.post("/api/offseason/proposal-preview", json=_DEMO_PROPOSAL_REQUEST)
    trace = resp.json()["agent_trace"]
    # approved_preview is the max — never "executed" or "applied".
    assert trace["approval_state"] in (
        "required", "approved_preview", "blocked", "not_required",
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
