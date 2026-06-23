"""Transaction models for the M2 transaction rule engine.

These are DEMO/SAMPLE/SIMULATION models. They implement a deliberately
simplified subset of NBA-style transaction rules. They are NOT a
complete reimplementation of the NBA CBA.

All dataclasses are frozen so that callers (including the future agent
layer) cannot mutate transaction state in place. The rule engine
returns new ``ValidationResult`` instances and never writes to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class TransactionType(str, Enum):
    """Kind of transaction the rule engine is validating."""

    MINIMUM_SIGNING = "MINIMUM_SIGNING"
    MLE_SIGNING = "MLE_SIGNING"
    SIMPLE_FA_SIGNING = "SIMPLE_FA_SIGNING"
    TWO_TEAM_TRADE = "TWO_TEAM_TRADE"


class ValidationStatus(str, Enum):
    """Overall status of a ``ValidationResult``.

    - ``PASS``: no issues and no warnings.
    - ``WARNING``: no fail-severity issues, but at least one warning.
    - ``FAIL``: at least one fail-severity issue.
    """

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class IssueSeverity(str, Enum):
    """Severity of a single ``ValidationIssue``."""

    WARNING = "WARNING"
    FAIL = "FAIL"


class AssetType(str, Enum):
    """Kind of asset exchanged in a trade."""

    PLAYER_CONTRACT = "PLAYER_CONTRACT"
    CASH = "CASH"
    DRAFT_PICK = "DRAFT_PICK"


# --------------------------------------------------------------------------- #
# Assets & transactions
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class TransactionAsset:
    """A single asset moving in a trade.

    Attributes:
        player_id: Player identifier (required for PLAYER_CONTRACT).
        contract_id: Optional contract identifier.
        salary: Salary cap hit attached to this asset (USD). Required
            for salary matching; for non-contract assets use 0.
        from_team_id: Team sending the asset.
        to_team_id: Team receiving the asset.
        asset_type: Kind of asset.
    """

    player_id: str
    contract_id: Optional[str] = None
    salary: int = 0
    from_team_id: Optional[str] = None
    to_team_id: Optional[str] = None
    asset_type: AssetType = AssetType.PLAYER_CONTRACT


@dataclass(frozen=True)
class SigningTransaction:
    """A signing proposal (minimum / MLE / simple FA).

    Attributes:
        transaction_id: Stable transaction identifier.
        transaction_type: One of the signing ``TransactionType`` values.
        team_id: Team making the signing.
        player_id: Player being signed.
        salary: First-season salary (cap hit).
        years: Total years of the new contract.
        evidence_ids: Evidence supporting this proposal.
        requires_human_approval: Always True in M2; the agent cannot
            bypass human approval.
        sample_data: True if this is demo/sample/simulation data.
    """

    transaction_id: str
    transaction_type: TransactionType
    team_id: str
    player_id: str
    salary: int
    years: int
    evidence_ids: Tuple[str, ...] = field(default_factory=tuple)
    requires_human_approval: bool = True
    sample_data: bool = True


@dataclass(frozen=True)
class TradeTransaction:
    """A two-team trade proposal.

    Attributes:
        transaction_id: Stable transaction identifier.
        transaction_type: Must be ``TWO_TEAM_TRADE``.
        team_a_id: First team.
        team_b_id: Second team.
        outgoing_from_a: Assets leaving team A (going to team B).
        outgoing_from_b: Assets leaving team B (going to team A).
        evidence_ids: Evidence supporting this proposal.
        requires_human_approval: Always True in M2.
        sample_data: True if this is demo/sample/simulation data.
    """

    transaction_id: str
    transaction_type: TransactionType
    team_a_id: str
    team_b_id: str
    outgoing_from_a: Tuple[TransactionAsset, ...] = field(default_factory=tuple)
    outgoing_from_b: Tuple[TransactionAsset, ...] = field(default_factory=tuple)
    evidence_ids: Tuple[str, ...] = field(default_factory=tuple)
    requires_human_approval: bool = True
    sample_data: bool = True


# --------------------------------------------------------------------------- #
# Validation result
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ValidationIssue:
    """A single issue raised by the rule engine.

    Attributes:
        code: Stable machine-readable code, e.g. ``cap_space_insufficient``.
        message: Human-readable explanation.
        severity: ``WARNING`` or ``FAIL``.
        field: Optional field name the issue applies to.
    """

    code: str
    message: str
    severity: IssueSeverity
    field: Optional[str] = None


@dataclass(frozen=True)
class ValidationResult:
    """Deterministic verdict for a transaction.

    Attributes:
        transaction_id: Transaction this result applies to.
        transaction_type: Transaction type.
        status: Overall ``ValidationStatus``.
        is_valid: True if there are no FAIL-severity issues.
        issues: All issues (warnings + fails), in insertion order.
        warnings: Convenience tuple of warning-severity issues.
        cap_summary_before: Cap summary of the acting team(s) before the
            transaction. For trades, this is team A's summary.
        cap_summary_after: Optional cap summary after the transaction.
            For trades, this is team A's post-trade summary.
        evidence_ids: Evidence ids echoed back from the transaction.
        requires_human_approval: Always True in M2.
        limitations: Notes about MVP simplifications.
    """

    transaction_id: str
    transaction_type: TransactionType
    status: ValidationStatus
    is_valid: bool
    issues: Tuple[ValidationIssue, ...] = field(default_factory=tuple)
    warnings: Tuple[ValidationIssue, ...] = field(default_factory=tuple)
    cap_summary_before: Optional[object] = None
    cap_summary_after: Optional[object] = None
    evidence_ids: Tuple[str, ...] = field(default_factory=tuple)
    requires_human_approval: bool = True
    limitations: Tuple[str, ...] = field(default_factory=tuple)
