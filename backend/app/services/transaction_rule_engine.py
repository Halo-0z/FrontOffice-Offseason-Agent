"""Transaction rule engine.

Responsibility: deterministic validation of signings and trades.
Returns ``TransactionValidationResult`` with a clear verdict and reason
codes. The agent layer is **not** allowed to declare transactions valid;
only this engine can.

Milestone: M2.

M0 scope: docstring + TODO only.
"""

# TODO(M2): implement validate_signing(proposal, cap_sheet) -> ValidationResult.
# TODO(M2): implement validate_trade(proposal, cap_sheet_a, cap_sheet_b) -> ValidationResult.
# TODO(M2): reason codes: cap_space_insufficient, salary_mismatch,
#           roster_full, missing_contract, apron_breached.
# TODO(M2): ensure this module never mutates state; it only returns verdicts.
