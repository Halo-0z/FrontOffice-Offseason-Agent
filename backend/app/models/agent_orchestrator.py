"""Agent orchestrator request/result models (M8-E5).

These dataclasses define the thin service-layer contract for the
preview-only Agent Orchestrator Stub. The orchestrator is a **deterministic
intent router** that maps an explicit allowlisted intent to the project's
existing deterministic preview capabilities (signing preview, trade
preview demo, or hold). It does NOT call any LLM, does NOT use MCP,
does NOT execute transactions, and does NOT mutate any data file.

Design notes
------------
- ``intent`` is an explicit string validated against an allowlist
  (``signing_preview``, ``trade_preview_demo``, ``hold``). Free-form
  natural language is NOT auto-routed to signing or trade.
- Every ``AgentOrchestratorResult`` has ``requires_human_approval=True``.
- The orchestrator never invents verdicts: validation status is read
  directly from the underlying deterministic preview payload.
- All dataclasses are frozen to prevent post-hoc mutation of verdicts.

Hard guardrails (enforced by tests in test_agent_orchestrator.py):
- No LLM / MCP / network imports.
- No execute / apply / commit / mutation endpoints.
- No roster / contract / cap-state / snapshot writes.
- Unsupported intents return blocked/hold — never guessed.
- Demo/historical data is always labeled as demo/sample/historical,
  never as current/live NBA data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class OrchestratorIntent(str, Enum):
    """Allowlisted intents for the preview-only orchestrator."""

    SIGNING_PREVIEW = "signing_preview"
    TRADE_PREVIEW_DEMO = "trade_preview_demo"
    HOLD = "hold"


class OrchestratorStatus(str, Enum):
    """Overall orchestration result status."""

    AWAITING_HUMAN_APPROVAL = "awaiting_human_approval"
    BLOCKED = "blocked"
    HOLD = "hold"


class OrchestratorStepStatus(str, Enum):
    """Status of a single orchestrator trace step."""

    COMPLETED = "completed"
    WARNING = "warning"
    BLOCKED = "blocked"


ORCHESTRATOR_READ_ONLY_MESSAGE = "这是只读预览编排结果，不会自动执行任何操作。"


@dataclass(frozen=True)
class AgentOrchestratorRequest:
    """Input to :func:`orchestrate_preview`.

    Attributes:
        intent: Explicit intent string — must be one of
            ``signing_preview``, ``trade_preview_demo``, ``hold``.
        team_id: Optional team id for signing_preview runs.
        locale: Optional locale hint (reserved for future i18n).
        objective: Optional objective string passed through to the
            signing preview builder.
        metadata: Optional caller-supplied metadata (reserved).
    """

    intent: str
    team_id: Optional[str] = None
    locale: Optional[str] = None
    objective: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OrchestratorTraceStep:
    """A single step in the orchestrator-level agent trace.

    This is the high-level orchestration trace (5 stable steps), not
    the inner per-tool trace produced by ``agent_trace_builder``.

    Attributes:
        step_id: Stable unique id within this orchestration run.
        sequence: 1-based ordering.
        status: ``OrchestratorStepStatus`` value (string).
        title: Human-readable Chinese title.
        plain_language_summary: One-sentence summary.
        tool_name: Contracted orchestrator tool name.
        inputs_summary: Short input summary.
        outputs_summary: Short output summary.
        warnings: Warning strings (may be empty).
        requires_human_review: Whether this step needs manual review.
        technical_details: Developer-facing dict (folded in UI).
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
    requires_human_review: bool = False
    technical_details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
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
            "requires_human_review": self.requires_human_review,
            "technical_details": dict(self.technical_details),
        }


@dataclass(frozen=True)
class OrchestratorTrace:
    """High-level orchestration trace (5 stable steps).

    Steps:
        1. intake_request
        2. route_intent
        3. run_deterministic_preview  (or hold_without_execution)
        4. summarize_validation_and_evidence
        5. request_human_approval
    """

    run_id: str
    intent: str
    overall_status: str
    steps: List[OrchestratorTraceStep] = field(default_factory=list)
    requires_human_approval: bool = True
    data_source_label: str = "演示数据"
    final_message: str = ORCHESTRATOR_READ_ONLY_MESSAGE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "intent": self.intent,
            "overall_status": self.overall_status,
            "steps": [s.to_dict() for s in self.steps],
            "requires_human_approval": self.requires_human_approval,
            "data_source_label": self.data_source_label,
            "final_message": self.final_message,
        }


@dataclass(frozen=True)
class AgentOrchestratorResult:
    """Result returned by :func:`orchestrate_preview`.

    Attributes:
        intent: The resolved intent (always on the allowlist).
        status: ``OrchestratorStatus`` value (string).
        requires_human_approval: Always ``True``.
        preview_payload: The deterministic preview payload from the
            underlying capability (signing payload, trade payload, or
            a minimal hold payload).
        agent_trace: The orchestrator-level trace (5 steps).
        warnings: Non-blocking warning strings.
        limitations: Hard limitation / disclaimer strings.
    """

    intent: str
    status: str
    requires_human_approval: bool
    preview_payload: Dict[str, Any]
    agent_trace: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "status": self.status,
            "requires_human_approval": self.requires_human_approval,
            "preview_payload": dict(self.preview_payload),
            "agent_trace": self.agent_trace,
            "warnings": list(self.warnings),
            "limitations": list(self.limitations),
        }
