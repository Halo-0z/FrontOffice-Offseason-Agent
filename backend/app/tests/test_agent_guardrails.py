"""Tests for agent guardrails.

M2 scope: validate that the rule engine is the single source of truth
for transaction legality, and that no proposal can be treated as
approved without a ``ValidationResult``. The future agent (M4) must not
be able to bypass these checks.

M4 will add: agent-blocked-from-writing-roster / cap_sheet / contracts,
and structured-brief field validation. Those remain TODOs here.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.models.transaction import (
    IssueSeverity,
    SigningTransaction,
    TradeTransaction,
    TransactionAsset,
    TransactionType,
    ValidationStatus,
)
from backend.app.services.transaction_rule_engine import (
    validate_signing,
    validate_trade,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


@pytest.fixture(scope="module")
def client():
    """Module-scoped FastAPI TestClient for API-level guardrail tests."""
    from fastapi.testclient import TestClient
    from backend.app.api import app
    return TestClient(app)


def _minimum_signing(tx_id: str, salary: int = 1_000_000) -> SigningTransaction:
    return SigningTransaction(
        transaction_id=tx_id,
        transaction_type=TransactionType.MINIMUM_SIGNING,
        team_id="DEM-ATL",
        player_id="fa-001",
        salary=salary,
        years=1,
        evidence_ids=("ev-001",),
    )


def _asset(player_id: str, salary: int, frm: str, to: str) -> TransactionAsset:
    return TransactionAsset(
        player_id=player_id,
        salary=salary,
        from_team_id=frm,
        to_team_id=to,
    )


# --------------------------------------------------------------------------- #
# M2 guardrails
# --------------------------------------------------------------------------- #


def test_proposal_without_validation_result_cannot_be_approved() -> None:
    """A bare ``SigningTransaction`` carries no verdict. Callers must not
    treat a transaction object as approved without first obtaining a
    ``ValidationResult`` from the rule engine. We encode this invariant
    by asserting the transaction dataclass has no ``is_valid`` /
    ``status`` field — only ``ValidationResult`` does."""
    tx = _minimum_signing("tx-guard-1")
    assert not hasattr(tx, "is_valid"), "transaction must not carry its own verdict"
    assert not hasattr(tx, "status"), "transaction must not carry its own status"
    # Only the rule engine produces a verdict.
    result = validate_signing(tx, DATA_DIR)
    assert hasattr(result, "is_valid")
    assert hasattr(result, "status")


def test_validation_result_requires_human_approval_is_always_true() -> None:
    """Even a PASS result must require human approval in M2."""
    tx = _minimum_signing("tx-guard-2", salary=1_000_000)
    result = validate_signing(tx, DATA_DIR)
    assert result.requires_human_approval is True
    # And a FAIL also requires it.
    bad_tx = _minimum_signing("tx-guard-2-bad", salary=5_000_000)
    bad_result = validate_signing(bad_tx, DATA_DIR)
    assert bad_result.requires_human_approval is True


def test_failed_validation_must_not_be_treatable_as_approved() -> None:
    """When the rule engine FAILs, ``is_valid`` is False and ``status``
    is FAIL. No downstream code should be able to flip these without
    re-running the engine."""
    tx = _minimum_signing("tx-guard-3", salary=5_000_000)  # > minimum_salary
    result = validate_signing(tx, DATA_DIR)
    assert result.status is ValidationStatus.FAIL
    assert result.is_valid is False
    # Frozen dataclass: cannot mutate the verdict.
    with pytest.raises(Exception):
        result.is_valid = True  # type: ignore[misc]
    with pytest.raises(Exception):
        result.status = ValidationStatus.PASS  # type: ignore[misc]


def test_rule_engine_does_not_write_to_contracts_json() -> None:
    """The rule engine must not persist any state. A failed validation
    must not mutate ``data/contracts.json``."""
    contracts_path = DATA_DIR / "contracts.json"
    before = contracts_path.read_bytes()
    # Run a failing signing and a failing trade.
    validate_signing(_minimum_signing("tx-guard-4", salary=99_999_999), DATA_DIR)
    trade = TradeTransaction(
        transaction_id="tx-guard-4-trade",
        transaction_type=TransactionType.TWO_TEAM_TRADE,
        team_a_id="DEM-ATL",
        team_b_id="DEM-PDX",
        outgoing_from_a=(_asset("pl-001", 28_000_000, "DEM-ATL", "DEM-PDX"),),
        outgoing_from_b=(_asset("pl-005", 30_000_000, "DEM-PDX", "DEM-ATL"),),
        evidence_ids=(),
    )
    validate_trade(trade, DATA_DIR)
    after = contracts_path.read_bytes()
    assert before == after


# --------------------------------------------------------------------------- #
# M3-B guardrails: preview requires human approval; failed validation
# cannot be approved; free_agent_service cannot bypass rule engine.
# --------------------------------------------------------------------------- #


def test_preview_always_requires_human_approval() -> None:
    """Every ``TransactionPreview`` — pass or fail — must require human
    approval. The agent (M4) cannot bypass this."""
    from backend.app.services.trade_simulator import preview_signing

    # A passing preview.
    good = preview_signing(_minimum_signing("tx-m3b-good", salary=1_000_000), DATA_DIR)
    assert good.requires_human_approval is True
    # A failing preview.
    bad = preview_signing(_minimum_signing("tx-m3b-bad", salary=5_000_000), DATA_DIR)
    assert bad.requires_human_approval is True


def test_failed_validation_preview_cannot_be_treated_as_approved() -> None:
    """A failed ``TransactionPreview`` must have ``is_valid=False`` and
    no structured after-state. Downstream code must not be able to flip
    the verdict."""
    from backend.app.services.trade_simulator import preview_signing

    preview = preview_signing(_minimum_signing("tx-m3b-fail", salary=5_000_000), DATA_DIR)
    assert preview.validation_result.is_valid is False
    assert preview.roster_need_after is None
    assert preview.depth_chart_after is None
    # Frozen: cannot flip.
    with pytest.raises(Exception):
        preview.requires_human_approval = False  # type: ignore[misc]


def test_free_agent_service_cannot_bypass_rule_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``free_agent_service`` returns ``FreeAgentFit`` suggestions only —
    never an approved transaction. Patching the rule engine to raise
    must not affect free-agent matching, AND the matching output must
    not be a ``ValidationResult`` or carry an approval flag."""
    from backend.app.models.roster import FreeAgentFit
    from backend.app.services import transaction_rule_engine as engine
    from backend.app.services.free_agent_service import rank_free_agents_for_team

    def _boom(*args, **kwargs):
        raise AssertionError("free_agent_service must not call the rule engine")

    monkeypatch.setattr(engine, "validate_transaction", _boom)
    monkeypatch.setattr(engine, "validate_signing", _boom)
    monkeypatch.setattr(engine, "validate_trade", _boom)

    fits = rank_free_agents_for_team("DEM-ATL", DATA_DIR)
    assert len(fits) > 0
    for f in fits:
        assert isinstance(f, FreeAgentFit)
        # FreeAgentFit has no is_valid / status / approval field.
        assert not hasattr(f, "is_valid")
        assert not hasattr(f, "status")
        assert not hasattr(f, "requires_human_approval")


# --------------------------------------------------------------------------- #
# M4-A guardrails: evidence_service cannot fabricate notes, must mark
# sample_data=True, must not generate proposals, must not call the
# rule engine.
# --------------------------------------------------------------------------- #


def test_evidence_service_missing_evidence_does_not_fabricate_notes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When evidence ids are missing, evidence_service must return an
    empty (or partial) bundle with a clear fallback_reason — it must
    NEVER fabricate matched_notes."""
    from backend.app.services.evidence_service import get_evidence_by_ids

    bundle = get_evidence_by_ids(("ev-demo-missing-1", "ev-demo-missing-2"), DATA_DIR)
    assert bundle.matched_notes == ()
    assert bundle.missing_evidence_ids == (
        "ev-demo-missing-1",
        "ev-demo-missing-2",
    )
    assert bundle.fallback_reason is not None
    assert "No evidence found" in bundle.fallback_reason


def test_evidence_service_returns_sample_data_true() -> None:
    """Every returned note and bundle must be marked sample_data=True
    (these are demo notes, not real news)."""
    from backend.app.services.evidence_service import search_evidence

    bundle = search_evidence(team_id="DEM-ATL", limit=3, data_dir=DATA_DIR)
    assert bundle.sample_data is True
    for note in bundle.matched_notes:
        assert note.sample_data is True


def test_evidence_service_does_not_generate_transaction_proposal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """evidence_service must not produce transaction proposals. We
    verify by asserting the returned bundle has no proposal-shaped
    fields (no 'transaction', no 'proposal', no 'is_valid')."""
    from backend.app.models.evidence import EvidenceBundle
    from backend.app.services.evidence_service import search_evidence

    bundle = search_evidence(team_id="DEM-ATL", limit=3, data_dir=DATA_DIR)
    assert isinstance(bundle, EvidenceBundle)
    # EvidenceBundle must not carry proposal/transaction fields.
    for forbidden in ("transaction", "proposal", "is_valid", "validation_result"):
        assert not hasattr(bundle, forbidden), (
            f"EvidenceBundle must not carry {forbidden!r} field"
        )
    for note in bundle.matched_notes:
        for forbidden in ("transaction", "proposal", "is_valid", "validation_result"):
            assert not hasattr(note, forbidden), (
                f"EvidenceNote must not carry {forbidden!r} field"
            )


def test_evidence_service_does_not_call_transaction_rule_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """evidence_service must not call transaction_rule_engine. We
    monkeypatch the engine to raise and verify evidence retrieval still
    works."""
    from backend.app.services import transaction_rule_engine as engine
    from backend.app.services.evidence_service import (
        get_evidence_by_ids,
        search_evidence,
    )

    def _boom(*args, **kwargs):
        raise AssertionError(
            "evidence_service must not call transaction_rule_engine"
        )

    monkeypatch.setattr(engine, "validate_transaction", _boom)
    monkeypatch.setattr(engine, "validate_signing", _boom)
    monkeypatch.setattr(engine, "validate_trade", _boom)

    # Both retrieval paths must still work.
    b1 = get_evidence_by_ids(("ev-001",), DATA_DIR)
    assert len(b1.matched_notes) == 1
    b2 = search_evidence(team_id="DEM-ATL", limit=3, data_dir=DATA_DIR)
    assert len(b2.matched_notes) > 0


# --------------------------------------------------------------------------- #
# M4-B guardrails: the offseason_agent orchestrator must require human
# approval, must not bypass trade_simulator, must record a complete
# tool_call_trace, must not use MCP/LLM, and must not write data files.
# --------------------------------------------------------------------------- #


def _m4b_goal():
    from backend.app.models.agent import OffseasonGoal

    return OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )


def test_agent_run_requires_human_approval_is_true() -> None:
    """The ``OffseasonAgentRun`` must always have
    ``requires_human_approval=True`` — the orchestrator never approves
    anything."""
    from backend.app.services.offseason_agent import run_offseason_plan

    run = run_offseason_plan(_m4b_goal(), DATA_DIR)
    assert run.requires_human_approval is True


def test_agent_signing_previews_are_not_approved() -> None:
    """Every signing preview must have ``requires_human_approval=True``.
    Even when ``validation_result.is_valid`` is True, the preview is
    NOT an approval — it still requires human sign-off."""
    from backend.app.services.offseason_agent import run_offseason_plan

    run = run_offseason_plan(_m4b_goal(), DATA_DIR)
    for preview in run.signing_previews:
        assert preview.requires_human_approval is True
        # Even a valid preview is not "approved".
        vr = preview.validation_result
        if vr is not None and vr.is_valid:
            assert preview.requires_human_approval is True


def test_agent_does_not_bypass_trade_simulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The agent must route every signing preview through
    ``trade_simulator.preview_signing`` (which internally calls
    ``transaction_rule_engine.validate_transaction``). If we patch
    ``preview_signing`` to raise, the agent must record a FAILED trace
    entry — it must NOT silently produce an approved preview."""
    from backend.app.services import offseason_agent as agent_mod
    from backend.app.services.offseason_agent import run_offseason_plan

    def _boom(*args, **kwargs):
        raise AssertionError(
            "agent must call preview_signing; this patch should not be bypassed"
        )

    monkeypatch.setattr(agent_mod, "preview_signing", _boom)
    run = run_offseason_plan(_m4b_goal(), DATA_DIR)
    # The preview tool must appear in the trace with FAILED status.
    preview_traces = [
        c for c in run.tool_call_trace if "preview_signing" in c.tool_name
    ]
    assert len(preview_traces) > 0
    for c in preview_traces:
        assert c.status.value == "FAILED"


def test_agent_tool_trace_records_all_key_tools() -> None:
    """The ``tool_call_trace`` must include entries for all six key
    tools: cap_sheet, roster_need, depth_chart, free_agent,
    preview_signing, and evidence_service."""
    from backend.app.services.offseason_agent import run_offseason_plan

    run = run_offseason_plan(_m4b_goal(), DATA_DIR)
    tool_names = {c.tool_name for c in run.tool_call_trace}
    assert "cap_sheet_service.summarize_cap_sheet" in tool_names
    assert "roster_need_service.evaluate_roster_needs" in tool_names
    assert "depth_chart_projector.project_current_depth_chart" in tool_names
    assert "free_agent_service.rank_free_agents_for_team" in tool_names
    assert "trade_simulator.preview_signing" in tool_names
    assert "evidence_service.search_evidence" in tool_names


def test_agent_does_not_use_mcp_or_llm() -> None:
    """The offseason_agent module must not import or expose any MCP or
    LLM client attributes."""
    from backend.app.services import offseason_agent as agent_mod

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
        assert not hasattr(agent_mod, forbidden), (
            f"offseason_agent must not expose {forbidden!r}"
        )


def test_agent_does_not_write_data_files() -> None:
    """Running the agent must not mutate any of the four core data
    files."""
    from backend.app.services.offseason_agent import run_offseason_plan

    files = [
        DATA_DIR / "players.json",
        DATA_DIR / "contracts.json",
        DATA_DIR / "free_agents.json",
        DATA_DIR / "evidence_notes.json",
    ]
    before = {f: f.read_bytes() for f in files}
    run_offseason_plan(_m4b_goal(), DATA_DIR)
    after = {f: f.read_bytes() for f in files}
    for f in files:
        assert before[f] == after[f], f"agent must not mutate {f.name}"


# --------------------------------------------------------------------------- #
# M4-C guardrails: the proposal_builder must require human approval,
# must not mark previews as approved, must not bypass the agent_run to
# re-validate transactions, must only cite evidence from the bundle,
# must not use MCP/LLM, and must not write data files.
# --------------------------------------------------------------------------- #


def _m4c_goal():
    from backend.app.models.agent import OffseasonGoal

    return OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )


def test_proposal_requires_human_approval_is_true() -> None:
    """The ``StructuredProposal`` must always have
    ``requires_human_approval=True`` — the builder never approves
    anything."""
    from backend.app.services.proposal_builder import run_goal_and_build_proposal

    proposal = run_goal_and_build_proposal(_m4c_goal(), DATA_DIR)
    assert proposal.requires_human_approval is True


def test_proposal_actions_cannot_be_marked_approved_or_finalized() -> None:
    """Every ``ProposalAction`` must have ``requires_human_approval=True``.
    Even when ``is_valid=True``, the action is NOT approved/finalized."""
    from backend.app.services.proposal_builder import run_goal_and_build_proposal

    proposal = run_goal_and_build_proposal(_m4c_goal(), DATA_DIR)
    for action in proposal.recommended_actions:
        assert action.requires_human_approval is True
        # Even a valid action is not "approved".
        if action.is_valid:
            assert action.requires_human_approval is True


def test_proposal_builder_does_not_re_validate_transactions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``build_structured_proposal`` must NOT call
    ``transaction_rule_engine`` or ``trade_simulator`` to re-validate
    transactions. It only consumes the ``OffseasonAgentRun``. If we
    patch the engine/simulator to raise, the builder must still work
    on a pre-built run."""
    from backend.app.services import transaction_rule_engine as engine
    from backend.app.services import trade_simulator as sim
    from backend.app.services.offseason_agent import run_offseason_plan
    from backend.app.services.proposal_builder import build_structured_proposal

    def _boom_engine(*args, **kwargs):
        raise AssertionError(
            "proposal_builder must not call transaction_rule_engine"
        )

    def _boom_sim(*args, **kwargs):
        raise AssertionError("proposal_builder must not call trade_simulator")

    monkeypatch.setattr(engine, "validate_transaction", _boom_engine)
    monkeypatch.setattr(engine, "validate_signing", _boom_engine)
    monkeypatch.setattr(engine, "validate_trade", _boom_engine)
    monkeypatch.setattr(sim, "preview_signing", _boom_sim)
    monkeypatch.setattr(sim, "preview_trade", _boom_sim)
    monkeypatch.setattr(sim, "preview_transaction", _boom_sim)

    # Build the run BEFORE patching (so run_offseason_plan works), then
    # patch, then build the proposal. The builder must not call any of
    # the patched functions.
    run = run_offseason_plan(_m4c_goal(), DATA_DIR)
    monkeypatch.setattr(engine, "validate_transaction", _boom_engine)
    monkeypatch.setattr(sim, "preview_signing", _boom_sim)
    proposal = build_structured_proposal(run)
    assert proposal is not None


def test_proposal_evidence_refs_only_from_evidence_bundle() -> None:
    """Every ``ProposalEvidenceRef`` must correspond to a
    ``matched_notes`` entry in the agent run's evidence bundle. The
    builder must not fabricate evidence ids."""
    from backend.app.services.offseason_agent import run_offseason_plan
    from backend.app.services.proposal_builder import build_structured_proposal

    run = run_offseason_plan(_m4c_goal(), DATA_DIR)
    proposal = build_structured_proposal(run)
    bundle_note_ids = {n.evidence_id for n in run.evidence_bundle.matched_notes}
    ref_ids = {r.evidence_id for r in proposal.evidence_refs}
    assert ref_ids == bundle_note_ids
    # No ref should have an id that's not in the bundle.
    for ref in proposal.evidence_refs:
        assert ref.evidence_id in bundle_note_ids


def test_proposal_builder_does_not_use_mcp_or_llm() -> None:
    """The proposal_builder module must not import or expose any MCP or
    LLM client attributes."""
    from backend.app.services import proposal_builder as builder_mod

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
        assert not hasattr(builder_mod, forbidden), (
            f"proposal_builder must not expose {forbidden!r}"
        )


def test_proposal_builder_does_not_write_data_files() -> None:
    """Running the proposal builder must not mutate any of the four
    core data files."""
    from backend.app.services.proposal_builder import run_goal_and_build_proposal

    files = [
        DATA_DIR / "players.json",
        DATA_DIR / "contracts.json",
        DATA_DIR / "free_agents.json",
        DATA_DIR / "evidence_notes.json",
    ]
    before = {f: f.read_bytes() for f in files}
    run_goal_and_build_proposal(_m4c_goal(), DATA_DIR)
    after = {f: f.read_bytes() for f in files}
    for f in files:
        assert before[f] == after[f], f"proposal_builder must not mutate {f.name}"


# --------------------------------------------------------------------------- #
# M4-D guardrails: the proposal_evaluator must not approve transactions,
# must not change proposal status to approved, must not call LLM/MCP,
# must not write data files, and must FAIL proposals missing human
# approval.
# --------------------------------------------------------------------------- #


def _m4d_goal():
    from backend.app.models.agent import OffseasonGoal

    return OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )


def test_evaluator_does_not_approve_transactions() -> None:
    """The evaluator must never mark a proposal or action as approved.
    It only produces issues; it never changes the proposal's
    ``requires_human_approval`` invariant."""
    from backend.app.services.proposal_builder import run_goal_and_build_proposal
    from backend.app.services.proposal_evaluator import evaluate_structured_proposal

    proposal = run_goal_and_build_proposal(_m4d_goal(), DATA_DIR)
    evaluation = evaluate_structured_proposal(proposal)
    # The evaluation must not have any "approved" field or status.
    assert not hasattr(evaluation, "approved")
    assert not hasattr(evaluation, "is_approved")
    # The proposal itself must still require human approval.
    assert proposal.requires_human_approval is True
    for action in proposal.recommended_actions:
        assert action.requires_human_approval is True


def test_evaluator_does_not_change_proposal_status_to_approved() -> None:
    """The evaluator must not change the proposal's status. It returns
    a separate ``ProposalEvaluation`` with its own ``status`` (PASS /
    WARNING / FAIL) that is distinct from the proposal's
    ``ProposalStatus``."""
    from backend.app.models.evaluation import EvaluationStatus
    from backend.app.services.proposal_builder import run_goal_and_build_proposal
    from backend.app.services.proposal_evaluator import evaluate_structured_proposal

    proposal = run_goal_and_build_proposal(_m4d_goal(), DATA_DIR)
    original_proposal_status = proposal.status
    evaluation = evaluate_structured_proposal(proposal)
    # The proposal's status must be unchanged.
    assert proposal.status == original_proposal_status
    # The evaluation status must be one of PASS/WARNING/FAIL, NOT any
    # ProposalStatus value like RECOMMENDED.
    assert evaluation.status in (
        EvaluationStatus.PASS,
        EvaluationStatus.WARNING,
        EvaluationStatus.FAIL,
    )


def test_evaluator_does_not_use_mcp_or_llm() -> None:
    """The proposal_evaluator module must not import or expose any MCP
    or LLM client attributes."""
    from backend.app.services import proposal_evaluator as evaluator_mod

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
        assert not hasattr(evaluator_mod, forbidden), (
            f"proposal_evaluator must not expose {forbidden!r}"
        )


def test_evaluator_does_not_write_data_files() -> None:
    """Running the evaluator must not mutate any of the four core data
    files."""
    from backend.app.services.proposal_builder import run_goal_and_build_proposal
    from backend.app.services.proposal_evaluator import (
        run_default_evaluation_scenarios,
    )

    files = [
        DATA_DIR / "players.json",
        DATA_DIR / "contracts.json",
        DATA_DIR / "free_agents.json",
        DATA_DIR / "evidence_notes.json",
    ]
    before = {f: f.read_bytes() for f in files}
    # Run the full default scenario suite (which builds proposals and
    # evaluates them).
    run_default_evaluation_scenarios(DATA_DIR)
    after = {f: f.read_bytes() for f in files}
    for f in files:
        assert before[f] == after[f], f"proposal_evaluator must not mutate {f.name}"


def test_evaluator_fails_proposal_missing_human_approval() -> None:
    """A proposal missing ``requires_human_approval=True`` must produce
    a FAIL evaluation with a ``missing_human_approval`` issue."""
    import dataclasses

    from backend.app.models.evaluation import EvaluationIssueCode, EvaluationStatus
    from backend.app.models.proposal import (
        ProposalAction,
        ProposalActionType,
        ProposalRisk,
        ProposalRiskLevel,
        ProposalStatus,
        StructuredProposal,
    )
    from backend.app.services.proposal_evaluator import evaluate_structured_proposal

    # Build a synthetic proposal with requires_human_approval=False.
    bad_proposal = StructuredProposal(
        proposal_id="prop-bad",
        team_id="DEM-ATL",
        objective="Bad proposal",
        status=ProposalStatus.RECOMMENDED,
        recommended_actions=(
            ProposalAction(
                action_id="act-0-bad",
                action_type=ProposalActionType.SIGNING,
                team_id="DEM-ATL",
                validation_status="PASS",
                is_valid=True,
                requires_human_approval=True,
            ),
        ),
        risks=(
            ProposalRisk(
                code="sample_data",
                level=ProposalRiskLevel.LOW,
                summary="Demo.",
            ),
        ),
        evidence_refs=(),
        tool_call_trace=(),
        fallback_reasons=(),
        limitations=("M4-C MVP.",),
        requires_human_approval=False,  # BAD
        sample_data=True,
    )
    evaluation = evaluate_structured_proposal(bad_proposal)
    assert evaluation.status is EvaluationStatus.FAIL
    codes = [i.code for i in evaluation.issues]
    assert EvaluationIssueCode.missing_human_approval in codes


# --------------------------------------------------------------------------- #
# M5-A guardrails: the proposal_viewer / CLI demo must not approve
# transactions, must not call LLM/MCP, must not write data files, and
# the CLI demo output must mention human approval / sample data
# limitations.
# --------------------------------------------------------------------------- #


def _m5a_goal():
    from backend.app.models.agent import OffseasonGoal

    return OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )


def test_viewer_does_not_approve_transactions() -> None:
    """The proposal_viewer must never mark a proposal or action as
    approved. It only formats existing data; it never changes the
    proposal's ``requires_human_approval`` invariant."""
    from backend.app.services.proposal_builder import run_goal_and_build_proposal
    from backend.app.services.proposal_evaluator import evaluate_structured_proposal
    from backend.app.services.proposal_viewer import format_proposal_brief

    proposal = run_goal_and_build_proposal(_m5a_goal(), DATA_DIR)
    evaluation = evaluate_structured_proposal(proposal)
    brief = format_proposal_brief(proposal, evaluation)
    # The brief must not contain approval language.
    assert "approved" not in brief.lower()
    assert "approval granted" not in brief.lower()
    # The proposal itself must still require human approval.
    assert proposal.requires_human_approval is True
    for action in proposal.recommended_actions:
        assert action.requires_human_approval is True


def test_viewer_does_not_use_mcp_or_llm() -> None:
    """The proposal_viewer module must not import or expose any MCP or
    LLM client attributes."""
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


def test_viewer_does_not_write_data_files() -> None:
    """Running the viewer must not mutate any of the four core data
    files."""
    from backend.app.services.proposal_viewer import build_demo_brief

    files = [
        DATA_DIR / "players.json",
        DATA_DIR / "contracts.json",
        DATA_DIR / "free_agents.json",
        DATA_DIR / "evidence_notes.json",
    ]
    before = {f: f.read_bytes() for f in files}
    build_demo_brief(_m5a_goal(), DATA_DIR)
    after = {f: f.read_bytes() for f in files}
    for f in files:
        assert before[f] == after[f], f"proposal_viewer must not mutate {f.name}"


def test_cli_demo_does_not_write_data_files() -> None:
    """Running the CLI demo script must not mutate any of the four
    core data files."""
    import subprocess
    import sys

    script = REPO_ROOT / "backend" / "scripts" / "run_offseason_demo.py"
    files = [
        DATA_DIR / "players.json",
        DATA_DIR / "contracts.json",
        DATA_DIR / "free_agents.json",
        DATA_DIR / "evidence_notes.json",
    ]
    before = {f: f.read_bytes() for f in files}
    subprocess.run(
        [sys.executable, str(script)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    after = {f: f.read_bytes() for f in files}
    for f in files:
        assert before[f] == after[f], f"CLI demo must not mutate {f.name}"


def test_cli_demo_output_mentions_human_approval_and_sample_data() -> None:
    """The CLI demo text output must mention ``requires_human_approval``
    and ``sample_data`` so it is never mistaken for a real NBA
    prediction."""
    import subprocess
    import sys

    script = REPO_ROOT / "backend" / "scripts" / "run_offseason_demo.py"
    result = subprocess.run(
        [sys.executable, str(script), "--format", "text"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert "requires_human_approval" in result.stdout
    assert "sample_data" in result.stdout
    assert "True" in result.stdout
    # The output must also mention the MVP limitations.
    assert "No LLM call" in result.stdout
    assert "No MCP" in result.stdout


# --------------------------------------------------------------------------- #
# M8-E guardrails: agent_trace_builder must not call LLM/MCP, must not
# write data, must not mutate payload, must not re-validate transactions,
# and trace content must never claim execution.
# --------------------------------------------------------------------------- #


def test_agent_trace_builder_does_not_use_mcp_or_llm() -> None:
    """agent_trace_builder module must not import or expose any MCP or
    LLM client attributes."""
    from backend.app.services import agent_trace_builder as builder_mod

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
        assert not hasattr(builder_mod, forbidden), (
            f"agent_trace_builder must not expose {forbidden!r}"
        )


def test_agent_trace_builder_does_not_write_data_files() -> None:
    """Building proposal and trade traces must not mutate any core data
    files."""
    import copy

    from backend.app.services.agent_trace_builder import (
        build_proposal_agent_trace,
        build_trade_agent_trace,
    )
    from backend.app.services.proposal_viewer import build_demo_payload

    files = [
        DATA_DIR / "players.json",
        DATA_DIR / "contracts.json",
        DATA_DIR / "free_agents.json",
        DATA_DIR / "evidence_notes.json",
    ]
    before = {f: f.read_bytes() for f in files}

    from backend.app.models.agent import OffseasonGoal

    goal = OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )
    payload = build_demo_payload(goal, DATA_DIR)
    payload_snapshot = copy.deepcopy(payload)

    build_proposal_agent_trace(
        goal_team_id="DEM-ATL",
        goal_objective="Add frontcourt help",
        payload=payload,
    )

    import sys
    scripts_dir = REPO_ROOT / "backend" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from run_trade_preview_demo import build_trade_preview_payload  # type: ignore

    trade_payload = build_trade_preview_payload(DATA_DIR)
    trade_payload_snapshot = copy.deepcopy(trade_payload)
    build_trade_agent_trace(trade_payload)

    after = {f: f.read_bytes() for f in files}
    for f in files:
        assert before[f] == after[f], (
            f"agent_trace_builder must not mutate {f.name}"
        )
    # Also verify the input payload dicts were not mutated.
    assert payload == payload_snapshot, "build_proposal_agent_trace must not mutate input payload"
    assert trade_payload == trade_payload_snapshot, "build_trade_agent_trace must not mutate input payload"


def test_agent_trace_builder_does_not_call_rule_engine_or_simulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """agent_trace_builder must NOT call transaction_rule_engine or
    trade_simulator to re-validate transactions. It only reads the
    already-serialized payload. Patching those to raise must not affect
    trace building."""
    from backend.app.services import agent_trace_builder as builder_mod
    from backend.app.services import trade_simulator as sim
    from backend.app.services import transaction_rule_engine as engine
    from backend.app.services.proposal_viewer import build_demo_payload
    from backend.app.models.agent import OffseasonGoal

    def _boom(*args, **kwargs):
        raise AssertionError(
            "agent_trace_builder must not call validation/simulation tools"
        )

    monkeypatch.setattr(engine, "validate_transaction", _boom)
    monkeypatch.setattr(engine, "validate_signing", _boom)
    monkeypatch.setattr(engine, "validate_trade", _boom)
    monkeypatch.setattr(sim, "preview_signing", _boom)
    monkeypatch.setattr(sim, "preview_trade", _boom)
    monkeypatch.setattr(sim, "preview_transaction", _boom)

    goal = OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )
    payload = build_demo_payload(goal, DATA_DIR)
    trace = builder_mod.build_proposal_agent_trace(
        goal_team_id="DEM-ATL",
        goal_objective="Add frontcourt help",
        payload=payload,
    )
    assert trace is not None
    assert trace["requires_human_approval"] is True
    assert len(trace["steps"]) == 8


def test_agent_trace_proposal_eight_steps_contracted_order() -> None:
    """Proposal agent_trace must have exactly 8 steps in the contracted
    order with correct tool_names."""
    from backend.app.services.agent_trace_builder import build_proposal_agent_trace
    from backend.app.services.proposal_viewer import build_demo_payload
    from backend.app.models.agent import OffseasonGoal

    expected_tool_names = [
        "load_active_data_source",
        "inspect_team_context",
        "find_candidate_players",
        "simulate_signing",
        "validate_salary_rules",
        "validate_roster_balance",
        "collect_evidence",
        "request_human_approval",
    ]

    goal = OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )
    payload = build_demo_payload(goal, DATA_DIR)
    trace = build_proposal_agent_trace(
        goal_team_id="DEM-ATL",
        goal_objective="Add frontcourt help",
        payload=payload,
    )
    steps = trace["steps"]
    assert len(steps) == 8
    actual_tool_names = [s["tool_name"] for s in steps]
    assert actual_tool_names == expected_tool_names
    # sequence must be 1..8
    for i, s in enumerate(steps):
        assert s["sequence"] == i + 1


def test_agent_trace_trade_eight_steps_contracted_order() -> None:
    """Trade agent_trace must have exactly 8 steps in the contracted
    order with correct tool_names."""
    import sys

    scripts_dir = REPO_ROOT / "backend" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from run_trade_preview_demo import build_trade_preview_payload  # type: ignore
    from backend.app.services.agent_trace_builder import build_trade_agent_trace

    expected_tool_names = [
        "load_active_data_source",
        "inspect_team_context",
        "find_candidate_players",
        "simulate_trade",
        "validate_salary_rules",
        "validate_roster_balance",
        "collect_evidence",
        "request_human_approval",
    ]

    payload = build_trade_preview_payload(DATA_DIR)
    trace = build_trade_agent_trace(payload)
    steps = trace["steps"]
    assert len(steps) == 8
    actual_tool_names = [s["tool_name"] for s in steps]
    assert actual_tool_names == expected_tool_names
    for i, s in enumerate(steps):
        assert s["sequence"] == i + 1


def test_agent_trace_final_message_always_read_only_disclaimer() -> None:
    """final_message must always be the fixed read-only disclaimer
    containing '这是只读预览，不会自动执行。'."""
    from backend.app.services.agent_trace_builder import (
        build_proposal_agent_trace,
        build_trade_agent_trace,
        FINAL_MESSAGE_READ_ONLY,
    )
    from backend.app.services.proposal_viewer import build_demo_payload
    from backend.app.models.agent import OffseasonGoal

    # Signing path
    goal = OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )
    payload = build_demo_payload(goal, DATA_DIR)
    trace = build_proposal_agent_trace(
        goal_team_id="DEM-ATL",
        goal_objective="Add frontcourt help",
        payload=payload,
    )
    assert trace["final_message"] == FINAL_MESSAGE_READ_ONLY
    assert "只读预览" in trace["final_message"]
    assert "不会自动执行" in trace["final_message"]

    # Hold path (strict budget)
    goal_hold = OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=15_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )
    payload_hold = build_demo_payload(goal_hold, DATA_DIR)
    trace_hold = build_proposal_agent_trace(
        goal_team_id="DEM-ATL",
        goal_objective="Add frontcourt help",
        payload=payload_hold,
    )
    assert trace_hold["final_message"] == FINAL_MESSAGE_READ_ONLY

    # Trade path
    import sys
    scripts_dir = REPO_ROOT / "backend" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from run_trade_preview_demo import build_trade_preview_payload  # type: ignore

    trade_payload = build_trade_preview_payload(DATA_DIR)
    trace_trade = build_trade_agent_trace(trade_payload)
    assert trace_trade["final_message"] == FINAL_MESSAGE_READ_ONLY


def test_agent_trace_requires_human_approval_always_true() -> None:
    """agent_trace.requires_human_approval must be True for signing,
    hold, and trade paths."""
    from backend.app.services.agent_trace_builder import (
        build_proposal_agent_trace,
        build_trade_agent_trace,
    )
    from backend.app.services.proposal_viewer import build_demo_payload
    from backend.app.models.agent import OffseasonGoal

    # Signing (RECOMMENDED)
    goal = OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )
    payload = build_demo_payload(goal, DATA_DIR)
    trace = build_proposal_agent_trace(
        goal_team_id="DEM-ATL",
        goal_objective="Add frontcourt help",
        payload=payload,
    )
    assert trace["requires_human_approval"] is True

    # Hold (NO_ACTION)
    goal_hold = OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=15_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )
    payload_hold = build_demo_payload(goal_hold, DATA_DIR)
    trace_hold = build_proposal_agent_trace(
        goal_team_id="DEM-ATL",
        goal_objective="Add frontcourt help",
        payload=payload_hold,
    )
    assert trace_hold["requires_human_approval"] is True

    # Trade
    import sys
    scripts_dir = REPO_ROOT / "backend" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from run_trade_preview_demo import build_trade_preview_payload  # type: ignore

    trade_payload = build_trade_preview_payload(DATA_DIR)
    trace_trade = build_trade_agent_trace(trade_payload)
    assert trace_trade["requires_human_approval"] is True


def test_agent_trace_approval_state_never_executes() -> None:
    """approval_state must never be an execution state like
    'executed', 'applied', or 'committed'."""
    from backend.app.services.agent_trace_builder import (
        build_proposal_agent_trace,
        build_trade_agent_trace,
    )
    from backend.app.services.proposal_viewer import build_demo_payload
    from backend.app.models.agent import OffseasonGoal

    forbidden_states = {"executed", "applied", "committed", "completed_execution"}
    allowed_states = {"required", "approved_preview", "blocked", "not_required"}

    goal = OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )
    payload = build_demo_payload(goal, DATA_DIR)
    trace = build_proposal_agent_trace(
        goal_team_id="DEM-ATL",
        goal_objective="Add frontcourt help",
        payload=payload,
    )
    assert trace["approval_state"] not in forbidden_states
    assert trace["approval_state"] in allowed_states

    import sys
    scripts_dir = REPO_ROOT / "backend" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from run_trade_preview_demo import build_trade_preview_payload  # type: ignore

    trade_payload = build_trade_preview_payload(DATA_DIR)
    trace_trade = build_trade_agent_trace(trade_payload)
    assert trace_trade["approval_state"] not in forbidden_states
    assert trace_trade["approval_state"] in allowed_states


def test_agent_trace_human_approval_step_requires_review() -> None:
    """Step 8 (request_human_approval) must have
    requires_human_review=True for both proposal and trade traces."""
    from backend.app.services.agent_trace_builder import (
        build_proposal_agent_trace,
        build_trade_agent_trace,
    )
    from backend.app.services.proposal_viewer import build_demo_payload
    from backend.app.models.agent import OffseasonGoal

    goal = OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )
    payload = build_demo_payload(goal, DATA_DIR)
    trace = build_proposal_agent_trace(
        goal_team_id="DEM-ATL",
        goal_objective="Add frontcourt help",
        payload=payload,
    )
    approval_step = trace["steps"][-1]
    assert approval_step["tool_name"] == "request_human_approval"
    assert approval_step["requires_human_review"] is True

    import sys
    scripts_dir = REPO_ROOT / "backend" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from run_trade_preview_demo import build_trade_preview_payload  # type: ignore

    trade_payload = build_trade_preview_payload(DATA_DIR)
    trace_trade = build_trade_agent_trace(trade_payload)
    trade_approval_step = trace_trade["steps"][-1]
    assert trade_approval_step["tool_name"] == "request_human_approval"
    assert trade_approval_step["requires_human_review"] is True


def test_agent_trace_no_step_claims_execution() -> None:
    """No step in proposal or trade trace may contain executed/applied/
    committed flags in technical_details or anywhere else."""
    from backend.app.services.agent_trace_builder import (
        build_proposal_agent_trace,
        build_trade_agent_trace,
    )
    from backend.app.services.proposal_viewer import build_demo_payload
    from backend.app.models.agent import OffseasonGoal

    forbidden_keys = {"executed", "applied", "committed", "apply_transaction", "mutation_performed"}
    allowed_true_flags = {
        "is_valid", "passed", "requires_human_approval",
        "requires_human_review", "sample_data",
        "team_a_passed", "team_b_passed",
    }

    goal = OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )
    payload = build_demo_payload(goal, DATA_DIR)
    trace = build_proposal_agent_trace(
        goal_team_id="DEM-ATL",
        goal_objective="Add frontcourt help",
        payload=payload,
    )

    def _check_no_execution(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                assert k not in forbidden_keys, (
                    f"forbidden key {k!r} in trace at {path}"
                )
                if isinstance(v, bool):
                    assert k in allowed_true_flags or v is not True, (
                        f"suspicious True flag at {path}.{k}"
                    )
                _check_no_execution(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                _check_no_execution(item, f"{path}[{i}]")
        elif isinstance(obj, str):
            lower = obj.lower()
            for term in ("transaction executed", "trade executed", "signing executed",
                         "committed to roster", "applied to cap"):
                assert term not in lower, f"execution language in trace text at {path}: {obj!r}"

    _check_no_execution(trace)

    import sys
    scripts_dir = REPO_ROOT / "backend" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from run_trade_preview_demo import build_trade_preview_payload  # type: ignore

    trade_payload = build_trade_preview_payload(DATA_DIR)
    trace_trade = build_trade_agent_trace(trade_payload)
    _check_no_execution(trace_trade)


def test_agent_trace_salary_step_status_strictly_from_verdict() -> None:
    """The validate_salary_rules step status must be strictly derived
    from the deterministic validation verdict. For the demo signing
    (PASS) it must be 'completed'; for the demo trade (PASS) it must
    be 'completed'."""
    from backend.app.services.agent_trace_builder import (
        build_proposal_agent_trace,
        build_trade_agent_trace,
    )
    from backend.app.services.proposal_viewer import build_demo_payload
    from backend.app.models.agent import OffseasonGoal

    goal = OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )
    payload = build_demo_payload(goal, DATA_DIR)
    trace = build_proposal_agent_trace(
        goal_team_id="DEM-ATL",
        goal_objective="Add frontcourt help",
        payload=payload,
    )
    salary_step = next(s for s in trace["steps"] if s["tool_name"] == "validate_salary_rules")
    primary_action = payload["actions"][0]
    vstatus = primary_action["validation_status"]
    if vstatus == "PASS":
        assert salary_step["status"] == "completed"
    elif vstatus == "FAIL":
        assert salary_step["status"] == "blocked"
    else:
        assert salary_step["status"] in ("completed", "warning", "blocked")
    # technical_details must echo the verdict; builder must not invent it
    assert salary_step["technical_details"]["validation_status"] == vstatus
    assert salary_step["technical_details"]["is_valid"] == primary_action["is_valid"]


def test_agent_trace_steps_all_have_technical_details_field() -> None:
    """Every step must include a technical_details dict so the frontend
    can render the collapsible section."""
    from backend.app.services.agent_trace_builder import (
        build_proposal_agent_trace,
        build_trade_agent_trace,
    )
    from backend.app.services.proposal_viewer import build_demo_payload
    from backend.app.models.agent import OffseasonGoal

    goal = OffseasonGoal(
        team_id="DEM-ATL",
        objective="Add frontcourt help",
        target_positions=("C",),
        max_salary=20_000_000,
        max_candidates=2,
        evidence_query="center need cap flexibility",
    )
    payload = build_demo_payload(goal, DATA_DIR)
    trace = build_proposal_agent_trace(
        goal_team_id="DEM-ATL",
        goal_objective="Add frontcourt help",
        payload=payload,
    )
    for s in trace["steps"]:
        assert "technical_details" in s
        assert isinstance(s["technical_details"], dict)

    import sys
    scripts_dir = REPO_ROOT / "backend" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from run_trade_preview_demo import build_trade_preview_payload  # type: ignore

    trade_payload = build_trade_preview_payload(DATA_DIR)
    trace_trade = build_trade_agent_trace(trade_payload)
    for s in trace_trade["steps"]:
        assert "technical_details" in s
        assert isinstance(s["technical_details"], dict)


def test_agent_trace_plain_language_summary_no_raw_snapshot_id() -> None:
    """plain_language_summary must not contain raw long snapshot_id
    strings like 'sourcepack' or 'nba_2025_26'."""
    import os
    from backend.app.services.agent_trace_builder import build_proposal_agent_trace
    from backend.app.services.proposal_viewer import build_demo_payload
    from backend.app.models.agent import OffseasonGoal

    # Run in demo mode (no snapshot set); plain text must stay clean.
    old_env = {k: os.environ.get(k) for k in ("DATA_MODE", "DATA_SNAPSHOT_ID", "DATA_ROOT")}
    for k in old_env:
        os.environ.pop(k, None)
    try:
        goal = OffseasonGoal(
            team_id="DEM-ATL",
            objective="Add frontcourt help",
            target_positions=("C",),
            max_salary=20_000_000,
            max_candidates=2,
            evidence_query="center need cap flexibility",
        )
        payload = build_demo_payload(goal, DATA_DIR)
        trace = build_proposal_agent_trace(
            goal_team_id="DEM-ATL",
            goal_objective="Add frontcourt help",
            payload=payload,
        )
        for s in trace["steps"]:
            summary = s["plain_language_summary"]
            assert "sourcepack" not in summary.lower()
            assert "nba_2025_26" not in summary.lower()
            assert len(summary) < 200, "plain_language_summary must stay concise"
    finally:
        for k, v in old_env.items():
            if v is not None:
                os.environ[k] = v


# --------------------------------------------------------------------------- #
# M8-E API guardrails: no execution endpoints; payloads must not advertise
# execution; backward compatibility preserved.
# --------------------------------------------------------------------------- #


def test_api_has_no_execution_endpoints() -> None:
    """The FastAPI app must not expose any /execute /apply /commit
    endpoints that could be misinterpreted as performing real
    transactions."""
    from backend.app.api import app

    routes = {r.path for r in app.routes}
    forbidden_prefixes = ("/execute", "/apply", "/commit", "/mutate", "/write")
    for path in routes:
        for prefix in forbidden_prefixes:
            assert not path.startswith(prefix), (
                f"API must not expose execution endpoint: {path}"
            )
    # The two preview endpoints must exist (read-only).
    assert "/api/offseason/proposal-preview" in routes
    assert "/api/offseason/trade-preview-demo" in routes
    assert "/api/health" in routes


def test_api_proposal_preview_response_has_no_executed_flag(client) -> None:
    """proposal-preview response body must not have executed/applied/
    committed at the top level or nested."""
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
    forbidden_top = {"executed", "applied", "committed", "transaction_applied"}
    for k in forbidden_top:
        assert k not in body, f"top-level key {k!r} must not exist"
    # The response must still carry requires_human_approval=true.
    assert body["requires_human_approval"] is True


def test_api_trade_preview_response_has_no_executed_flag(client) -> None:
    """trade-preview-demo response body must not have executed/applied/
    committed at the top level."""
    resp = client.get("/api/offseason/trade-preview-demo")
    assert resp.status_code == 200
    body = resp.json()
    forbidden_top = {"executed", "applied", "committed", "trade_executed"}
    for k in forbidden_top:
        assert k not in body, f"top-level key {k!r} must not exist"
    assert body["requires_human_approval"] is True


def test_api_trace_intent_type_is_contractual(client) -> None:
    """agent_trace.intent_type must be one of signing/trade/hold/compare
    — never 'execute' or similar."""
    allowed_intents = {"signing", "trade", "hold", "compare"}

    # Signing path
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
    assert resp.json()["agent_trace"]["intent_type"] in allowed_intents

    # Hold path
    resp2 = client.post(
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
    assert resp2.json()["agent_trace"]["intent_type"] in allowed_intents

    # Trade path
    resp3 = client.get("/api/offseason/trade-preview-demo")
    assert resp3.json()["agent_trace"]["intent_type"] in allowed_intents


def test_api_trace_overall_status_contractual(client) -> None:
    """agent_trace.overall_status must be one of the contracted values
    (completed/warning/blocked/awaiting_human_approval) — never
    'executed' or 'approved_final'."""
    allowed_overall = {"completed", "warning", "blocked", "awaiting_human_approval"}

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
    assert resp.json()["agent_trace"]["overall_status"] in allowed_overall

    resp2 = client.get("/api/offseason/trade-preview-demo")
    assert resp2.json()["agent_trace"]["overall_status"] in allowed_overall


def test_api_agent_trace_model_frozen_does_not_leak_verdict_mutability() -> None:
    """AgentTrace and AgentTraceStep are frozen dataclasses; downstream
    code cannot flip a 'blocked' to 'completed' or mutate the
    read-only message."""
    from backend.app.models.agent_trace import (
        AgentTrace,
        AgentTraceStep,
        ApprovalState,
        FINAL_MESSAGE_READ_ONLY,
        TraceIntentType,
        TraceOverallStatus,
        TraceStepStatus,
    )

    step = AgentTraceStep(
        step_id="s1",
        sequence=1,
        status=TraceStepStatus.BLOCKED.value,
        title="blocked",
        plain_language_summary="blocked by salary",
        tool_name="validate_salary_rules",
    )
    with pytest.raises(Exception):
        step.status = TraceStepStatus.COMPLETED.value  # type: ignore[misc]

    trace = AgentTrace(
        run_id="r1",
        intent_type=TraceIntentType.SIGNING.value,
        overall_status=TraceOverallStatus.AWAITING_HUMAN_APPROVAL.value,
        current_state="awaiting_human_approval",
        data_source_label="demo",
        steps=[step],
        requires_human_approval=True,
        approval_state=ApprovalState.REQUIRED.value,
        final_message=FINAL_MESSAGE_READ_ONLY,
    )
    with pytest.raises(Exception):
        trace.requires_human_approval = False  # type: ignore[misc]
    with pytest.raises(Exception):
        trace.final_message = "executed"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# M9-A guardrails: Agent Intelligence Summary adapter
#
# The deterministic fake adapter must:
# - never import LLM / network / scraping libraries
# - never call deterministic engines (rule_engine / trade_simulator /
#   snapshot_loader) — it only reads already-built payloads
# - never expose execute/apply/commit/mutate semantics in its output
# - never claim live/real-time/current data
# - never leak technical IDs into the natural-language summary
# - be a frozen dataclass (immutable after construction)
# --------------------------------------------------------------------------- #


_M9A_FORBIDDEN_MODULE_IMPORTS = [
    "openai",
    "anthropic",
    "mcp",
    "requests",
    "httpx",
    "aiohttp",
    "urllib",
    "socket",
    "selenium",
    "playwright",
    "bs4",
    "beautifulsoup",
    "scrapy",
    "websocket",
]

_M9A_FORBIDDEN_ENGINE_IMPORTS = [
    "transaction_rule_engine",
    "trade_simulator",
    "snapshot_loader",
]


def _read_module_source(module_name: str) -> str:
    import importlib
    from pathlib import Path

    mod = importlib.import_module(module_name)
    return Path(mod.__file__).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "module_name",
    [
        "backend.app.services.agent_intelligence",
        "backend.app.models.agent_intelligence",
    ],
)
def test_m9a_intelligence_modules_no_llm_or_network_imports(module_name: str) -> None:
    src = _read_module_source(module_name)
    for name in _M9A_FORBIDDEN_MODULE_IMPORTS:
        assert f"import {name}" not in src and f"from {name}" not in src, (
            f"M9-A violation: {module_name} must not import {name!r}"
        )


@pytest.mark.parametrize(
    "module_name",
    [
        "backend.app.services.agent_intelligence",
    ],
)
def test_m9a_intelligence_service_does_not_import_deterministic_engines(
    module_name: str,
) -> None:
    """The intelligence adapter is an explainer only; it must not call the
    deterministic engines (those run BEFORE the summary is built)."""
    src = _read_module_source(module_name)
    for name in _M9A_FORBIDDEN_ENGINE_IMPORTS:
        assert f"import {name}" not in src and f"from {name}" not in src, (
            f"M9-A violation: {module_name} must not import {name!r}"
        )


def test_m9a_intelligence_summary_is_frozen_dataclass() -> None:
    from backend.app.models.agent_intelligence import AgentIntelligenceSummary

    s = AgentIntelligenceSummary(
        summary_title="t",
        plain_language_summary="p",
        deterministic_verdict="v",
    )
    with pytest.raises(Exception):
        s.summary_title = "changed"  # type: ignore[misc]


def test_m9a_orchestrator_endpoint_summary_never_claims_execution(client) -> None:
    """Across all supported intents, the serialized intelligence_summary
    must never advertise execution semantics."""
    import json

    for intent in ("signing_preview", "trade_preview_demo", "hold", "execute_trade"):
        resp = client.post(
            "/api/agent/orchestrate-preview",
            json={"intent": intent, "team_id": "DEM-ATL"},
        )
        assert resp.status_code == 200
        body = resp.json()
        s = body["intelligence_summary"]
        blob = json.dumps(s, ensure_ascii=False).lower()
        for bad in (
            "executed",
            "applied",
            "committed",
            "auto_execute",
            "auto_approve",
            "已执行",
            "已完成签约",
            "已完成交易",
            "自动批准",
            "已提交",
            "已落地",
        ):
            assert bad not in blob, (
                f"M9-A violation: intelligence_summary for intent={intent!r} "
                f"contains execution-semantic word {bad!r}"
            )


def test_m9a_intelligence_summary_does_not_claim_live_or_current_data() -> None:
    """The summary must not claim live/real-time/current NBA data."""
    from backend.app.models.agent_orchestrator import AgentOrchestratorRequest
    from backend.app.services.agent_orchestrator import orchestrate_preview
    import json

    for intent in ("signing_preview", "trade_preview_demo", "hold", "execute_trade"):
        req = AgentOrchestratorRequest(intent=intent, team_id="DEM-ATL")
        r = orchestrate_preview(req, DATA_DIR)
        s = r.intelligence_summary
        assert s is not None
        blob = json.dumps(s.to_dict(), ensure_ascii=False).lower()
        for bad in ("live nba", "real-time nba", "real time nba", "实时", "最新"):
            assert bad not in blob, (
                f"M9-A violation: summary for {intent!r} contains {bad!r}"
            )
        # "current" (without being "current nba") is also banned per spec in
        # the English list — confirm no standalone "current" survives in the
        # final serialized summary.
        assert "current" not in blob, (
            f"M9-A violation: summary for {intent!r} contains forbidden word 'current'"
        )


def test_m9a_intelligence_summary_exposes_no_execute_functions() -> None:
    """The intelligence service module must not expose functions that
    sound like they mutate/write data."""
    import backend.app.services.agent_intelligence as ai

    for forbidden in (
        "execute",
        "apply",
        "commit",
        "mutate",
        "write",
        "sign_player",
        "trade_player",
        "save_snapshot",
    ):
        assert not hasattr(ai, forbidden), (
            f"M9-A violation: agent_intelligence must not expose {forbidden!r}"
        )
