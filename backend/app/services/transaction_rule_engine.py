"""Transaction rule engine.

Responsibility: deterministic validation of signings and trades.
Returns ``TransactionValidationResult`` with a clear verdict and reason
codes. The agent layer is **not** allowed to declare transactions valid;
only this engine can.

Milestone: M2. This module is intentionally a placeholder in M1.

M1 boundary:

- ``cap_sheet_service`` (M1) computes cap math and exposes
  ``apply_signing_preview`` for previewing a signing's cap impact.
- This engine (M2) will consume a ``TeamCapSheet`` /
  ``CapSheetSummary`` plus a ``TransactionProposal`` and return a
  deterministic verdict (valid / invalid + reason codes).
- M1 does NOT implement any signing/trade legality logic here. M1 only
  clarifies this boundary so the cap sheet service can stay focused on
  math.

Planned M2 surface:

- ``validate_signing(proposal, cap_sheet) -> TransactionValidationResult``
- ``validate_trade(proposal, cap_sheet_a, cap_sheet_b) -> TransactionValidationResult``
- reason codes: ``cap_space_insufficient``, ``salary_mismatch``,
  ``roster_full``, ``missing_contract``, ``apron_breached``.
- The engine never mutates state; it only returns verdicts.
"""

# TODO(M2): implement validate_signing(proposal, cap_sheet) -> ValidationResult.
# TODO(M2): implement validate_trade(proposal, cap_sheet_a, cap_sheet_b) -> ValidationResult.
# TODO(M2): reason codes: cap_space_insufficient, salary_mismatch,
#           roster_full, missing_contract, apron_breached.
# TODO(M2): ensure this module never mutates state; it only returns verdicts.
