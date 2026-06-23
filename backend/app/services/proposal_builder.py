"""Deterministic structured proposal builder (M4-C).

This module is a **deterministic proposal builder**. It is NOT an MCP
server, NOT an MCP client, NOT an LLM agent, and NOT an OpenAI
function-calling harness. It does not call any LLM and does not touch
the network.

The builder consumes an M4-B ``OffseasonAgentRun`` and produces a
frontend-friendly ``StructuredProposal``. It does NOT re-run any tool,
does NOT call ``transaction_rule_engine`` or ``trade_simulator``
directly, and does NOT write to disk. Every action in the proposal is
a **preview** that requires human approval.

Public API:

- ``build_structured_proposal(agent_run) -> StructuredProposal``
- ``run_goal_and_build_proposal(goal, data_dir) -> StructuredProposal``
  (convenience wrapper that calls ``run_offseason_plan`` first)

Run tests:

    python -m pytest backend/app/tests/test_proposal_builder.py
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from ..models.agent import (
    AgentRunStatus,
    OffseasonAgentRun,
    OffseasonGoal,
    ToolCallRecord,
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
from ..models.transaction import ValidationStatus
from .offseason_agent import run_offseason_plan


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class ProposalBuilderError(Exception):
    """Base class for proposal_builder errors."""


# --------------------------------------------------------------------------- #
# Constants / MVP limitations
# --------------------------------------------------------------------------- #

_MVP_LIMITATIONS: Tuple[str, ...] = (
    "M4-C deterministic structured proposal builder only.",
    "No LLM call.",
    "No MCP server/client.",
    "No external NBA API or live salary data.",
    "All actions are previews and require human approval.",
    "Proposal is derived from sample/simulation data.",
)

# Cap pressure thresholds (relative to luxury tax / first apron).
# If the team's current total_salary is within this fraction of the
# luxury tax line, we emit a cap_pressure risk. These thresholds are
# deliberately conservative and only trigger when the cap summary
# fields are available.
_CAP_PRESSURE_TAX_FACTOR = 0.9  # within 90% of luxury tax
_CAP_PRESSURE_APRON_FACTOR = 0.95  # within 95% of first apron


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


def _build_proposal_id(team_id: str, objective: str) -> str:
    """Deterministic proposal id from team_id + objective.

    We avoid hashing so the id is human-readable and stable across
    runs. We slugify the objective to its first 40 chars of
    alphanumerics.
    """
    slug = "".join(c if c.isalnum() else "-" for c in objective.lower())
    # Collapse repeated dashes and strip leading/trailing dashes.
    while "--" in slug:
        slug = slug.replace("--", "-")
    slug = slug.strip("-")[:40]
    return f"prop-{team_id}-{slug}"


def _summarize_cap(cap_summary: object) -> str:
    """Short deterministic cap summary string."""
    if cap_summary is None:
        return "Cap summary unavailable."
    total = _safe_getattr(cap_summary, "total_salary", "?")
    space = _safe_getattr(cap_summary, "cap_space", "?")
    tax_dist = _safe_getattr(cap_summary, "tax_distance", "?")
    roster = _safe_getattr(cap_summary, "roster_count", "?")
    return (
        f"total_salary={total}, cap_space={space}, "
        f"tax_distance={tax_dist}, roster_count={roster}"
    )


def _summarize_roster_need(report: object) -> str:
    """Short deterministic roster-need summary string."""
    if report is None:
        return "Roster need report unavailable."
    roster_count = _safe_getattr(report, "roster_count", "?")
    needs = _safe_getattr(report, "needs", ()) or ()
    parts = []
    for n in needs:
        pos = _safe_getattr(n, "position", "?")
        pos_val = _enum_value(pos) if pos != "?" else "?"
        current = _safe_getattr(n, "current_count", "?")
        target = _safe_getattr(n, "target_count", "?")
        priority = _safe_getattr(n, "priority", "?")
        priority_val = _enum_value(priority) if priority != "?" else "?"
        parts.append(f"{pos_val}:{current}/{target}({priority_val})")
    return f"roster_count={roster_count}, needs=[{', '.join(parts)}]"


def _summarize_depth_chart(chart: object) -> str:
    """Short deterministic depth-chart summary string."""
    if chart is None:
        return "Depth chart unavailable."
    slots = _safe_getattr(chart, "slots", ()) or ()
    parts = []
    for s in slots:
        pos = _safe_getattr(s, "position", "?")
        pos_val = _enum_value(pos) if pos != "?" else "?"
        starter = _safe_getattr(s, "starter", None)
        starter_id = (
            _safe_getattr(starter, "player_id", "None") if starter else "None"
        )
        need_level = _safe_getattr(s, "need_level", "?")
        need_val = _enum_value(need_level) if need_level != "?" else "?"
        parts.append(f"{pos_val}:{starter_id}/{need_val}")
    return ",".join(parts)


def _summarize_cap_impact(preview: object) -> str:
    """Short deterministic cap-impact summary for a single preview."""
    if preview is None:
        return "Preview unavailable."
    vr = _safe_getattr(preview, "validation_result", None)
    cap_after = _safe_getattr(preview, "cap_summary_after", None)
    if cap_after is None:
        cap_after = _safe_getattr(vr, "cap_summary_after", None)
    if cap_after is None:
        return "cap_summary_after unavailable."
    total = _safe_getattr(cap_after, "total_salary", "?")
    space = _safe_getattr(cap_after, "cap_space", "?")
    return f"after: total_salary={total}, cap_space={space}"


def _summarize_roster_impact(preview: object) -> str:
    """Short deterministic roster-impact summary for a single preview."""
    if preview is None:
        return "Preview unavailable."
    after = _safe_getattr(preview, "roster_need_after", None)
    if after is None:
        return "roster_need_after unavailable (validation failed or missing profile)."
    return _summarize_roster_need(after)


def _summarize_depth_chart_impact(preview: object) -> str:
    """Short deterministic depth-chart-impact summary for a preview."""
    if preview is None:
        return "Preview unavailable."
    after = _safe_getattr(preview, "depth_chart_after", None)
    if after is None:
        return "depth_chart_after unavailable (validation failed or missing profile)."
    return _summarize_depth_chart(after)


def _match_fit_to_preview(
    preview: object, fits: Tuple[object, ...]
) -> Optional[object]:
    """Find the ``FreeAgentFit`` whose ``free_agent_id`` matches the
    preview's underlying transaction ``player_id``.

    The preview itself only carries ``transaction_id``; we look up the
    validation_result to get the player_id. Returns ``None`` if no fit
    matches.
    """
    vr = _safe_getattr(preview, "validation_result", None)
    if vr is None:
        return None
    # ValidationResult doesn't carry player_id directly, but the
    # transaction_id in the preview encodes the player. We match by
    # scanning fits and checking if their free_agent_id appears in the
    # preview's transaction_id (the M4-B builder formats
    # ``m4b-preview-{idx}-{free_agent_id}``).
    tx_id = _safe_getattr(preview, "transaction_id", "") or ""
    for fit in fits:
        fa_id = _safe_getattr(fit, "free_agent_id", "")
        if fa_id and fa_id in str(tx_id):
            return fit
    return None


def _matched_need_summary(fit: object) -> Optional[str]:
    """Short string describing the matched position need for a fit."""
    if fit is None:
        return None
    matched = _safe_getattr(fit, "matched_need", None)
    if matched is None:
        return None
    pos = _safe_getattr(matched, "position", "?")
    pos_val = _enum_value(pos) if pos != "?" else "?"
    current = _safe_getattr(matched, "current_count", "?")
    target = _safe_getattr(matched, "target_count", "?")
    priority = _safe_getattr(matched, "priority", "?")
    priority_val = _enum_value(priority) if priority != "?" else "?"
    return f"{pos_val}: have {current}, target {target} (priority={priority_val})"


def _build_action_from_preview(
    preview: object,
    team_id: str,
    fits: Tuple[object, ...],
    action_index: int,
) -> ProposalAction:
    """Build a ``ProposalAction`` from a ``TransactionPreview``.

    Looks up the matching ``FreeAgentFit`` to fill in player_name /
    position / fit_score / matched_need. The action's
    ``requires_human_approval`` is always ``True``.
    """
    tx_id = _safe_getattr(preview, "transaction_id", None)
    tx_id_str = str(tx_id) if tx_id is not None else None

    vr = _safe_getattr(preview, "validation_result", None)
    validation_status_str = "NOT_VALIDATED"
    is_valid = False
    if vr is not None:
        status = _safe_getattr(vr, "status", None)
        validation_status_str = _enum_value(status) if status is not None else "NOT_VALIDATED"
        is_valid = bool(_safe_getattr(vr, "is_valid", False))

    fit = _match_fit_to_preview(preview, fits)

    player_id = _safe_getattr(fit, "free_agent_id", None) if fit else None
    player_name = _safe_getattr(fit, "name", None) if fit else None
    position = _safe_getattr(fit, "position", None) if fit else None
    position_str = _enum_value(position) if position is not None else None
    salary = _safe_getattr(fit, "expected_salary", None) if fit else None
    fit_score = _safe_getattr(fit, "fit_score", None) if fit else None
    matched_need = _matched_need_summary(fit)
    evidence_ids: Tuple[str, ...] = ()
    if fit is not None:
        raw_eids = _safe_getattr(fit, "evidence_ids", ()) or ()
        evidence_ids = tuple(str(e) for e in raw_eids)

    # Years: M4-B always uses 1-year preview contracts.
    years = 1

    # Limitations: echo the preview's limitations.
    raw_limitations = _safe_getattr(preview, "limitations", ()) or ()
    limitations = tuple(str(l) for l in raw_limitations)

    # action_id: deterministic, derived from transaction_id.
    action_id = f"act-{action_index}-{tx_id_str or 'hold'}"

    return ProposalAction(
        action_id=action_id,
        action_type=ProposalActionType.SIGNING,
        team_id=team_id,
        validation_status=validation_status_str,
        is_valid=is_valid,
        requires_human_approval=True,
        transaction_id=tx_id_str,
        player_id=str(player_id) if player_id is not None else None,
        player_name=str(player_name) if player_name is not None else None,
        position=position_str,
        salary=int(salary) if salary is not None else None,
        years=years,
        fit_score=float(fit_score) if fit_score is not None else None,
        matched_need=matched_need,
        cap_impact_summary=_summarize_cap_impact(preview),
        roster_impact_summary=_summarize_roster_impact(preview),
        depth_chart_impact_summary=_summarize_depth_chart_impact(preview),
        evidence_ids=evidence_ids,
        limitations=limitations,
    )


def _derive_proposal_status(
    agent_run_status: AgentRunStatus,
    signing_previews: Tuple[object, ...],
    free_agent_fits: Tuple[object, ...],
) -> ProposalStatus:
    """Derive the ``ProposalStatus`` from the agent run + previews.

    Rules (in order):

    - No fits and no previews -> ``NO_ACTION``.
    - Previews exist but ALL failed validation -> ``BLOCKED``.
    - At least one valid preview and agent_run_status is SUCCESS ->
      ``RECOMMENDED``.
    - Otherwise (mixed valid/failed, or agent_run_status is PARTIAL) ->
      ``PARTIAL``.
    - If agent_run_status is FAILED -> ``BLOCKED`` (we cannot recommend
      anything when the orchestrator failed).
    """
    if agent_run_status is AgentRunStatus.FAILED:
        return ProposalStatus.BLOCKED

    if not free_agent_fits and not signing_previews:
        return ProposalStatus.NO_ACTION

    if not signing_previews:
        # Had fits but no previews were generated (e.g. all filtered
        # out, or preview tool failed). Treat as PARTIAL.
        return ProposalStatus.PARTIAL

    # Check validation results.
    any_valid = False
    any_failed = False
    for p in signing_previews:
        vr = _safe_getattr(p, "validation_result", None)
        if vr is None:
            any_failed = True
            continue
        is_valid = bool(_safe_getattr(vr, "is_valid", False))
        if is_valid:
            any_valid = True
        else:
            any_failed = True

    if not any_valid and any_failed:
        return ProposalStatus.BLOCKED

    if any_valid and not any_failed and agent_run_status is AgentRunStatus.SUCCESS:
        return ProposalStatus.RECOMMENDED

    return ProposalStatus.PARTIAL


def _build_evidence_refs(evidence_bundle: object) -> Tuple[ProposalEvidenceRef, ...]:
    """Build ``ProposalEvidenceRef`` objects from the evidence bundle.

    Only matched notes are referenced — the builder never fabricates
    evidence ids. ``sample_data`` is always ``True``.
    """
    if evidence_bundle is None:
        return ()
    matched = _safe_getattr(evidence_bundle, "matched_notes", ()) or ()
    refs: List[ProposalEvidenceRef] = []
    for note in matched:
        eid = _safe_getattr(note, "evidence_id", None)
        if eid is None:
            continue
        title = _safe_getattr(note, "title", "") or ""
        source = _safe_getattr(note, "source", "") or ""
        etype = _safe_getattr(note, "evidence_type", None)
        etype_str = _enum_value(etype) if etype is not None else ""
        sample = bool(_safe_getattr(note, "sample_data", True))
        refs.append(
            ProposalEvidenceRef(
                evidence_id=str(eid),
                title=str(title),
                source=str(source),
                evidence_type=etype_str,
                sample_data=sample,
            )
        )
    return tuple(refs)


def _build_risks(
    agent_run: OffseasonAgentRun,
    signing_previews: Tuple[object, ...],
    free_agent_fits: Tuple[object, ...],
    proposal_status: ProposalStatus,
) -> Tuple[ProposalRisk, ...]:
    """Build the ``ProposalRisk`` tuple from the agent run state.

    Risks emitted:

    - ``evidence_missing`` (MEDIUM) when the evidence bundle has a
      non-empty ``fallback_reason`` or non-empty ``missing_evidence_ids``.
    - ``validation_failed`` (HIGH) when any signing preview failed
      validation.
    - ``no_matching_candidate`` (HIGH) when there are no free-agent
      fits.
    - ``cap_pressure`` (MEDIUM) when the team's current cap summary
      shows total_salary within ``_CAP_PRESSURE_TAX_FACTOR`` of the
      luxury tax line (only emitted when the cap summary fields are
      available).
    - ``sample_data`` (LOW) always, because the proposal is built from
      demo/simulation data.
    """
    risks: List[ProposalRisk] = []

    # evidence_missing
    bundle = agent_run.evidence_bundle
    if bundle is not None:
        fallback = _safe_getattr(bundle, "fallback_reason", None)
        missing = _safe_getattr(bundle, "missing_evidence_ids", ()) or ()
        if fallback or missing:
            summary_parts = []
            if fallback:
                summary_parts.append(str(fallback))
            if missing:
                summary_parts.append(f"missing_evidence_ids={list(missing)}")
            risks.append(
                ProposalRisk(
                    code="evidence_missing",
                    level=ProposalRiskLevel.MEDIUM,
                    summary="; ".join(summary_parts),
                    evidence_ids=tuple(str(e) for e in missing),
                )
            )

    # validation_failed
    failed_evidence_ids: List[str] = []
    any_failed = False
    for p in signing_previews:
        vr = _safe_getattr(p, "validation_result", None)
        if vr is None:
            any_failed = True
            continue
        is_valid = bool(_safe_getattr(vr, "is_valid", False))
        if not is_valid:
            any_failed = True
            eids = _safe_getattr(vr, "evidence_ids", ()) or ()
            for e in eids:
                if str(e) not in failed_evidence_ids:
                    failed_evidence_ids.append(str(e))
    if any_failed:
        risks.append(
            ProposalRisk(
                code="validation_failed",
                level=ProposalRiskLevel.HIGH,
                summary=(
                    "One or more signing previews failed validation; "
                    "those actions are blocked and not recommended."
                ),
                evidence_ids=tuple(failed_evidence_ids),
            )
        )

    # no_matching_candidate
    if not free_agent_fits:
        risks.append(
            ProposalRisk(
                code="no_matching_candidate",
                level=ProposalRiskLevel.HIGH,
                summary=(
                    "No free-agent candidates matched the goal constraints "
                    "(target_positions / max_salary / max_candidates)."
                ),
            )
        )

    # cap_pressure (only when cap summary fields are available)
    cap = agent_run.cap_summary
    if cap is not None:
        total_salary = _safe_getattr(cap, "total_salary", None)
        tax_distance = _safe_getattr(cap, "tax_distance", None)
        first_apron_distance = _safe_getattr(cap, "first_apron_distance", None)
        # We need the luxury tax line and first apron line to compute
        # thresholds. These are not on the CapSheetSummary directly,
        # but we can infer pressure from the distance fields: a small
        # positive distance means close to the line; negative means
        # over the line.
        if (
            total_salary is not None
            and isinstance(total_salary, int)
            and tax_distance is not None
            and isinstance(tax_distance, int)
        ):
            # If tax_distance is negative, team is over the tax line.
            # If tax_distance is small positive, team is close.
            # We emit cap_pressure when tax_distance <= 10% of
            # total_salary (a rough proxy for "within 90% of the tax
            # line"). We avoid division by zero.
            if total_salary > 0:
                ratio = tax_distance / total_salary
                if ratio <= 0.1:
                    risks.append(
                        ProposalRisk(
                            code="cap_pressure",
                            level=ProposalRiskLevel.MEDIUM,
                            summary=(
                                f"Team is close to or over the luxury tax "
                                f"line (tax_distance={tax_distance}, "
                                f"total_salary={total_salary})."
                            ),
                        )
                    )
            elif tax_distance < 0:
                risks.append(
                    ProposalRisk(
                        code="cap_pressure",
                        level=ProposalRiskLevel.MEDIUM,
                        summary=(
                            f"Team is over the luxury tax line "
                            f"(tax_distance={tax_distance})."
                        ),
                    )
                )
        if (
            first_apron_distance is not None
            and isinstance(first_apron_distance, int)
            and first_apron_distance < 0
        ):
            # Over the first apron — upgrade existing cap_pressure or
            # add a new one.
            existing = next(
                (r for r in risks if r.code == "cap_pressure"), None
            )
            if existing is None:
                risks.append(
                    ProposalRisk(
                        code="cap_pressure",
                        level=ProposalRiskLevel.HIGH,
                        summary=(
                            f"Team is over the first apron "
                            f"(first_apron_distance={first_apron_distance})."
                        ),
                    )
                )

    # sample_data (always)
    risks.append(
        ProposalRisk(
            code="sample_data",
            level=ProposalRiskLevel.LOW,
            summary=(
                "Proposal is built from DEMO/SAMPLE/SIMULATION data; "
                "not real NBA data."
            ),
        )
    )

    return tuple(risks)


def _build_fallback_reasons(agent_run: OffseasonAgentRun) -> Tuple[str, ...]:
    """Collect human-readable fallback reasons from the agent run."""
    reasons: List[str] = []

    # From tool_call_trace: any FALLBACK / FAILED entries.
    for record in agent_run.tool_call_trace:
        status = _safe_getattr(record, "status", None)
        status_val = _enum_value(status) if status is not None else ""
        reason = _safe_getattr(record, "fallback_reason", None)
        tool = _safe_getattr(record, "tool_name", "?")
        if status_val == "FALLBACK" and reason:
            reasons.append(f"{tool}: {reason}")
        elif status_val == "FAILED" and reason:
            reasons.append(f"{tool} FAILED: {reason}")

    # From evidence bundle: missing evidence ids.
    bundle = agent_run.evidence_bundle
    if bundle is not None:
        missing = _safe_getattr(bundle, "missing_evidence_ids", ()) or ()
        if missing:
            reasons.append(
                f"evidence_service: missing evidence ids {list(missing)}"
            )
        fallback = _safe_getattr(bundle, "fallback_reason", None)
        if fallback:
            reasons.append(f"evidence_service: {fallback}")

    # From agent_run.limitations: echo any that mention "fallback" or
    # "failed" or "missing" (case-insensitive).
    for lim in agent_run.limitations:
        lim_lower = str(lim).lower()
        if any(kw in lim_lower for kw in ("fallback", "failed", "missing", "no candidates")):
            reasons.append(str(lim))

    # Dedup while preserving order.
    seen = set()
    deduped: List[str] = []
    for r in reasons:
        if r not in seen:
            deduped.append(r)
            seen.add(r)
    return tuple(deduped)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def build_structured_proposal(
    agent_run: OffseasonAgentRun,
) -> StructuredProposal:
    """Build a ``StructuredProposal`` from an ``OffseasonAgentRun``.

    This function is **deterministic**: the same ``agent_run`` always
    produces the same proposal. It does NOT call any LLM, does NOT use
    MCP, does NOT call ``transaction_rule_engine`` or
    ``trade_simulator``, and does NOT write to disk.

    The proposal's ``requires_human_approval`` is always ``True``;
    ``sample_data`` is always ``True``. Every ``ProposalAction`` in
    ``recommended_actions`` has ``requires_human_approval=True``.
    """
    team_id = agent_run.team_id
    objective = str(_safe_getattr(agent_run.goal, "objective", ""))

    # Derive proposal status.
    proposal_status = _derive_proposal_status(
        agent_run.status,
        agent_run.signing_previews,
        agent_run.free_agent_fits,
    )

    # Build actions from signing previews. We include ALL previews
    # (valid and invalid) so the frontend can show why blocked actions
    # were blocked. The ``is_valid`` flag distinguishes them.
    actions: List[ProposalAction] = []
    for idx, preview in enumerate(agent_run.signing_previews):
        actions.append(
            _build_action_from_preview(
                preview, team_id, agent_run.free_agent_fits, idx
            )
        )

    # If there were no previews but the goal was a signing goal, emit
    # a single HOLD action so the frontend has something to show.
    if not actions and not agent_run.free_agent_fits:
        actions.append(
            ProposalAction(
                action_id=f"act-0-hold-{team_id}",
                action_type=ProposalActionType.HOLD,
                team_id=team_id,
                validation_status="NOT_VALIDATED",
                is_valid=False,
                requires_human_approval=True,
                cap_impact_summary="No action; no candidates matched.",
                roster_impact_summary="No action; roster unchanged.",
                depth_chart_impact_summary="No action; depth chart unchanged.",
                limitations=(
                    "No free-agent candidates matched the goal constraints.",
                ),
            )
        )

    # Build evidence refs.
    evidence_refs = _build_evidence_refs(agent_run.evidence_bundle)

    # Build risks.
    risks = _build_risks(
        agent_run,
        agent_run.signing_previews,
        agent_run.free_agent_fits,
        proposal_status,
    )

    # Build summaries.
    cap_summary_str = _summarize_cap(agent_run.cap_summary)
    roster_need_summary_str = _summarize_roster_need(agent_run.roster_need_report)
    depth_chart_summary_str = _summarize_depth_chart(agent_run.current_depth_chart)

    # Build fallback reasons.
    fallback_reasons = _build_fallback_reasons(agent_run)

    # Limitations: MVP limitations + echoed agent_run limitations.
    limitations: List[str] = list(_MVP_LIMITATIONS)
    for lim in agent_run.limitations:
        if str(lim) not in limitations:
            limitations.append(str(lim))

    # proposal_id: deterministic.
    proposal_id = _build_proposal_id(team_id, objective)

    return StructuredProposal(
        proposal_id=proposal_id,
        team_id=team_id,
        objective=objective,
        status=proposal_status,
        recommended_actions=tuple(actions),
        risks=risks,
        evidence_refs=evidence_refs,
        tool_call_trace=agent_run.tool_call_trace,
        cap_summary=cap_summary_str,
        roster_need_summary=roster_need_summary_str,
        depth_chart_summary=depth_chart_summary_str,
        fallback_reasons=fallback_reasons,
        limitations=tuple(limitations),
        requires_human_approval=True,
        sample_data=True,
    )


def run_goal_and_build_proposal(
    goal: OffseasonGoal, data_dir: Path | str = "data"
) -> StructuredProposal:
    """Convenience wrapper: run ``run_offseason_plan`` then
    ``build_structured_proposal``.

    This is the one-call entry point for callers who have an
    ``OffseasonGoal`` and want a finished proposal. It does NOT call
    any LLM, does NOT use MCP, and does NOT write to disk.
    """
    agent_run = run_offseason_plan(goal, data_dir)
    return build_structured_proposal(agent_run)
