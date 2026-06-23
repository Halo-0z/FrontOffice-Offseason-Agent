"""Tests for the deterministic proposal_evaluator (M4-D).

These tests verify that:

- ``evaluate_structured_proposal`` returns a ``ProposalEvaluation``.
- A valid RECOMMENDED proposal produces PASS or WARNING (not FAIL).
- Missing ``requires_human_approval`` produces a FAIL issue.
- ``validation_status=FAIL`` but ``is_valid=True`` produces a FAIL
  issue.
- Invalid signing actions cannot get a clean PASS.
- Empty ``evidence_refs`` with RECOMMENDED produces a WARNING.
- Missing evidence fallback without a risk produces a WARNING.
- Missing key tools in ``tool_call_trace`` produces an issue.
- NO_ACTION with a HOLD action / no_matching_candidate risk does not
  FAIL.
- No candidates but RECOMMENDED produces a FAIL.
- ``sample_data=True`` is recognized and produces an INFO note.
- The evaluator does not mutate any data file.
- The evaluator does not call LLM / MCP / ``transaction_rule_engine``
  / ``trade_simulator``.
- ``run_evaluation_scenario`` returns an ``EvaluationScenarioResult``.
- ``run_default_evaluation_scenarios`` returns multiple results.
- Default scenarios do not FAIL (unless explicitly testing failure).
- Scenario outputs are deterministic.
- Models are frozen.

Run tests:

    python -m pytest backend/app/tests/test_proposal_evaluator.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.models.agent import OffseasonGoal
from backend.app.models.evaluation import (
    EvaluationIssue,
    EvaluationIssueCode,
    EvaluationScenario,
    EvaluationScenarioResult,
    EvaluationSeverity,
    EvaluationStatus,
    ProposalEvaluation,
)
from backend.app.models.proposal import (
    ProposalAction,
    ProposalActionType,
    ProposalEvidenceRef,
    ProposalRisk,
    ProposalRiskLevel,
    ProposalStatus,
    StructuredProposal,
)
from backend.app.services.proposal_builder import run_goal_and_build_proposal
from backend.app.services.proposal_evaluator import (
    evaluate_structured_proposal,
    run_default_evaluation_scenarios,
    run_evaluation_scenario,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


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


def _build_recommended_proposal() -> StructuredProposal:
    """Build a real RECOMMENDED proposal via the builder."""
    return run_goal_and_build_proposal(_atl_goal(), DATA_DIR)


def _make_action(
    action_id: str = "act-0-test",
    action_type: ProposalActionType = ProposalActionType.SIGNING,
    team_id: str = "DEM-ATL",
    validation_status: str = "PASS",
    is_valid: bool = True,
    requires_human_approval: bool = True,
    transaction_id: str | None = "tx-test",
    player_id: str | None = "fa-005",
    player_name: str | None = "Demo FA Quebec",
    position: str | None = "C",
    salary: int | None = 18_000_000,
    years: int | None = 1,
    fit_score: float | None = 0.8,
    matched_need: str | None = "C: have 0, target 2",
    cap_impact_summary: str = "after: total_salary=80M, cap_space=60M",
    roster_impact_summary: str = "roster_count=13, needs=[]",
    depth_chart_impact_summary: str = "C:fa-005/low",
    evidence_ids: tuple = ("ev-001",),
    limitations: tuple = ("MVP preview.",),
) -> ProposalAction:
    return ProposalAction(
        action_id=action_id,
        action_type=action_type,
        team_id=team_id,
        validation_status=validation_status,
        is_valid=is_valid,
        requires_human_approval=requires_human_approval,
        transaction_id=transaction_id,
        player_id=player_id,
        player_name=player_name,
        position=position,
        salary=salary,
        years=years,
        fit_score=fit_score,
        matched_need=matched_need,
        cap_impact_summary=cap_impact_summary,
        roster_impact_summary=roster_impact_summary,
        depth_chart_impact_summary=depth_chart_impact_summary,
        evidence_ids=evidence_ids,
        limitations=limitations,
    )


def _make_proposal(
    status: ProposalStatus = ProposalStatus.RECOMMENDED,
    recommended_actions: tuple | None = None,
    risks: tuple | None = None,
    evidence_refs: tuple | None = None,
    tool_call_trace: tuple | None = None,
    fallback_reasons: tuple = (),
    limitations: tuple = ("M4-C MVP.",),
    requires_human_approval: bool = True,
    sample_data: bool = True,
    proposal_id: str = "prop-DEM-ATL-test",
    team_id: str = "DEM-ATL",
    objective: str = "Test objective",
) -> StructuredProposal:
    """Build a synthetic StructuredProposal for testing."""
    if recommended_actions is None:
        recommended_actions = (_make_action(),)
    if risks is None:
        risks = (
            ProposalRisk(
                code="sample_data",
                level=ProposalRiskLevel.LOW,
                summary="Demo data.",
            ),
        )
    if evidence_refs is None:
        evidence_refs = (
            ProposalEvidenceRef(
                evidence_id="ev-001",
                title="Demo note",
                source="demo",
                evidence_type="roster_context",
                sample_data=True,
            ),
        )
    if tool_call_trace is None:
        # Build a minimal complete trace with all required tools.
        from backend.app.models.agent import ToolCallRecord, ToolCallStatus

        tool_call_trace = tuple(
            ToolCallRecord(
                tool_name=name,
                status=ToolCallStatus.SUCCESS,
                input_summary="test",
                output_summary="test",
            )
            for name in (
                "cap_sheet_service.summarize_cap_sheet",
                "roster_need_service.evaluate_roster_needs",
                "depth_chart_projector.project_current_depth_chart",
                "free_agent_service.rank_free_agents_for_team",
                "trade_simulator.preview_signing",
                "evidence_service.search_evidence",
            )
        )
    return StructuredProposal(
        proposal_id=proposal_id,
        team_id=team_id,
        objective=objective,
        status=status,
        recommended_actions=recommended_actions,
        risks=risks,
        evidence_refs=evidence_refs,
        tool_call_trace=tool_call_trace,
        cap_summary="total_salary=80M",
        roster_need_summary="roster_count=12",
        depth_chart_summary="C:None/high",
        fallback_reasons=fallback_reasons,
        limitations=limitations,
        requires_human_approval=requires_human_approval,
        sample_data=sample_data,
    )


# --------------------------------------------------------------------------- #
# Basic structure
# --------------------------------------------------------------------------- #


def test_evaluate_structured_proposal_returns_proposal_evaluation() -> None:
    proposal = _build_recommended_proposal()
    evaluation = evaluate_structured_proposal(proposal)
    assert isinstance(evaluation, ProposalEvaluation)
    assert evaluation.proposal_id == proposal.proposal_id
    assert evaluation.team_id == proposal.team_id
    assert evaluation.sample_data is True


def test_valid_recommended_proposal_evaluation_not_fail() -> None:
    proposal = _build_recommended_proposal()
    evaluation = evaluate_structured_proposal(proposal)
    assert evaluation.status in (EvaluationStatus.PASS, EvaluationStatus.WARNING)
    assert evaluation.status is not EvaluationStatus.FAIL


# --------------------------------------------------------------------------- #
# Human approval guardrail
# --------------------------------------------------------------------------- #


def test_missing_proposal_human_approval_produces_fail_issue() -> None:
    proposal = _make_proposal(requires_human_approval=False)
    evaluation = evaluate_structured_proposal(proposal)
    assert evaluation.status is EvaluationStatus.FAIL
    codes = [i.code for i in evaluation.issues]
    assert EvaluationIssueCode.missing_human_approval in codes
    assert "human_approval_guardrail" in evaluation.failed_checks


def test_missing_action_human_approval_produces_fail_issue() -> None:
    bad_action = _make_action(requires_human_approval=False)
    proposal = _make_proposal(recommended_actions=(bad_action,))
    evaluation = evaluate_structured_proposal(proposal)
    assert evaluation.status is EvaluationStatus.FAIL
    codes = [i.code for i in evaluation.issues]
    assert EvaluationIssueCode.missing_human_approval in codes


# --------------------------------------------------------------------------- #
# Validation guardrail
# --------------------------------------------------------------------------- #


def test_validation_status_fail_but_is_valid_true_produces_fail_issue() -> None:
    bad_action = _make_action(validation_status="FAIL", is_valid=True)
    proposal = _make_proposal(recommended_actions=(bad_action,))
    evaluation = evaluate_structured_proposal(proposal)
    assert evaluation.status is EvaluationStatus.FAIL
    codes = [i.code for i in evaluation.issues]
    assert EvaluationIssueCode.approved_without_validation in codes


def test_invalid_signing_action_cannot_get_clean_pass() -> None:
    # RECOMMENDED but the only action is invalid (is_valid=False).
    bad_action = _make_action(is_valid=False, validation_status="FAIL")
    proposal = _make_proposal(
        status=ProposalStatus.RECOMMENDED,
        recommended_actions=(bad_action,),
    )
    evaluation = evaluate_structured_proposal(proposal)
    assert evaluation.status is EvaluationStatus.FAIL
    codes = [i.code for i in evaluation.issues]
    assert EvaluationIssueCode.invalid_action_recommended in codes


# --------------------------------------------------------------------------- #
# Evidence guardrail
# --------------------------------------------------------------------------- #


def test_empty_evidence_refs_with_recommended_produces_warning() -> None:
    proposal = _make_proposal(evidence_refs=())
    evaluation = evaluate_structured_proposal(proposal)
    codes = [i.code for i in evaluation.issues]
    assert EvaluationIssueCode.missing_evidence in codes
    # The missing_evidence issue should be a WARNING.
    for issue in evaluation.issues:
        if issue.code is EvaluationIssueCode.missing_evidence:
            assert issue.severity is EvaluationSeverity.WARNING


def test_missing_evidence_fallback_without_risk_produces_warning() -> None:
    # fallback_reasons mention missing evidence, but no evidence_missing risk.
    proposal = _make_proposal(
        fallback_reasons=("evidence_service: missing evidence ids ['ev-x']",),
        risks=(
            ProposalRisk(
                code="sample_data",
                level=ProposalRiskLevel.LOW,
                summary="Demo data.",
            ),
        ),
    )
    evaluation = evaluate_structured_proposal(proposal)
    codes = [i.code for i in evaluation.issues]
    assert EvaluationIssueCode.missing_evidence in codes


# --------------------------------------------------------------------------- #
# Tool trace guardrail
# --------------------------------------------------------------------------- #


def test_missing_tool_trace_produces_issue() -> None:
    # Build a trace missing one required tool.
    from backend.app.models.agent import ToolCallRecord, ToolCallStatus

    incomplete_trace = tuple(
        ToolCallRecord(
            tool_name=name,
            status=ToolCallStatus.SUCCESS,
            input_summary="test",
            output_summary="test",
        )
        for name in (
            "cap_sheet_service.summarize_cap_sheet",
            "roster_need_service.evaluate_roster_needs",
            # Missing depth_chart_projector, free_agent_service,
            # trade_simulator.preview_signing, evidence_service.
        )
    )
    proposal = _make_proposal(tool_call_trace=incomplete_trace)
    evaluation = evaluate_structured_proposal(proposal)
    codes = [i.code for i in evaluation.issues]
    assert EvaluationIssueCode.missing_tool_trace in codes


# --------------------------------------------------------------------------- #
# Fallback consistency
# --------------------------------------------------------------------------- #


def test_no_action_with_hold_action_does_not_fail() -> None:
    hold_action = _make_action(
        action_type=ProposalActionType.HOLD,
        validation_status="NOT_VALIDATED",
        is_valid=False,
        transaction_id=None,
        player_id=None,
        player_name=None,
        position=None,
        salary=None,
        years=None,
        fit_score=None,
        matched_need=None,
        evidence_ids=(),
    )
    proposal = _make_proposal(
        status=ProposalStatus.NO_ACTION,
        recommended_actions=(hold_action,),
        risks=(
            ProposalRisk(
                code="no_matching_candidate",
                level=ProposalRiskLevel.HIGH,
                summary="No candidates.",
            ),
            ProposalRisk(
                code="sample_data",
                level=ProposalRiskLevel.LOW,
                summary="Demo data.",
            ),
        ),
    )
    evaluation = evaluate_structured_proposal(proposal)
    # Should not FAIL just because it's NO_ACTION with a HOLD action.
    assert evaluation.status is not EvaluationStatus.FAIL


def test_no_candidates_but_recommended_produces_fail() -> None:
    # RECOMMENDED with no actions at all.
    proposal = _make_proposal(
        status=ProposalStatus.RECOMMENDED,
        recommended_actions=(),
    )
    evaluation = evaluate_structured_proposal(proposal)
    assert evaluation.status is EvaluationStatus.FAIL
    codes = [i.code for i in evaluation.issues]
    assert EvaluationIssueCode.invalid_action_recommended in codes


# --------------------------------------------------------------------------- #
# Sample data
# --------------------------------------------------------------------------- #


def test_sample_data_true_produces_info_note() -> None:
    proposal = _make_proposal(sample_data=True)
    evaluation = evaluate_structured_proposal(proposal)
    sample_issues = [
        i for i in evaluation.issues if i.code is EvaluationIssueCode.sample_data_only
    ]
    assert len(sample_issues) >= 1
    assert all(i.severity is EvaluationSeverity.INFO for i in sample_issues)


def test_sample_data_false_produces_fail() -> None:
    proposal = _make_proposal(sample_data=False)
    evaluation = evaluate_structured_proposal(proposal)
    assert evaluation.status is EvaluationStatus.FAIL
    codes = [i.code for i in evaluation.issues]
    assert EvaluationIssueCode.sample_data_only in codes


# --------------------------------------------------------------------------- #
# No mutation of data files
# --------------------------------------------------------------------------- #


def test_evaluator_does_not_mutate_players_json() -> None:
    path = DATA_DIR / "players.json"
    before = path.read_bytes()
    proposal = _build_recommended_proposal()
    evaluate_structured_proposal(proposal)
    after = path.read_bytes()
    assert before == after


def test_evaluator_does_not_mutate_contracts_json() -> None:
    path = DATA_DIR / "contracts.json"
    before = path.read_bytes()
    proposal = _build_recommended_proposal()
    evaluate_structured_proposal(proposal)
    after = path.read_bytes()
    assert before == after


def test_evaluator_does_not_mutate_free_agents_json() -> None:
    path = DATA_DIR / "free_agents.json"
    before = path.read_bytes()
    proposal = _build_recommended_proposal()
    evaluate_structured_proposal(proposal)
    after = path.read_bytes()
    assert before == after


def test_evaluator_does_not_mutate_evidence_notes_json() -> None:
    path = DATA_DIR / "evidence_notes.json"
    before = path.read_bytes()
    proposal = _build_recommended_proposal()
    evaluate_structured_proposal(proposal)
    after = path.read_bytes()
    assert before == after


# --------------------------------------------------------------------------- #
# No LLM / MCP / rule engine / trade simulator
# --------------------------------------------------------------------------- #


def test_evaluator_does_not_call_llm_or_openai_api() -> None:
    from backend.app.services import proposal_evaluator as evaluator_mod

    for forbidden in ("openai", "llm", "anthropic", "chat_completion"):
        assert not hasattr(evaluator_mod, forbidden), (
            f"proposal_evaluator must not expose {forbidden!r}"
        )


def test_evaluator_does_not_use_mcp() -> None:
    from backend.app.services import proposal_evaluator as evaluator_mod

    for forbidden in ("mcp", "mcp_client", "mcp_server", "MCPClient"):
        assert not hasattr(evaluator_mod, forbidden), (
            f"proposal_evaluator must not expose {forbidden!r}"
        )


def test_evaluator_does_not_call_transaction_rule_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``evaluate_structured_proposal`` must not call
    ``transaction_rule_engine``. We monkeypatch the engine to raise
    and verify the evaluator still works on a pre-built proposal."""
    from backend.app.services import transaction_rule_engine as engine

    def _boom(*args, **kwargs):
        raise AssertionError(
            "proposal_evaluator must not call transaction_rule_engine"
        )

    monkeypatch.setattr(engine, "validate_transaction", _boom)
    monkeypatch.setattr(engine, "validate_signing", _boom)
    monkeypatch.setattr(engine, "validate_trade", _boom)

    proposal = _build_recommended_proposal()
    evaluation = evaluate_structured_proposal(proposal)
    assert isinstance(evaluation, ProposalEvaluation)


def test_evaluator_does_not_call_trade_simulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``evaluate_structured_proposal`` must not call
    ``trade_simulator``. We monkeypatch it to raise and verify the
    evaluator still works on a pre-built proposal."""
    from backend.app.services import trade_simulator as sim

    def _boom(*args, **kwargs):
        raise AssertionError("proposal_evaluator must not call trade_simulator")

    monkeypatch.setattr(sim, "preview_signing", _boom)
    monkeypatch.setattr(sim, "preview_trade", _boom)
    monkeypatch.setattr(sim, "preview_transaction", _boom)

    proposal = _build_recommended_proposal()
    evaluation = evaluate_structured_proposal(proposal)
    assert isinstance(evaluation, ProposalEvaluation)


# --------------------------------------------------------------------------- #
# Scenario runner
# --------------------------------------------------------------------------- #


def test_run_evaluation_scenario_returns_result() -> None:
    scenario = EvaluationScenario(
        scenario_id="test-scenario",
        description="Test scenario",
        goal=_atl_goal(),
        expected_statuses=("RECOMMENDED",),
        expected_min_actions=1,
        expected_risk_codes=("sample_data",),
    )
    result = run_evaluation_scenario(scenario, DATA_DIR)
    assert isinstance(result, EvaluationScenarioResult)
    assert result.scenario_id == "test-scenario"
    assert result.proposal is not None
    assert result.evaluation is not None


def test_run_default_evaluation_scenarios_returns_multiple_results() -> None:
    results = run_default_evaluation_scenarios(DATA_DIR)
    assert len(results) >= 3
    # Each result should be an EvaluationScenarioResult.
    for r in results:
        assert isinstance(r, EvaluationScenarioResult)


def test_default_scenarios_do_not_fail_unless_testing_failure() -> None:
    """All default scenarios should produce PASS or WARNING, not FAIL,
    because they're designed to test valid paths."""
    results = run_default_evaluation_scenarios(DATA_DIR)
    for r in results:
        # The scenario result status should not be FAIL for the default
        # scenarios (they're designed to test valid paths, not failures).
        assert r.status is not EvaluationStatus.FAIL, (
            f"Scenario {r.scenario_id} unexpectedly FAILED: "
            f"{[i.summary for i in r.evaluation.issues if i.severity is EvaluationSeverity.ERROR]}"
        )


def test_scenario_outputs_are_deterministic() -> None:
    r1 = run_default_evaluation_scenarios(DATA_DIR)
    r2 = run_default_evaluation_scenarios(DATA_DIR)
    assert r1 == r2


# --------------------------------------------------------------------------- #
# Immutability
# --------------------------------------------------------------------------- #


def test_proposal_evaluation_is_frozen() -> None:
    proposal = _build_recommended_proposal()
    evaluation = evaluate_structured_proposal(proposal)
    with pytest.raises(Exception):
        evaluation.status = EvaluationStatus.FAIL  # type: ignore[misc]
    with pytest.raises(Exception):
        evaluation.issues = ()  # type: ignore[misc]


def test_evaluation_issue_is_frozen() -> None:
    proposal = _build_recommended_proposal()
    evaluation = evaluate_structured_proposal(proposal)
    if not evaluation.issues:
        pytest.skip("no issues to test")
    issue = evaluation.issues[0]
    with pytest.raises(Exception):
        issue.severity = EvaluationSeverity.ERROR  # type: ignore[misc]
    with pytest.raises(Exception):
        issue.code = EvaluationIssueCode.missing_evidence  # type: ignore[misc]


def test_evaluation_scenario_result_is_frozen() -> None:
    results = run_default_evaluation_scenarios(DATA_DIR)
    result = results[0]
    with pytest.raises(Exception):
        result.status = EvaluationStatus.FAIL  # type: ignore[misc]
    with pytest.raises(Exception):
        result.scenario_id = "tampered"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Additional coverage
# --------------------------------------------------------------------------- #


def test_evaluation_passed_checks_populated() -> None:
    proposal = _build_recommended_proposal()
    evaluation = evaluate_structured_proposal(proposal)
    # A clean RECOMMENDED proposal should pass several checks.
    assert len(evaluation.passed_checks) > 0
    assert "human_approval_guardrail" in evaluation.passed_checks


def test_evaluation_limitations_document_mvp_scope() -> None:
    proposal = _build_recommended_proposal()
    evaluation = evaluate_structured_proposal(proposal)
    joined = " ".join(evaluation.limitations).lower()
    assert "m4-d" in joined
    assert "no llm" in joined
    assert "no mcp" in joined
    assert "does not approve" in joined


def test_no_action_fallback_without_hold_or_risk_produces_warning() -> None:
    # NO_ACTION with no HOLD action and no no_matching_candidate risk.
    proposal = _make_proposal(
        status=ProposalStatus.NO_ACTION,
        recommended_actions=(),
        risks=(
            ProposalRisk(
                code="sample_data",
                level=ProposalRiskLevel.LOW,
                summary="Demo data.",
            ),
        ),
    )
    evaluation = evaluate_structured_proposal(proposal)
    codes = [i.code for i in evaluation.issues]
    assert EvaluationIssueCode.no_action_fallback in codes


def test_fallback_reasons_without_risk_or_limitation_produces_warning() -> None:
    # fallback_reasons non-empty but no risks and no limitations.
    proposal = _make_proposal(
        fallback_reasons=("some fallback",),
        risks=(),
        limitations=(),
    )
    evaluation = evaluate_structured_proposal(proposal)
    codes = [i.code for i in evaluation.issues]
    assert EvaluationIssueCode.missing_risk_for_fallback in codes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
