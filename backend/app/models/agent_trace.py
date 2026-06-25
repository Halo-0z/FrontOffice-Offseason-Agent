"""Agent trace schema models (M8-E2).

These dataclasses describe the **agent execution trace** that the
backend attaches to ``proposal-preview`` and ``trade-preview-demo``
payloads so the frontend can render a human-readable step-by-step view
of what the Agent did.

Design notes
------------
- These are **additive** presentation models. They do NOT replace the
  existing ``ToolCallRecord`` / ``OffseasonAgentRun`` / ``tool_call_trace``
  structures; they are a user-facing projection on top of them.
- ``status`` values for a step mirror the M8-E1 contract:
  ``pending`` / ``running`` / ``completed`` / ``warning`` / ``blocked``.
- The salary-validation verdict (``PASS`` / ``WARNING`` / ``FAIL`` from
  ``ValidationStatus``) is mapped to step status by the builder. The
  builder is the only place that performs this mapping — the schema
  itself is verdict-agnostic.
- ``final_message`` is always the read-only disclaimer
  ``"这是只读预览，不会自动执行。"``.
- All dataclasses are frozen and serialize to plain dicts via
  ``to_dict()`` so they can be merged into JSON payloads directly.

Guardrails (same as the rest of the project):
- No LLM call. No MCP. No external NBA API. No network.
- A trace step never claims a transaction was executed.
- ``requires_human_review`` on the final approval step is always ``True``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class TraceStepStatus(str, Enum):
    """Status of a single trace step.

    - ``completed``: the tool ran successfully.
    - ``warning``: the tool ran but produced a caveat (fallback,
      manual-review data, partial result).
    - ``blocked``: the tool failed and the run cannot proceed past it
      (e.g. salary validation ``FAIL``).
    - ``pending`` / ``running``: reserved for future live-streaming use;
      the builder always emits a terminal status.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    WARNING = "warning"
    BLOCKED = "blocked"


class TraceOverallStatus(str, Enum):
    """Overall status of an agent trace run."""

    COMPLETED = "completed"
    WARNING = "warning"
    BLOCKED = "blocked"
    AWAITING_HUMAN_APPROVAL = "awaiting_human_approval"


class ApprovalState(str, Enum):
    """Human-approval gate state for a trace run.

    - ``not_required``: the run ended in a state that does not need
      approval (e.g. blocked before any proposal).
    - ``required``: the run produced a preview and is waiting for human
      confirmation.
    - ``approved_preview``: a human confirmed the preview — this is
      still NOT a real transaction execution.
    - ``blocked``: the run is blocked and cannot reach the approval
      gate.
    """

    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    APPROVED_PREVIEW = "approved_preview"
    BLOCKED = "blocked"


class TraceIntentType(str, Enum):
    """Intent type for a trace run."""

    SIGNING = "signing"
    TRADE = "trade"
    HOLD = "hold"
    COMPARE = "compare"


# --------------------------------------------------------------------------- #
# Step
# --------------------------------------------------------------------------- #


# The unified read-only disclaimer. Every trace ends with this message.
FINAL_MESSAGE_READ_ONLY = "这是只读预览，不会自动执行。"


@dataclass(frozen=True)
class AgentTraceStep:
    """A single step in the agent trace.

    Attributes:
        step_id: Stable unique id for the step within this run.
        sequence: 1-based sequence number for ordering.
        status: ``TraceStepStatus`` value (string).
        title: User-visible human-language title (e.g. "读取当前数据").
        plain_language_summary: One-sentence plain-language summary.
        tool_name: The contracted tool name from M8-E1 (e.g.
            ``load_active_data_source``). Surfaced only in technical
            details, not as the main title.
        inputs_summary: Short summary of inputs (dict / list / str).
        outputs_summary: Short summary of outputs (dict / list / str).
        warnings: List of warning strings (may be empty).
        evidence_ids: Evidence ids referenced by this step.
        requires_human_review: Whether this step's output needs manual
            review.
        technical_details: Developer-facing dict (folded in frontend).
        started_at: ISO timestamp when the step started (optional).
        finished_at: ISO timestamp when the step finished (optional).
    """

    step_id: str
    sequence: int
    status: str
    title: str
    plain_language_summary: str
    tool_name: str
    inputs_summary: Any = None
    outputs_summary: Any = None
    warnings: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    requires_human_review: bool = False
    technical_details: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for JSON payloads."""
        return {
            "step_id": self.step_id,
            "sequence": self.sequence,
            "status": self.status,
            "title": self.title,
            "plain_language_summary": self.plain_language_summary,
            "tool_name": self.tool_name,
            "inputs_summary": self.inputs_summary,
            "outputs_summary": self.outputs_summary,
            "warnings": list(self.warnings),
            "evidence_ids": list(self.evidence_ids),
            "requires_human_review": self.requires_human_review,
            "technical_details": dict(self.technical_details),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


# --------------------------------------------------------------------------- #
# Trace
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AgentTrace:
    """The full agent trace attached to a proposal/trade payload.

    Attributes:
        run_id: Stable run id (derived from proposal_id / transaction_id).
        intent_type: ``TraceIntentType`` value (string).
        overall_status: ``TraceOverallStatus`` value (string).
        current_state: The decision-state-machine state this run ended in
            (e.g. ``awaiting_human_approval`` / ``blocked``).
        data_source_label: Plain-language data source label (e.g.
            "演示数据" / "历史数据样本").
        steps: Ordered list of ``AgentTraceStep``.
        requires_human_approval: Whether the run requires human approval.
        approval_state: ``ApprovalState`` value (string).
        final_message: Always the read-only disclaimer.
    """

    run_id: str
    intent_type: str
    overall_status: str
    current_state: str
    data_source_label: str
    steps: List[AgentTraceStep] = field(default_factory=list)
    requires_human_approval: bool = True
    approval_state: str = ApprovalState.REQUIRED.value
    final_message: str = FINAL_MESSAGE_READ_ONLY

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for JSON payloads."""
        return {
            "run_id": self.run_id,
            "intent_type": self.intent_type,
            "overall_status": self.overall_status,
            "current_state": self.current_state,
            "data_source_label": self.data_source_label,
            "steps": [s.to_dict() for s in self.steps],
            "requires_human_approval": self.requires_human_approval,
            "approval_state": self.approval_state,
            "final_message": self.final_message,
        }
