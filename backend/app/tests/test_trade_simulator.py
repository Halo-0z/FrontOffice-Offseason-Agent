"""Tests for ``trade_simulator`` (M3-B).

Coverage:

1. ``preview_signing`` calls ``validate_transaction`` / ``validate_signing``.
2. Valid signing preview returns ``requires_human_approval=True``.
3. Invalid signing preview is NOT approved (``is_valid=False``).
4. Valid signing preview has structured ``depth_chart_after`` / ``roster_need_after``.
5. Preview does not mutate ``data/players.json``.
6. Preview does not mutate ``data/contracts.json``.
7. ``preview_trade`` on a valid trade returns a structured preview.
8. Invalid trade returns a validation-failed fallback preview.
9. ``preview_transaction`` dispatches signing/trade correctly.
10. Unsupported transaction type raises a clear exception.
11. M0/M1/M2/M3-A existing tests continue passing (covered by their files).

Run:

    python -m pytest backend/app/tests/test_trade_simulator.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.models.roster import (
    NeedLevel,
    Position,
    ProjectedDepthChart,
    RosterNeedReport,
    TransactionPreview,
)
from backend.app.models.transaction import (
    AssetType,
    SigningTransaction,
    TradeTransaction,
    TransactionAsset,
    TransactionType,
    ValidationStatus,
)
from backend.app.services.transaction_rule_engine import (
    TransactionRuleEngineError,
    validate_transaction,
)
from backend.app.services.trade_simulator import (
    preview_signing,
    preview_trade,
    preview_transaction,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _minimum_signing(
    tx_id: str,
    team_id: str = "DEM-ATL",
    salary: int = 1_000_000,
) -> SigningTransaction:
    return SigningTransaction(
        transaction_id=tx_id,
        transaction_type=TransactionType.MINIMUM_SIGNING,
        team_id=team_id,
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
        asset_type=AssetType.PLAYER_CONTRACT,
    )


def _valid_trade_in_tmp(tmp_dir: Path) -> TradeTransaction:
    """Build a salary-matching trade against a tmp data dir with balanced
    salaries so validation passes."""
    for name in ("cap_config.json", "teams.json"):
        (tmp_dir / name).write_text(
            (DATA_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    contracts = [
        {"contract_id": "ct-a1", "player_id": "pl-a1", "team_id": "DEM-ATL", "salary": 20_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True},
        {"contract_id": "ct-b1", "player_id": "pl-b1", "team_id": "DEM-PDX", "salary": 20_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True},
    ]
    (tmp_dir / "contracts.json").write_text(
        json.dumps({"sample_data": True, "contracts": contracts}), encoding="utf-8"
    )
    # Also need players.json so roster preview can load.
    (tmp_dir / "players.json").write_text(
        json.dumps(
            {
                "sample_data": True,
                "players": [
                    {"player_id": "pl-a1", "name": "A1", "team_id": "DEM-ATL", "position": "PG", "role": "starter", "sample_data": True},
                    {"player_id": "pl-b1", "name": "B1", "team_id": "DEM-PDX", "position": "SG", "role": "starter", "sample_data": True},
                ],
            }
        ),
        encoding="utf-8",
    )
    return TradeTransaction(
        transaction_id="tx-trade-valid",
        transaction_type=TransactionType.TWO_TEAM_TRADE,
        team_a_id="DEM-ATL",
        team_b_id="DEM-PDX",
        outgoing_from_a=(_asset("pl-a1", 20_000_000, "DEM-ATL", "DEM-PDX"),),
        outgoing_from_b=(_asset("pl-b1", 20_000_000, "DEM-PDX", "DEM-ATL"),),
        evidence_ids=("ev-004",),
    )


# --------------------------------------------------------------------------- #
# 1. preview_signing calls validate_transaction
# --------------------------------------------------------------------------- #


def test_preview_signing_calls_validate_transaction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Patching ``validate_transaction`` to raise must surface in preview_signing."""
    from backend.app.services import trade_simulator

    called = {"count": 0}

    def _spy(tx, data_dir="data"):
        called["count"] += 1
        return validate_transaction(tx, data_dir)

    monkeypatch.setattr(trade_simulator, "validate_transaction", _spy)
    tx = _minimum_signing("tx-spy")
    preview_signing(tx, DATA_DIR)
    assert called["count"] == 1, "preview_signing must call validate_transaction exactly once"


# --------------------------------------------------------------------------- #
# 2. Valid signing preview: requires_human_approval=True
# --------------------------------------------------------------------------- #


def test_valid_signing_preview_requires_human_approval() -> None:
    tx = _minimum_signing("tx-valid-approval", salary=1_000_000)
    preview = preview_signing(tx, DATA_DIR)
    assert isinstance(preview, TransactionPreview)
    assert preview.requires_human_approval is True
    assert preview.transaction_id == "tx-valid-approval"


# --------------------------------------------------------------------------- #
# 3. Invalid signing preview: NOT approved
# --------------------------------------------------------------------------- #


def test_invalid_signing_preview_is_not_approved() -> None:
    # MINIMUM_SIGNING with salary > minimum_salary -> FAIL.
    tx = _minimum_signing("tx-invalid", salary=5_000_000)
    preview = preview_signing(tx, DATA_DIR)
    assert preview.validation_result is not None
    assert preview.validation_result.is_valid is False
    assert preview.validation_result.status is ValidationStatus.FAIL
    assert preview.requires_human_approval is True
    # Fallback: no structured after-state.
    assert preview.roster_need_after is None
    assert preview.depth_chart_after is None
    # And limitations document the fallback.
    assert any("Validation failed" in lim for lim in preview.limitations)


# --------------------------------------------------------------------------- #
# 4. Valid signing preview has structured after-state
# --------------------------------------------------------------------------- #


def test_valid_signing_preview_has_structured_after_state() -> None:
    tx = _minimum_signing("tx-structured", salary=1_000_000)
    preview = preview_signing(tx, DATA_DIR)
    assert preview.validation_result.is_valid is True
    assert isinstance(preview.roster_need_after, RosterNeedReport)
    assert isinstance(preview.depth_chart_after, ProjectedDepthChart)
    # The preview roster should have one more player than the current roster.
    from backend.app.services.roster_need_service import load_roster_players

    current_count = len(load_roster_players("DEM-ATL", DATA_DIR))
    assert preview.roster_need_after.roster_count == current_count + 1
    assert preview.depth_chart_after.roster_count == current_count + 1


# --------------------------------------------------------------------------- #
# 5 & 6. Preview does not mutate data files
# --------------------------------------------------------------------------- #


def test_preview_signing_does_not_mutate_players_json() -> None:
    path = DATA_DIR / "players.json"
    before = path.read_bytes()
    preview_signing(_minimum_signing("tx-mut-1"), DATA_DIR)
    preview_signing(_minimum_signing("tx-mut-2", salary=1_200_000), DATA_DIR)
    after = path.read_bytes()
    assert before == after


def test_preview_signing_does_not_mutate_contracts_json() -> None:
    path = DATA_DIR / "contracts.json"
    before = path.read_bytes()
    preview_signing(_minimum_signing("tx-mut-3"), DATA_DIR)
    after = path.read_bytes()
    assert before == after


def test_preview_trade_does_not_mutate_data_files(tmp_path: Path) -> None:
    """Trade preview against a tmp data dir must not mutate any file."""
    tx = _valid_trade_in_tmp(tmp_path)
    players_before = (tmp_path / "players.json").read_bytes()
    contracts_before = (tmp_path / "contracts.json").read_bytes()
    preview_trade(tx, tmp_path)
    assert (tmp_path / "players.json").read_bytes() == players_before
    assert (tmp_path / "contracts.json").read_bytes() == contracts_before


# --------------------------------------------------------------------------- #
# 7. preview_trade on valid trade returns structured preview
# --------------------------------------------------------------------------- #


def test_preview_trade_valid_returns_structured_preview(tmp_path: Path) -> None:
    tx = _valid_trade_in_tmp(tmp_path)
    preview = preview_trade(tx, tmp_path)
    assert isinstance(preview, TransactionPreview)
    assert preview.transaction_id == "tx-trade-valid"
    assert preview.validation_result.is_valid is True
    assert preview.requires_human_approval is True
    assert isinstance(preview.roster_need_after, RosterNeedReport)
    assert isinstance(preview.depth_chart_after, ProjectedDepthChart)
    # Team A sent 1, received 1 -> roster count unchanged (1 -> 1).
    assert preview.roster_need_after.roster_count == 1


# --------------------------------------------------------------------------- #
# 8. Invalid trade returns validation-failed fallback
# --------------------------------------------------------------------------- #


def test_preview_trade_invalid_returns_fallback() -> None:
    # Salary mismatch: ATL sends 5M, PDX sends 30M.
    tx = TradeTransaction(
        transaction_id="tx-trade-invalid",
        transaction_type=TransactionType.TWO_TEAM_TRADE,
        team_a_id="DEM-ATL",
        team_b_id="DEM-PDX",
        outgoing_from_a=(_asset("pl-001", 5_000_000, "DEM-ATL", "DEM-PDX"),),
        outgoing_from_b=(_asset("pl-005", 30_000_000, "DEM-PDX", "DEM-ATL"),),
        evidence_ids=(),
    )
    preview = preview_trade(tx, DATA_DIR)
    assert preview.validation_result.is_valid is False
    assert preview.roster_need_after is None
    assert preview.depth_chart_after is None
    assert preview.requires_human_approval is True
    assert any("Validation failed" in lim for lim in preview.limitations)


# --------------------------------------------------------------------------- #
# 9. preview_transaction dispatches correctly
# --------------------------------------------------------------------------- #


def test_preview_transaction_dispatches_signing() -> None:
    tx = _minimum_signing("tx-dispatch-signing")
    preview = preview_transaction(tx, DATA_DIR)
    assert preview.transaction_id == "tx-dispatch-signing"
    assert preview.validation_result.transaction_type is TransactionType.MINIMUM_SIGNING


def test_preview_transaction_dispatches_trade(tmp_path: Path) -> None:
    tx = _valid_trade_in_tmp(tmp_path)
    preview = preview_transaction(tx, tmp_path)
    assert preview.validation_result.transaction_type is TransactionType.TWO_TEAM_TRADE


# --------------------------------------------------------------------------- #
# 10. Unsupported transaction type raises
# --------------------------------------------------------------------------- #


def test_preview_transaction_rejects_unsupported_type() -> None:
    with pytest.raises(TransactionRuleEngineError):
        preview_transaction("not-a-transaction", DATA_DIR)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Bonus: determinism + immutability
# --------------------------------------------------------------------------- #


def test_preview_is_deterministic() -> None:
    tx = _minimum_signing("tx-det")
    p1 = preview_signing(tx, DATA_DIR)
    p2 = preview_signing(tx, DATA_DIR)
    assert p1 == p2


def test_preview_is_immutable() -> None:
    tx = _minimum_signing("tx-imm")
    preview = preview_signing(tx, DATA_DIR)
    with pytest.raises(Exception):
        preview.requires_human_approval = False  # type: ignore[misc]


def test_valid_signing_preview_cap_summary_after_present() -> None:
    tx = _minimum_signing("tx-cap")
    preview = preview_signing(tx, DATA_DIR)
    assert preview.cap_summary_after is not None
    assert preview.cap_summary_after.total_salary > 0


# --------------------------------------------------------------------------- #
# M3-B patch: real FA position + unknown-FA fallback
# --------------------------------------------------------------------------- #


def _signing_for_fa(
    tx_id: str, player_id: str, salary: int = 1_000_000
) -> SigningTransaction:
    return SigningTransaction(
        transaction_id=tx_id,
        transaction_type=TransactionType.MINIMUM_SIGNING,
        team_id="DEM-ATL",
        player_id=player_id,
        salary=salary,
        years=1,
        evidence_ids=("ev-001",),
    )


def test_preview_signing_uses_real_fa_position_for_center() -> None:
    """fa-005 / Demo FA Quebec is a C. ATL has 0 centers, so the C slot
    is currently empty (need_level=high). After previewing the signing,
    fa-005 must appear in the C slot (as starter or backup) and the C
    need_level must drop from high to medium (1 player)."""
    tx = _signing_for_fa("tx-real-pos-c", player_id="fa-005", salary=1_000_000)
    preview = preview_signing(tx, DATA_DIR)
    assert preview.validation_result.is_valid is True
    assert preview.depth_chart_after is not None
    assert preview.roster_need_after is not None

    # Find the C slot.
    c_slot = next(
        s for s in preview.depth_chart_after.slots if s.position is Position.C
    )
    # fa-005 must be in the slot (starter or backup).
    c_player_ids = [c_slot.starter.player_id] if c_slot.starter else []
    c_player_ids += [b.player_id for b in c_slot.backups]
    assert "fa-005" in c_player_ids, "fa-005 must appear in the C slot"
    # With 1 C on the roster, need_level should drop from high to medium.
    assert c_slot.need_level is NeedLevel.MEDIUM

    # And the C need should be satisfied (no longer a HIGH-priority gap
    # of 2; gap is now 1 -> MEDIUM).
    c_needs = [
        n for n in preview.roster_need_after.needs if n.position is Position.C
    ]
    assert len(c_needs) == 1
    assert c_needs[0].current_count == 1
    assert c_needs[0].priority.value == "medium"


def test_preview_signing_uses_real_fa_name_and_role() -> None:
    """The preview roster should use the FA's real name/role from
    free_agents.json, not a hardcoded 'Preview Signing ...' placeholder."""
    tx = _signing_for_fa("tx-real-name", player_id="fa-005", salary=1_000_000)
    preview = preview_signing(tx, DATA_DIR)
    assert preview.depth_chart_after is not None
    c_slot = next(
        s for s in preview.depth_chart_after.slots if s.position is Position.C
    )
    starter = c_slot.starter
    assert starter is not None
    assert starter.player_id == "fa-005"
    assert starter.name == "Demo FA Quebec"
    assert starter.role == "starter"


def test_preview_signing_unknown_fa_does_not_default_to_pg() -> None:
    """When player_id is not in free_agents.json, the preview must NOT
    hardcode a default PG position. depth_chart_after and
    roster_need_after must be None, and a fallback limitation must
    explain why."""
    tx = _signing_for_fa(
        "tx-unknown-fa", player_id="UNKNOWN-FA", salary=1_000_000
    )
    preview = preview_signing(tx, DATA_DIR)
    # Validation can still pass (minimum signing salary is within limit).
    # The key assertion is that we don't fabricate a PG roster entry.
    assert preview.requires_human_approval is True
    assert preview.depth_chart_after is None
    assert preview.roster_need_after is None
    # Must have a clear fallback limitation.
    assert any(
        "Missing free-agent profile" in lim for lim in preview.limitations
    ), "must document the missing-profile fallback"


def test_preview_signing_unknown_fa_not_in_pg_slot() -> None:
    """Belt-and-suspenders: even if some future bug produced a depth
    chart, UNKNOWN-FA must never appear in the PG slot. With the current
    fallback, depth_chart_after is None so this is trivially true; the
    test guards against a regression that re-introduces a default PG."""
    tx = _signing_for_fa(
        "tx-unknown-fa-pg", player_id="UNKNOWN-FA", salary=1_000_000
    )
    preview = preview_signing(tx, DATA_DIR)
    if preview.depth_chart_after is not None:
        pg_slot = next(
            s for s in preview.depth_chart_after.slots if s.position is Position.PG
        )
        pg_ids = [pg_slot.starter.player_id] if pg_slot.starter else []
        pg_ids += [b.player_id for b in pg_slot.backups]
        assert "UNKNOWN-FA" not in pg_ids


def test_preview_signing_does_not_mutate_free_agents_json() -> None:
    path = DATA_DIR / "free_agents.json"
    before = path.read_bytes()
    preview_signing(_signing_for_fa("tx-no-mut-fa", player_id="fa-005"), DATA_DIR)
    preview_signing(
        _signing_for_fa("tx-no-mut-fa-2", player_id="UNKNOWN-FA"), DATA_DIR
    )
    after = path.read_bytes()
    assert before == after


def test_preview_signing_real_fa_does_not_mutate_players_json() -> None:
    """Additional no-mutation check using a real FA (fa-005) to ensure
    the new lookup path doesn't accidentally write to players.json."""
    path = DATA_DIR / "players.json"
    before = path.read_bytes()
    preview_signing(_signing_for_fa("tx-no-mut-players", player_id="fa-005"), DATA_DIR)
    after = path.read_bytes()
    assert before == after


def test_preview_signing_real_fa_still_requires_human_approval() -> None:
    """A valid preview with a real FA profile must still require human
    approval (the patch must not weaken this guardrail)."""
    tx = _signing_for_fa("tx-approval-real", player_id="fa-005", salary=1_000_000)
    preview = preview_signing(tx, DATA_DIR)
    assert preview.validation_result.is_valid is True
    assert preview.requires_human_approval is True


def test_get_free_agent_by_id_returns_profile_and_none() -> None:
    """Direct test of the new helper."""
    from backend.app.services.free_agent_service import get_free_agent_by_id

    profile = get_free_agent_by_id("fa-005", DATA_DIR)
    assert profile is not None
    assert profile["position"] == "C"
    assert profile["name"] == "Demo FA Quebec"

    missing = get_free_agent_by_id("DOES-NOT-EXIST", DATA_DIR)
    assert missing is None


# --------------------------------------------------------------------------- #
# M3-B patch 2: preview_trade uses real incoming player position
# --------------------------------------------------------------------------- #


def _valid_trade_real_data(
    tx_id: str = "tx-trade-real",
    incoming_to_a_player_id: str = "pl-009",
    incoming_to_a_salary: int = 17_000_000,
    outgoing_from_a_player_id: str = "pl-001",
    outgoing_from_a_salary: int = 18_000_000,
) -> TradeTransaction:
    """Build a salary-matching trade against the REAL data dir.

    ATL sends pl-001 (18M) to PDX; PDX sends pl-009 (17M) to ATL.
    Salary matching: A incoming 17M <= 18M*1.25+100k=22.6M OK;
    B incoming 18M <= 17M*1.25+100k=21.35M OK. Both players exist in
    players.json (pl-001 PG ATL, pl-009 PG CHI — get_player_by_id
    searches across all teams).
    """
    return TradeTransaction(
        transaction_id=tx_id,
        transaction_type=TransactionType.TWO_TEAM_TRADE,
        team_a_id="DEM-ATL",
        team_b_id="DEM-PDX",
        outgoing_from_a=(
            _asset(
                outgoing_from_a_player_id,
                outgoing_from_a_salary,
                "DEM-ATL",
                "DEM-PDX",
            ),
        ),
        outgoing_from_b=(
            _asset(
                incoming_to_a_player_id,
                incoming_to_a_salary,
                "DEM-PDX",
                "DEM-ATL",
            ),
        ),
        evidence_ids=("ev-demo-cap-001",),
    )


def test_preview_trade_uses_real_incoming_player_position() -> None:
    """When the incoming player has a profile in players.json, the
    preview must use the REAL position. pl-009 is a PG, so it should
    appear in the PG slot of team A's depth_chart_after — NOT in some
    default slot. We also verify the real name is used."""
    tx = _valid_trade_real_data(
        tx_id="tx-trade-real-pos",
        incoming_to_a_player_id="pl-009",
        incoming_to_a_salary=17_000_000,
        outgoing_from_a_player_id="pl-001",
        outgoing_from_a_salary=18_000_000,
    )
    preview = preview_trade(tx, DATA_DIR)
    assert preview.validation_result.is_valid is True
    assert preview.depth_chart_after is not None
    assert preview.roster_need_after is not None

    # pl-009 is a PG; pl-001 (also PG) was sent away. So PG slot should
    # have pl-009 as the starter (ATL originally had pl-001 as PG starter,
    # now pl-001 is gone and pl-009 is the incoming PG).
    pg_slot = next(
        s for s in preview.depth_chart_after.slots if s.position is Position.PG
    )
    pg_ids = [pg_slot.starter.player_id] if pg_slot.starter else []
    pg_ids += [b.player_id for b in pg_slot.backups]
    assert "pl-009" in pg_ids, "pl-009 must appear in the PG slot"
    # pl-001 was sent away, must NOT appear.
    all_ids = []
    for s in preview.depth_chart_after.slots:
        if s.starter:
            all_ids.append(s.starter.player_id)
        all_ids.extend(b.player_id for b in s.backups)
    assert "pl-001" not in all_ids, "pl-001 was traded away and must not appear"

    # Real name should be used, not a "Trade Incoming ..." placeholder.
    assert pg_slot.starter is not None
    assert pg_slot.starter.name == "Demo Player India"


def test_preview_trade_real_position_not_default_pg_for_non_pg() -> None:
    """Belt-and-suspenders: when the incoming player is NOT a PG, the
    preview must place them at their real position. We use pl-007 (C,
    DEM-PDX) incoming to ATL. ATL originally has 0 centers, so after
    the trade the C slot should have pl-007 and need_level should drop
    from high to medium.

    To make salary matching work: ATL sends pl-003 (18M) to PDX; PDX
    sends pl-007 (26M) to ATL. Check: A incoming 26M <= 18M*1.25+100k
    = 22.6M? NO, 26M > 22.6M -> FAIL. So we adjust: ATL sends pl-001
    (28M) to PDX; PDX sends pl-007 (26M) to ATL. A incoming 26M <=
    28M*1.25+100k=35.1M OK; B incoming 28M <= 26M*1.25+100k=32.6M OK.
    """
    tx = _valid_trade_real_data(
        tx_id="tx-trade-real-c",
        incoming_to_a_player_id="pl-007",
        incoming_to_a_salary=26_000_000,
        outgoing_from_a_player_id="pl-001",
        outgoing_from_a_salary=28_000_000,
    )
    preview = preview_trade(tx, DATA_DIR)
    assert preview.validation_result.is_valid is True
    assert preview.depth_chart_after is not None

    c_slot = next(
        s for s in preview.depth_chart_after.slots if s.position is Position.C
    )
    c_ids = [c_slot.starter.player_id] if c_slot.starter else []
    c_ids += [b.player_id for b in c_slot.backups]
    assert "pl-007" in c_ids, "pl-007 (C) must appear in the C slot"
    # ATL originally had 0 centers; now has 1 -> need_level medium.
    assert c_slot.need_level is NeedLevel.MEDIUM


def test_preview_trade_unknown_incoming_does_not_default_to_pg() -> None:
    """When an incoming player_id is NOT in players.json, the preview
    must NOT hardcode a default PG position. depth_chart_after and
    roster_need_after must be None, and a fallback limitation must
    explain why. UNKNOWN-INCOMING must never appear in any slot."""
    tx = _valid_trade_real_data(
        tx_id="tx-trade-unknown",
        incoming_to_a_player_id="UNKNOWN-INCOMING",
        incoming_to_a_salary=17_000_000,
        outgoing_from_a_player_id="pl-001",
        outgoing_from_a_salary=18_000_000,
    )
    preview = preview_trade(tx, DATA_DIR)
    assert preview.requires_human_approval is True
    assert preview.depth_chart_after is None
    assert preview.roster_need_after is None
    assert any(
        "Missing incoming player profile" in lim
        for lim in preview.limitations
    ), "must document the missing-profile fallback"


def test_preview_trade_unknown_incoming_not_in_any_slot() -> None:
    """Belt-and-suspenders: even if some future bug produced a depth
    chart, UNKNOWN-INCOMING must never appear in any slot. With the
    current fallback, depth_chart_after is None so this is trivially
    true; the test guards against a regression."""
    tx = _valid_trade_real_data(
        tx_id="tx-trade-unknown-regression",
        incoming_to_a_player_id="UNKNOWN-INCOMING",
        incoming_to_a_salary=17_000_000,
        outgoing_from_a_player_id="pl-001",
        outgoing_from_a_salary=18_000_000,
    )
    preview = preview_trade(tx, DATA_DIR)
    if preview.depth_chart_after is not None:
        for slot in preview.depth_chart_after.slots:
            slot_ids = [slot.starter.player_id] if slot.starter else []
            slot_ids += [b.player_id for b in slot.backups]
            assert "UNKNOWN-INCOMING" not in slot_ids


def test_preview_trade_does_not_mutate_players_json() -> None:
    path = DATA_DIR / "players.json"
    before = path.read_bytes()
    preview_trade(
        _valid_trade_real_data(tx_id="tx-trade-no-mut-players"), DATA_DIR
    )
    # Also test the unknown-incoming path.
    preview_trade(
        _valid_trade_real_data(
            tx_id="tx-trade-no-mut-players-2",
            incoming_to_a_player_id="UNKNOWN-INCOMING",
        ),
        DATA_DIR,
    )
    after = path.read_bytes()
    assert before == after


def test_preview_trade_does_not_mutate_contracts_json() -> None:
    path = DATA_DIR / "contracts.json"
    before = path.read_bytes()
    preview_trade(
        _valid_trade_real_data(tx_id="tx-trade-no-mut-contracts"), DATA_DIR
    )
    after = path.read_bytes()
    assert before == after


def test_preview_trade_real_still_requires_human_approval() -> None:
    """A valid trade preview with real incoming profiles must still
    require human approval (the patch must not weaken this guardrail)."""
    tx = _valid_trade_real_data(tx_id="tx-trade-approval")
    preview = preview_trade(tx, DATA_DIR)
    assert preview.validation_result.is_valid is True
    assert preview.requires_human_approval is True


def test_get_player_by_id_returns_profile_and_none() -> None:
    """Direct test of the new helper in roster_need_service."""
    from backend.app.services.roster_need_service import get_player_by_id

    profile = get_player_by_id("pl-009", DATA_DIR)
    assert profile is not None
    assert profile["position"] == "PG"
    assert profile["name"] == "Demo Player India"

    missing = get_player_by_id("DOES-NOT-EXIST", DATA_DIR)
    assert missing is None


# --------------------------------------------------------------------------- #
# M7-C: Team B full trade preview
# --------------------------------------------------------------------------- #


def test_preview_trade_returns_team_b_post_trade_preview() -> None:
    """preview_trade must return Team B's post-trade cap summary, roster
    need, and depth chart — not just Team A's."""
    tx = _valid_trade_real_data(tx_id="tx-m7c-team-b-full")
    preview = preview_trade(tx, DATA_DIR)
    assert preview.validation_result.is_valid is True

    # Team A (legacy fields, still present for backward compat).
    assert preview.cap_summary_after is not None
    assert preview.roster_need_after is not None
    assert preview.depth_chart_after is not None

    # Team B (M7-C new fields).
    assert preview.team_b_cap_summary_after is not None
    assert preview.team_b_roster_need_after is not None
    assert preview.team_b_depth_chart_after is not None


def test_preview_trade_team_a_cap_summary_after_correct() -> None:
    """Team A cap_summary_after must be for DEM-ATL and reflect a
    post-trade total salary change."""
    tx = _valid_trade_real_data(tx_id="tx-m7c-team-a-cap")
    preview = preview_trade(tx, DATA_DIR)
    assert preview.cap_summary_after is not None
    assert preview.cap_summary_after.team_id == "DEM-ATL"
    # The trade must have changed Team A's salary (before != after).
    vr = preview.validation_result
    assert vr.cap_summary_before is not None
    assert vr.cap_summary_after is not None
    assert vr.cap_summary_before.total_salary != vr.cap_summary_after.total_salary


def test_preview_trade_team_b_cap_summary_after_correct() -> None:
    """Team B cap_summary_after must be for DEM-PDX and reflect a
    post-trade total salary change (M7-C)."""
    tx = _valid_trade_real_data(tx_id="tx-m7c-team-b-cap")
    preview = preview_trade(tx, DATA_DIR)
    assert preview.team_b_cap_summary_after is not None
    assert preview.team_b_cap_summary_after.team_id == "DEM-PDX"
    # The trade must have changed Team B's salary (before != after).
    vr = preview.validation_result
    assert vr.team_b_cap_summary_before is not None
    assert vr.team_b_cap_summary_after is not None
    assert (
        vr.team_b_cap_summary_before.total_salary
        != vr.team_b_cap_summary_after.total_salary
    )


def test_preview_trade_team_a_roster_need_after_exists() -> None:
    """Team A roster_need_after must be a RosterNeedReport for DEM-ATL."""
    tx = _valid_trade_real_data(tx_id="tx-m7c-team-a-need")
    preview = preview_trade(tx, DATA_DIR)
    assert isinstance(preview.roster_need_after, RosterNeedReport)
    assert preview.roster_need_after.team_id == "DEM-ATL"


def test_preview_trade_team_b_roster_need_after_exists() -> None:
    """Team B roster_need_after must be a RosterNeedReport for DEM-PDX (M7-C)."""
    tx = _valid_trade_real_data(tx_id="tx-m7c-team-b-need")
    preview = preview_trade(tx, DATA_DIR)
    assert isinstance(preview.team_b_roster_need_after, RosterNeedReport)
    assert preview.team_b_roster_need_after.team_id == "DEM-PDX"


def test_preview_trade_team_a_depth_chart_after_exists() -> None:
    """Team A depth_chart_after must be a ProjectedDepthChart for DEM-ATL."""
    tx = _valid_trade_real_data(tx_id="tx-m7c-team-a-depth")
    preview = preview_trade(tx, DATA_DIR)
    assert isinstance(preview.depth_chart_after, ProjectedDepthChart)
    assert preview.depth_chart_after.team_id == "DEM-ATL"


def test_preview_trade_team_b_depth_chart_after_exists() -> None:
    """Team B depth_chart_after must be a ProjectedDepthChart for DEM-PDX (M7-C)."""
    tx = _valid_trade_real_data(tx_id="tx-m7c-team-b-depth")
    preview = preview_trade(tx, DATA_DIR)
    assert isinstance(preview.team_b_depth_chart_after, ProjectedDepthChart)
    assert preview.team_b_depth_chart_after.team_id == "DEM-PDX"


def test_preview_trade_team_b_still_requires_human_approval() -> None:
    """Team B preview must not weaken the human-approval guardrail."""
    tx = _valid_trade_real_data(tx_id="tx-m7c-team-b-approval")
    preview = preview_trade(tx, DATA_DIR)
    assert preview.requires_human_approval is True


def test_preview_trade_team_b_does_not_mutate_data_files() -> None:
    """Team B preview computation must not mutate any data file."""
    players_before = (DATA_DIR / "players.json").read_bytes()
    contracts_before = (DATA_DIR / "contracts.json").read_bytes()
    fa_before = (DATA_DIR / "free_agents.json").read_bytes()
    tx = _valid_trade_real_data(tx_id="tx-m7c-team-b-no-mut")
    preview_trade(tx, DATA_DIR)
    assert (DATA_DIR / "players.json").read_bytes() == players_before
    assert (DATA_DIR / "contracts.json").read_bytes() == contracts_before
    assert (DATA_DIR / "free_agents.json").read_bytes() == fa_before


def test_preview_trade_team_b_cap_matches_validation_result() -> None:
    """The preview's team_b_cap_summary_after must equal the validation
    result's team_b_cap_summary_after (single source of truth)."""
    tx = _valid_trade_real_data(tx_id="tx-m7c-team-b-match")
    preview = preview_trade(tx, DATA_DIR)
    vr = preview.validation_result
    assert preview.team_b_cap_summary_after == vr.team_b_cap_summary_after


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
