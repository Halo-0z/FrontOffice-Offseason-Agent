"""Evaluation models for FrontOffice-Offseason-Agent (M4-D).

These are DEMO/SAMPLE/SIMULATION models. They represent the structured
result of a deterministic evaluation of an M4-C ``StructuredProposal``.
They are **not** approvals, **not** LLM judgments, and **not** MCP
payloads.

All dataclasses are frozen so callers cannot mutate the evaluation in
place. The ``proposal_evaluator`` returns new instances and never
writes to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class EvaluationStatus(str, Enum):
    """Overall status of a ``ProposalEvaluation``.

    - ``PASS``: no ERROR-severity issues. The proposal is safe to
      surface (still requires human approval — evaluation never
      approves anything).
    - ``WARNING``: no ERROR-severity issues, but at least one
      WARNING-severity issue.
    - ``FAIL``: at least one ERROR-severity issue. The proposal has a
      guardrail violation that must be fixed before surfacing.
    """

    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class EvaluationSeverity(str, Enum):
    """Severity of a single ``EvaluationIssue``.

    - ``INFO``: informational note (e.g. sample_data_only).
    - ``WARNING``: notable concern that does not block surfacing.
    - ``ERROR``: guardrail violation that blocks surfacing.
    """

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class EvaluationIssueCode(str, Enum):
    """Stable machine-readable code for an ``EvaluationIssue``.

    - ``missing_human_approval``: a proposal or action is missing the
      ``requires_human_approval=True`` invariant.
    - ``approved_without_validation``: an action is marked
      ``is_valid=True`` but its ``validation_status`` is ``FAIL`` (or
      otherwise inconsistent).
    - ``invalid_action_recommended``: the proposal status is
      ``RECOMMENDED`` but no action is actually valid, or an invalid
      signing action is being recommended.
    - ``missing_tool_trace``: the ``tool_call_trace`` is missing one
      or more required key tools.
    - ``missing_evidence``: the proposal is ``RECOMMENDED`` but has
      no ``evidence_refs``, or a fallback mentions missing evidence
      without a corresponding risk.
    - ``sample_data_only``: the proposal is built from sample data
      (informational; always emitted as INFO).
    - ``no_action_fallback``: the proposal is ``NO_ACTION`` but has
      no HOLD action and no ``no_matching_candidate`` risk.
    - ``no_mutation_guardrail``: reserved for mutation guardrail
      violations (emitted by tests, not by the evaluator itself).
    - ``missing_risk_for_fallback``: ``fallback_reasons`` is non-empty
      but no corresponding risk or limitation is present.
    - ``non_deterministic_output``: reserved for determinism
      violations (emitted by scenario tests, not by the evaluator
      itself).
    """

    missing_human_approval = "missing_human_approval"
    approved_without_validation = "approved_without_validation"
    invalid_action_recommended = "invalid_action_recommended"
    missing_tool_trace = "missing_tool_trace"
    missing_evidence = "missing_evidence"
    sample_data_only = "sample_data_only"
    no_action_fallback = "no_action_fallback"
    no_mutation_guardrail = "no_mutation_guardrail"
    missing_risk_for_fallback = "missing_risk_for_fallback"
    non_deterministic_output = "non_deterministic_output"


# --------------------------------------------------------------------------- #
# Issue
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EvaluationIssue:
    """A single issue raised by the evaluator.

    Attributes:
        code: Stable ``EvaluationIssueCode`` (or string).
        severity: ``INFO`` / ``WARNING`` / ``ERROR``.
        summary: Short deterministic explanation.
        action_id: Optional action id this issue applies to.
        evidence_ids: Evidence ids relevant to this issue (may be empty).
        remediation: Short deterministic remediation suggestion.
    """

    code: EvaluationIssueCode
    severity: EvaluationSeverity
    summary: str
    action_id: Optional[str] = None
    evidence_ids: Tuple[str, ...] = field(default_factory=tuple)
    remediation: str = ""


# --------------------------------------------------------------------------- #
# Evaluation result
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProposalEvaluation:
    """Structured evaluation of a ``StructuredProposal``.

    All fields are immutable. ``sample_data`` is always ``True``.

    Attributes:
        proposal_id: Echoed from the evaluated proposal.
        team_id: Echoed from the evaluated proposal.
        status: ``PASS`` / ``WARNING`` / ``FAIL``.
        issues: All issues (info + warnings + errors), in insertion
            order.
        passed_checks: Tuple of check names that passed.
        failed_checks: Tuple of check names that failed (ERROR only).
        warnings: Tuple of check names that produced warnings.
        limitations: MVP limitation notes.
        sample_data: Always ``True``.
    """

    proposal_id: str
    team_id: str
    status: EvaluationStatus
    issues: Tuple[EvaluationIssue, ...] = field(default_factory=tuple)
    passed_checks: Tuple[str, ...] = field(default_factory=tuple)
    failed_checks: Tuple[str, ...] = field(default_factory=tuple)
    warnings: Tuple[str, ...] = field(default_factory=tuple)
    limitations: Tuple[str, ...] = field(default_factory=tuple)
    sample_data: bool = True


# --------------------------------------------------------------------------- #
# Scenario models
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class EvaluationScenario:
    """A fixed demo scenario for regression evaluation.

    Attributes:
        scenario_id: Stable scenario identifier.
        description: Short human-readable description.
        goal: The ``OffseasonGoal`` to run.
        expected_statuses: Tuple of acceptable ``ProposalStatus`` values
            for the built proposal.
        expected_min_actions: Minimum number of actions the proposal
            must have.
        expected_risk_codes: Risk codes that must appear in the
            proposal's ``risks`` tuple.
        sample_data: Always ``True``.
    """

    scenario_id: str
    description: str
    goal: object  # OffseasonGoal, typed as object to avoid import cycle
    expected_statuses: Tuple[str, ...] = field(default_factory=tuple)
    expected_min_actions: int = 0
    expected_risk_codes: Tuple[str, ...] = field(default_factory=tuple)
    sample_data: bool = True


@dataclass(frozen=True)
class EvaluationScenarioResult:
    """Result of running one ``EvaluationScenario``.

    Attributes:
        scenario_id: Echoed from the scenario.
        proposal: The ``StructuredProposal`` built from the scenario's
            goal.
        evaluation: The ``ProposalEvaluation`` of the proposal.
        status: ``PASS`` / ``WARNING`` / ``FAIL`` — derived from the
            evaluation status and the scenario's expected constraints.
        limitations: MVP limitation notes.
    """

    scenario_id: str
    proposal: object  # StructuredProposal
    evaluation: object  # ProposalEvaluation
    status: EvaluationStatus
    limitations: Tuple[str, ...] = field(default_factory=tuple)
