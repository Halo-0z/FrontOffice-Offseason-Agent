"""Deterministic offseason agent tool orchestrator (M4-B).

This module is a **local deterministic tool orchestrator**. It is NOT
an MCP server, NOT an MCP client, NOT an LLM agent, and NOT an OpenAI
function-calling harness. It does not call any LLM and does not touch
the network.

The orchestrator runs a fixed sequence of internal tool calls against
the existing M1–M4-A services, records a ``ToolCallRecord`` for each
call, and returns a structured ``OffseasonAgentRun``. Every
transaction output is a **preview** that requires human approval; the
agent never writes to ``data/`` and never approves anything.

Flow:

  goal
    -> cap_sheet_service.summarize_cap_sheet
    -> roster_need_service.evaluate_roster_needs
    -> depth_chart_projector.project_current_depth_chart
    -> free_agent_service.rank_free_agents_for_team (filtered)
    -> trade_simulator.preview_signing (per top fit)
    -> evidence_service.search_evidence + get_evidence_by_ids
    -> OffseasonAgentRun

Guardrails:

- No LLM. No MCP. No network. No disk writes.
- Never bypasses ``transaction_rule_engine`` — every signing preview
  goes through ``trade_simulator.preview_signing`` which calls
  ``validate_transaction`` internally.
- ``requires_human_approval`` is always ``True`` on the run and on
  every preview.
- On tool failure, records a ``FAILED``/``FALLBACK`` ``ToolCallRecord``
  and continues (unless the team_id is unknown, which fails the run).

Run tests:

    python -m pytest backend/app/tests/test_offseason_agent.py
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from ..models.agent import (
    AgentRunStatus,
    OffseasonAgentRun,
    OffseasonGoal,
    ToolCallRecord,
    ToolCallStatus,
)
from ..models.transaction import SigningTransaction, TransactionType
from .cap_sheet_service import (
    CapSheetError,
    TeamNotFoundError,
    load_team_cap_sheet,
    summarize_cap_sheet,
)
from .depth_chart_projector import project_current_depth_chart
from .evidence_service import (
    EvidenceBundle,
    get_evidence_by_ids,
    search_evidence,
)
from .free_agent_service import rank_free_agents_for_team
from .roster_need_service import RosterNeedError, evaluate_roster_needs
from .trade_simulator import preview_signing


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class OffseasonAgentError(Exception):
    """Base class for offseason_agent errors."""


# --------------------------------------------------------------------------- #
# Constants / MVP limitations
# --------------------------------------------------------------------------- #

_MVP_LIMITATIONS: Tuple[str, ...] = (
    "M4-B deterministic local tool orchestration only.",
    "No LLM call.",
    "No MCP server/client.",
    "No external NBA API or live salary data.",
    "All transaction outputs are previews and require human approval.",
)

# Default years for a preview signing contract.
_DEFAULT_SIGNING_YEARS = 1


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _summarize_cap(summary: object) -> str:
    """Build a short deterministic summary string for a CapSheetSummary."""
    if summary is None:
        return "None"
    try:
        return (
            f"total_salary={getattr(summary, 'total_salary', '?')},"
            f"cap_space={getattr(summary, 'cap_space', '?')},"
            f"roster_count={getattr(summary, 'roster_count', '?')}"
        )
    except Exception:
        return repr(summary)


def _summarize_roster_need(report: object) -> str:
    """Build a short deterministic summary string for a RosterNeedReport."""
    if report is None:
        return "None"
    try:
        needs = getattr(report, "needs", ())
        positions = ",".join(
            getattr(n, "position", "?").value
            if hasattr(getattr(n, "position", "?"), "value")
            else str(getattr(n, "position", "?"))
            for n in needs
        )
        return f"roster_count={getattr(report, 'roster_count', '?')},needs=[{positions}]"
    except Exception:
        return repr(report)


def _summarize_depth_chart(chart: object) -> str:
    """Build a short deterministic summary string for a ProjectedDepthChart."""
    if chart is None:
        return "None"
    try:
        slots = getattr(chart, "slots", ())
        parts = []
        for s in slots:
            pos = getattr(s, "position", "?")
            pos_val = pos.value if hasattr(pos, "value") else str(pos)
            starter = getattr(s, "starter", None)
            starter_id = getattr(starter, "player_id", "None") if starter else "None"
            parts.append(f"{pos_val}:{starter_id}")
        return ",".join(parts)
    except Exception:
        return repr(chart)


def _summarize_fits(fits: Tuple[object, ...]) -> str:
    """Build a short deterministic summary string for FreeAgentFit tuple."""
    if not fits:
        return "0 fits"
    parts = []
    for f in fits:
        fid = getattr(f, "free_agent_id", "?")
        score = getattr(f, "fit_score", 0.0)
        parts.append(f"{fid}:{score:.3f}")
    return f"{len(fits)} fits=[{','.join(parts)}]"


def _summarize_preview(preview: object) -> str:
    """Build a short deterministic summary string for a TransactionPreview."""
    if preview is None:
        return "None"
    try:
        tx_id = getattr(preview, "transaction_id", "?")
        vr = getattr(preview, "validation_result", None)
        is_valid = getattr(vr, "is_valid", None) if vr else None
        return f"tx={tx_id},is_valid={is_valid}"
    except Exception:
        return repr(preview)


def _summarize_bundle(bundle: object) -> str:
    """Build a short deterministic summary string for an EvidenceBundle."""
    if bundle is None:
        return "None"
    try:
        matched = getattr(bundle, "matched_notes", ())
        missing = getattr(bundle, "missing_evidence_ids", ())
        return f"matched={len(matched)},missing={len(missing)}"
    except Exception:
        return repr(bundle)


def _pick_signing_type(salary: int, minimum_salary: int, mle: int) -> TransactionType:
    """Pick a conservative ``TransactionType`` for a preview signing.

    - ``salary <= minimum_salary`` -> ``MINIMUM_SIGNING``
    - ``salary <= mle``            -> ``MLE_SIGNING``
    - otherwise                    -> ``SIMPLE_FA_SIGNING`` (let the
      rule engine decide; it will FAIL if over the cap, which is the
      conservative outcome).
    """
    if salary <= minimum_salary:
        return TransactionType.MINIMUM_SIGNING
    if salary <= mle:
        return TransactionType.MLE_SIGNING
    return TransactionType.SIMPLE_FA_SIGNING


def _filter_fits(
    fits: Tuple[object, ...],
    goal: OffseasonGoal,
) -> Tuple[object, ...]:
    """Apply ``target_positions`` / ``max_salary`` / ``max_candidates`` filters."""
    filtered: List[object] = []
    for f in fits:
        # target_positions filter (compare against Position.value).
        if goal.target_positions:
            pos = getattr(f, "position", None)
            pos_val = pos.value if hasattr(pos, "value") else str(pos)
            if pos_val not in goal.target_positions:
                continue
        # max_salary filter (0 or None means no filter).
        if goal.max_salary and goal.max_salary > 0:
            salary = getattr(f, "expected_salary", 0)
            if salary > goal.max_salary:
                continue
        filtered.append(f)
    # max_candidates cap (0 means no limit).
    if goal.max_candidates and goal.max_candidates > 0:
        filtered = filtered[: goal.max_candidates]
    return tuple(filtered)


def _build_signing_transaction_from_fit(
    fit: object,
    team_id: str,
    minimum_salary: int,
    mle: int,
    run_index: int,
) -> SigningTransaction:
    """Build a preview ``SigningTransaction`` from a ``FreeAgentFit``.

    The transaction is a **proposal preview** only; it is never written
    to disk and never approved. ``requires_human_approval`` is True.
    """
    salary = int(getattr(fit, "expected_salary", 0))
    tx_type = _pick_signing_type(salary, minimum_salary, mle)
    return SigningTransaction(
        transaction_id=f"m4b-preview-{run_index}-{getattr(fit, 'free_agent_id', 'unknown')}",
        transaction_type=tx_type,
        team_id=team_id,
        player_id=getattr(fit, "free_agent_id", ""),
        salary=salary,
        years=_DEFAULT_SIGNING_YEARS,
        evidence_ids=tuple(getattr(fit, "evidence_ids", ())),
        requires_human_approval=True,
        sample_data=True,
    )


def _status_from_tool_trace(
    trace: Tuple[ToolCallRecord, ...],
) -> AgentRunStatus:
    """Derive the overall ``AgentRunStatus`` from the tool call trace.

    - Any FAILED -> FAILED (unless we still produced useful output; the
      caller may override). For this orchestrator, FAILED in a critical
      tool (cap/roster) means the run is FAILED.
    - Any FALLBACK and no FAILED -> PARTIAL.
    - Otherwise -> SUCCESS.
    """
    has_failed = any(r.status is ToolCallStatus.FAILED for r in trace)
    has_fallback = any(r.status is ToolCallStatus.FALLBACK for r in trace)
    if has_failed:
        return AgentRunStatus.FAILED
    if has_fallback:
        return AgentRunStatus.PARTIAL
    return AgentRunStatus.SUCCESS


# --------------------------------------------------------------------------- #
# Public orchestrator
# --------------------------------------------------------------------------- #


def run_offseason_plan(
    goal: OffseasonGoal, data_dir: Path | str = "data"
) -> OffseasonAgentRun:
    """Run the deterministic offseason tool orchestration for ``goal``.

    Returns a structured ``OffseasonAgentRun`` with a full
    ``tool_call_trace``. Never writes to disk. Never calls an LLM.
    Never approves a transaction.

    Raises:
        TeamNotFoundError: if ``goal.team_id`` is not in ``teams.json``
            (critical failure — the run cannot proceed).
    """
    trace: List[ToolCallRecord] = []
    limitations: List[str] = list(_MVP_LIMITATIONS)

    # ----------------------------------------------------------------- #
    # A. cap_sheet_service
    # ----------------------------------------------------------------- #
    cap_summary: Optional[object] = None
    minimum_salary = 0
    mle = 0
    try:
        sheet = load_team_cap_sheet(goal.team_id, data_dir)
        cap_summary = summarize_cap_sheet(sheet)
        minimum_salary = sheet.cap_config.minimum_salary
        mle = sheet.cap_config.mid_level_exception
        trace.append(
            ToolCallRecord(
                tool_name="cap_sheet_service.summarize_cap_sheet",
                status=ToolCallStatus.SUCCESS,
                input_summary=f"team_id={goal.team_id}",
                output_summary=_summarize_cap(cap_summary),
            )
        )
    except TeamNotFoundError:
        # Critical: cannot proceed without a valid team.
        raise
    except CapSheetError as exc:
        trace.append(
            ToolCallRecord(
                tool_name="cap_sheet_service.summarize_cap_sheet",
                status=ToolCallStatus.FAILED,
                input_summary=f"team_id={goal.team_id}",
                output_summary="None",
                fallback_reason=f"CapSheetError: {exc}",
            )
        )
        limitations.append("cap_sheet_service failed; cap_summary is None.")

    # ----------------------------------------------------------------- #
    # B. roster_need_service
    # ----------------------------------------------------------------- #
    roster_need_report: Optional[object] = None
    try:
        roster_need_report = evaluate_roster_needs(goal.team_id, data_dir)
        trace.append(
            ToolCallRecord(
                tool_name="roster_need_service.evaluate_roster_needs",
                status=ToolCallStatus.SUCCESS,
                input_summary=f"team_id={goal.team_id}",
                output_summary=_summarize_roster_need(roster_need_report),
            )
        )
    except (RosterNeedError, TeamNotFoundError) as exc:
        trace.append(
            ToolCallRecord(
                tool_name="roster_need_service.evaluate_roster_needs",
                status=ToolCallStatus.FAILED,
                input_summary=f"team_id={goal.team_id}",
                output_summary="None",
                fallback_reason=f"{type(exc).__name__}: {exc}",
            )
        )
        limitations.append("roster_need_service failed; roster_need_report is None.")

    # ----------------------------------------------------------------- #
    # C. depth_chart_projector
    # ----------------------------------------------------------------- #
    current_depth_chart: Optional[object] = None
    try:
        current_depth_chart = project_current_depth_chart(goal.team_id, data_dir)
        trace.append(
            ToolCallRecord(
                tool_name="depth_chart_projector.project_current_depth_chart",
                status=ToolCallStatus.SUCCESS,
                input_summary=f"team_id={goal.team_id}",
                output_summary=_summarize_depth_chart(current_depth_chart),
            )
        )
    except Exception as exc:  # noqa: BLE001 — depth tool may raise various errors
        trace.append(
            ToolCallRecord(
                tool_name="depth_chart_projector.project_current_depth_chart",
                status=ToolCallStatus.FAILED,
                input_summary=f"team_id={goal.team_id}",
                output_summary="None",
                fallback_reason=f"{type(exc).__name__}: {exc}",
            )
        )
        limitations.append("depth_chart_projector failed; current_depth_chart is None.")

    # ----------------------------------------------------------------- #
    # D. free_agent_service
    # ----------------------------------------------------------------- #
    free_agent_fits: Tuple[object, ...] = ()
    try:
        raw_fits = rank_free_agents_for_team(goal.team_id, data_dir)
        free_agent_fits = _filter_fits(raw_fits, goal)
        fa_status = ToolCallStatus.SUCCESS
        if not free_agent_fits:
            fa_status = ToolCallStatus.FALLBACK
            limitations.append(
                "free_agent_service returned no candidates after filtering; "
                "signing_previews is empty."
            )
        trace.append(
            ToolCallRecord(
                tool_name="free_agent_service.rank_free_agents_for_team",
                status=fa_status,
                input_summary=(
                    f"team_id={goal.team_id},"
                    f"target_positions={goal.target_positions},"
                    f"max_salary={goal.max_salary},"
                    f"max_candidates={goal.max_candidates}"
                ),
                output_summary=_summarize_fits(free_agent_fits),
                fallback_reason=(
                    "No free-agent candidates after filtering."
                    if not free_agent_fits
                    else None
                ),
            )
        )
    except Exception as exc:  # noqa: BLE001
        trace.append(
            ToolCallRecord(
                tool_name="free_agent_service.rank_free_agents_for_team",
                status=ToolCallStatus.FAILED,
                input_summary=f"team_id={goal.team_id}",
                output_summary="0 fits",
                fallback_reason=f"{type(exc).__name__}: {exc}",
            )
        )
        limitations.append("free_agent_service failed; free_agent_fits is empty.")

    # ----------------------------------------------------------------- #
    # E. trade_simulator.preview_signing (per top fit)
    # ----------------------------------------------------------------- #
    signing_previews: List[object] = []
    if free_agent_fits:
        for idx, fit in enumerate(free_agent_fits):
            try:
                tx = _build_signing_transaction_from_fit(
                    fit, goal.team_id, minimum_salary, mle, idx
                )
                preview = preview_signing(tx, data_dir)
                signing_previews.append(preview)
                vr = getattr(preview, "validation_result", None)
                is_valid = getattr(vr, "is_valid", None) if vr else None
                preview_status = ToolCallStatus.SUCCESS
                fallback_reason = None
                if not is_valid:
                    preview_status = ToolCallStatus.FALLBACK
                    fallback_reason = (
                        f"preview_signing validation failed for "
                        f"{getattr(fit, 'free_agent_id', '?')}"
                    )
                trace.append(
                    ToolCallRecord(
                        tool_name="trade_simulator.preview_signing",
                        status=preview_status,
                        input_summary=(
                            f"player_id={getattr(fit, 'free_agent_id', '?')},"
                            f"salary={getattr(fit, 'expected_salary', 0)},"
                            f"type={tx.transaction_type.value}"
                        ),
                        output_summary=_summarize_preview(preview),
                        fallback_reason=fallback_reason,
                        evidence_ids=tuple(getattr(fit, "evidence_ids", ())),
                    )
                )
            except Exception as exc:  # noqa: BLE001
                trace.append(
                    ToolCallRecord(
                        tool_name="trade_simulator.preview_signing",
                        status=ToolCallStatus.FAILED,
                        input_summary=(
                            f"player_id={getattr(fit, 'free_agent_id', '?')}"
                        ),
                        output_summary="None",
                        fallback_reason=f"{type(exc).__name__}: {exc}",
                    )
                )
                limitations.append(
                    f"preview_signing failed for {getattr(fit, 'free_agent_id', '?')}."
                )
    else:
        # No fits to preview — record a single FALLBACK trace entry so
        # the trace clearly shows the preview step was considered.
        trace.append(
            ToolCallRecord(
                tool_name="trade_simulator.preview_signing",
                status=ToolCallStatus.FALLBACK,
                input_summary="no free-agent candidates",
                output_summary="0 previews",
                fallback_reason="Skipped: no free-agent candidates to preview.",
            )
        )

    # ----------------------------------------------------------------- #
    # F. evidence_service
    # ----------------------------------------------------------------- #
    evidence_bundle: Optional[EvidenceBundle] = None
    try:
        # Combine: search by query/team_id + fetch by fit evidence_ids.
        search_bundle = search_evidence(
            query=goal.evidence_query,
            team_id=goal.team_id,
            limit=5,
            data_dir=data_dir,
        )
        # Collect evidence_ids from fits.
        fit_evidence_ids: List[str] = []
        for f in free_agent_fits:
            for eid in getattr(f, "evidence_ids", ()):
                if eid and eid not in fit_evidence_ids:
                    fit_evidence_ids.append(eid)
        if fit_evidence_ids:
            id_bundle = get_evidence_by_ids(tuple(fit_evidence_ids), data_dir)
            # Merge: union of matched notes (dedup by evidence_id),
            # preserve deterministic order (search order first, then
            # id-lookup order for new ones).
            seen = {n.evidence_id for n in search_bundle.matched_notes}
            merged_notes = list(search_bundle.matched_notes)
            for n in id_bundle.matched_notes:
                if n.evidence_id not in seen:
                    merged_notes.append(n)
                    seen.add(n.evidence_id)
            # Use the merged notes + carry forward missing ids.
            evidence_bundle = EvidenceBundle(
                query=search_bundle.query,
                matched_notes=tuple(merged_notes),
                missing_evidence_ids=id_bundle.missing_evidence_ids,
                fallback_reason=(
                    search_bundle.fallback_reason
                    or id_bundle.fallback_reason
                ),
                limitations=search_bundle.limitations,
                sample_data=True,
            )
        else:
            evidence_bundle = search_bundle

        ev_status = ToolCallStatus.SUCCESS
        if not evidence_bundle.matched_notes:
            ev_status = ToolCallStatus.FALLBACK
            limitations.append(
                "evidence_service returned no matched notes; "
                "evidence_bundle.fallback_reason is set."
            )
        trace.append(
            ToolCallRecord(
                tool_name="evidence_service.search_evidence",
                status=ev_status,
                input_summary=(
                    f"query={goal.evidence_query!r},team_id={goal.team_id}"
                ),
                output_summary=_summarize_bundle(evidence_bundle),
                fallback_reason=(
                    "No evidence matched."
                    if not evidence_bundle.matched_notes
                    else None
                ),
            )
        )
    except Exception as exc:  # noqa: BLE001
        trace.append(
            ToolCallRecord(
                tool_name="evidence_service.search_evidence",
                status=ToolCallStatus.FAILED,
                input_summary=f"query={goal.evidence_query!r},team_id={goal.team_id}",
                output_summary="None",
                fallback_reason=f"{type(exc).__name__}: {exc}",
            )
        )
        limitations.append("evidence_service failed; evidence_bundle is None.")

    # ----------------------------------------------------------------- #
    # G. assemble run
    # ----------------------------------------------------------------- #
    status = _status_from_tool_trace(tuple(trace))

    return OffseasonAgentRun(
        team_id=goal.team_id,
        goal=goal,
        status=status,
        cap_summary=cap_summary,
        roster_need_report=roster_need_report,
        current_depth_chart=current_depth_chart,
        free_agent_fits=free_agent_fits,
        signing_previews=tuple(signing_previews),
        evidence_bundle=evidence_bundle,
        tool_call_trace=tuple(trace),
        limitations=tuple(limitations),
        requires_human_approval=True,
        sample_data=True,
    )
