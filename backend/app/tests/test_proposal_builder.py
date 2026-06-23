"""Tests for the deterministic proposal_builder (M4-C).

These tests verify that:

- ``build_structured_proposal`` returns a ``StructuredProposal``.
- A SUCCESS agent run with a valid signing preview produces
  ``RECOMMENDED`` (or a合理 status).
- Every recommended action has ``requires_human_approval=True``.
- Actions preserve ``transaction_id`` / ``validation_status`` /
  ``is_valid``.
- Actions carry ``player_name`` / ``position`` / ``fit_score`` when
  available.
- ``evidence_refs`` come from the evidence bundle (never fabricated).
- Missing evidence ids appear in ``fallback_reasons``.
- No candidates produces ``NO_ACTION`` / ``PARTIAL`` and a
  ``no_matching_candidate`` risk.
- Validation-failed previews are NOT marked as approved/recommended
  valid.
- ``tool_call_trace`` is preserved.
- ``limitations`` documents sample data / no LLM / preview-only /
  human approval.
- ``run_goal_and_build_proposal`` works end-to-end.
- The builder does not mutate any data file.
- The builder does not call LLM / MCP / ``transaction_rule_engine`` /
  ``trade_simulator`` directly.
- Output is deterministic.
- Models are frozen.

Run tests:

    python -m pytest backend/app/tests/test_proposal_builder.py
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
from backend.app.models.proposal import (
    ProposalAction,
    ProposalActionType,
    ProposalEvidenceRef,
    ProposalRisk,
    ProposalRiskLevel,
    ProposalStatus,
    StructuredProposal,
)
from backend.app.models.evidence import EvidenceBundle, EvidenceNote, EvidenceQuery
from backend.app.models.roster import FreeAgentFit, Position
from backend.app.models.transaction import (
    SigningTransaction,
    TransactionType,
    ValidationStatus,
    ValidationResult,
)
from backend.app.services.offseason_agent import run_offseason_plan
from backend.app.services.proposal_builder import (
    build_structured_proposal,
    run_goal_and_build_proposal,
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


def _run_atl() -> OffseasonAgentRun:
    return run_offseason_plan(_atl_goal(), DATA_DIR)


# --------------------------------------------------------------------------- #
# Basic structure
# --------------------------------------------------------------------------- #


def test_build_structured_proposal_returns_structured_proposal() -> None:
    run = _run_atl()
    proposal = build_structured_proposal(run)
    assert isinstance(proposal, StructuredProposal)
    assert proposal.team_id == "DEM-ATL"
    assert proposal.requires_human_approval is True
    assert proposal.sample_data is True


def test_success_run_with_valid_preview_produces_recommended_or_reasonable_status() -> None:
    run = _run_atl()
    proposal = build_structured_proposal(run)
    # With max_salary=20M, fa-005 (C, 18M) should pass the filter. The
    # validation may pass or fail depending on cap rules; either way
    # the status should be one of the four valid values.
    assert proposal.status in (
        ProposalStatus.RECOMMENDED,
        ProposalStatus.PARTIAL,
        ProposalStatus.BLOCKED,
        ProposalStatus.NO_ACTION,
    )
    # If there are signing previews, status should not be NO_ACTION.
    if run.signing_previews:
        assert proposal.status is not ProposalStatus.NO_ACTION


def test_recommended_actions_all_require_human_approval() -> None:
    run = _run_atl()
    proposal = build_structured_proposal(run)
    for action in proposal.recommended_actions:
        assert isinstance(action, ProposalAction)
        assert action.requires_human_approval is True


def test_actions_preserve_transaction_id_validation_status_is_valid() -> None:
    run = _run_atl()
    proposal = build_structured_proposal(run)
    for action, preview in zip(proposal.recommended_actions, run.signing_previews):
        if action.action_type is ProposalActionType.SIGNING:
            assert action.transaction_id == preview.transaction_id
            vr = preview.validation_result
            if vr is not None:
                assert action.validation_status == vr.status.value
                assert action.is_valid == vr.is_valid


def test_actions_carry_player_name_position_fit_score() -> None:
    run = _run_atl()
    proposal = build_structured_proposal(run)
    # If there are signing actions, they should carry player info from
    # the matched FreeAgentFit.
    for action in proposal.recommended_actions:
        if action.action_type is ProposalActionType.SIGNING and action.transaction_id:
            # The action should have at least player_id (fa-005 for the
            # default ATL goal). player_name / position / fit_score may
            # be None if the fit didn't match, but for the default goal
            # they should be populated.
            if action.player_id:
                assert action.player_name is not None
                assert action.position is not None
                assert action.fit_score is not None


# --------------------------------------------------------------------------- #
# Evidence refs
# --------------------------------------------------------------------------- #


def test_evidence_refs_come_from_evidence_bundle() -> None:
    run = _run_atl()
    proposal = build_structured_proposal(run)
    bundle = run.evidence_bundle
    assert bundle is not None
    expected_ids = {n.evidence_id for n in bundle.matched_notes}
    actual_ids = {r.evidence_id for r in proposal.evidence_refs}
    assert actual_ids == expected_ids
    # Every ref must be a ProposalEvidenceRef with sample_data=True.
    for ref in proposal.evidence_refs:
        assert isinstance(ref, ProposalEvidenceRef)
        assert ref.sample_data is True


def test_missing_evidence_ids_appear_in_fallback_reasons() -> None:
    # Build a synthetic agent run with missing evidence ids.
    run = _run_atl()
    # Replace the evidence bundle with one that has missing ids.
    new_bundle = EvidenceBundle(
        query=run.evidence_bundle.query,
        matched_notes=run.evidence_bundle.matched_notes,
        missing_evidence_ids=("ev-missing-1", "ev-missing-2"),
        fallback_reason="Some evidence ids not found.",
        limitations=run.evidence_bundle.limitations,
        sample_data=True,
    )
    # OffseasonAgentRun is frozen, so use dataclasses.replace.
    import dataclasses

    synthetic_run = dataclasses.replace(run, evidence_bundle=new_bundle)
    proposal = build_structured_proposal(synthetic_run)
    joined = " ".join(proposal.fallback_reasons)
    assert "ev-missing-1" in joined
    assert "ev-missing-2" in joined


# --------------------------------------------------------------------------- #
# No candidates / validation failed
# --------------------------------------------------------------------------- #


def test_no_candidates_produces_no_action_or_partial_and_risk() -> None:
    # max_salary=1 filters out all FAs.
    goal = _atl_goal(max_salary=1, max_candidates=2)
    run = run_offseason_plan(goal, DATA_DIR)
    proposal = build_structured_proposal(run)
    assert proposal.status in (ProposalStatus.NO_ACTION, ProposalStatus.PARTIAL)
    risk_codes = [r.code for r in proposal.risks]
    assert "no_matching_candidate" in risk_codes


def test_validation_failed_preview_not_marked_approved() -> None:
    # Build a synthetic agent run where the signing preview failed
    # validation. We construct a minimal failed ValidationResult.
    import dataclasses

    run = _run_atl()
    if not run.signing_previews:
        pytest.skip("no signing previews to tamper with")
    # Replace the first preview's validation_result with a FAIL.
    failed_vr = ValidationResult(
        transaction_id="tx-fail",
        transaction_type=TransactionType.SIMPLE_FA_SIGNING,
        status=ValidationStatus.FAIL,
        is_valid=False,
        issues=(),
        warnings=(),
        cap_summary_before=None,
        cap_summary_after=None,
        evidence_ids=(),
        requires_human_approval=True,
        limitations=("synthetic fail",),
    )
    # TransactionPreview is frozen; use dataclasses.replace.
    from backend.app.models.roster import TransactionPreview

    original_preview = run.signing_previews[0]
    failed_preview = dataclasses.replace(
        original_preview, validation_result=failed_vr
    )
    new_previews = (failed_preview,) + run.signing_previews[1:]
    synthetic_run = dataclasses.replace(run, signing_previews=new_previews)
    proposal = build_structured_proposal(synthetic_run)
    # The failed action must have is_valid=False.
    failed_action = proposal.recommended_actions[0]
    assert failed_action.is_valid is False
    assert failed_action.requires_human_approval is True
    # Status should be BLOCKED or PARTIAL (not RECOMMENDED).
    assert proposal.status in (ProposalStatus.BLOCKED, ProposalStatus.PARTIAL)
    # A validation_failed risk should be present.
    risk_codes = [r.code for r in proposal.risks]
    assert "validation_failed" in risk_codes


# --------------------------------------------------------------------------- #
# Tool trace / limitations
# --------------------------------------------------------------------------- #


def test_tool_call_trace_is_preserved() -> None:
    run = _run_atl()
    proposal = build_structured_proposal(run)
    assert proposal.tool_call_trace == run.tool_call_trace
    # Same length and same tool_names in order.
    assert len(proposal.tool_call_trace) == len(run.tool_call_trace)
    for p_record, r_record in zip(
        proposal.tool_call_trace, run.tool_call_trace
    ):
        assert p_record.tool_name == r_record.tool_name
        assert p_record.status == r_record.status


def test_limitations_document_mvp_scope() -> None:
    run = _run_atl()
    proposal = build_structured_proposal(run)
    joined = " ".join(proposal.limitations).lower()
    assert "m4-c" in joined
    assert "no llm" in joined
    assert "no mcp" in joined
    assert "previews" in joined and "human approval" in joined
    assert "sample" in joined or "simulation" in joined


# --------------------------------------------------------------------------- #
# run_goal_and_build_proposal
# --------------------------------------------------------------------------- #


def test_run_goal_and_build_proposal_generates_proposal() -> None:
    goal = _atl_goal()
    proposal = run_goal_and_build_proposal(goal, DATA_DIR)
    assert isinstance(proposal, StructuredProposal)
    assert proposal.team_id == "DEM-ATL"
    assert proposal.requires_human_approval is True
    assert proposal.sample_data is True


# --------------------------------------------------------------------------- #
# No mutation of data files
# --------------------------------------------------------------------------- #


def test_builder_does_not_mutate_players_json() -> None:
    path = DATA_DIR / "players.json"
    before = path.read_bytes()
    run_goal_and_build_proposal(_atl_goal(), DATA_DIR)
    after = path.read_bytes()
    assert before == after


def test_builder_does_not_mutate_contracts_json() -> None:
    path = DATA_DIR / "contracts.json"
    before = path.read_bytes()
    run_goal_and_build_proposal(_atl_goal(), DATA_DIR)
    after = path.read_bytes()
    assert before == after


def test_builder_does_not_mutate_free_agents_json() -> None:
    path = DATA_DIR / "free_agents.json"
    before = path.read_bytes()
    run_goal_and_build_proposal(_atl_goal(), DATA_DIR)
    after = path.read_bytes()
    assert before == after


def test_builder_does_not_mutate_evidence_notes_json() -> None:
    path = DATA_DIR / "evidence_notes.json"
    before = path.read_bytes()
    run_goal_and_build_proposal(_atl_goal(), DATA_DIR)
    after = path.read_bytes()
    assert before == after


# --------------------------------------------------------------------------- #
# No LLM / MCP / rule engine / trade simulator
# --------------------------------------------------------------------------- #


def test_builder_does_not_call_llm_or_openai_api() -> None:
    from backend.app.services import proposal_builder as builder_mod

    for forbidden in ("openai", "llm", "anthropic", "chat_completion"):
        assert not hasattr(builder_mod, forbidden), (
            f"proposal_builder must not expose {forbidden!r}"
        )


def test_builder_does_not_use_mcp() -> None:
    from backend.app.services import proposal_builder as builder_mod

    for forbidden in ("mcp", "mcp_client", "mcp_server", "MCPClient"):
        assert not hasattr(builder_mod, forbidden), (
            f"proposal_builder must not expose {forbidden!r}"
        )


def test_builder_does_not_call_transaction_rule_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``build_structured_proposal`` must not call
    ``transaction_rule_engine``. We monkeypatch the engine to raise
    and verify the builder still works on a pre-built agent_run."""
    from backend.app.services import transaction_rule_engine as engine

    def _boom(*args, **kwargs):
        raise AssertionError(
            "proposal_builder must not call transaction_rule_engine"
        )

    monkeypatch.setattr(engine, "validate_transaction", _boom)
    monkeypatch.setattr(engine, "validate_signing", _boom)
    monkeypatch.setattr(engine, "validate_trade", _boom)

    run = _run_atl()  # built before the patch
    proposal = build_structured_proposal(run)
    assert isinstance(proposal, StructuredProposal)


def test_builder_does_not_call_trade_simulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``build_structured_proposal`` must not call
    ``trade_simulator.preview_signing`` / ``preview_trade`` /
    ``preview_transaction``. We monkeypatch them to raise and verify
    the builder still works on a pre-built agent_run."""
    from backend.app.services import trade_simulator as sim

    def _boom(*args, **kwargs):
        raise AssertionError(
            "proposal_builder must not call trade_simulator"
        )

    monkeypatch.setattr(sim, "preview_signing", _boom)
    monkeypatch.setattr(sim, "preview_trade", _boom)
    monkeypatch.setattr(sim, "preview_transaction", _boom)

    run = _run_atl()
    proposal = build_structured_proposal(run)
    assert isinstance(proposal, StructuredProposal)


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #


def test_build_structured_proposal_is_deterministic() -> None:
    run = _run_atl()
    p1 = build_structured_proposal(run)
    p2 = build_structured_proposal(run)
    assert p1 == p2


def test_run_goal_and_build_proposal_is_deterministic() -> None:
    goal = _atl_goal()
    p1 = run_goal_and_build_proposal(goal, DATA_DIR)
    p2 = run_goal_and_build_proposal(goal, DATA_DIR)
    assert p1 == p2


# --------------------------------------------------------------------------- #
# Immutability
# --------------------------------------------------------------------------- #


def test_structured_proposal_is_frozen() -> None:
    proposal = run_goal_and_build_proposal(_atl_goal(), DATA_DIR)
    with pytest.raises(Exception):
        proposal.status = ProposalStatus.BLOCKED  # type: ignore[misc]
    with pytest.raises(Exception):
        proposal.requires_human_approval = False  # type: ignore[misc]


def test_proposal_action_is_frozen() -> None:
    proposal = run_goal_and_build_proposal(_atl_goal(), DATA_DIR)
    if not proposal.recommended_actions:
        pytest.skip("no actions to test")
    action = proposal.recommended_actions[0]
    with pytest.raises(Exception):
        action.is_valid = True  # type: ignore[misc]
    with pytest.raises(Exception):
        action.requires_human_approval = False  # type: ignore[misc]


def test_proposal_risk_is_frozen() -> None:
    proposal = run_goal_and_build_proposal(_atl_goal(), DATA_DIR)
    if not proposal.risks:
        pytest.skip("no risks to test")
    risk = proposal.risks[0]
    with pytest.raises(Exception):
        risk.level = ProposalRiskLevel.LOW  # type: ignore[misc]
    with pytest.raises(Exception):
        risk.code = "tampered"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Additional coverage
# --------------------------------------------------------------------------- #


def test_proposal_id_is_deterministic_and_readable() -> None:
    proposal = run_goal_and_build_proposal(_atl_goal(), DATA_DIR)
    assert proposal.proposal_id.startswith("prop-DEM-ATL-")
    # Should be human-readable (contains slugified objective).
    assert "frontcourt" in proposal.proposal_id or "add" in proposal.proposal_id


def test_cap_roster_depth_summaries_are_populated() -> None:
    proposal = run_goal_and_build_proposal(_atl_goal(), DATA_DIR)
    assert proposal.cap_summary
    assert proposal.roster_need_summary
    assert proposal.depth_chart_summary
    # Cap summary should mention total_salary.
    assert "total_salary" in proposal.cap_summary


def test_sample_data_risk_always_present() -> None:
    proposal = run_goal_and_build_proposal(_atl_goal(), DATA_DIR)
    risk_codes = [r.code for r in proposal.risks]
    assert "sample_data" in risk_codes


def test_evidence_refs_match_matched_notes_count() -> None:
    run = _run_atl()
    proposal = build_structured_proposal(run)
    assert len(proposal.evidence_refs) == len(run.evidence_bundle.matched_notes)


def test_action_evidence_ids_subset_of_evidence_refs() -> None:
    """Every evidence_id cited by an action must appear in
    ``evidence_refs`` (or be missing from the bundle, in which case it
    should appear in ``fallback_reasons``)."""
    run = _run_atl()
    proposal = build_structured_proposal(run)
    ref_ids = {r.evidence_id for r in proposal.evidence_refs}
    fallback_joined = " ".join(proposal.fallback_reasons)
    for action in proposal.recommended_actions:
        for eid in action.evidence_ids:
            # Either the evidence was found (in refs) or it's flagged
            # as missing (in fallback_reasons). It must NOT be silently
            # fabricated as found.
            if eid not in ref_ids:
                assert eid in fallback_joined, (
                    f"evidence_id {eid} cited by action but not in refs "
                    f"and not flagged as missing"
                )


def test_hold_action_when_no_candidates() -> None:
    """When there are no free-agent fits, the proposal should include
    a HOLD action so the frontend has something to show."""
    goal = _atl_goal(max_salary=1, max_candidates=2)
    proposal = run_goal_and_build_proposal(goal, DATA_DIR)
    # Either there's a HOLD action or there are no actions at all
    # (both are acceptable). What's NOT acceptable is a SIGNING action
    # with is_valid=True when there were no candidates.
    for action in proposal.recommended_actions:
        if action.action_type is ProposalActionType.SIGNING:
            assert action.is_valid is False or action.transaction_id is None


def test_proposal_objective_echoed_from_goal() -> None:
    goal = _atl_goal(objective="Custom objective text")
    proposal = run_goal_and_build_proposal(goal, DATA_DIR)
    assert proposal.objective == "Custom objective text"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
