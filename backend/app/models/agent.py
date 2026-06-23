"""Agent models for FrontOffice-Offseason-Agent (M4-B).

These are DEMO/SAMPLE/SIMULATION models. They represent the structured
result of a deterministic local tool-orchestration run by the
``offseason_agent``. They are **not** LLM messages, **not** MCP
requests, and **not** natural-language briefs (those are deferred to
M4-C).

All dataclasses are frozen so callers cannot mutate the run result in
place. The ``offseason_agent`` returns new instances and never writes
to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class AgentRunStatus(str, Enum):
    """Overall status of an ``OffseasonAgentRun``.

    - ``SUCCESS``: the orchestrator ran to completion. This does NOT
      mean any transaction was approved — every output is still a
      preview that requires human approval.
    - ``PARTIAL``: the orchestrator completed but one or more tools
      fell back (e.g. no free-agent candidates, missing evidence).
    - ``FAILED``: a critical tool failed (e.g. unknown team_id) and
      the run could not produce a useful result.
    """

    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ToolCallStatus(str, Enum):
    """Status of a single ``ToolCallRecord``.

    - ``SUCCESS``: the tool returned a normal result.
    - ``FALLBACK``: the tool returned a fallback/empty result (e.g.
      no evidence matched) but did not raise.
    - ``FAILED``: the tool raised an exception.
    """

    SUCCESS = "SUCCESS"
    FALLBACK = "FALLBACK"
    FAILED = "FAILED"


@dataclass(frozen=True)
class OffseasonGoal:
    """A user-supplied offseason goal for the agent to work on.

    Attributes:
        team_id: The team to plan for (must exist in ``teams.json``).
        objective: Free-form objective string (e.g. "add frontcourt
            help without losing flexibility"). The deterministic
            orchestrator does NOT parse this with an LLM; it is
            carried through for the run record only.
        target_positions: Optional position filter (e.g. ``("C",)``).
            Free-agent candidates whose position is NOT in this tuple
            are filtered out. Empty tuple = no filter.
        max_salary: Optional cap on ``expected_salary`` for free-agent
            candidates. ``None`` or ``0`` means no filter.
        max_candidates: Max number of free-agent fits to keep after
            filtering (applied after sorting by ``fit_score`` desc).
            ``0`` means no limit.
        evidence_query: Optional free-text query for
            ``evidence_service.search_evidence``.
    """

    team_id: str
    objective: str
    target_positions: Tuple[str, ...] = field(default_factory=tuple)
    max_salary: Optional[int] = None
    max_candidates: int = 3
    evidence_query: Optional[str] = None


@dataclass(frozen=True)
class ToolCallRecord:
    """A single tool call recorded in the agent's ``tool_call_trace``.

    Attributes:
        tool_name: Dotted name, e.g.
            ``"cap_sheet_service.summarize_cap_sheet"``.
        status: ``SUCCESS`` / ``FALLBACK`` / ``FAILED``.
        input_summary: Short deterministic string describing the input
            (e.g. ``"team_id=DEM-ATL"``).
        output_summary: Short deterministic string describing the
            output (e.g. ``"cap_space=66000000"``).
        fallback_reason: ``None`` on SUCCESS; a clear string on
            FALLBACK / FAILED.
        evidence_ids: Evidence ids produced or referenced by this
            tool call (may be empty).
    """

    tool_name: str
    status: ToolCallStatus
    input_summary: str
    output_summary: str
    fallback_reason: Optional[str] = None
    evidence_ids: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class OffseasonAgentRun:
    """Structured result of a deterministic ``run_offseason_plan`` call.

    All fields are immutable. ``requires_human_approval`` is always
    ``True``; ``sample_data`` is always ``True`` (demo data only).

    Attributes:
        team_id: The team the run was for.
        goal: The original ``OffseasonGoal``.
        status: ``SUCCESS`` / ``PARTIAL`` / ``FAILED``.
        cap_summary: The team's current ``CapSheetSummary`` (or
            ``None`` if the cap tool failed).
        roster_need_report: The team's current ``RosterNeedReport`` (or
            ``None`` if the roster tool failed).
        current_depth_chart: The team's current ``ProjectedDepthChart``
            (or ``None`` if the depth tool failed).
        free_agent_fits: Filtered + capped ``FreeAgentFit`` candidates.
        signing_previews: ``TransactionPreview`` objects for the top
            free-agent fits. Every preview has
            ``requires_human_approval=True``.
        evidence_bundle: The ``EvidenceBundle`` retrieved by
            ``evidence_service``.
        tool_call_trace: Ordered ``ToolCallRecord`` entries for every
            tool the orchestrator called.
        limitations: MVP limitation notes.
        requires_human_approval: Always ``True``.
        sample_data: Always ``True``.
    """

    team_id: str
    goal: OffseasonGoal
    status: AgentRunStatus
    cap_summary: Optional[object] = None
    roster_need_report: Optional[object] = None
    current_depth_chart: Optional[object] = None
    free_agent_fits: Tuple[object, ...] = field(default_factory=tuple)
    signing_previews: Tuple[object, ...] = field(default_factory=tuple)
    evidence_bundle: Optional[object] = None
    tool_call_trace: Tuple[ToolCallRecord, ...] = field(default_factory=tuple)
    limitations: Tuple[str, ...] = field(default_factory=tuple)
    requires_human_approval: bool = True
    sample_data: bool = True
