"""Deterministic proposal viewer / CLI demo formatter (M5-A).

This module is a **deterministic display layer**. It is NOT an MCP
server, NOT an MCP client, NOT an LLM agent, and NOT an OpenAI
function-calling harness. It does not call any LLM and does not touch
the network.

The viewer consumes an M4-C ``StructuredProposal`` and an M4-D
``ProposalEvaluation`` and produces a human-readable text brief or a
stable JSON-serializable dict. It does NOT re-run any tool, does NOT
call ``transaction_rule_engine`` or ``trade_simulator``, does NOT
re-build the proposal, does NOT re-evaluate the proposal, and does
NOT write to disk. The viewer NEVER approves a transaction — it only
formats existing proposal/evaluation data for display.

Public API:

- ``format_proposal_brief(proposal, evaluation) -> str``
- ``build_demo_payload(goal, data_dir) -> dict``
- ``build_demo_brief(goal, data_dir) -> str``

Run tests:

    python -m pytest backend/app/tests/test_proposal_viewer.py
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..models.agent import OffseasonGoal
from ..models.evaluation import (
    EvaluationIssue,
    EvaluationIssueCode,
    EvaluationSeverity,
    EvaluationStatus,
    ProposalEvaluation,
)
from ..models.proposal import (
    ProposalAction,
    ProposalActionType,
    ProposalEvidenceRef,
    ProposalRisk,
    ProposalRiskLevel,
    ProposalStatus,
    StructuredProposal,
)
from ..services.cap_sheet_service import TeamNotFoundError
from ..services.proposal_builder import run_goal_and_build_proposal
from ..services.proposal_evaluator import evaluate_structured_proposal


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class ProposalViewerError(Exception):
    """Base class for proposal_viewer errors."""


# --------------------------------------------------------------------------- #
# Constants / MVP limitations
# --------------------------------------------------------------------------- #

_MVP_LIMITATIONS: Tuple[str, ...] = (
    "M5-A deterministic proposal viewer / CLI demo only.",
    "No LLM call.",
    "No MCP.",
    "No external NBA API or live salary data.",
    "All actions are previews and require human approval.",
    "Demo uses sample/simulation data, not real NBA predictions.",
)

_BANNER: str = (
    "============================================================\n"
    " FrontOffice-Offseason-Agent  |  DEMO PREVIEW (sample data)\n"
    "============================================================"
)

_FOOTER: str = (
    "------------------------------------------------------------\n"
    " End of demo brief  |  preview only  |  requires human approval\n"
    "------------------------------------------------------------"
)


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _enum_value(obj: object) -> str:
    """Return ``obj.value`` if it's an enum, else ``str(obj)``."""
    if obj is None:
        return ""
    try:
        return obj.value if hasattr(obj, "value") else str(obj)
    except Exception:
        return str(obj)


def _safe_getattr(obj: object, name: str, default: object = None) -> object:
    """getattr that swallows exceptions and returns a default."""
    if obj is None:
        return default
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def _format_salary(salary: Optional[int]) -> str:
    """Format a salary integer as a deterministic string."""
    if salary is None:
        return "N/A"
    return f"${salary:,}"


def _format_fit_score(score: Optional[float]) -> str:
    """Format a fit_score float as a deterministic 2-decimal string."""
    if score is None:
        return "N/A"
    try:
        return f"{float(score):.2f}"
    except Exception:
        return "N/A"


def _format_bool(value: Optional[bool]) -> str:
    """Format a bool as ``True`` / ``False``."""
    if value is None:
        return "N/A"
    return "True" if value else "False"


# --------------------------------------------------------------------------- #
# Text brief formatting
# --------------------------------------------------------------------------- #


def _format_header(
    proposal: StructuredProposal, evaluation: ProposalEvaluation
) -> List[str]:
    """Build the header block of the text brief."""
    lines: List[str] = []
    lines.append(_BANNER)
    lines.append("")
    lines.append(f"team_id               : {proposal.team_id}")
    lines.append(f"objective             : {proposal.objective}")
    lines.append(f"proposal_id           : {proposal.proposal_id}")
    lines.append(f"proposal status       : {_enum_value(proposal.status)}")
    lines.append(f"evaluation status     : {_enum_value(evaluation.status)}")
    lines.append(
        f"requires_human_approval: {_format_bool(proposal.requires_human_approval)}"
    )
    lines.append(f"sample_data           : {_format_bool(proposal.sample_data)}")
    lines.append("")
    lines.append(f"cap summary           : {proposal.cap_summary or 'N/A'}")
    lines.append(f"roster need summary   : {proposal.roster_need_summary or 'N/A'}")
    lines.append(f"depth chart summary   : {proposal.depth_chart_summary or 'N/A'}")
    return lines


def _format_actions(proposal: StructuredProposal) -> List[str]:
    """Build the recommended actions block of the text brief."""
    lines: List[str] = []
    lines.append("")
    lines.append("--- Recommended Actions (preview only) ---")
    if not proposal.recommended_actions:
        lines.append("  (no actions)")
        return lines
    for idx, action in enumerate(proposal.recommended_actions):
        lines.append(f"  [{idx}] action_id        : {action.action_id}")
        lines.append(f"      action_type      : {_enum_value(action.action_type)}")
        lines.append(f"      team_id          : {action.team_id}")
        lines.append(f"      player_name      : {action.player_name or 'N/A'}")
        lines.append(f"      position         : {action.position or 'N/A'}")
        lines.append(f"      salary           : {_format_salary(action.salary)}")
        lines.append(f"      years            : {action.years if action.years is not None else 'N/A'}")
        lines.append(f"      validation_status: {action.validation_status}")
        lines.append(f"      is_valid         : {_format_bool(action.is_valid)}")
        lines.append(
            f"      requires_human_approval: {_format_bool(action.requires_human_approval)}"
        )
        lines.append(f"      fit_score        : {_format_fit_score(action.fit_score)}")
        lines.append(f"      matched_need     : {action.matched_need or 'N/A'}")
        lines.append(f"      transaction_id   : {action.transaction_id or 'N/A'}")
        lines.append(f"      cap_impact       : {action.cap_impact_summary or 'N/A'}")
        lines.append(f"      roster_impact    : {action.roster_impact_summary or 'N/A'}")
        lines.append(
            f"      depth_chart_impact: {action.depth_chart_impact_summary or 'N/A'}"
        )
        if action.evidence_ids:
            lines.append(f"      evidence_ids     : {', '.join(action.evidence_ids)}")
        else:
            lines.append("      evidence_ids     : (none)")
        if action.limitations:
            for lim in action.limitations:
                lines.append(f"      limitation       : {lim}")
    return lines


def _format_risks(proposal: StructuredProposal) -> List[str]:
    """Build the risks block of the text brief."""
    lines: List[str] = []
    lines.append("")
    lines.append("--- Risks ---")
    if not proposal.risks:
        lines.append("  (no risks)")
        return lines
    for idx, risk in enumerate(proposal.risks):
        lines.append(f"  [{idx}] code   : {risk.code}")
        lines.append(f"      level  : {_enum_value(risk.level)}")
        lines.append(f"      summary: {risk.summary}")
        if risk.evidence_ids:
            lines.append(f"      evidence_ids: {', '.join(risk.evidence_ids)}")
    return lines


def _format_evidence(proposal: StructuredProposal) -> List[str]:
    """Build the evidence block of the text brief."""
    lines: List[str] = []
    lines.append("")
    lines.append("--- Evidence (sample data) ---")
    if not proposal.evidence_refs:
        lines.append("  (no evidence refs)")
        return lines
    for idx, ref in enumerate(proposal.evidence_refs):
        lines.append(f"  [{idx}] evidence_id  : {ref.evidence_id}")
        lines.append(f"      title        : {ref.title}")
        lines.append(f"      source       : {ref.source}")
        lines.append(f"      evidence_type: {ref.evidence_type}")
        lines.append(f"      sample_data  : {_format_bool(ref.sample_data)}")
    return lines


def _format_tool_trace(proposal: StructuredProposal) -> List[str]:
    """Build the tool call trace block of the text brief."""
    lines: List[str] = []
    lines.append("")
    lines.append("--- Tool Call Trace ---")
    if not proposal.tool_call_trace:
        lines.append("  (no tool calls)")
        return lines
    for idx, call in enumerate(proposal.tool_call_trace):
        tool_name = _safe_getattr(call, "tool_name", "?")
        status = _enum_value(_safe_getattr(call, "status", "?"))
        input_summary = _safe_getattr(call, "input_summary", "")
        output_summary = _safe_getattr(call, "output_summary", "")
        fallback_reason = _safe_getattr(call, "fallback_reason", None)
        lines.append(f"  [{idx}] tool_name : {tool_name}")
        lines.append(f"      status    : {status}")
        lines.append(f"      input     : {input_summary}")
        lines.append(f"      output    : {output_summary}")
        if fallback_reason:
            lines.append(f"      fallback  : {fallback_reason}")
    return lines


def _format_evaluation(evaluation: ProposalEvaluation) -> List[str]:
    """Build the evaluation block of the text brief."""
    lines: List[str] = []
    lines.append("")
    lines.append("--- Evaluation ---")
    lines.append(f"  status        : {_enum_value(evaluation.status)}")
    lines.append(f"  issues count  : {len(evaluation.issues)}")
    lines.append(f"  warnings count: {len(evaluation.warnings)}")
    lines.append(f"  passed_checks : {len(evaluation.passed_checks)}")
    lines.append(f"  failed_checks : {len(evaluation.failed_checks)}")
    if evaluation.issues:
        lines.append("  issues:")
        for idx, issue in enumerate(evaluation.issues):
            code = _enum_value(issue.code)
            severity = _enum_value(issue.severity)
            lines.append(
                f"    [{idx}] code={code} severity={severity}"
            )
            lines.append(f"         summary: {issue.summary}")
            if issue.action_id:
                lines.append(f"         action_id: {issue.action_id}")
            if issue.remediation:
                lines.append(f"         remediation: {issue.remediation}")
    if evaluation.passed_checks:
        lines.append(
            f"  passed check names: {', '.join(evaluation.passed_checks)}"
        )
    if evaluation.failed_checks:
        lines.append(
            f"  failed check names: {', '.join(evaluation.failed_checks)}"
        )
    if evaluation.warnings:
        lines.append(
            f"  warning check names: {', '.join(evaluation.warnings)}"
        )
    return lines


def _format_fallback_reasons(proposal: StructuredProposal) -> List[str]:
    """Build the fallback reasons block of the text brief."""
    lines: List[str] = []
    lines.append("")
    lines.append("--- Fallback Reasons ---")
    if not proposal.fallback_reasons:
        lines.append("  (none)")
        return lines
    for idx, reason in enumerate(proposal.fallback_reasons):
        lines.append(f"  [{idx}] {reason}")
    return lines


def _format_limitations(proposal: StructuredProposal) -> List[str]:
    """Build the limitations block of the text brief."""
    lines: List[str] = []
    lines.append("")
    lines.append("--- Limitations ---")
    # Combine proposal limitations + viewer MVP limitations (deduped, order preserved).
    seen: set = set()
    combined: List[str] = []
    for lim in (*proposal.limitations, *_MVP_LIMITATIONS):
        if lim not in seen:
            seen.add(lim)
            combined.append(lim)
    if not combined:
        lines.append("  (none)")
        return lines
    for idx, lim in enumerate(combined):
        lines.append(f"  [{idx}] {lim}")
    return lines


def format_proposal_brief(
    proposal: StructuredProposal, evaluation: ProposalEvaluation
) -> str:
    """Format a ``StructuredProposal`` + ``ProposalEvaluation`` as a
    deterministic human-readable text brief.

    The brief is **deterministic**: the same inputs always produce the
    same output. It does NOT call any LLM, does NOT use MCP, does NOT
    call ``transaction_rule_engine`` or ``trade_simulator``, and does
    NOT write to disk. The viewer NEVER approves a transaction — it
    only formats existing data.

    The brief covers: header (team_id / objective / statuses /
    requires_human_approval / sample_data), recommended actions,
    risks, evidence refs, tool call trace, evaluation summary,
    fallback reasons, and limitations.
    """
    if not isinstance(proposal, StructuredProposal):
        raise ProposalViewerError(
            "proposal must be a StructuredProposal instance"
        )
    if not isinstance(evaluation, ProposalEvaluation):
        raise ProposalViewerError(
            "evaluation must be a ProposalEvaluation instance"
        )

    lines: List[str] = []
    lines.extend(_format_header(proposal, evaluation))
    lines.extend(_format_actions(proposal))
    lines.extend(_format_risks(proposal))
    lines.extend(_format_evidence(proposal))
    lines.extend(_format_tool_trace(proposal))
    lines.extend(_format_evaluation(evaluation))
    lines.extend(_format_fallback_reasons(proposal))
    lines.extend(_format_limitations(proposal))
    lines.append("")
    lines.append(_FOOTER)
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# JSON payload
# --------------------------------------------------------------------------- #


def _enum_to_str(obj: object) -> Any:
    """Convert enums to their string value; pass through other primitives."""
    if isinstance(obj, Enum):
        return obj.value
    return obj


def _serialize_action(action: ProposalAction) -> Dict[str, Any]:
    """Serialize a ``ProposalAction`` to a JSON-stable dict."""
    return {
        "action_id": action.action_id,
        "action_type": _enum_to_str(action.action_type),
        "team_id": action.team_id,
        "transaction_id": action.transaction_id,
        "player_id": action.player_id,
        "player_name": action.player_name,
        "position": action.position,
        "salary": action.salary,
        "years": action.years,
        "validation_status": action.validation_status,
        "is_valid": action.is_valid,
        "requires_human_approval": action.requires_human_approval,
        "fit_score": action.fit_score,
        "matched_need": action.matched_need,
        "cap_impact_summary": action.cap_impact_summary,
        "roster_impact_summary": action.roster_impact_summary,
        "depth_chart_impact_summary": action.depth_chart_impact_summary,
        "evidence_ids": list(action.evidence_ids),
        "limitations": list(action.limitations),
    }


def _serialize_risk(risk: ProposalRisk) -> Dict[str, Any]:
    """Serialize a ``ProposalRisk`` to a JSON-stable dict."""
    return {
        "code": risk.code,
        "level": _enum_to_str(risk.level),
        "summary": risk.summary,
        "evidence_ids": list(risk.evidence_ids),
    }


def _serialize_evidence_ref(ref: ProposalEvidenceRef) -> Dict[str, Any]:
    """Serialize a ``ProposalEvidenceRef`` to a JSON-stable dict."""
    return {
        "evidence_id": ref.evidence_id,
        "title": ref.title,
        "source": ref.source,
        "evidence_type": ref.evidence_type,
        "sample_data": ref.sample_data,
    }


def _serialize_tool_call(call: object) -> Dict[str, Any]:
    """Serialize a ``ToolCallRecord`` to a JSON-stable dict."""
    return {
        "tool_name": _safe_getattr(call, "tool_name", ""),
        "status": _enum_to_str(_safe_getattr(call, "status", "")),
        "input_summary": _safe_getattr(call, "input_summary", ""),
        "output_summary": _safe_getattr(call, "output_summary", ""),
        "fallback_reason": _safe_getattr(call, "fallback_reason", None),
        "evidence_ids": list(_safe_getattr(call, "evidence_ids", ()) or ()),
    }


def _serialize_issue(issue: EvaluationIssue) -> Dict[str, Any]:
    """Serialize an ``EvaluationIssue`` to a JSON-stable dict."""
    return {
        "code": _enum_to_str(issue.code),
        "severity": _enum_to_str(issue.severity),
        "summary": issue.summary,
        "action_id": issue.action_id,
        "evidence_ids": list(issue.evidence_ids),
        "remediation": issue.remediation,
    }


def _serialize_proposal(proposal: StructuredProposal) -> Dict[str, Any]:
    """Serialize a ``StructuredProposal`` to a JSON-stable dict."""
    return {
        "proposal_id": proposal.proposal_id,
        "team_id": proposal.team_id,
        "objective": proposal.objective,
        "status": _enum_to_str(proposal.status),
        "recommended_actions": [
            _serialize_action(a) for a in proposal.recommended_actions
        ],
        "risks": [_serialize_risk(r) for r in proposal.risks],
        "evidence_refs": [
            _serialize_evidence_ref(e) for e in proposal.evidence_refs
        ],
        "tool_call_trace": [
            _serialize_tool_call(c) for c in proposal.tool_call_trace
        ],
        "cap_summary": proposal.cap_summary,
        "roster_need_summary": proposal.roster_need_summary,
        "depth_chart_summary": proposal.depth_chart_summary,
        "fallback_reasons": list(proposal.fallback_reasons),
        "limitations": list(proposal.limitations),
        "requires_human_approval": proposal.requires_human_approval,
        "sample_data": proposal.sample_data,
    }


def _serialize_evaluation(evaluation: ProposalEvaluation) -> Dict[str, Any]:
    """Serialize a ``ProposalEvaluation`` to a JSON-stable dict."""
    return {
        "proposal_id": evaluation.proposal_id,
        "team_id": evaluation.team_id,
        "status": _enum_to_str(evaluation.status),
        "issues": [_serialize_issue(i) for i in evaluation.issues],
        "passed_checks": list(evaluation.passed_checks),
        "failed_checks": list(evaluation.failed_checks),
        "warnings": list(evaluation.warnings),
        "limitations": list(evaluation.limitations),
        "sample_data": evaluation.sample_data,
    }


def build_demo_payload(
    goal: OffseasonGoal, data_dir: Path | str = "data"
) -> Dict[str, Any]:
    """Build a stable JSON-serializable payload for a demo run.

    The payload contains:

    - ``proposal``: the serialized ``StructuredProposal``.
    - ``evaluation``: the serialized ``ProposalEvaluation``.
    - ``actions``: shortcut alias for ``proposal.recommended_actions``.
    - ``evidence``: shortcut alias for ``proposal.evidence_refs``.
    - ``tool_trace``: shortcut alias for ``proposal.tool_call_trace``.
    - ``limitations``: combined MVP limitations (viewer + proposal).
    - ``requires_human_approval``: always ``True``.
    - ``sample_data``: always ``True``.

    The payload is **deterministic**: the same goal + data_dir always
    produce the same payload. It does NOT call any LLM, does NOT use
    MCP, and does NOT write to disk.
    """
    if not isinstance(goal, OffseasonGoal):
        raise ProposalViewerError("goal must be an OffseasonGoal instance")

    proposal = run_goal_and_build_proposal(goal, data_dir)
    evaluation = evaluate_structured_proposal(proposal)

    proposal_dict = _serialize_proposal(proposal)
    evaluation_dict = _serialize_evaluation(evaluation)

    # Combine limitations (deduped, order preserved).
    seen: set = set()
    combined_limitations: List[str] = []
    for lim in (*proposal.limitations, *_MVP_LIMITATIONS):
        if lim not in seen:
            seen.add(lim)
            combined_limitations.append(lim)

    return {
        "proposal": proposal_dict,
        "evaluation": evaluation_dict,
        "actions": proposal_dict["recommended_actions"],
        "evidence": proposal_dict["evidence_refs"],
        "tool_trace": proposal_dict["tool_call_trace"],
        "limitations": combined_limitations,
        "requires_human_approval": proposal.requires_human_approval,
        "sample_data": proposal.sample_data,
    }


def build_demo_brief(
    goal: OffseasonGoal, data_dir: Path | str = "data"
) -> str:
    """Build a deterministic text brief for a demo run.

    Convenience wrapper: builds the proposal + evaluation via
    ``build_demo_payload`` (which calls ``run_goal_and_build_proposal``
    and ``evaluate_structured_proposal``), then formats the result as
    a text brief via ``format_proposal_brief``.

    Does NOT call any LLM, does NOT use MCP, and does NOT write to
    disk.
    """
    if not isinstance(goal, OffseasonGoal):
        raise ProposalViewerError("goal must be an OffseasonGoal instance")

    proposal = run_goal_and_build_proposal(goal, data_dir)
    evaluation = evaluate_structured_proposal(proposal)
    return format_proposal_brief(proposal, evaluation)


# --------------------------------------------------------------------------- #
# Module-level guardrail: no forbidden attributes
# --------------------------------------------------------------------------- #
# The viewer must not expose any MCP / LLM client attributes. This is
# verified by ``test_agent_guardrails.py``. We deliberately do NOT
# import any ``mcp`` / ``openai`` / ``anthropic`` module here.
