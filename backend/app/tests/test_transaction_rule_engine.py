"""Tests for the M2 transaction rule engine.

These tests validate the deterministic MVP rule engine for signings and
two-team trades. They do NOT exercise M3 roster projection or M4 agent
orchestration.

Coverage (see docs/evaluation.md):

1. minimum signing salary <= minimum_salary passes.
2. minimum signing salary > minimum_salary fails.
3. MLE signing salary <= mid_level_exception passes.
4. MLE signing salary > mid_level_exception fails.
5. simple FA signing within cap space passes.
6. simple FA signing over cap space fails.
7. signing over roster_max fails.
8. signing that crosses luxury_tax / first_apron / second_apron returns warnings.
9. valid two-team salary matching trade passes.
10. invalid two-team salary mismatch trade fails.
11. trade with unknown team fails clearly.
12. trade with empty outgoing assets fails.
13. trade roster_count preview over roster_max fails.
14. validate_transaction dispatches correctly.
15. validation result always requires human approval.
16. transaction_rule_engine does not mutate data/contracts.json.
17. M0 smoke test continues passing (covered by test_m0_skeleton.py).
18. M1 cap_sheet_service tests continue passing (covered by test_cap_sheet_service.py).

Run:

    python -m pytest backend/app/tests/test_transaction_rule_engine.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.models.transaction import (
    AssetType,
    IssueSeverity,
    SigningTransaction,
    TradeTransaction,
    TransactionAsset,
    TransactionType,
    ValidationIssue,
    ValidationResult,
    ValidationStatus,
)
from backend.app.services.transaction_rule_engine import (
    TransactionRuleEngineError,
    validate_signing,
    validate_trade,
    validate_transaction,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _minimum_signing(
    tx_id: str,
    team_id: str = "DEM-ATL",
    player_id: str = "fa-001",
    salary: int = 1_000_000,
    years: int = 1,
) -> SigningTransaction:
    return SigningTransaction(
        transaction_id=tx_id,
        transaction_type=TransactionType.MINIMUM_SIGNING,
        team_id=team_id,
        player_id=player_id,
        salary=salary,
        years=years,
        evidence_ids=("ev-001",),
    )


def _mle_signing(
    tx_id: str,
    team_id: str = "DEM-ATL",
    salary: int = 10_000_000,
) -> SigningTransaction:
    return SigningTransaction(
        transaction_id=tx_id,
        transaction_type=TransactionType.MLE_SIGNING,
        team_id=team_id,
        player_id="fa-002",
        salary=salary,
        years=2,
        evidence_ids=("ev-002",),
    )


def _simple_fa_signing(
    tx_id: str,
    team_id: str = "DEM-ATL",
    salary: int = 10_000_000,
) -> SigningTransaction:
    return SigningTransaction(
        transaction_id=tx_id,
        transaction_type=TransactionType.SIMPLE_FA_SIGNING,
        team_id=team_id,
        player_id="fa-003",
        salary=salary,
        years=2,
        evidence_ids=("ev-003",),
    )


def _asset(player_id: str, salary: int, from_team: str, to_team: str) -> TransactionAsset:
    return TransactionAsset(
        player_id=player_id,
        salary=salary,
        from_team_id=from_team,
        to_team_id=to_team,
        asset_type=AssetType.PLAYER_CONTRACT,
    )


# --------------------------------------------------------------------------- #
# 1. minimum signing salary <= minimum_salary passes
# --------------------------------------------------------------------------- #


def test_minimum_signing_at_or_below_minimum_salary_passes() -> None:
    # cap_config.minimum_salary == 1_200_000
    tx = _minimum_signing("tx-min-ok", salary=1_200_000)
    result = validate_signing(tx, DATA_DIR)
    assert result.status in (ValidationStatus.PASS, ValidationStatus.WARNING)
    assert result.is_valid is True
    # No fail-severity issue with code minimum_salary_exceeded.
    fail_codes = {i.code for i in result.issues if i.severity is IssueSeverity.FAIL}
    assert "minimum_salary_exceeded" not in fail_codes


# --------------------------------------------------------------------------- #
# 2. minimum signing salary > minimum_salary fails
# --------------------------------------------------------------------------- #


def test_minimum_signing_above_minimum_salary_fails() -> None:
    tx = _minimum_signing("tx-min-bad", salary=2_000_000)
    result = validate_signing(tx, DATA_DIR)
    assert result.status is ValidationStatus.FAIL
    assert result.is_valid is False
    codes = {i.code for i in result.issues if i.severity is IssueSeverity.FAIL}
    assert "minimum_salary_exceeded" in codes


# --------------------------------------------------------------------------- #
# 3. MLE signing salary <= mid_level_exception passes
# --------------------------------------------------------------------------- #


def test_mle_signing_at_or_below_mle_passes() -> None:
    # cap_config.mid_level_exception == 12_800_000
    tx = _mle_signing("tx-mle-ok", salary=12_800_000)
    result = validate_signing(tx, DATA_DIR)
    assert result.is_valid is True
    fail_codes = {i.code for i in result.issues if i.severity is IssueSeverity.FAIL}
    assert "mle_exceeded" not in fail_codes


# --------------------------------------------------------------------------- #
# 4. MLE signing salary > mid_level_exception fails
# --------------------------------------------------------------------------- #


def test_mle_signing_above_mle_fails() -> None:
    tx = _mle_signing("tx-mle-bad", salary=15_000_000)
    result = validate_signing(tx, DATA_DIR)
    assert result.status is ValidationStatus.FAIL
    assert result.is_valid is False
    codes = {i.code for i in result.issues if i.severity is IssueSeverity.FAIL}
    assert "mle_exceeded" in codes


# --------------------------------------------------------------------------- #
# 5. simple FA signing within cap space passes
# --------------------------------------------------------------------------- #


def test_simple_fa_signing_within_cap_space_passes() -> None:
    # ATL total = 74M, cap = 140M, so 60M of space. A 10M signing fits.
    tx = _simple_fa_signing("tx-fa-ok", salary=10_000_000)
    result = validate_signing(tx, DATA_DIR)
    assert result.is_valid is True
    fail_codes = {i.code for i in result.issues if i.severity is IssueSeverity.FAIL}
    assert "cap_space_insufficient" not in fail_codes


# --------------------------------------------------------------------------- #
# 6. simple FA signing over cap space fails
# --------------------------------------------------------------------------- #


def test_simple_fa_signing_over_cap_space_fails() -> None:
    # 80M signing would push ATL to 154M > 140M cap.
    tx = _simple_fa_signing("tx-fa-bad", salary=80_000_000)
    result = validate_signing(tx, DATA_DIR)
    assert result.status is ValidationStatus.FAIL
    assert result.is_valid is False
    codes = {i.code for i in result.issues if i.severity is IssueSeverity.FAIL}
    assert "cap_space_insufficient" in codes


# --------------------------------------------------------------------------- #
# 7. signing over roster_max fails
# --------------------------------------------------------------------------- #


def test_signing_over_roster_max_fails() -> None:
    # ATL has 4 contracts; roster_max = 15. To force a roster_full FAIL we
    # build a synthetic sheet by signing many players. Easier: use a team
    # and a salary that fits cap, but craft a transaction whose preview
    # would exceed roster_max. Since we can't easily inflate the roster
    # from the public API, we instead validate the rule directly by
    # constructing a team sheet with 15 contracts already.
    #
    # We simulate this by temporarily pointing the engine at a tmp data
    # dir where the team already has roster_max contracts.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        # Copy cap config + teams.
        for name in ("cap_config.json", "teams.json"):
            (tmp_dir / name).write_text(
                (DATA_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
            )
        # Build a contracts.json where DEM-ATL has exactly roster_max (15) contracts.
        contracts = []
        for i in range(15):
            contracts.append(
                {
                    "contract_id": f"ct-fill-{i:02d}",
                    "player_id": f"pl-fill-{i:02d}",
                    "team_id": "DEM-ATL",
                    "salary": 1_000_000,
                    "years_remaining": 1,
                    "guaranteed": False,
                    "player_option": False,
                    "team_option": False,
                    "no_trade_clause": False,
                    "sample_data": True,
                }
            )
        (tmp_dir / "contracts.json").write_text(
            json.dumps({"sample_data": True, "contracts": contracts}), encoding="utf-8"
        )
        # Now a minimum signing would push roster to 16 > 15.
        tx = _minimum_signing("tx-roster-full", salary=1_000_000)
        result = validate_signing(tx, tmp_dir)
        assert result.status is ValidationStatus.FAIL
        assert result.is_valid is False
        codes = {i.code for i in result.issues if i.severity is IssueSeverity.FAIL}
        assert "roster_full" in codes


def test_signing_to_exact_roster_max_returns_warning() -> None:
    """When the signing brings roster_count exactly to roster_max, the
    engine should emit a WARNING (not a FAIL)."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for name in ("cap_config.json", "teams.json"):
            (tmp_dir / name).write_text(
                (DATA_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
            )
        # 14 contracts -> signing brings to 15 == roster_max.
        contracts = [
            {
                "contract_id": f"ct-fill-{i:02d}",
                "player_id": f"pl-fill-{i:02d}",
                "team_id": "DEM-ATL",
                "salary": 1_000_000,
                "years_remaining": 1,
                "guaranteed": False,
                "sample_data": True,
            }
            for i in range(14)
        ]
        (tmp_dir / "contracts.json").write_text(
            json.dumps({"sample_data": True, "contracts": contracts}), encoding="utf-8"
        )
        tx = _minimum_signing("tx-roster-at-max", salary=1_000_000)
        result = validate_signing(tx, tmp_dir)
        assert result.is_valid is True  # warning, not fail
        warn_codes = {i.code for i in result.warnings}
        assert "roster_at_max" in warn_codes


# --------------------------------------------------------------------------- #
# 8. signing that crosses apron lines returns warnings
# --------------------------------------------------------------------------- #


def test_signing_crossing_apron_lines_returns_warnings() -> None:
    # ATL total = 74M. luxury_tax = 170M, first_apron = 178M, second_apron = 189M.
    # A signing of 110M pushes total to 184M, crossing luxury_tax (170M) and
    # first_apron (178M), but not second_apron (189M). We bump minimum_salary
    # so the MINIMUM_SIGNING salary rule itself passes.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        # Copy teams + contracts.
        for name in ("teams.json", "contracts.json"):
            (tmp_dir / name).write_text(
                (DATA_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
            )
        # Bump minimum_salary way up so a 110M minimum signing is "legal"
        # by the minimum rule, but crosses luxury_tax and first_apron.
        cap_cfg = json.loads((DATA_DIR / "cap_config.json").read_text(encoding="utf-8"))
        cap_cfg["cap_config"]["minimum_salary"] = 200_000_000
        (tmp_dir / "cap_config.json").write_text(
            json.dumps(cap_cfg), encoding="utf-8"
        )
        tx = _minimum_signing("tx-apron-warn", salary=110_000_000)
        result = validate_signing(tx, tmp_dir)
        # The signing itself is legal under the minimum rule (salary <= minimum_salary).
        fail_codes = {i.code for i in result.issues if i.severity is IssueSeverity.FAIL}
        assert "minimum_salary_exceeded" not in fail_codes
        # Apron warnings should be present for both crossed lines.
        warn_codes = {i.code for i in result.warnings}
        assert "apron_crossed:luxury_tax" in warn_codes
        assert "apron_crossed:first_apron" in warn_codes
        # second_apron (189M) is not crossed (184M < 189M).
        assert "apron_crossed:second_apron" not in warn_codes


# --------------------------------------------------------------------------- #
# 9. valid two-team salary matching trade passes
# --------------------------------------------------------------------------- #


def test_valid_two_team_trade_passes() -> None:
    # ATL sends pl-002 (22M) to PDX, PDX sends pl-008 (14M) to ATL.
    # For team A (ATL): outgoing=22M, incoming=14M -> 14M <= 22M*1.25+100k=27.6M OK.
    # For team B (PDX): outgoing=14M, incoming=22M -> 22M <= 14M*1.25+100k=17.6M? NO.
    # So this would fail for B. Let's pick salaries that match both ways.
    # Use a tmp contracts file with balanced salaries.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for name in ("cap_config.json", "teams.json"):
            (tmp_dir / name).write_text(
                (DATA_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
            )
        contracts = [
            {"contract_id": "ct-a1", "player_id": "pl-a1", "team_id": "DEM-ATL", "salary": 20_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True},
            {"contract_id": "ct-a2", "player_id": "pl-a2", "team_id": "DEM-ATL", "salary": 5_000_000, "years_remaining": 1, "guaranteed": True, "sample_data": True},
            {"contract_id": "ct-b1", "player_id": "pl-b1", "team_id": "DEM-PDX", "salary": 20_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True},
            {"contract_id": "ct-b2", "player_id": "pl-b2", "team_id": "DEM-PDX", "salary": 5_000_000, "years_remaining": 1, "guaranteed": True, "sample_data": True},
        ]
        (tmp_dir / "contracts.json").write_text(
            json.dumps({"sample_data": True, "contracts": contracts}), encoding="utf-8"
        )
        tx = TradeTransaction(
            transaction_id="tx-trade-ok",
            transaction_type=TransactionType.TWO_TEAM_TRADE,
            team_a_id="DEM-ATL",
            team_b_id="DEM-PDX",
            outgoing_from_a=(_asset("pl-a1", 20_000_000, "DEM-ATL", "DEM-PDX"),),
            outgoing_from_b=(_asset("pl-b1", 20_000_000, "DEM-PDX", "DEM-ATL"),),
            evidence_ids=("ev-004",),
        )
        result = validate_trade(tx, tmp_dir)
        fail_codes = {i.code for i in result.issues if i.severity is IssueSeverity.FAIL}
        assert "salary_mismatch" not in fail_codes
        assert "team_not_found" not in fail_codes
        assert result.is_valid is True


# --------------------------------------------------------------------------- #
# 10. invalid two-team salary mismatch trade fails
# --------------------------------------------------------------------------- #


def test_invalid_two_team_salary_mismatch_trade_fails() -> None:
    # ATL sends 5M, PDX sends 30M. For ATL: incoming=30M <= 5M*1.25+100k=6.35M? NO.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for name in ("cap_config.json", "teams.json"):
            (tmp_dir / name).write_text(
                (DATA_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
            )
        contracts = [
            {"contract_id": "ct-a1", "player_id": "pl-a1", "team_id": "DEM-ATL", "salary": 5_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True},
            {"contract_id": "ct-b1", "player_id": "pl-b1", "team_id": "DEM-PDX", "salary": 30_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True},
        ]
        (tmp_dir / "contracts.json").write_text(
            json.dumps({"sample_data": True, "contracts": contracts}), encoding="utf-8"
        )
        tx = TradeTransaction(
            transaction_id="tx-trade-mismatch",
            transaction_type=TransactionType.TWO_TEAM_TRADE,
            team_a_id="DEM-ATL",
            team_b_id="DEM-PDX",
            outgoing_from_a=(_asset("pl-a1", 5_000_000, "DEM-ATL", "DEM-PDX"),),
            outgoing_from_b=(_asset("pl-b1", 30_000_000, "DEM-PDX", "DEM-ATL"),),
            evidence_ids=(),
        )
        result = validate_trade(tx, tmp_dir)
        assert result.status is ValidationStatus.FAIL
        assert result.is_valid is False
        codes = {i.code for i in result.issues if i.severity is IssueSeverity.FAIL}
        assert "salary_mismatch" in codes


# --------------------------------------------------------------------------- #
# 11. trade with unknown team fails clearly
# --------------------------------------------------------------------------- #


def test_trade_with_unknown_team_fails_clearly() -> None:
    tx = TradeTransaction(
        transaction_id="tx-trade-unknown",
        transaction_type=TransactionType.TWO_TEAM_TRADE,
        team_a_id="DOES-NOT-EXIST",
        team_b_id="DEM-PDX",
        outgoing_from_a=(_asset("pl-x", 5_000_000, "DOES-NOT-EXIST", "DEM-PDX"),),
        outgoing_from_b=(_asset("pl-b1", 5_000_000, "DEM-PDX", "DOES-NOT-EXIST"),),
        evidence_ids=(),
    )
    result = validate_trade(tx, DATA_DIR)
    assert result.status is ValidationStatus.FAIL
    assert result.is_valid is False
    team_issues = [i for i in result.issues if i.code == "team_not_found"]
    assert len(team_issues) >= 1
    assert any("DOES-NOT-EXIST" in i.message for i in team_issues)


# --------------------------------------------------------------------------- #
# 12. trade with empty outgoing assets fails
# --------------------------------------------------------------------------- #


def test_trade_with_empty_outgoing_assets_fails() -> None:
    tx = TradeTransaction(
        transaction_id="tx-trade-empty",
        transaction_type=TransactionType.TWO_TEAM_TRADE,
        team_a_id="DEM-ATL",
        team_b_id="DEM-PDX",
        outgoing_from_a=(),  # empty
        outgoing_from_b=(_asset("pl-b1", 5_000_000, "DEM-PDX", "DEM-ATL"),),
        evidence_ids=(),
    )
    result = validate_trade(tx, DATA_DIR)
    assert result.status is ValidationStatus.FAIL
    codes = {i.code for i in result.issues if i.severity is IssueSeverity.FAIL}
    assert "empty_outgoing" in codes


# --------------------------------------------------------------------------- #
# 13. trade roster_count preview over roster_max fails
# --------------------------------------------------------------------------- #


def test_trade_roster_count_preview_over_roster_max_fails() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for name in ("cap_config.json", "teams.json"):
            (tmp_dir / name).write_text(
                (DATA_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
            )
        # Team A has 1 contract (so after receiving 15 it would be 16 > 15).
        # Team B has 15 contracts; sending 1 away leaves 14, receiving 1 -> 15 (ok).
        contracts = [
            {"contract_id": "ct-a1", "player_id": "pl-a1", "team_id": "DEM-ATL", "salary": 5_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True},
        ]
        for i in range(15):
            contracts.append(
                {
                    "contract_id": f"ct-b{i:02d}",
                    "player_id": f"pl-b{i:02d}",
                    "team_id": "DEM-PDX",
                    "salary": 5_000_000,
                    "years_remaining": 2,
                    "guaranteed": True,
                    "sample_data": True,
                }
            )
        (tmp_dir / "contracts.json").write_text(
            json.dumps({"sample_data": True, "contracts": contracts}), encoding="utf-8"
        )
        # ATL sends 1 (pl-a1, 5M), PDX sends 15 (5M each = 75M).
        # Salary matching for ATL: incoming=75M <= 5M*1.25+100k=6.35M? NO -> mismatch FAIL.
        # To isolate roster_full, make salaries match: ATL sends 15 players too.
        # But ATL only has 1. So instead: ATL sends 1 player worth 5M, PDX sends
        # 1 player worth 5M. Then ATL roster goes 1 -> 1 (no change). Not useful.
        #
        # Better: give ATL 15 contracts already, send 1, receive 2 -> 16 > 15.
        contracts = [
            {"contract_id": f"ct-a{i:02d}", "player_id": f"pl-a{i:02d}", "team_id": "DEM-ATL", "salary": 5_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True}
            for i in range(15)
        ]
        contracts.append(
            {"contract_id": "ct-b00", "player_id": "pl-b00", "team_id": "DEM-PDX", "salary": 5_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True}
        )
        contracts.append(
            {"contract_id": "ct-b01", "player_id": "pl-b01", "team_id": "DEM-PDX", "salary": 5_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True}
        )
        (tmp_dir / "contracts.json").write_text(
            json.dumps({"sample_data": True, "contracts": contracts}), encoding="utf-8"
        )
        # ATL sends 1 (5M), PDX sends 2 (10M). Salary match for ATL: 10M <= 5M*1.25+100k=6.35M? NO.
        # To make salary match, ATL sends 2 (10M), receives 2 (10M).
        # But then ATL roster: 15 - 2 + 2 = 15 (at max, warning not fail).
        # We need > 15. So ATL sends 1, receives 2 -> 16. Salary: incoming 10M <= outgoing 5M*1.25+100k? NO.
        # The salary mismatch FAIL will dominate. That's acceptable: the test
        # asserts roster_full appears among fail codes when roster exceeds max.
        # Let's instead make ATL send a high-salary player so salary matches.
        contracts = [
            {"contract_id": f"ct-a{i:02d}", "player_id": f"pl-a{i:02d}", "team_id": "DEM-ATL", "salary": 5_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True}
            for i in range(15)
        ]
        # Replace one ATL contract with a 20M salary so outgoing 20M can cover incoming 10M*1.25.
        contracts[0] = {"contract_id": "ct-a00", "player_id": "pl-a00", "team_id": "DEM-ATL", "salary": 20_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True}
        contracts.append({"contract_id": "ct-b00", "player_id": "pl-b00", "team_id": "DEM-PDX", "salary": 5_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True})
        contracts.append({"contract_id": "ct-b01", "player_id": "pl-b01", "team_id": "DEM-PDX", "salary": 5_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True})
        (tmp_dir / "contracts.json").write_text(
            json.dumps({"sample_data": True, "contracts": contracts}), encoding="utf-8"
        )
        # ATL sends pl-a00 (20M), receives pl-b00 + pl-b01 (10M total).
        # ATL roster: 15 - 1 + 2 = 16 > 15 -> roster_full FAIL.
        # Salary match ATL: incoming 10M <= 20M*1.25+100k=25.1M OK.
        # Salary match PDX: incoming 20M <= 10M*1.25+100k=12.6M? NO -> mismatch FAIL.
        # So PDX also fails. To avoid that, PDX sends only 1 player worth 20M.
        # But we want ATL to receive 2 to push roster over. Conflict.
        #
        # Simplest robust approach: assert roster_full is in fail codes when
        # it occurs, even if other fails also present. Build a scenario where
        # salary matches for both but ATL goes over roster.
        # ATL: 15 contracts. Send 1 worth 10M. Receive 2 worth 5M each (10M total).
        # ATL roster: 15 - 1 + 2 = 16 > 15 -> roster_full.
        # ATL salary match: 10M <= 10M*1.25+100k OK.
        # PDX: send 2 worth 5M each (10M). Receive 1 worth 10M.
        # PDX salary match: 10M <= 10M*1.25+100k OK.
        contracts = [
            {"contract_id": f"ct-a{i:02d}", "player_id": f"pl-a{i:02d}", "team_id": "DEM-ATL", "salary": 10_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True}
            for i in range(15)
        ]
        contracts.append({"contract_id": "ct-b00", "player_id": "pl-b00", "team_id": "DEM-PDX", "salary": 5_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True})
        contracts.append({"contract_id": "ct-b01", "player_id": "pl-b01", "team_id": "DEM-PDX", "salary": 5_000_000, "years_remaining": 2, "guaranteed": True, "sample_data": True})
        (tmp_dir / "contracts.json").write_text(
            json.dumps({"sample_data": True, "contracts": contracts}), encoding="utf-8"
        )
        tx = TradeTransaction(
            transaction_id="tx-trade-roster-full",
            transaction_type=TransactionType.TWO_TEAM_TRADE,
            team_a_id="DEM-ATL",
            team_b_id="DEM-PDX",
            outgoing_from_a=(_asset("pl-a00", 10_000_000, "DEM-ATL", "DEM-PDX"),),
            outgoing_from_b=(
                _asset("pl-b00", 5_000_000, "DEM-PDX", "DEM-ATL"),
                _asset("pl-b01", 5_000_000, "DEM-PDX", "DEM-ATL"),
            ),
            evidence_ids=(),
        )
        result = validate_trade(tx, tmp_dir)
        assert result.status is ValidationStatus.FAIL
        codes = {i.code for i in result.issues if i.severity is IssueSeverity.FAIL}
        assert "roster_full" in codes


# --------------------------------------------------------------------------- #
# 14. validate_transaction dispatches correctly
# --------------------------------------------------------------------------- #


def test_validate_transaction_dispatches_for_signing() -> None:
    tx = _minimum_signing("tx-dispatch-signing", salary=1_000_000)
    result = validate_transaction(tx, DATA_DIR)
    assert result.transaction_type is TransactionType.MINIMUM_SIGNING
    assert result.transaction_id == "tx-dispatch-signing"


def test_validate_transaction_dispatches_for_trade() -> None:
    tx = TradeTransaction(
        transaction_id="tx-dispatch-trade",
        transaction_type=TransactionType.TWO_TEAM_TRADE,
        team_a_id="DEM-ATL",
        team_b_id="DEM-PDX",
        outgoing_from_a=(_asset("pl-001", 28_000_000, "DEM-ATL", "DEM-PDX"),),
        outgoing_from_b=(_asset("pl-005", 30_000_000, "DEM-PDX", "DEM-ATL"),),
        evidence_ids=(),
    )
    result = validate_transaction(tx, DATA_DIR)
    assert result.transaction_type is TransactionType.TWO_TEAM_TRADE


def test_validate_transaction_rejects_unsupported_type() -> None:
    with pytest.raises(TransactionRuleEngineError):
        validate_transaction("not-a-transaction", DATA_DIR)  # type: ignore[arg-type]


def test_validate_signing_rejects_trade_type() -> None:
    tx = TradeTransaction(
        transaction_id="tx-bad",
        transaction_type=TransactionType.TWO_TEAM_TRADE,
        team_a_id="DEM-ATL",
        team_b_id="DEM-PDX",
        outgoing_from_a=(_asset("pl-001", 28_000_000, "DEM-ATL", "DEM-PDX"),),
        outgoing_from_b=(_asset("pl-005", 30_000_000, "DEM-PDX", "DEM-ATL"),),
        evidence_ids=(),
    )
    with pytest.raises(TransactionRuleEngineError):
        validate_signing(tx, DATA_DIR)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# 15. validation result always requires human approval
# --------------------------------------------------------------------------- #


def test_validation_result_always_requires_human_approval() -> None:
    # Even a clean PASS must still require human approval.
    tx = _minimum_signing("tx-approval", salary=1_000_000)
    result = validate_signing(tx, DATA_DIR)
    assert result.requires_human_approval is True
    # And a FAIL also requires it.
    bad_tx = _minimum_signing("tx-approval-bad", salary=5_000_000)
    bad_result = validate_signing(bad_tx, DATA_DIR)
    assert bad_result.requires_human_approval is True
    # And trades.
    trade = TradeTransaction(
        transaction_id="tx-approval-trade",
        transaction_type=TransactionType.TWO_TEAM_TRADE,
        team_a_id="DEM-ATL",
        team_b_id="DEM-PDX",
        outgoing_from_a=(_asset("pl-001", 28_000_000, "DEM-ATL", "DEM-PDX"),),
        outgoing_from_b=(_asset("pl-005", 30_000_000, "DEM-PDX", "DEM-ATL"),),
        evidence_ids=(),
    )
    trade_result = validate_trade(trade, DATA_DIR)
    assert trade_result.requires_human_approval is True


# --------------------------------------------------------------------------- #
# 16. transaction_rule_engine does not mutate data/contracts.json
# --------------------------------------------------------------------------- #


def test_rule_engine_does_not_mutate_contracts_json() -> None:
    contracts_path = DATA_DIR / "contracts.json"
    before = contracts_path.read_bytes()
    # Run several validations.
    validate_signing(_minimum_signing("tx-mut-1", salary=1_000_000), DATA_DIR)
    validate_signing(_mle_signing("tx-mut-2", salary=10_000_000), DATA_DIR)
    trade = TradeTransaction(
        transaction_id="tx-mut-3",
        transaction_type=TransactionType.TWO_TEAM_TRADE,
        team_a_id="DEM-ATL",
        team_b_id="DEM-PDX",
        outgoing_from_a=(_asset("pl-001", 28_000_000, "DEM-ATL", "DEM-PDX"),),
        outgoing_from_b=(_asset("pl-005", 30_000_000, "DEM-PDX", "DEM-ATL"),),
        evidence_ids=(),
    )
    validate_trade(trade, DATA_DIR)
    after = contracts_path.read_bytes()
    assert before == after, "rule engine must not mutate data/contracts.json"


def test_validation_result_structure_has_all_required_fields() -> None:
    tx = _minimum_signing("tx-structure", salary=1_000_000)
    result = validate_signing(tx, DATA_DIR)
    required = [
        "transaction_id",
        "transaction_type",
        "status",
        "is_valid",
        "issues",
        "warnings",
        "cap_summary_before",
        "cap_summary_after",
        "evidence_ids",
        "requires_human_approval",
        "limitations",
    ]
    for name in required:
        assert hasattr(result, name), f"ValidationResult missing field {name}"
    assert isinstance(result.issues, tuple)
    assert isinstance(result.warnings, tuple)
    assert isinstance(result.evidence_ids, tuple)
    assert isinstance(result.limitations, tuple)
    assert len(result.limitations) > 0  # MVP limitations must be documented


def test_evidence_ids_are_echoed_back() -> None:
    tx = SigningTransaction(
        transaction_id="tx-evidence",
        transaction_type=TransactionType.MINIMUM_SIGNING,
        team_id="DEM-ATL",
        player_id="fa-001",
        salary=1_000_000,
        years=1,
        evidence_ids=("ev-001", "ev-003"),
    )
    result = validate_signing(tx, DATA_DIR)
    assert result.evidence_ids == ("ev-001", "ev-003")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
