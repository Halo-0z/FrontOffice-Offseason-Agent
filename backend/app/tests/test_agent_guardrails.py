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
