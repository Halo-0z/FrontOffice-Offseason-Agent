"""Tests for the deterministic offseason_agent orchestrator (M4-B).

These tests verify that:

- The orchestrator returns a structured ``OffseasonAgentRun`` with a
  complete ``tool_call_trace``.
- Every signing preview requires human approval.
- The agent never writes to ``data/`` files.
- The agent never calls an LLM / MCP / OpenAI API.
- The agent never approves a transaction.
- Filtering by ``target_positions`` / ``max_salary`` / ``max_candidates``
  works.
- Unknown ``team_id`` raises a clear exception.
- Tool failures produce ``FAILED``/``FALLBACK`` trace records and a
  ``PARTIAL``/``FAILED`` run status.
- Output is deterministic.
- Models are frozen.

Run tests:

    python -m pytest backend/app/tests/test_offseason_agent.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.models.agent import (
    AgentRunStatus,
    OffseasonAgentRun,
    OffseasonGoal,
    ToolCallRecord,
    ToolCallStatus,
)
from backend.app.models.evidence import EvidenceBundle
from backend.app.models.roster import FreeAgentFit, TransactionPreview
from backend.app.services.cap_sheet_service import TeamNotFoundError
from backend.app.services.offseason_agent import run_offseason_plan

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"

_DATA_FILES = (
    "data/players.json",
    "data/contracts.json",
    "data/free_agents.json",
    "data/evidence_notes.json",
)


def _atl_goal(
    objective: str = "Add frontcourt help",
    target_positions: tuple = ("C",),
    max_salary: int | None = 20_000_000,
    max_candidates: int = 2,
    evidence_query: str | None = "center need cap flexibility",
) -> OffseasonGoal:
    return OffseasonGoal(
        team_id="DEM-ATL",
        objective=objective,
        target_positions=target_positions,
        max_salary=max_salary,
        max_candidates=max_candidates,
        evidence_query=evidence_query,
    )


# --------------------------------------------------------------------------- #
# Basic structure
# --------------------------------------------------------------------------- #


def test_run_offseason_plan_returns_offseason_agent_run() -> None:
    run = run_offseason_plan(_atl_goal(), DATA_DIR)
    assert isinstance(run, OffseasonAgentRun)
    assert run.team_id == "DEM-ATL"
    assert run.requires_human_approval is True
    assert run.sample_data is True


def test_tool_call_trace_includes_all_required_tools() -> None:
    run = run_offseason_plan(_atl_goal(), DATA_DIR)
    tool_names = [c.tool_name for c in run.tool_call_trace]
    assert "cap_sheet_service.summarize_cap_sheet" in tool_names
    assert "roster_need_service.evaluate_roster_needs" in tool_names
    assert "depth_chart_projector.project_current_depth_chart" in tool_names
    assert "free_agent_service.rank_free_agents_for_team" in tool_names
    assert "trade_simulator.preview_signing" in tool_names
    assert "evidence_service.search_evidence" in tool_names


def test_atl_run_identifies_roster_needs_and_free_agent_fits() -> None:
    run = run_offseason_plan(_atl_goal(), DATA_DIR)
    assert run.roster_need_report is not None
    assert len(run.roster_need_report.needs) > 0
    assert len(run.free_agent_fits) > 0
    for f in run.free_agent_fits:
        assert isinstance(f, FreeAgentFit)


def test_signing_previews_all_require_human_approval() -> None:
    run = run_offseason_plan(_atl_goal(), DATA_DIR)
    for p in run.signing_previews:
        assert isinstance(p, TransactionPreview)
        assert p.requires_human_approval is True


# --------------------------------------------------------------------------- #
# No mutation of data files
# --------------------------------------------------------------------------- #


def test_agent_does_not_mutate_players_json() -> None:
    path = DATA_DIR / "players.json"
    before = path.read_bytes()
    run_offseason_plan(_atl_goal(), DATA_DIR)
    after = path.read_bytes()
    assert before == after


def test_agent_does_not_mutate_contracts_json() -> None:
    path = DATA_DIR / "contracts.json"
    before = path.read_bytes()
    run_offseason_plan(_atl_goal(), DATA_DIR)
    after = path.read_bytes()
    assert before == after


def test_agent_does_not_mutate_free_agents_json() -> None:
    path = DATA_DIR / "free_agents.json"
    before = path.read_bytes()
    run_offseason_plan(_atl_goal(), DATA_DIR)
    after = path.read_bytes()
    assert before == after


def test_agent_does_not_mutate_evidence_notes_json() -> None:
    path = DATA_DIR / "evidence_notes.json"
    before = path.read_bytes()
    run_offseason_plan(_atl_goal(), DATA_DIR)
    after = path.read_bytes()
    assert before == after


# --------------------------------------------------------------------------- #
# No LLM / MCP / approved transactions
# --------------------------------------------------------------------------- #


def test_agent_does_not_call_llm_or_openai_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The agent must not import or call any LLM/OpenAI client. We verify
    by asserting the offseason_agent module has no ``openai`` / ``llm``
    / ``anthropic`` attributes, and that no network call is made (the
    test runs offline)."""
    from backend.app.services import offseason_agent as agent_mod

    for forbidden in ("openai", "llm", "anthropic", "chat_completion"):
        assert not hasattr(agent_mod, forbidden), (
            f"offseason_agent must not expose {forbidden!r}"
        )


def test_agent_does_not_use_mcp() -> None:
    """The agent must not import or use any MCP client/server."""
    from backend.app.services import offseason_agent as agent_mod

    for forbidden in ("mcp", "mcp_client", "mcp_server", "MCPClient"):
        assert not hasattr(agent_mod, forbidden), (
            f"offseason_agent must not expose {forbidden!r}"
        )


def test_agent_does_not_generate_approved_transaction() -> None:
    """No signing preview may have ``is_valid=True`` AND
    ``requires_human_approval=False``. Even valid previews must require
    human approval."""
    run = run_offseason_plan(_atl_goal(), DATA_DIR)
    for p in run.signing_previews:
        vr = p.validation_result
        if vr is not None and getattr(vr, "is_valid", False):
            assert p.requires_human_approval is True


# --------------------------------------------------------------------------- #
# Evidence bundle
# --------------------------------------------------------------------------- #


def test_evidence_bundle_is_returned_from_evidence_service() -> None:
    run = run_offseason_plan(_atl_goal(), DATA_DIR)
    assert isinstance(run.evidence_bundle, EvidenceBundle)
    # fallback_reason may be None (success) or a string (fallback), but
    # the bundle must always be present.
    assert run.evidence_bundle is not None


def test_evidence_bundle_preserves_missing_and_fallback() -> None:
    """When evidence ids from fits are missing, the bundle must report
    them in missing_evidence_ids and carry forward fallback_reason."""
    # Use a goal whose fits have evidence_ids (fa-005 has ev-001, ev-005).
    run = run_offseason_plan(
        _atl_goal(evidence_query="center market"),
        DATA_DIR,
    )
    bundle = run.evidence_bundle
    assert bundle is not None
    # If there are missing ids, fallback_reason must be set.
    if bundle.missing_evidence_ids:
        assert bundle.fallback_reason is not None


# --------------------------------------------------------------------------- #
# Error handling
# --------------------------------------------------------------------------- #


def test_unknown_team_id_raises_clear_exception() -> None:
    goal = OffseasonGoal(
        team_id="DEM-NONEXISTENT",
        objective="test",
        target_positions=("C",),
        max_salary=10_000_000,
        max_candidates=2,
        evidence_query="center",
    )
    with pytest.raises(TeamNotFoundError):
        run_offseason_plan(goal, DATA_DIR)


# --------------------------------------------------------------------------- #
# Filtering
# --------------------------------------------------------------------------- #


def test_max_candidates_is_applied() -> None:
    goal = _atl_goal(max_candidates=1)
    run = run_offseason_plan(goal, DATA_DIR)
    assert len(run.free_agent_fits) <= 1


def test_max_salary_is_applied() -> None:
    """With max_salary=1_000_000, only minimum-salary FAs pass the
    filter. fa-006 (PG, 5M) and fa-005 (C, 18M) should be filtered out."""
    goal = _atl_goal(max_salary=1_000_000, target_positions=())
    run = run_offseason_plan(goal, DATA_DIR)
    for f in run.free_agent_fits:
        assert f.expected_salary <= 1_000_000


def test_target_positions_is_applied() -> None:
    """With target_positions=('C',), only C candidates should remain."""
    goal = _atl_goal(target_positions=("C",), max_salary=0, max_candidates=0)
    run = run_offseason_plan(goal, DATA_DIR)
    for f in run.free_agent_fits:
        pos_val = f.position.value if hasattr(f.position, "value") else str(f.position)
        assert pos_val == "C"


# --------------------------------------------------------------------------- #
# Tool failure / fallback
# --------------------------------------------------------------------------- #


def test_tool_failure_produces_failed_or_fallback_trace_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When free_agent_service raises, the trace must record a FAILED
    entry and the run status must be FAILED (since a tool failed)."""
    from backend.app.services import offseason_agent as agent_mod

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated FA service failure")

    # Patch the reference imported into offseason_agent, not the source
    # module — otherwise the orchestrator still calls the original.
    monkeypatch.setattr(agent_mod, "rank_free_agents_for_team", _boom)
    run = run_offseason_plan(_atl_goal(), DATA_DIR)
    fa_trace = [c for c in run.tool_call_trace if "free_agent_service" in c.tool_name]
    assert len(fa_trace) == 1
    assert fa_trace[0].status is ToolCallStatus.FAILED
    assert fa_trace[0].fallback_reason is not None
    assert run.status is AgentRunStatus.FAILED
    assert run.free_agent_fits == ()


def test_no_free_agent_candidates_produces_partial_status() -> None:
    """When filtering removes all candidates, the FA trace is FALLBACK
    and the run status is PARTIAL."""
    goal = _atl_goal(
        target_positions=("C",),
        max_salary=1,  # impossibly low — no FA will pass
        max_candidates=2,
    )
    run = run_offseason_plan(goal, DATA_DIR)
    fa_trace = [c for c in run.tool_call_trace if "free_agent_service" in c.tool_name]
    assert fa_trace[0].status is ToolCallStatus.FALLBACK
    assert run.free_agent_fits == ()
    assert run.signing_previews == ()
    assert run.status is AgentRunStatus.PARTIAL


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #


def test_run_is_deterministic() -> None:
    goal = _atl_goal()
    r1 = run_offseason_plan(goal, DATA_DIR)
    r2 = run_offseason_plan(goal, DATA_DIR)
    assert r1 == r2


def test_tool_call_trace_is_deterministic() -> None:
    goal = _atl_goal()
    r1 = run_offseason_plan(goal, DATA_DIR)
    r2 = run_offseason_plan(goal, DATA_DIR)
    t1 = [(c.tool_name, c.status.value, c.input_summary, c.output_summary) for c in r1.tool_call_trace]
    t2 = [(c.tool_name, c.status.value, c.input_summary, c.output_summary) for c in r2.tool_call_trace]
    assert t1 == t2


# --------------------------------------------------------------------------- #
# Immutability
# --------------------------------------------------------------------------- #


def test_offseason_agent_run_is_frozen() -> None:
    run = run_offseason_plan(_atl_goal(), DATA_DIR)
    with pytest.raises(Exception):
        run.status = AgentRunStatus.FAILED  # type: ignore[misc]
    with pytest.raises(Exception):
        run.requires_human_approval = False  # type: ignore[misc]


def test_tool_call_record_is_frozen() -> None:
    run = run_offseason_plan(_atl_goal(), DATA_DIR)
    record = run.tool_call_trace[0]
    with pytest.raises(Exception):
        record.status = ToolCallStatus.FAILED  # type: ignore[misc]
    with pytest.raises(Exception):
        record.fallback_reason = "tampered"  # type: ignore[misc]


def test_offseason_goal_is_frozen() -> None:
    goal = _atl_goal()
    with pytest.raises(Exception):
        goal.team_id = "tampered"  # type: ignore[misc]
    with pytest.raises(Exception):
        goal.objective = "tampered"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Tool call trace structure
# --------------------------------------------------------------------------- #


def test_every_tool_call_record_has_required_fields() -> None:
    run = run_offseason_plan(_atl_goal(), DATA_DIR)
    for c in run.tool_call_trace:
        assert isinstance(c, ToolCallRecord)
        assert c.tool_name
        assert isinstance(c.status, ToolCallStatus)
        assert isinstance(c.input_summary, str)
        assert isinstance(c.output_summary, str)
        # fallback_reason is None on SUCCESS, a string on FALLBACK/FAILED.
        if c.status is ToolCallStatus.SUCCESS:
            assert c.fallback_reason is None
        else:
            assert c.fallback_reason is not None


def test_run_limitations_document_mvp_scope() -> None:
    run = run_offseason_plan(_atl_goal(), DATA_DIR)
    joined = " ".join(run.limitations).lower()
    assert "m4-b" in joined
    assert "no llm" in joined
    assert "no mcp" in joined
    assert "no external nba api" in joined
    assert "previews" in joined and "human approval" in joined


def test_cap_summary_and_depth_chart_are_populated() -> None:
    run = run_offseason_plan(_atl_goal(), DATA_DIR)
    assert run.cap_summary is not None
    assert run.current_depth_chart is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
