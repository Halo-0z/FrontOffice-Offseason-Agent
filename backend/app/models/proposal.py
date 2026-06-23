"""Structured proposal models for FrontOffice-Offseason-Agent (M4-C).

These are DEMO/SAMPLE/SIMULATION models. They represent the
frontend-friendly structured proposal produced by the deterministic
``proposal_builder`` from an M4-B ``OffseasonAgentRun``. They are
**not** LLM-generated natural-language briefs, **not** MCP payloads,
and **not** approved transactions.

All dataclasses are frozen so callers cannot mutate the proposal in
place. The ``proposal_builder`` returns new instances and never writes
to disk.

Field naming is intentionally stable and snake_case so a frontend can
render these objects directly without renaming.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #


class ProposalStatus(str, Enum):
    """Overall status of a ``StructuredProposal``.

    - ``RECOMMENDED``: the orchestrator ran cleanly and at least one
      signing preview passed validation. This does NOT mean any
      transaction was approved — every action still requires human
      approval.
    - ``PARTIAL``: the orchestrator completed but one or more tools
      fell back (e.g. evidence missing, some previews failed
      validation) and the proposal is incomplete.
    - ``BLOCKED``: every signing preview failed validation; no action
      can be recommended without changes to the goal or roster.
    - ``NO_ACTION``: no free-agent candidates were produced, so no
      signing previews were generated.
    """

    RECOMMENDED = "RECOMMENDED"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"
    NO_ACTION = "NO_ACTION"


class ProposalActionType(str, Enum):
    """Kind of action a ``ProposalAction`` represents.

    - ``SIGNING``: a free-agent signing preview.
    - ``TRADE``: a two-team trade preview (reserved for future use;
      M4-C only emits SIGNING actions).
    - ``HOLD``: a no-op recommendation (e.g. when no candidates match
      the goal constraints).
    """

    SIGNING = "SIGNING"
    TRADE = "TRADE"
    HOLD = "HOLD"


class ProposalRiskLevel(str, Enum):
    """Severity of a ``ProposalRisk``.

    - ``LOW``: minor caveat (e.g. sample data, MVP heuristic).
    - ``MEDIUM``: notable concern (e.g. partial evidence, single
      candidate).
    - ``HIGH``: blocking concern (e.g. validation failed, no
      candidates).
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# --------------------------------------------------------------------------- #
# Evidence ref
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProposalEvidenceRef:
    """A flattened reference to an ``EvidenceNote`` in a proposal.

    Built only from notes that actually exist in
    ``data/evidence_notes.json`` — the builder never fabricates
    evidence ids.

    Attributes:
        evidence_id: Stable identifier, e.g. ``"ev-001"``.
        title: Short title (echoed from the note).
        source: Source label (echoed from the note).
        evidence_type: ``EvidenceType`` value as a string.
        sample_data: Always ``True`` for demo notes.
    """

    evidence_id: str
    title: str
    source: str
    evidence_type: str
    sample_data: bool = True


# --------------------------------------------------------------------------- #
# Action
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProposalAction:
    """A single recommended (or blocked) action in a proposal.

    This is a **proposal** object, never an approved transaction.
    ``requires_human_approval`` is always ``True``.

    Attributes:
        action_id: Stable action identifier (derived from
            transaction_id when available, else a deterministic slug).
        action_type: ``SIGNING`` / ``TRADE`` / ``HOLD``.
        transaction_id: Echoed from the underlying ``SigningTransaction``
            when available; ``None`` for HOLD actions.
        team_id: Team the action is for.
        player_id: Free-agent id being signed, when available.
        player_name: Display name, when available.
        position: Position string (e.g. ``"C"``), when available.
        salary: First-season salary, when available.
        years: Contract years, when available.
        validation_status: ``ValidationStatus`` value as a string
            (``"PASS"`` / ``"WARNING"`` / ``"FAIL"``), or ``"NOT_VALIDATED"``
            for HOLD actions.
        is_valid: ``True`` if the underlying validation result had no
            FAIL-severity issues. ``False`` otherwise.
        fit_score: ``FreeAgentFit.fit_score`` when available.
        matched_need: Short string describing the matched position need
            (e.g. ``"C: have 0, target 2"``), when available.
        cap_impact_summary: Short deterministic summary of the cap
            impact, derived from the validation result.
        roster_impact_summary: Short deterministic summary of the
            roster impact, derived from ``roster_need_after``.
        depth_chart_impact_summary: Short deterministic summary of the
            depth-chart impact, derived from ``depth_chart_after``.
        evidence_ids: Evidence ids cited by this action.
        requires_human_approval: Always ``True``.
        limitations: MVP limitation notes for this action.
    """

    action_id: str
    action_type: ProposalActionType
    team_id: str
    validation_status: str
    is_valid: bool
    requires_human_approval: bool = True
    transaction_id: Optional[str] = None
    player_id: Optional[str] = None
    player_name: Optional[str] = None
    position: Optional[str] = None
    salary: Optional[int] = None
    years: Optional[int] = None
    fit_score: Optional[float] = None
    matched_need: Optional[str] = None
    cap_impact_summary: str = ""
    roster_impact_summary: str = ""
    depth_chart_impact_summary: str = ""
    evidence_ids: Tuple[str, ...] = field(default_factory=tuple)
    limitations: Tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# Risk
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ProposalRisk:
    """A single risk note attached to a proposal.

    Attributes:
        code: Stable machine-readable code, e.g.
            ``"evidence_missing"``, ``"validation_failed"``,
            ``"no_matching_candidate"``, ``"cap_pressure"``,
            ``"sample_data"``.
        level: ``LOW`` / ``MEDIUM`` / ``HIGH``.
        summary: Short deterministic explanation.
        evidence_ids: Evidence ids relevant to this risk (may be empty).
    """

    code: str
    level: ProposalRiskLevel
    summary: str
    evidence_ids: Tuple[str, ...] = field(default_factory=tuple)


# --------------------------------------------------------------------------- #
# Structured proposal
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class StructuredProposal:
    """A frontend-friendly structured proposal built from an
    ``OffseasonAgentRun``.

    All fields are immutable. ``requires_human_approval`` is always
    ``True``; ``sample_data`` is always ``True`` (demo data only).

    Attributes:
        proposal_id: Stable deterministic id derived from team_id and
            goal.
        team_id: Team the proposal is for.
        objective: Echoed from the ``OffseasonGoal``.
        status: ``RECOMMENDED`` / ``PARTIAL`` / ``BLOCKED`` / ``NO_ACTION``.
        recommended_actions: Tuple of ``ProposalAction`` objects. Only
            actions whose validation passed are marked ``is_valid=True``;
            failed actions are still included (with ``is_valid=False``)
            so the frontend can show why they were blocked.
        risks: Tuple of ``ProposalRisk`` objects.
        evidence_refs: Tuple of ``ProposalEvidenceRef`` objects, one per
            matched note in the evidence bundle.
        tool_call_trace: Echoed from the ``OffseasonAgentRun`` so the
            frontend can show the full tool trace.
        cap_summary: Short deterministic summary of the team's current
            cap situation.
        roster_need_summary: Short deterministic summary of the team's
            current roster needs.
        depth_chart_summary: Short deterministic summary of the team's
            current depth chart.
        fallback_reasons: Tuple of human-readable fallback strings
            (e.g. missing evidence, no candidates).
        limitations: MVP limitation notes.
        requires_human_approval: Always ``True``.
        sample_data: Always ``True``.
    """

    proposal_id: str
    team_id: str
    objective: str
    status: ProposalStatus
    recommended_actions: Tuple[ProposalAction, ...] = field(default_factory=tuple)
    risks: Tuple[ProposalRisk, ...] = field(default_factory=tuple)
    evidence_refs: Tuple[ProposalEvidenceRef, ...] = field(default_factory=tuple)
    tool_call_trace: Tuple[object, ...] = field(default_factory=tuple)
    cap_summary: str = ""
    roster_need_summary: str = ""
    depth_chart_summary: str = ""
    fallback_reasons: Tuple[str, ...] = field(default_factory=tuple)
    limitations: Tuple[str, ...] = field(default_factory=tuple)
    requires_human_approval: bool = True
    sample_data: bool = True
