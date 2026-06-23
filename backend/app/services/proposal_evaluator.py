"""Deterministic proposal evaluator (M4-D).

This module is a **deterministic proposal evaluator**. It is NOT an
MCP server, NOT an MCP client, NOT an LLM agent, and NOT an OpenAI
function-calling harness. It does not call any LLM and does not touch
the network.

The evaluator consumes an M4-C ``StructuredProposal`` and produces a
``ProposalEvaluation`` with structured issues. It does NOT re-run any
tool, does NOT call ``transaction_rule_engine`` or ``trade_simulator``
directly, does NOT re-build the proposal, and does NOT write to disk.
The evaluator NEVER approves a transaction — it only checks whether
the proposal is safe, complete, and trustworthy enough to surface.

Public API:

- ``evaluate_structured_proposal(proposal) -> ProposalEvaluation``
- ``run_evaluation_scenario(scenario, data_dir) -> EvaluationScenarioResult``
- ``run_default_evaluation_scenarios(data_dir) -> tuple[EvaluationScenarioResult, ...]``

Run tests:

    python -m pytest backend/app/tests/test_proposal_evaluator.py
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from ..models.agent import OffseasonGoal
from ..models.evaluation import (
    EvaluationIssue,
    EvaluationIssueCode,
    EvaluationScenario,
    EvaluationScenarioResult,
    EvaluationSeverity,
    EvaluationStatus,
    ProposalEvaluation,
)
from ..models.proposal import (
    ProposalAction,
    ProposalActionType,
    ProposalStatus,
    StructuredProposal,
)
from .proposal_builder import run_goal_and_build_proposal


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class ProposalEvaluatorError(Exception):
    """Base class for proposal_evaluator errors."""


# --------------------------------------------------------------------------- #
# Constants / MVP limitations
# --------------------------------------------------------------------------- #

_MVP_LIMITATIONS: Tuple[str, ...] = (
    "M4-D deterministic proposal evaluation only.",
    "No LLM call.",
    "No MCP.",
    "No external NBA API or live salary data.",
    "Evaluation does not approve transactions.",
)

# Required tool names that must appear in the proposal's tool_call_trace.
_REQUIRED_TOOL_NAMES: Tuple[str, ...] = (
    "cap_sheet_service.summarize_cap_sheet",
    "roster_need_service.evaluate_roster_needs",
    "depth_chart_projector.project_current_depth_chart",
    "free_agent_service.rank_free_agents_for_team",
    "trade_simulator.preview_signing",
    "evidence_service.search_evidence",
)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _safe_getattr(obj: object, name: str, default: object = None) -> object:
    """getattr that swallows exceptions and returns a default."""
    if obj is None:
        return default
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _enum_value(obj: object) -> str:
    """Return ``obj.value`` if it's an enum, else ``str(obj)``."""
    if obj is None:
        return ""
    try:
        return obj.value if hasattr(obj, "value") else str(obj)
    except Exception:
        return str(obj)


def _status_from_issues(
    issues: Tuple[EvaluationIssue, ...],
) -> EvaluationStatus:
    """Derive the overall ``EvaluationStatus`` from the issues.

    - Any ERROR-severity issue → ``FAIL``.
    - Any WARNING-severity issue (no ERROR) → ``WARNING``.
    - Otherwise → ``PASS``.
    """
    has_error = any(i.severity is EvaluationSeverity.ERROR for i in issues)
    has_warning = any(i.severity is EvaluationSeverity.WARNING for i in issues)
    if has_error:
        return EvaluationStatus.FAIL
    if has_warning:
        return EvaluationStatus.WARNING
    return EvaluationStatus.PASS


def _check_human_approval(
    proposal: StructuredProposal,
    issues: List[EvaluationIssue],
    passed: List[str],
    warnings: List[str],
    failed: List[str],
) -> None:
    """Check A: human approval guardrail.

    - ``StructuredProposal.requires_human_approval`` must be ``True``.
    - Every ``ProposalAction.requires_human_approval`` must be ``True``.
    """
    check_name = "human_approval_guardrail"
    if not proposal.requires_human_approval:
        issues.append(
            EvaluationIssue(
                code=EvaluationIssueCode.missing_human_approval,
                severity=EvaluationSeverity.ERROR,
                summary=(
                    "StructuredProposal.requires_human_approval is False; "
                    "must always be True."
                ),
                remediation="Set requires_human_approval=True on the proposal.",
            )
        )
        failed.append(check_name)
        return
    for action in proposal.recommended_actions:
        if not action.requires_human_approval:
            issues.append(
                EvaluationIssue(
                    code=EvaluationIssueCode.missing_human_approval,
                    severity=EvaluationSeverity.ERROR,
                    summary=(
                        f"Action {action.action_id} requires_human_approval "
                        f"is False; must always be True."
                    ),
                    action_id=action.action_id,
                    remediation=(
                        f"Set requires_human_approval=True on action "
                        f"{action.action_id}."
                    ),
                )
            )
            failed.append(check_name)
            return
    passed.append(check_name)


def _check_validation_consistency(
    proposal: StructuredProposal,
    issues: List[EvaluationIssue],
    passed: List[str],
    warnings: List[str],
    failed: List[str],
) -> None:
    """Check B: validation guardrail.

    - A SIGNING action with ``validation_status == "FAIL"`` but
      ``is_valid == True`` is an ERROR (approved_without_validation).
    - A SIGNING action with ``is_valid == False`` must NOT be treated
      as a recommended valid action. If the proposal status is
      RECOMMENDED but no SIGNING action is valid, that's an ERROR
      (invalid_action_recommended).
    - HOLD actions are not signings and must not be treated as
      approved signings.
    """
    check_name = "validation_guardrail"
    has_invalid_inconsistent = False
    for action in proposal.recommended_actions:
        if action.action_type is ProposalActionType.SIGNING:
            if action.validation_status == "FAIL" and action.is_valid:
                issues.append(
                    EvaluationIssue(
                        code=EvaluationIssueCode.approved_without_validation,
                        severity=EvaluationSeverity.ERROR,
                        summary=(
                            f"Action {action.action_id} has validation_status=FAIL "
                            f"but is_valid=True; this is an approval inconsistency."
                        ),
                        action_id=action.action_id,
                        remediation=(
                            f"Set is_valid=False on action {action.action_id} "
                            f"or fix the validation status."
                        ),
                    )
                )
                has_invalid_inconsistent = True
        # HOLD actions are not signings; we don't flag them here.

    # If proposal is RECOMMENDED, at least one SIGNING action must be
    # valid. Otherwise it's invalid_action_recommended.
    if proposal.status is ProposalStatus.RECOMMENDED:
        any_valid_signing = any(
            a.action_type is ProposalActionType.SIGNING and a.is_valid
            for a in proposal.recommended_actions
        )
        if not any_valid_signing:
            issues.append(
                EvaluationIssue(
                    code=EvaluationIssueCode.invalid_action_recommended,
                    severity=EvaluationSeverity.ERROR,
                    summary=(
                        "Proposal status is RECOMMENDED but no SIGNING action "
                        "is valid; cannot recommend without a valid action."
                    ),
                    remediation=(
                        "Change proposal status to PARTIAL/BLOCKED/NO_ACTION, "
                        "or add a valid SIGNING action."
                    ),
                )
            )
            has_invalid_inconsistent = True

    if has_invalid_inconsistent:
        failed.append(check_name)
    else:
        passed.append(check_name)


def _check_evidence(
    proposal: StructuredProposal,
    issues: List[EvaluationIssue],
    passed: List[str],
    warnings: List[str],
    failed: List[str],
) -> None:
    """Check C: evidence guardrail.

    - If ``fallback_reasons`` mentions evidence missing but no
      ``evidence_missing`` risk is present, WARNING.
    - If ``evidence_refs`` is empty but proposal status is RECOMMENDED,
      WARNING.
    - ``sample_data`` must be True (checked separately, but we note it
      here for the evidence layer).
    """
    check_name = "evidence_guardrail"
    has_warning = False

    # Look for "evidence" + "missing" in fallback_reasons (case-insensitive).
    fallback_mentions_evidence_missing = any(
        "evidence" in r.lower() and "missing" in r.lower()
        for r in proposal.fallback_reasons
    )
    risk_codes = {r.code for r in proposal.risks}
    if fallback_mentions_evidence_missing and "evidence_missing" not in risk_codes:
        issues.append(
            EvaluationIssue(
                code=EvaluationIssueCode.missing_evidence,
                severity=EvaluationSeverity.WARNING,
                summary=(
                    "fallback_reasons mention missing evidence but no "
                    "evidence_missing risk is present in the proposal."
                ),
                remediation=(
                    "Add an evidence_missing risk to the proposal, or remove "
                    "the fallback_reason mentioning missing evidence."
                ),
            )
        )
        has_warning = True

    # Empty evidence_refs + RECOMMENDED → WARNING.
    if (
        proposal.status is ProposalStatus.RECOMMENDED
        and not proposal.evidence_refs
    ):
        issues.append(
            EvaluationIssue(
                code=EvaluationIssueCode.missing_evidence,
                severity=EvaluationSeverity.WARNING,
                summary=(
                    "Proposal status is RECOMMENDED but evidence_refs is empty; "
                    "a recommended proposal should cite supporting evidence."
                ),
                remediation=(
                    "Add supporting evidence to the proposal, or change the "
                    "status to PARTIAL."
                ),
            )
        )
        has_warning = True

    if has_warning:
        warnings.append(check_name)
    else:
        passed.append(check_name)


def _check_tool_trace(
    proposal: StructuredProposal,
    issues: List[EvaluationIssue],
    passed: List[str],
    warnings: List[str],
    failed: List[str],
) -> None:
    """Check D: tool trace guardrail.

    The ``tool_call_trace`` must include all required key tools. Missing
    tools produce a WARNING (the proposal may still be safe to surface,
    but the trace is incomplete).
    """
    check_name = "tool_trace_guardrail"
    trace_names = {
        _safe_getattr(rec, "tool_name", "") for rec in proposal.tool_call_trace
    }
    trace_names = {str(n) for n in trace_names if n}
    missing = [t for t in _REQUIRED_TOOL_NAMES if t not in trace_names]
    if missing:
        issues.append(
            EvaluationIssue(
                code=EvaluationIssueCode.missing_tool_trace,
                severity=EvaluationSeverity.WARNING,
                summary=(
                    f"tool_call_trace is missing required tools: {missing}."
                ),
                remediation=(
                    "Ensure the offseason_agent orchestrator calls all "
                    "required tools and records them in the trace."
                ),
            )
        )
        warnings.append(check_name)
    else:
        passed.append(check_name)


def _check_fallback_consistency(
    proposal: StructuredProposal,
    issues: List[EvaluationIssue],
    passed: List[str],
    warnings: List[str],
    failed: List[str],
) -> None:
    """Check E: fallback consistency.

    - If ``proposal.status == NO_ACTION``, there should be a HOLD action
      or a ``no_matching_candidate`` risk. Otherwise WARNING
      (no_action_fallback).
    - If ``fallback_reasons`` is non-empty but there's no risk and no
      limitation, WARNING (missing_risk_for_fallback).
    - If no candidates (no free-agent fits implied by NO_ACTION and no
      signing actions) but status is RECOMMENDED, that's an ERROR
      (invalid_action_recommended) — but this is also caught by
      _check_validation_consistency, so we only add a fallback-specific
      ERROR here if the status is RECOMMENDED and there are no
      recommended_actions at all.
    """
    check_name = "fallback_consistency_guardrail"
    has_warning = False
    has_error = False

    risk_codes = {r.code for r in proposal.risks}

    # NO_ACTION should have a HOLD action or no_matching_candidate risk.
    if proposal.status is ProposalStatus.NO_ACTION:
        has_hold = any(
            a.action_type is ProposalActionType.HOLD
            for a in proposal.recommended_actions
        )
        if not has_hold and "no_matching_candidate" not in risk_codes:
            issues.append(
                EvaluationIssue(
                    code=EvaluationIssueCode.no_action_fallback,
                    severity=EvaluationSeverity.WARNING,
                    summary=(
                        "Proposal status is NO_ACTION but there is no HOLD "
                        "action and no no_matching_candidate risk."
                    ),
                    remediation=(
                        "Add a HOLD action or a no_matching_candidate risk "
                        "to the proposal."
                    ),
                )
            )
            has_warning = True

    # fallback_reasons non-empty but no risk and no limitation.
    if proposal.fallback_reasons and not proposal.risks and not proposal.limitations:
        issues.append(
            EvaluationIssue(
                code=EvaluationIssueCode.missing_risk_for_fallback,
                severity=EvaluationSeverity.WARNING,
                summary=(
                    "fallback_reasons is non-empty but the proposal has no "
                    "risks and no limitations; fallbacks should be reflected "
                    "in risks or limitations."
                ),
                remediation=(
                    "Add a risk or limitation to the proposal that "
                    "corresponds to each fallback_reason."
                ),
            )
        )
        has_warning = True

    # RECOMMENDED with no actions at all → ERROR (should have been caught
    # by validation guardrail, but we add a fallback-specific one too).
    if (
        proposal.status is ProposalStatus.RECOMMENDED
        and not proposal.recommended_actions
    ):
        issues.append(
            EvaluationIssue(
                code=EvaluationIssueCode.invalid_action_recommended,
                severity=EvaluationSeverity.ERROR,
                summary=(
                    "Proposal status is RECOMMENDED but recommended_actions "
                    "is empty; cannot recommend without any action."
                ),
                remediation=(
                    "Change proposal status to NO_ACTION, or add at least "
                    "one valid action."
                ),
            )
        )
        has_error = True

    if has_error:
        failed.append(check_name)
    elif has_warning:
        warnings.append(check_name)
    else:
        passed.append(check_name)


def _check_sample_data(
    proposal: StructuredProposal,
    issues: List[EvaluationIssue],
    passed: List[str],
    warnings: List[str],
    failed: List[str],
) -> None:
    """Check F: sample data guardrail.

    The proposal must have ``sample_data=True``. We always emit an INFO
    issue noting that the proposal is sample-data-only, so downstream
    consumers can't mistake it for real NBA data.
    """
    check_name = "sample_data_guardrail"
    if not proposal.sample_data:
        issues.append(
            EvaluationIssue(
                code=EvaluationIssueCode.sample_data_only,
                severity=EvaluationSeverity.ERROR,
                summary=(
                    "StructuredProposal.sample_data is False; demo proposals "
                    "must always be sample_data=True."
                ),
                remediation="Set sample_data=True on the proposal.",
            )
        )
        failed.append(check_name)
        return
    # Always emit an INFO note so consumers know this is sample data.
    issues.append(
        EvaluationIssue(
            code=EvaluationIssueCode.sample_data_only,
            severity=EvaluationSeverity.INFO,
            summary=(
                "Proposal is built from DEMO/SAMPLE/SIMULATION data; not "
                "real NBA data."
            ),
            remediation="No action needed; informational note.",
        )
    )
    passed.append(check_name)


# --------------------------------------------------------------------------- #
# Public API: evaluate_structured_proposal
# --------------------------------------------------------------------------- #


def evaluate_structured_proposal(
    proposal: StructuredProposal,
) -> ProposalEvaluation:
    """Evaluate a ``StructuredProposal`` and return a
    ``ProposalEvaluation``.

    This function is **deterministic**: the same proposal always
    produces the same evaluation. It does NOT call any LLM, does NOT
    use MCP, does NOT call ``transaction_rule_engine`` or
    ``trade_simulator``, and does NOT write to disk. The evaluator
    NEVER approves a transaction — it only checks whether the proposal
    is safe, complete, and trustworthy enough to surface.

    Checks performed:

    - A. Human approval guardrail (ERROR if missing).
    - B. Validation guardrail (ERROR if inconsistent).
    - C. Evidence guardrail (WARNING if missing/empty).
    - D. Tool trace guardrail (WARNING if incomplete).
    - E. Fallback consistency guardrail (WARNING/ERROR).
    - F. Sample data guardrail (ERROR if False; INFO always).
    """
    issues: List[EvaluationIssue] = []
    passed: List[str] = []
    warnings: List[str] = []
    failed: List[str] = []

    _check_human_approval(proposal, issues, passed, warnings, failed)
    _check_validation_consistency(proposal, issues, passed, warnings, failed)
    _check_evidence(proposal, issues, passed, warnings, failed)
    _check_tool_trace(proposal, issues, passed, warnings, failed)
    _check_fallback_consistency(proposal, issues, passed, warnings, failed)
    _check_sample_data(proposal, issues, passed, warnings, failed)

    status = _status_from_issues(tuple(issues))

    return ProposalEvaluation(
        proposal_id=proposal.proposal_id,
        team_id=proposal.team_id,
        status=status,
        issues=tuple(issues),
        passed_checks=tuple(passed),
        failed_checks=tuple(failed),
        warnings=tuple(warnings),
        limitations=_MVP_LIMITATIONS,
        sample_data=True,
    )


# --------------------------------------------------------------------------- #
# Default scenarios
# --------------------------------------------------------------------------- #


def _build_default_scenarios() -> Tuple[EvaluationScenario, ...]:
    """Build the fixed set of default regression scenarios.

    These scenarios cover the main paths: a successful center signing,
    a strict-budget no-action case, a broad-need multi-candidate case,
    and an evidence-fallback case.
    """
    scenarios: List[EvaluationScenario] = []

    # 1. success_center_signing
    scenarios.append(
        EvaluationScenario(
            scenario_id="success_center_signing",
            description=(
                "DEM-ATL targets a center with a 20M budget; expects a "
                "RECOMMENDED proposal with at least 1 action and a "
                "sample_data risk."
            ),
            goal=OffseasonGoal(
                team_id="DEM-ATL",
                objective="Add frontcourt help",
                target_positions=("C",),
                max_salary=20_000_000,
                max_candidates=2,
                evidence_query="center need cap flexibility",
            ),
            expected_statuses=("RECOMMENDED",),
            expected_min_actions=1,
            expected_risk_codes=("sample_data",),
        )
    )

    # 2. strict_budget_no_action
    scenarios.append(
        EvaluationScenario(
            scenario_id="strict_budget_no_action",
            description=(
                "DEM-ATL targets a center with a 15M budget; fa-005 (18M) "
                "is filtered out, so expects NO_ACTION or PARTIAL with a "
                "no_matching_candidate risk."
            ),
            goal=OffseasonGoal(
                team_id="DEM-ATL",
                objective="Strict budget center search",
                target_positions=("C",),
                max_salary=15_000_000,
                max_candidates=2,
                evidence_query="center need cap flexibility",
            ),
            expected_statuses=("NO_ACTION", "PARTIAL"),
            expected_min_actions=0,
            expected_risk_codes=("no_matching_candidate",),
        )
    )

    # 3. broad_need_multiple_candidates
    scenarios.append(
        EvaluationScenario(
            scenario_id="broad_need_multiple_candidates",
            description=(
                "DEM-ATL with no position filter and a 20M budget; expects "
                "at least 1 action (multiple candidates may be ranked)."
            ),
            goal=OffseasonGoal(
                team_id="DEM-ATL",
                objective="Broad roster upgrade",
                target_positions=(),
                max_salary=20_000_000,
                max_candidates=2,
                evidence_query="roster need cap flexibility",
            ),
            expected_statuses=("RECOMMENDED", "PARTIAL"),
            expected_min_actions=1,
            expected_risk_codes=("sample_data",),
        )
    )

    # 4. evidence_fallback_case
    scenarios.append(
        EvaluationScenario(
            scenario_id="evidence_fallback_case",
            description=(
                "DEM-ATL with an evidence query that won't match any note "
                "tokens; expects the proposal to still build, with "
                "fallback_reasons mentioning missing/empty evidence."
            ),
            goal=OffseasonGoal(
                team_id="DEM-ATL",
                objective="Center search with unlikely evidence query",
                target_positions=("C",),
                max_salary=20_000_000,
                max_candidates=2,
                evidence_query="zzz_no_such_topic_zzz",
            ),
            expected_statuses=("RECOMMENDED", "PARTIAL"),
            expected_min_actions=0,
            expected_risk_codes=(),
        )
    )

    return tuple(scenarios)


# --------------------------------------------------------------------------- #
# Public API: scenario runner
# --------------------------------------------------------------------------- #


def run_evaluation_scenario(
    scenario: EvaluationScenario, data_dir: Path | str = "data"
) -> EvaluationScenarioResult:
    """Run one ``EvaluationScenario`` end-to-end.

    Builds a proposal from the scenario's goal (via
    ``run_goal_and_build_proposal``), evaluates it, and checks the
    scenario's expected constraints. The result status is ``PASS`` if
    the evaluation passed and all expected constraints are met,
    ``WARNING`` if the evaluation passed with warnings but constraints
    are met, and ``FAIL`` if the evaluation failed or any expected
    constraint is violated.
    """
    proposal = run_goal_and_build_proposal(scenario.goal, data_dir)
    evaluation = evaluate_structured_proposal(proposal)

    # Check expected constraints.
    constraint_issues: List[EvaluationIssue] = []
    proposal_status_str = _enum_value(proposal.status)

    # Expected statuses.
    if scenario.expected_statuses:
        if proposal_status_str not in scenario.expected_statuses:
            constraint_issues.append(
                EvaluationIssue(
                    code=EvaluationIssueCode.invalid_action_recommended,
                    severity=EvaluationSeverity.ERROR,
                    summary=(
                        f"Scenario expected proposal status in "
                        f"{list(scenario.expected_statuses)} but got "
                        f"{proposal_status_str}."
                    ),
                    remediation="Adjust the goal or the expected_statuses.",
                )
            )

    # Expected min actions.
    if scenario.expected_min_actions > 0:
        actual_actions = len(proposal.recommended_actions)
        if actual_actions < scenario.expected_min_actions:
            constraint_issues.append(
                EvaluationIssue(
                    code=EvaluationIssueCode.invalid_action_recommended,
                    severity=EvaluationSeverity.ERROR,
                    summary=(
                        f"Scenario expected at least "
                        f"{scenario.expected_min_actions} action(s) but got "
                        f"{actual_actions}."
                    ),
                    remediation="Adjust the goal or the expected_min_actions.",
                )
            )

    # Expected risk codes.
    actual_risk_codes = {r.code for r in proposal.risks}
    for expected_code in scenario.expected_risk_codes:
        if expected_code not in actual_risk_codes:
            constraint_issues.append(
                EvaluationIssue(
                    code=EvaluationIssueCode.missing_risk_for_fallback,
                    severity=EvaluationSeverity.WARNING,
                    summary=(
                        f"Scenario expected risk code {expected_code!r} but "
                        f"it is not present in the proposal."
                    ),
                    remediation="Adjust the goal or the expected_risk_codes.",
                )
            )

    # Derive scenario status.
    if evaluation.status is EvaluationStatus.FAIL or any(
        i.severity is EvaluationSeverity.ERROR for i in constraint_issues
    ):
        scenario_status = EvaluationStatus.FAIL
    elif evaluation.status is EvaluationStatus.WARNING or any(
        i.severity is EvaluationSeverity.WARNING for i in constraint_issues
    ):
        scenario_status = EvaluationStatus.WARNING
    else:
        scenario_status = EvaluationStatus.PASS

    return EvaluationScenarioResult(
        scenario_id=scenario.scenario_id,
        proposal=proposal,
        evaluation=evaluation,
        status=scenario_status,
        limitations=_MVP_LIMITATIONS,
    )


def run_default_evaluation_scenarios(
    data_dir: Path | str = "data",
) -> Tuple[EvaluationScenarioResult, ...]:
    """Run all default regression scenarios and return their results.

    This is the one-call entry point for regression evaluation. It
    runs each scenario in ``_build_default_scenarios`` via
    ``run_evaluation_scenario`` and returns a tuple of results in
    deterministic order.
    """
    return tuple(
        run_evaluation_scenario(scenario, data_dir)
        for scenario in _build_default_scenarios()
    )
