"""Transaction rule engine (M2).

Deterministic validation of demo-level signings and simple two-team
trades. This is the single entry point that decides whether a proposed
transaction is legal under the MVP rules. The agent layer is **not**
allowed to declare transactions valid; only this engine can.

Guardrails:

- No LLM calls. No network. No disk writes.
- Never mutates ``data/contracts.json`` or any other state. All
  previews are computed on fresh in-memory ``TeamCapSheet`` objects
  built by ``cap_sheet_service.apply_signing_preview``.
- Every ``ValidationResult`` has ``requires_human_approval=True``.
- A ``WARNING`` status does not block the proposal; only ``FAIL`` does.

MVP rule summary (NOT the real NBA CBA):

Signing rules:

- ``MINIMUM_SIGNING``: PASS iff ``salary <= cap_config.minimum_salary``.
- ``MLE_SIGNING``     : PASS iff ``salary <= cap_config.mid_level_exception``.
- ``SIMPLE_FA_SIGNING``: PASS iff the post-signing ``total_salary``
  stays ``<= salary_cap``. Going over cap on a simple FA signing is a
  FAIL (use an exception type instead).
- Roster slot: post-signing ``roster_count > roster_max`` is a FAIL.
  ``roster_count == roster_max`` after the signing is a WARNING.
- Apron warnings: crossing ``luxury_tax`` / ``first_apron`` /
  ``second_apron`` produces WARNING issues (not FAIL) in M2.

Trade rules (two-team only):

- ``transaction_type`` must be ``TWO_TEAM_TRADE``.
- Both teams must exist in ``teams.json``.
- ``outgoing_from_a`` and ``outgoing_from_b`` must be non-empty.
- Salary matching (simplified): for each team, ``incoming_salary``
  must be ``<= outgoing_salary * 1.25 + 100_000``. Otherwise FAIL.
- Roster slot: post-trade ``roster_count > roster_max`` for either
  team is a FAIL.
- Apron warnings are emitted for each team that crosses a line.

Run tests:

    python -m pytest backend/app/tests/test_transaction_rule_engine.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple, Union

from ..models.cap import (
    CapSheetSummary,
    PlayerContract,
    TeamCapSheet,
)
from ..models.transaction import (
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
from .cap_sheet_service import (
    CapSheetError,
    TeamNotFoundError,
    apply_signing_preview,
    load_team_cap_sheet,
    summarize_cap_sheet,
)


# --------------------------------------------------------------------------- #
# Public errors
# --------------------------------------------------------------------------- #


class TransactionRuleEngineError(Exception):
    """Base class for rule engine errors (distinct from validation FAIL)."""


# --------------------------------------------------------------------------- #
# Constants / MVP limitations
# --------------------------------------------------------------------------- #

_MVP_LIMITATIONS: Tuple[str, ...] = (
    "MVP salary matching rule: incoming <= outgoing * 1.25 + 100000. Not the real NBA CBA.",
    "Apron hard caps are NOT enforced in M2; apron crossings are warnings only.",
    "No Bird rights, no sign-and-trade rules, no draft-pick value rules in M2.",
    "Only two-team trades are supported.",
)

# Salary matching tolerance for the MVP trade rule.
_SALARY_MATCH_FACTOR = 1.25
_SALARY_MATCH_TOLERANCE = 100_000


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _issue(code: str, message: str, severity: IssueSeverity, field: str | None = None) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, severity=severity, field=field)


def _aggregate_status(issues: Iterable[ValidationIssue]) -> Tuple[ValidationStatus, bool, Tuple[ValidationIssue, ...]]:
    """Compute (status, is_valid, warnings) from a list of issues."""
    issues_t = tuple(issues)
    has_fail = any(i.severity is IssueSeverity.FAIL for i in issues_t)
    warnings = tuple(i for i in issues_t if i.severity is IssueSeverity.WARNING)
    if has_fail:
        status = ValidationStatus.FAIL
    elif warnings:
        status = ValidationStatus.WARNING
    else:
        status = ValidationStatus.PASS
    return status, (not has_fail), warnings


def _build_apron_warnings(
    summary_before: CapSheetSummary,
    summary_after: CapSheetSummary,
    team_label: str,
) -> List[ValidationIssue]:
    """Emit WARNING issues for each apron/tax line crossed by the transaction.

    A line is "crossed" if the signed distance went from non-negative
    (team was under the line) to negative (team is now over the line).
    """
    out: List[ValidationIssue] = []
    pairs = [
        ("luxury_tax", summary_before.tax_distance, summary_after.tax_distance),
        ("first_apron", summary_before.first_apron_distance, summary_after.first_apron_distance),
        ("second_apron", summary_before.second_apron_distance, summary_after.second_apron_distance),
    ]
    for label, before_dist, after_dist in pairs:
        was_under = before_dist >= 0
        now_over = after_dist < 0
        if was_under and now_over:
            out.append(
                _issue(
                    code=f"apron_crossed:{label}",
                    message=(
                        f"{team_label} crosses the {label} line as a result of this "
                        f"transaction (distance before={before_dist}, after={after_dist})."
                    ),
                    severity=IssueSeverity.WARNING,
                    field=label,
                )
            )
    return out


def _validate_roster_slots(
    roster_count_before: int,
    roster_count_after: int,
    roster_max: int,
    team_label: str,
) -> List[ValidationIssue]:
    """Roster slot checks. Over max is FAIL; at max after the move is WARNING."""
    out: List[ValidationIssue] = []
    if roster_count_after > roster_max:
        out.append(
            _issue(
                code="roster_full",
                message=(
                    f"{team_label} roster_count={roster_count_after} exceeds "
                    f"roster_max={roster_max}."
                ),
                severity=IssueSeverity.FAIL,
                field="roster_count",
            )
        )
    elif roster_count_after == roster_max:
        out.append(
            _issue(
                code="roster_at_max",
                message=(
                    f"{team_label} roster_count={roster_count_after} is at "
                    f"roster_max={roster_max}; no further signings allowed."
                ),
                severity=IssueSeverity.WARNING,
                field="roster_count",
            )
        )
    return out


def _salary_matching_ok(
    outgoing_salary: int, incoming_salary: int
) -> bool:
    """MVP salary matching: incoming <= outgoing * 1.25 + 100_000."""
    return incoming_salary <= outgoing_salary * _SALARY_MATCH_FACTOR + _SALARY_MATCH_TOLERANCE


def _make_contract_from_signing(tx: SigningTransaction) -> PlayerContract:
    """Build a preview ``PlayerContract`` from a signing transaction."""
    return PlayerContract(
        contract_id=f"{tx.transaction_id}-preview",
        player_id=tx.player_id,
        team_id=tx.team_id,
        salary=tx.salary,
        years_remaining=max(tx.years - 1, 0),
        guaranteed=True,
        sample_data=tx.sample_data,
    )


# --------------------------------------------------------------------------- #
# Signing validation
# --------------------------------------------------------------------------- #


def validate_signing(
    transaction: SigningTransaction, data_dir: Path | str = "data"
) -> ValidationResult:
    """Validate a signing transaction against the MVP rules."""
    if transaction.transaction_type is TransactionType.TWO_TEAM_TRADE:
        raise TransactionRuleEngineError(
            "validate_signing received a TWO_TEAM_TRADE; use validate_trade instead."
        )

    issues: List[ValidationIssue] = []

    # Load the team cap sheet (raises TeamNotFoundError for unknown teams).
    try:
        sheet = load_team_cap_sheet(transaction.team_id, data_dir)
    except TeamNotFoundError as exc:
        issues.append(
            _issue(
                code="team_not_found",
                message=str(exc),
                severity=IssueSeverity.FAIL,
                field="team_id",
            )
        )
        return ValidationResult(
            transaction_id=transaction.transaction_id,
            transaction_type=transaction.transaction_type,
            status=ValidationStatus.FAIL,
            is_valid=False,
            issues=tuple(issues),
            warnings=(),
            cap_summary_before=None,
            cap_summary_after=None,
            evidence_ids=transaction.evidence_ids,
            requires_human_approval=True,
            limitations=_MVP_LIMITATIONS,
        )

    cfg = sheet.cap_config
    summary_before = summarize_cap_sheet(sheet)

    # --- Type-specific salary rule ---------------------------------------- #
    ttype = transaction.transaction_type
    if ttype is TransactionType.MINIMUM_SIGNING:
        if transaction.salary > cfg.minimum_salary:
            issues.append(
                _issue(
                    code="minimum_salary_exceeded",
                    message=(
                        f"MINIMUM_SIGNING salary={transaction.salary} exceeds "
                        f"minimum_salary={cfg.minimum_salary}."
                    ),
                    severity=IssueSeverity.FAIL,
                    field="salary",
                )
            )
    elif ttype is TransactionType.MLE_SIGNING:
        if transaction.salary > cfg.mid_level_exception:
            issues.append(
                _issue(
                    code="mle_exceeded",
                    message=(
                        f"MLE_SIGNING salary={transaction.salary} exceeds "
                        f"mid_level_exception={cfg.mid_level_exception}."
                    ),
                    severity=IssueSeverity.FAIL,
                    field="salary",
                )
            )
    elif ttype is TransactionType.SIMPLE_FA_SIGNING:
        # Simple FA must stay under the cap.
        projected_total = summary_before.total_salary + transaction.salary
        if projected_total > cfg.salary_cap:
            issues.append(
                _issue(
                    code="cap_space_insufficient",
                    message=(
                        f"SIMPLE_FA_SIGNING projected total_salary={projected_total} "
                        f"exceeds salary_cap={cfg.salary_cap}. Use an exception type."
                    ),
                    severity=IssueSeverity.FAIL,
                    field="salary",
                )
            )
    else:
        issues.append(
            _issue(
                code="unknown_signing_type",
                message=f"Unknown signing type: {ttype!r}",
                severity=IssueSeverity.FAIL,
                field="transaction_type",
            )
        )

    # --- Build preview sheet & summary ------------------------------------ #
    preview_contract = _make_contract_from_signing(transaction)
    preview_sheet = apply_signing_preview(sheet, preview_contract)
    summary_after = summarize_cap_sheet(preview_sheet)

    # --- Roster slot checks ---------------------------------------------- #
    issues.extend(
        _validate_roster_slots(
            roster_count_before=summary_before.roster_count,
            roster_count_after=summary_after.roster_count,
            roster_max=cfg.roster_max,
            team_label=transaction.team_id,
        )
    )

    # --- Apron warnings -------------------------------------------------- #
    issues.extend(
        _build_apron_warnings(summary_before, summary_after, transaction.team_id)
    )

    status, is_valid, warnings = _aggregate_status(issues)
    return ValidationResult(
        transaction_id=transaction.transaction_id,
        transaction_type=transaction.transaction_type,
        status=status,
        is_valid=is_valid,
        issues=tuple(issues),
        warnings=warnings,
        cap_summary_before=summary_before,
        cap_summary_after=summary_after,
        evidence_ids=transaction.evidence_ids,
        requires_human_approval=True,
        limitations=_MVP_LIMITATIONS,
    )


# --------------------------------------------------------------------------- #
# Trade validation
# --------------------------------------------------------------------------- #


def validate_trade(
    transaction: TradeTransaction, data_dir: Path | str = "data"
) -> ValidationResult:
    """Validate a two-team trade against the MVP rules."""
    if transaction.transaction_type is not TransactionType.TWO_TEAM_TRADE:
        raise TransactionRuleEngineError(
            "validate_trade requires transaction_type=TWO_TEAM_TRADE."
        )

    issues: List[ValidationIssue] = []

    # --- Team existence -------------------------------------------------- #
    team_ids: set[str] = set()
    try:
        from .cap_sheet_service import _load_team_ids
        team_ids = _load_team_ids(data_dir)
    except CapSheetError as exc:
        issues.append(
            _issue(
                code="data_error",
                message=str(exc),
                severity=IssueSeverity.FAIL,
                field="data_dir",
            )
        )

    for tid, label in ((transaction.team_a_id, "team_a_id"), (transaction.team_b_id, "team_b_id")):
        if tid not in team_ids:
            issues.append(
                _issue(
                    code="team_not_found",
                    message=f"{label}={tid!r} not found in teams.json; known={sorted(team_ids)}",
                    severity=IssueSeverity.FAIL,
                    field=label,
                )
            )

    # --- Non-empty outgoing assets --------------------------------------- #
    if not transaction.outgoing_from_a:
        issues.append(
            _issue(
                code="empty_outgoing",
                message="outgoing_from_a must be non-empty.",
                severity=IssueSeverity.FAIL,
                field="outgoing_from_a",
            )
        )
    if not transaction.outgoing_from_b:
        issues.append(
            _issue(
                code="empty_outgoing",
                message="outgoing_from_b must be non-empty.",
                severity=IssueSeverity.FAIL,
                field="outgoing_from_b",
            )
        )

    # --- Salary matching ------------------------------------------------- #
    out_a_salary = sum(a.salary for a in transaction.outgoing_from_a)
    out_b_salary = sum(a.salary for a in transaction.outgoing_from_b)
    # incoming for A = outgoing from B, and vice versa.
    in_a_salary = out_b_salary
    in_b_salary = out_a_salary

    if not _salary_matching_ok(outgoing_salary=out_a_salary, incoming_salary=in_a_salary):
        issues.append(
            _issue(
                code="salary_mismatch",
                message=(
                    f"Team A salary mismatch: incoming={in_a_salary} > "
                    f"outgoing*1.25+100000={int(out_a_salary * _SALARY_MATCH_FACTOR) + _SALARY_MATCH_TOLERANCE}."
                ),
                severity=IssueSeverity.FAIL,
                field="outgoing_from_a",
            )
        )
    if not _salary_matching_ok(outgoing_salary=out_b_salary, incoming_salary=in_b_salary):
        issues.append(
            _issue(
                code="salary_mismatch",
                message=(
                    f"Team B salary mismatch: incoming={in_b_salary} > "
                    f"outgoing*1.25+100000={int(out_b_salary * _SALARY_MATCH_FACTOR) + _SALARY_MATCH_TOLERANCE}."
                ),
                severity=IssueSeverity.FAIL,
                field="outgoing_from_b",
            )
        )

    # --- Roster slot + apron previews ------------------------------------ #
    # Only compute if both teams loaded successfully.
    cap_summary_before: CapSheetSummary | None = None
    cap_summary_after: CapSheetSummary | None = None
    if transaction.team_a_id in team_ids and transaction.team_b_id in team_ids:
        try:
            sheet_a = load_team_cap_sheet(transaction.team_a_id, data_dir)
            sheet_b = load_team_cap_sheet(transaction.team_b_id, data_dir)
            cfg = sheet_a.cap_config
            cap_summary_before = summarize_cap_sheet(sheet_a)

            # Build preview sheets: remove outgoing, add incoming.
            out_a_ids = {a.player_id for a in transaction.outgoing_from_a}
            out_b_ids = {a.player_id for a in transaction.outgoing_from_b}

            kept_a = tuple(c for c in sheet_a.contracts if c.player_id not in out_a_ids)
            kept_b = tuple(c for c in sheet_b.contracts if c.player_id not in out_b_ids)

            # Incoming contracts become new PlayerContract objects on the
            # receiving team. We reuse the salary from the asset.
            incoming_to_a = tuple(
                PlayerContract(
                    contract_id=f"{transaction.transaction_id}-in-{a.player_id}",
                    player_id=a.player_id,
                    team_id=transaction.team_a_id,
                    salary=a.salary,
                    years_remaining=0,
                    guaranteed=True,
                    sample_data=True,
                )
                for a in transaction.outgoing_from_b
            )
            incoming_to_b = tuple(
                PlayerContract(
                    contract_id=f"{transaction.transaction_id}-in-{a.player_id}",
                    player_id=a.player_id,
                    team_id=transaction.team_b_id,
                    salary=a.salary,
                    years_remaining=0,
                    guaranteed=True,
                    sample_data=True,
                )
                for a in transaction.outgoing_from_a
            )

            preview_a = TeamCapSheet(
                team_id=transaction.team_a_id,
                season=sheet_a.season,
                cap_config=cfg,
                contracts=(*kept_a, *incoming_to_a),
            )
            preview_b = TeamCapSheet(
                team_id=transaction.team_b_id,
                season=sheet_b.season,
                cap_config=cfg,
                contracts=(*kept_b, *incoming_to_b),
            )

            summary_a_before = summarize_cap_sheet(sheet_a)
            summary_a_after = summarize_cap_sheet(preview_a)
            summary_b_before = summarize_cap_sheet(sheet_b)
            summary_b_after = summarize_cap_sheet(preview_b)

            cap_summary_after = summary_a_after

            issues.extend(
                _validate_roster_slots(
                    roster_count_before=summary_a_before.roster_count,
                    roster_count_after=summary_a_after.roster_count,
                    roster_max=cfg.roster_max,
                    team_label=transaction.team_a_id,
                )
            )
            issues.extend(
                _validate_roster_slots(
                    roster_count_before=summary_b_before.roster_count,
                    roster_count_after=summary_b_after.roster_count,
                    roster_max=cfg.roster_max,
                    team_label=transaction.team_b_id,
                )
            )
            issues.extend(
                _build_apron_warnings(summary_a_before, summary_a_after, transaction.team_a_id)
            )
            issues.extend(
                _build_apron_warnings(summary_b_before, summary_b_after, transaction.team_b_id)
            )
        except TeamNotFoundError as exc:
            issues.append(
                _issue(
                    code="team_not_found",
                    message=str(exc),
                    severity=IssueSeverity.FAIL,
                    field="team_id",
                )
            )
        except CapSheetError as exc:
            issues.append(
                _issue(
                    code="data_error",
                    message=str(exc),
                    severity=IssueSeverity.FAIL,
                    field="data_dir",
                )
            )

    status, is_valid, warnings = _aggregate_status(issues)
    return ValidationResult(
        transaction_id=transaction.transaction_id,
        transaction_type=transaction.transaction_type,
        status=status,
        is_valid=is_valid,
        issues=tuple(issues),
        warnings=warnings,
        cap_summary_before=cap_summary_before,
        cap_summary_after=cap_summary_after,
        evidence_ids=transaction.evidence_ids,
        requires_human_approval=True,
        limitations=_MVP_LIMITATIONS,
    )


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #


def validate_transaction(
    transaction: Union[SigningTransaction, TradeTransaction],
    data_dir: Path | str = "data",
) -> ValidationResult:
    """Dispatch to ``validate_signing`` or ``validate_trade`` by type."""
    if isinstance(transaction, SigningTransaction):
        return validate_signing(transaction, data_dir)
    if isinstance(transaction, TradeTransaction):
        return validate_trade(transaction, data_dir)
    raise TransactionRuleEngineError(
        f"Unsupported transaction type: {type(transaction).__name__}"
    )
