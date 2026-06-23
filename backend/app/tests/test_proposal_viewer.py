"""Tests for the deterministic proposal_viewer (M5-A).

These tests verify that:

- ``format_proposal_brief`` returns a ``str``.
- The brief contains team_id / objective / proposal status / evaluation
  status.
- The brief contains recommended action player_name / position /
  validation_status.
- The brief contains evidence_id / evidence title.
- The brief contains tool_call_trace.
- The brief contains ``requires_human_approval=True``.
- The brief contains ``sample_data=True``.
- The NO_ACTION path shows HOLD / fallback / no_matching_candidate.
- ``build_demo_payload`` returns a stable structure.
- ``build_demo_brief`` runs the default DEM-ATL C scenario.
- Output is deterministic (same input -> same output).
- The viewer does not mutate any data file.
- The viewer does not call LLM / OpenAI API.
- The viewer does not use MCP.
- The viewer does not call external APIs.
- The viewer does not approve transactions.

Run tests:

    python -m pytest backend/app/tests/test_proposal_viewer.py
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.models.agent import OffseasonGoal
from backend.app.models.evaluation import (
    EvaluationIssue,
    EvaluationIssueCode,
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
from backend.app.services.proposal_evaluator import evaluate_structured_proposal
from backend.app.services.proposal_viewer import (
    build_demo_brief,
    build_demo_payload,
    format_proposal_brief,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


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


def _strict_budget_goal() -> OffseasonGoal:
    """A goal that produces NO_ACTION (fa-005 at 18M is filtered out)."""
    return OffseasonGoal(
        team_id="DEM-ATL",
        objective="Strict budget center search",
        target_positions=("C",),
        max_salary=15_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )


def _build_recommended_proposal_and_eval() -> tuple:
    """Build a real RECOMMENDED proposal + evaluation via the pipeline."""
    proposal = run_goal_and_build_proposal(_atl_goal(), DATA_DIR)
    evaluation = evaluate_structured_proposal(proposal)
    return proposal, evaluation


def _build_no_action_proposal_and_eval() -> tuple:
    """Build a NO_ACTION proposal + evaluation via the strict budget path."""
    proposal = run_goal_and_build_proposal(_strict_budget_goal(), DATA_DIR)
    evaluation = evaluate_structured_proposal(proposal)
    return proposal, evaluation


# --------------------------------------------------------------------------- #
# format_proposal_brief tests
# --------------------------------------------------------------------------- #


def test_format_proposal_brief_returns_str() -> None:
    """``format_proposal_brief`` must return a ``str``."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    brief = format_proposal_brief(proposal, evaluation)
    assert isinstance(brief, str)
    assert len(brief) > 0


def test_brief_contains_header_fields() -> None:
    """The brief must contain team_id / objective / proposal status /
    evaluation status."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    brief = format_proposal_brief(proposal, evaluation)
    assert proposal.team_id in brief
    assert proposal.objective in brief
    assert "proposal status" in brief.lower()
    assert "evaluation status" in brief.lower()
    assert proposal.status.value in brief
    assert evaluation.status.value in brief


def test_brief_contains_recommended_action_fields() -> None:
    """The brief must contain recommended action player_name / position /
    validation_status."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    brief = format_proposal_brief(proposal, evaluation)
    assert "Recommended Actions" in brief
    for action in proposal.recommended_actions:
        if action.player_name:
            assert action.player_name in brief
        if action.position:
            assert action.position in brief
        assert action.validation_status in brief
        assert action.action_id in brief


def test_brief_contains_evidence_refs() -> None:
    """The brief must contain evidence_id / evidence title."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    brief = format_proposal_brief(proposal, evaluation)
    assert "Evidence" in brief
    for ref in proposal.evidence_refs:
        assert ref.evidence_id in brief
        assert ref.title in brief


def test_brief_contains_tool_call_trace() -> None:
    """The brief must contain tool_call_trace entries."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    brief = format_proposal_brief(proposal, evaluation)
    assert "Tool Call Trace" in brief
    for call in proposal.tool_call_trace:
        assert call.tool_name in brief


def test_brief_contains_requires_human_approval_true() -> None:
    """The brief must contain ``requires_human_approval=True``."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    brief = format_proposal_brief(proposal, evaluation)
    assert "requires_human_approval" in brief
    assert "True" in brief


def test_brief_contains_sample_data_true() -> None:
    """The brief must contain ``sample_data=True``."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    brief = format_proposal_brief(proposal, evaluation)
    assert "sample_data" in brief
    assert "True" in brief


def test_brief_no_action_shows_hold_and_fallback() -> None:
    """The NO_ACTION path must show HOLD action / fallback reasons /
    no_matching_candidate risk."""
    proposal, evaluation = _build_no_action_proposal_and_eval()
    brief = format_proposal_brief(proposal, evaluation)
    assert "NO_ACTION" in brief or "NO_ACTION".lower() in brief.lower()
    # The proposal should have a HOLD action or a no_matching_candidate risk.
    has_hold = any(
        a.action_type is ProposalActionType.HOLD for a in proposal.recommended_actions
    )
    has_no_match_risk = any(
        r.code == "no_matching_candidate" for r in proposal.risks
    )
    assert has_hold or has_no_match_risk, (
        "NO_ACTION proposal must have a HOLD action or no_matching_candidate risk"
    )
    if has_hold:
        assert "HOLD" in brief
    if has_no_match_risk:
        assert "no_matching_candidate" in brief


def test_brief_contains_evaluation_summary() -> None:
    """The brief must contain the evaluation summary (status / issues
    count / passed_checks)."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    brief = format_proposal_brief(proposal, evaluation)
    assert "Evaluation" in brief
    assert evaluation.status.value in brief
    assert "issues count" in brief.lower()
    assert "passed_checks" in brief.lower()


def test_brief_contains_limitations() -> None:
    """The brief must contain limitations including the M5-A MVP notes."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    brief = format_proposal_brief(proposal, evaluation)
    assert "Limitations" in brief
    assert "No LLM call" in brief
    assert "No MCP" in brief
    assert "human approval" in brief.lower()


def test_brief_contains_fallback_reasons_section() -> None:
    """The brief must contain a Fallback Reasons section (even if empty)."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    brief = format_proposal_brief(proposal, evaluation)
    assert "Fallback Reasons" in brief


def test_format_proposal_brief_rejects_non_proposal() -> None:
    """``format_proposal_brief`` must reject non-StructuredProposal inputs."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    with pytest.raises(Exception):
        format_proposal_brief("not a proposal", evaluation)  # type: ignore[arg-type]
    with pytest.raises(Exception):
        format_proposal_brief(proposal, "not an evaluation")  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# build_demo_payload tests
# --------------------------------------------------------------------------- #


def test_build_demo_payload_returns_stable_structure() -> None:
    """``build_demo_payload`` must return a dict with the expected keys."""
    payload = build_demo_payload(_atl_goal(), DATA_DIR)
    assert isinstance(payload, dict)
    # Top-level keys.
    assert "proposal" in payload
    assert "evaluation" in payload
    assert "actions" in payload
    assert "evidence" in payload
    assert "tool_trace" in payload
    assert "limitations" in payload
    assert payload["requires_human_approval"] is True
    assert payload["sample_data"] is True
    # Proposal sub-keys.
    proposal = payload["proposal"]
    assert proposal["team_id"] == "DEM-ATL"
    assert proposal["status"] == "RECOMMENDED"
    assert "recommended_actions" in proposal
    assert "risks" in proposal
    assert "evidence_refs" in proposal
    assert "tool_call_trace" in proposal
    # Evaluation sub-keys.
    evaluation = payload["evaluation"]
    assert "status" in evaluation
    assert "issues" in evaluation
    assert "passed_checks" in evaluation
    # Actions shortcut.
    assert payload["actions"] == proposal["recommended_actions"]
    assert payload["evidence"] == proposal["evidence_refs"]
    assert payload["tool_trace"] == proposal["tool_call_trace"]


def test_build_demo_payload_actions_have_expected_fields() -> None:
    """Each action in the payload must have the expected fields."""
    payload = build_demo_payload(_atl_goal(), DATA_DIR)
    actions = payload["actions"]
    assert len(actions) > 0
    for action in actions:
        assert "action_id" in action
        assert "action_type" in action
        assert "validation_status" in action
        assert "is_valid" in action
        assert "requires_human_approval" in action
        assert action["requires_human_approval"] is True


def test_build_demo_payload_no_action_path() -> None:
    """The NO_ACTION path must produce a payload with a HOLD action or
    no_matching_candidate risk."""
    payload = build_demo_payload(_strict_budget_goal(), DATA_DIR)
    proposal = payload["proposal"]
    assert proposal["status"] in ("NO_ACTION", "PARTIAL")
    actions = payload["actions"]
    risks = proposal["risks"]
    has_hold = any(a["action_type"] == "HOLD" for a in actions)
    has_no_match_risk = any(r["code"] == "no_matching_candidate" for r in risks)
    assert has_hold or has_no_match_risk


# --------------------------------------------------------------------------- #
# build_demo_brief tests
# --------------------------------------------------------------------------- #


def test_build_demo_brief_runs_default_scenario() -> None:
    """``build_demo_brief`` must run the default DEM-ATL C scenario and
    return a non-empty string."""
    brief = build_demo_brief(_atl_goal(), DATA_DIR)
    assert isinstance(brief, str)
    assert "DEM-ATL" in brief
    assert "RECOMMENDED" in brief


def test_build_demo_brief_rejects_non_goal() -> None:
    """``build_demo_brief`` must reject non-OffseasonGoal inputs."""
    with pytest.raises(Exception):
        build_demo_brief("not a goal", DATA_DIR)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Determinism tests
# --------------------------------------------------------------------------- #


def test_format_proposal_brief_is_deterministic() -> None:
    """Same proposal + evaluation must produce the same brief."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    brief1 = format_proposal_brief(proposal, evaluation)
    brief2 = format_proposal_brief(proposal, evaluation)
    assert brief1 == brief2


def test_build_demo_brief_is_deterministic() -> None:
    """Same goal must produce the same brief across repeated calls."""
    brief1 = build_demo_brief(_atl_goal(), DATA_DIR)
    brief2 = build_demo_brief(_atl_goal(), DATA_DIR)
    assert brief1 == brief2


def test_build_demo_payload_is_deterministic() -> None:
    """Same goal must produce the same payload across repeated calls."""
    p1 = build_demo_payload(_atl_goal(), DATA_DIR)
    p2 = build_demo_payload(_atl_goal(), DATA_DIR)
    assert p1 == p2


# --------------------------------------------------------------------------- #
# No-mutation tests
# --------------------------------------------------------------------------- #


def test_viewer_does_not_mutate_players_json() -> None:
    """Running the viewer must not mutate ``data/players.json``."""
    path = DATA_DIR / "players.json"
    before = path.read_bytes()
    build_demo_brief(_atl_goal(), DATA_DIR)
    after = path.read_bytes()
    assert before == after


def test_viewer_does_not_mutate_contracts_json() -> None:
    """Running the viewer must not mutate ``data/contracts.json``."""
    path = DATA_DIR / "contracts.json"
    before = path.read_bytes()
    build_demo_brief(_atl_goal(), DATA_DIR)
    after = path.read_bytes()
    assert before == after


def test_viewer_does_not_mutate_free_agents_json() -> None:
    """Running the viewer must not mutate ``data/free_agents.json``."""
    path = DATA_DIR / "free_agents.json"
    before = path.read_bytes()
    build_demo_brief(_atl_goal(), DATA_DIR)
    after = path.read_bytes()
    assert before == after


def test_viewer_does_not_mutate_evidence_notes_json() -> None:
    """Running the viewer must not mutate ``data/evidence_notes.json``."""
    path = DATA_DIR / "evidence_notes.json"
    before = path.read_bytes()
    build_demo_brief(_atl_goal(), DATA_DIR)
    after = path.read_bytes()
    assert before == after


# --------------------------------------------------------------------------- #
# No LLM / MCP / external API tests
# --------------------------------------------------------------------------- #


def test_viewer_does_not_expose_llm_attributes() -> None:
    """The proposal_viewer module must not expose LLM client attributes."""
    from backend.app.services import proposal_viewer as viewer_mod

    for forbidden in (
        "mcp",
        "mcp_client",
        "mcp_server",
        "MCPClient",
        "openai",
        "llm",
        "anthropic",
        "chat_completion",
    ):
        assert not hasattr(viewer_mod, forbidden), (
            f"proposal_viewer must not expose {forbidden!r}"
        )


def test_viewer_does_not_call_llm_or_mcp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The viewer must not import or call any LLM / MCP client. We
    verify by asserting the module has no ``openai`` / ``anthropic`` /
    ``mcp`` attributes and that ``build_demo_brief`` still works."""
    from backend.app.services import proposal_viewer as viewer_mod

    for forbidden in ("openai", "anthropic", "mcp", "llm_client"):
        assert not hasattr(viewer_mod, forbidden)
    brief = build_demo_brief(_atl_goal(), DATA_DIR)
    assert isinstance(brief, str)


# --------------------------------------------------------------------------- #
# No transaction approval tests
# --------------------------------------------------------------------------- #


def test_viewer_does_not_approve_transactions() -> None:
    """The viewer must never mark a proposal or action as approved. It
    only formats existing data; it does not change the proposal's
    ``requires_human_approval`` invariant."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    brief = format_proposal_brief(proposal, evaluation)
    # The brief must not contain approval language.
    assert "approved" not in brief.lower()
    assert "approval granted" not in brief.lower()
    assert "transaction confirmed" not in brief.lower()
    # The proposal itself must still require human approval.
    assert proposal.requires_human_approval is True
    for action in proposal.recommended_actions:
        assert action.requires_human_approval is True


def test_viewer_does_not_change_proposal_status() -> None:
    """The viewer must not change the proposal's status. It only
    formats the existing proposal/evaluation."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    original_status = proposal.status
    format_proposal_brief(proposal, evaluation)
    assert proposal.status == original_status


def test_viewer_does_not_change_evaluation_status() -> None:
    """The viewer must not change the evaluation's status."""
    proposal, evaluation = _build_recommended_proposal_and_eval()
    original_status = evaluation.status
    format_proposal_brief(proposal, evaluation)
    assert evaluation.status == original_status


# --------------------------------------------------------------------------- #
# Synthetic proposal tests (covers edge cases without running the pipeline)
# --------------------------------------------------------------------------- #


def _make_synthetic_proposal(
    status: ProposalStatus = ProposalStatus.RECOMMENDED,
    actions: tuple | None = None,
    risks: tuple | None = None,
    evidence_refs: tuple | None = None,
    tool_call_trace: tuple | None = None,
    fallback_reasons: tuple = (),
) -> StructuredProposal:
    """Build a synthetic StructuredProposal for edge-case tests."""
    if actions is None:
        actions = (
            ProposalAction(
                action_id="act-0-syn",
                action_type=ProposalActionType.SIGNING,
                team_id="DEM-ATL",
                validation_status="PASS",
                is_valid=True,
                requires_human_approval=True,
                player_name="Demo Synthetic Player",
                position="C",
                salary=10_000_000,
                years=1,
                fit_score=0.75,
                matched_need="C: have 0, target 2",
                evidence_ids=("ev-001",),
            ),
        )
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
                title="Demo evidence note",
                source="Demo source",
                evidence_type="team",
                sample_data=True,
            ),
        )
    if tool_call_trace is None:
        from backend.app.models.agent import ToolCallRecord, ToolCallStatus

        tool_call_trace = (
            ToolCallRecord(
                tool_name="cap_sheet_service.summarize_cap_sheet",
                status=ToolCallStatus.SUCCESS,
                input_summary="team_id=DEM-ATL",
                output_summary="cap_space=66000000",
            ),
        )
    return StructuredProposal(
        proposal_id="prop-DEM-ATL-syn",
        team_id="DEM-ATL",
        objective="Synthetic test objective",
        status=status,
        recommended_actions=actions,
        risks=risks,
        evidence_refs=evidence_refs,
        tool_call_trace=tool_call_trace,
        cap_summary="total_salary=74M, cap_space=66M",
        roster_need_summary="roster_count=4, needs=[C:0/2(high)]",
        depth_chart_summary="C:None/high",
        fallback_reasons=fallback_reasons,
        limitations=("M5-A synthetic test.",),
        requires_human_approval=True,
        sample_data=True,
    )


def _make_synthetic_evaluation(
    status: EvaluationStatus = EvaluationStatus.PASS,
    issues: tuple | None = None,
) -> ProposalEvaluation:
    """Build a synthetic ProposalEvaluation for edge-case tests."""
    if issues is None:
        issues = (
            EvaluationIssue(
                code=EvaluationIssueCode.sample_data_only,
                severity=EvaluationSeverity.INFO,
                summary="Proposal is built from sample data.",
                remediation="Use real data source in production.",
            ),
        )
    return ProposalEvaluation(
        proposal_id="prop-DEM-ATL-syn",
        team_id="DEM-ATL",
        status=status,
        issues=issues,
        passed_checks=("human_approval", "validation", "tool_trace"),
        failed_checks=(),
        warnings=(),
        limitations=("M5-A deterministic viewer.",),
        sample_data=True,
    )


def test_format_proposal_brief_with_synthetic_proposal() -> None:
    """``format_proposal_brief`` must work with a synthetic proposal."""
    proposal = _make_synthetic_proposal()
    evaluation = _make_synthetic_evaluation()
    brief = format_proposal_brief(proposal, evaluation)
    assert isinstance(brief, str)
    assert "DEM-ATL" in brief
    assert "Synthetic test objective" in brief
    assert "Demo Synthetic Player" in brief
    assert "ev-001" in brief
    assert "Demo evidence note" in brief


def test_format_proposal_brief_no_evidence() -> None:
    """The brief must handle a proposal with no evidence refs."""
    proposal = _make_synthetic_proposal(evidence_refs=())
    evaluation = _make_synthetic_evaluation()
    brief = format_proposal_brief(proposal, evaluation)
    assert "no evidence refs" in brief.lower()


def test_format_proposal_brief_no_actions() -> None:
    """The brief must handle a proposal with no actions."""
    proposal = _make_synthetic_proposal(actions=())
    evaluation = _make_synthetic_evaluation()
    brief = format_proposal_brief(proposal, evaluation)
    assert "no actions" in brief.lower()


def test_format_proposal_brief_with_fallback_reasons() -> None:
    """The brief must show fallback reasons when present."""
    proposal = _make_synthetic_proposal(
        fallback_reasons=("No matching free-agent candidates.",)
    )
    evaluation = _make_synthetic_evaluation()
    brief = format_proposal_brief(proposal, evaluation)
    assert "No matching free-agent candidates." in brief


def test_format_proposal_brief_with_failed_evaluation() -> None:
    """The brief must show FAIL evaluation status and issues."""
    proposal = _make_synthetic_proposal()
    evaluation = _make_synthetic_evaluation(
        status=EvaluationStatus.FAIL,
        issues=(
            EvaluationIssue(
                code=EvaluationIssueCode.missing_human_approval,
                severity=EvaluationSeverity.ERROR,
                summary="Proposal missing requires_human_approval.",
                remediation="Set requires_human_approval=True.",
            ),
        ),
    )
    brief = format_proposal_brief(proposal, evaluation)
    assert "FAIL" in brief
    assert "missing_human_approval" in brief
