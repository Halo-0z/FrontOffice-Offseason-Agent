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
# M4 TODOs (not implemented in M2/M3-B)
# --------------------------------------------------------------------------- #

# TODO(M4): test_agent_blocked_from_writing_roster.
# TODO(M4): test_agent_blocked_from_writing_cap_sheet.
# TODO(M4): test_agent_blocked_from_writing_contracts.
# TODO(M4): test_brief_rejected_when_required_field_missing.
# TODO(M4): test_brief_rejected_when_evidence_ids_missing.
# TODO(M4): test_guardrail_violation_count_is_zero_on_clean_run.
