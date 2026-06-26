"""Service-only preview-only Agent Orchestrator Stub (M8-E5).

This module implements a **thin deterministic intent-routing layer**
that wraps the project's existing deterministic preview capabilities
(signing preview via ``proposal_viewer.build_demo_payload``, trade
preview demo via ``build_trade_preview_payload``, and hold) into a
single ``orchestrate_preview`` entry point.

This is NOT an LLM agent. This is NOT an autonomous execution system.
This module does NOT call any LLM, does NOT use MCP, does NOT touch
the network, does NOT execute or commit any transaction, does NOT
modify rosters/contracts/cap state, and does NOT write to snapshot
files. Every returned result has ``requires_human_approval=True``.

Intent allowlist:
- ``signing_preview``: invokes the existing signing/proposal preview
  pipeline (deterministic; demo/sample data).
- ``trade_preview_demo``: invokes the existing fixed demo trade
  preview pipeline (deterministic; sample data).
- ``hold``: returns a hold/blocked preview result without calling
  any signing/trade simulation.

Any other intent is blocked (hold) with a warning — never guessed.

The orchestrator attaches an ``agent_trace`` with exactly 5 stable
high-level steps:
1. intake_request
2. route_intent
3. run_deterministic_preview (or hold_without_execution)
4. summarize_validation_and_evidence
5. request_human_approval

Public API:
- ``orchestrate_preview(request, data_dir) -> AgentOrchestratorResult``
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.models.agent import OffseasonGoal
from backend.app.models.agent_orchestrator import (
    AgentOrchestratorRequest,
    AgentOrchestratorResult,
    ORCHESTRATOR_READ_ONLY_MESSAGE,
    OrchestratorIntent,
    OrchestratorStatus,
    OrchestratorStepStatus,
    OrchestratorTrace,
    OrchestratorTraceStep,
)
from backend.app.services.data_source_resolver import build_data_source_metadata
from backend.app.services.proposal_viewer import build_demo_payload


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

_ALLOWED_INTENTS = {
    OrchestratorIntent.SIGNING_PREVIEW.value,
    OrchestratorIntent.TRADE_PREVIEW_DEMO.value,
    OrchestratorIntent.HOLD.value,
}

_DEFAULT_DATA_DIR = "data"

_DEFAULT_OBJECTIVE = "评估休赛期操作方案（演示数据）"

# Hard limitations surfaced in every result.
_ORCHESTRATOR_LIMITATIONS: tuple[str, ...] = (
    "M8-E5 preview-only orchestrator stub.",
    "No LLM call. No MCP. No network.",
    "No autonomous transaction execution.",
    "All actions are read-only previews and require human approval.",
    "Demo/sample/historical snapshot only — pre-season data, not real-time.",
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_id(prefix: str) -> str:
    return f"orch-{prefix}-{uuid.uuid4().hex[:8]}"


def _data_source_label() -> str:
    metadata = build_data_source_metadata()
    data_mode = metadata.get("data_mode")
    fallback_reason = metadata.get("fallback_reason")
    if data_mode == "snapshot" and not fallback_reason:
        return "历史数据样本"
    return "演示数据"


def _make_hold_payload(intent: str, reason: str) -> Dict[str, Any]:
    return {
        "intent": intent,
        "status": "hold",
        "requires_human_approval": True,
        "sample_data": True,
        "hold_reason": reason,
        "recommended_actions": [],
        "evidence": [],
        "tool_trace": [],
        "limitations": list(_ORCHESTRATOR_LIMITATIONS),
    }


def _build_trace(
    run_id: str,
    intent: str,
    overall_status: str,
    steps: List[OrchestratorTraceStep],
) -> Dict[str, Any]:
    ds_label = _data_source_label()
    trace = OrchestratorTrace(
        run_id=run_id,
        intent=intent,
        overall_status=overall_status,
        steps=steps,
        requires_human_approval=True,
        data_source_label=ds_label,
        final_message=ORCHESTRATOR_READ_ONLY_MESSAGE,
    )
    return trace.to_dict()


# --------------------------------------------------------------------------- #
# Signing preview
# --------------------------------------------------------------------------- #


def _run_signing_preview(
    request: AgentOrchestratorRequest,
    data_dir: Path | str,
) -> Dict[str, Any]:
    team_id = request.team_id or "DEM-ATL"
    objective = request.objective or _DEFAULT_OBJECTIVE
    goal = OffseasonGoal(
        team_id=team_id,
        objective=objective,
        target_positions=tuple(),
        max_salary=None,
        max_candidates=3,
        evidence_query=None,
    )
    payload = build_demo_payload(goal, data_dir)
    return payload


# --------------------------------------------------------------------------- #
# Trade preview demo
# --------------------------------------------------------------------------- #


def _run_trade_preview_demo(data_dir: Path | str) -> Dict[str, Any]:
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    from run_trade_preview_demo import build_trade_preview_payload  # type: ignore[import-not-found]

    return build_trade_preview_payload(data_dir)


# --------------------------------------------------------------------------- #
# Trace step builders
# --------------------------------------------------------------------------- #


def _step_intake(request: AgentOrchestratorRequest) -> OrchestratorTraceStep:
    return OrchestratorTraceStep(
        step_id="orch-step-1-intake",
        sequence=1,
        status=OrchestratorStepStatus.COMPLETED.value,
        title="接收编排请求",
        plain_language_summary=(
            f"接收到 intent={request.intent} 的预览编排请求。"
        ),
        tool_name="intake_request",
        inputs_summary={
            "intent": request.intent,
            "team_id": request.team_id,
            "objective": request.objective,
        },
        outputs_summary={"request_received": True},
        warnings=[],
        requires_human_review=False,
        technical_details={
            "locale": request.locale,
            "metadata_keys": sorted(request.metadata.keys()),
        },
    )


def _step_route_intent(
    request: AgentOrchestratorRequest,
    intent_allowed: bool,
) -> tuple[OrchestratorTraceStep, List[str]]:
    warnings: List[str] = []
    if intent_allowed:
        status = OrchestratorStepStatus.COMPLETED.value
        summary = f"Intent {request.intent} 在 allowlist 中，路由到对应确定性预览能力。"
    else:
        status = OrchestratorStepStatus.BLOCKED.value
        warnings.append(
            f"不支持的 intent: {request.intent}，将阻断并返回 hold 结果。"
        )
        summary = f"Intent {request.intent} 不在 allowlist 中，阻断。"
    return (
        OrchestratorTraceStep(
            step_id="orch-step-2-route",
            sequence=2,
            status=status,
            title="路由 Intent",
            plain_language_summary=summary,
            tool_name="route_intent",
            inputs_summary={"intent": request.intent},
            outputs_summary={
                "intent_allowed": intent_allowed,
                "allowed_intents": sorted(_ALLOWED_INTENTS),
            },
            warnings=warnings,
            requires_human_review=False,
            technical_details={"allowlist": sorted(_ALLOWED_INTENTS)},
        ),
        warnings,
    )


def _step_run_preview_signing(
    payload: Dict[str, Any],
) -> OrchestratorTraceStep:
    actions = payload.get("actions", [])
    primary = actions[0] if actions else {}
    return OrchestratorTraceStep(
        step_id="orch-step-3-preview",
        sequence=3,
        status=OrchestratorStepStatus.COMPLETED.value,
        title="运行确定性签约预览",
        plain_language_summary="调用现有签约预览管线生成只读方案，不执行任何真实操作。",
        tool_name="run_deterministic_preview",
        inputs_summary={"capability": "signing_preview"},
        outputs_summary={
            "proposal_id": payload.get("proposal", {}).get("proposal_id"),
            "action_count": len(actions),
            "primary_validation_status": primary.get("validation_status"),
        },
        warnings=[],
        requires_human_review=False,
        technical_details={
            "sample_data": payload.get("sample_data", True),
        },
    )


def _step_run_preview_trade(
    payload: Dict[str, Any],
) -> OrchestratorTraceStep:
    vr = payload.get("preview", {}).get("validation_result", {})
    return OrchestratorTraceStep(
        step_id="orch-step-3-preview",
        sequence=3,
        status=OrchestratorStepStatus.COMPLETED.value,
        title="运行确定性交易预览（演示）",
        plain_language_summary="调用现有演示交易预览管线生成只读方案，不执行任何真实操作。",
        tool_name="run_deterministic_preview",
        inputs_summary={"capability": "trade_preview_demo"},
        outputs_summary={
            "transaction_id": payload.get("trade_transaction", {}).get("transaction_id"),
            "validation_status": vr.get("status"),
            "is_valid": vr.get("is_valid"),
        },
        warnings=[],
        requires_human_review=False,
        technical_details={"sample_data": payload.get("sample_data", True)},
    )


def _step_hold(
    reason: str,
) -> OrchestratorTraceStep:
    return OrchestratorTraceStep(
        step_id="orch-step-3-hold",
        sequence=3,
        status=OrchestratorStepStatus.COMPLETED.value,
        title="保持观望（不执行）",
        plain_language_summary=f"返回 hold 结果：{reason}",
        tool_name="hold_without_execution",
        inputs_summary={"reason": reason},
        outputs_summary={"action_taken": "hold"},
        warnings=[],
        requires_human_review=False,
        technical_details={"mutations_performed": False},
    )


def _step_unsupported_blocked(
    reason: str,
) -> OrchestratorTraceStep:
    return OrchestratorTraceStep(
        step_id="orch-step-3-blocked",
        sequence=3,
        status=OrchestratorStepStatus.BLOCKED.value,
        title="不支持的 Intent，阻断",
        plain_language_summary=f"未调用任何预览能力，返回阻断结果：{reason}",
        tool_name="hold_without_execution",
        inputs_summary={"reason": reason},
        outputs_summary={"action_taken": "blocked"},
        warnings=[reason],
        requires_human_review=False,
        technical_details={"mutations_performed": False},
    )


def _step_summarize(
    payload: Dict[str, Any],
    is_blocked: bool,
) -> OrchestratorTraceStep:
    status = (
        OrchestratorStepStatus.WARNING.value
        if is_blocked
        else OrchestratorStepStatus.COMPLETED.value
    )
    evidence_ids: List[str] = []
    for ref in payload.get("evidence", []) or []:
        if isinstance(ref, dict) and ref.get("evidence_id"):
            evidence_ids.append(ref["evidence_id"])
    actions = payload.get("actions", []) or []
    vr = payload.get("preview", {}).get("validation_result", {})
    validation_status = (
        (actions[0].get("validation_status") if actions else None)
        or vr.get("status")
        or "N/A"
    )
    return OrchestratorTraceStep(
        step_id="orch-step-4-summarize",
        sequence=4,
        status=status,
        title="汇总校验结果与证据",
        plain_language_summary=(
            f"汇总确定性工具裁决与证据记录。校验状态：{validation_status}。"
        ),
        tool_name="summarize_validation_and_evidence",
        inputs_summary={"preview_payload_keys": sorted(payload.keys())},
        outputs_summary={
            "validation_status": validation_status,
            "evidence_count": len(evidence_ids),
            "sample_data": payload.get("sample_data", True),
        },
        warnings=[],
        requires_human_review=False,
        technical_details={
            "evidence_ids": evidence_ids,
            "limitations_count": len(payload.get("limitations", []) or []),
        },
    )


def _step_human_approval(
    overall_status: str,
) -> OrchestratorTraceStep:
    return OrchestratorTraceStep(
        step_id="orch-step-5-approval",
        sequence=5,
        status=OrchestratorStepStatus.COMPLETED.value,
        title="等待人工确认",
        plain_language_summary=ORCHESTRATOR_READ_ONLY_MESSAGE,
        tool_name="request_human_approval",
        inputs_summary={"overall_status": overall_status},
        outputs_summary={
            "requires_human_approval": True,
            "approval_gate": "manual",
        },
        warnings=[],
        requires_human_review=True,
        technical_details={
            "auto_execution_performed": False,
            "roster_mutated": False,
            "contracts_mutated": False,
            "snapshot_written": False,
        },
    )


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def orchestrate_preview(
    request: AgentOrchestratorRequest,
    data_dir: Path | str = _DEFAULT_DATA_DIR,
) -> AgentOrchestratorResult:
    """Orchestrate a single preview-only run.

    Takes an :class:`AgentOrchestratorRequest` with an explicit
    allowlisted intent and returns an :class:`AgentOrchestratorResult`
    that wraps the existing deterministic preview payload plus a
    5-step orchestrator trace.

    Guardrails enforced here:
    - Only ``signing_preview``, ``trade_preview_demo``, ``hold`` are
      accepted; any other intent is blocked (hold) with a warning.
    - ``requires_human_approval`` is always ``True`` on the result.
    - No mutation is performed; no data files are written.
    - No LLM / MCP / network call is made.
    - Demo/historical labels are preserved; nothing is claimed to be
      live/current NBA data.
    """
    run_id = _run_id(request.intent.replace("_", "-"))
    warnings: List[str] = []
    limitations: List[str] = list(_ORCHESTRATOR_LIMITATIONS)

    # Step 1: intake
    step1 = _step_intake(request)

    # Step 2: route intent
    intent_allowed = request.intent in _ALLOWED_INTENTS
    step2, route_warnings = _step_route_intent(request, intent_allowed)
    warnings.extend(route_warnings)

    # Step 3: run preview OR hold OR blocked
    preview_payload: Dict[str, Any]
    step3: OrchestratorTraceStep
    overall_status: str

    if not intent_allowed:
        reason = f"不支持的 intent: {request.intent}。仅支持 {sorted(_ALLOWED_INTENTS)}。"
        preview_payload = _make_hold_payload(request.intent, reason)
        step3 = _step_unsupported_blocked(reason)
        overall_status = OrchestratorStatus.BLOCKED.value
    elif request.intent == OrchestratorIntent.HOLD.value:
        reason = "用户选择保持观望，不执行签约或交易。"
        preview_payload = _make_hold_payload(request.intent, reason)
        step3 = _step_hold(reason)
        overall_status = OrchestratorStatus.HOLD.value
    elif request.intent == OrchestratorIntent.SIGNING_PREVIEW.value:
        try:
            preview_payload = _run_signing_preview(request, data_dir)
            step3 = _step_run_preview_signing(preview_payload)
            overall_status = OrchestratorStatus.AWAITING_HUMAN_APPROVAL.value
        except Exception as exc:
            reason = f"签约预览失败，走 hold fallback：{exc}"
            warnings.append(reason)
            preview_payload = _make_hold_payload(request.intent, reason)
            step3 = _step_hold(reason)
            overall_status = OrchestratorStatus.HOLD.value
    elif request.intent == OrchestratorIntent.TRADE_PREVIEW_DEMO.value:
        try:
            preview_payload = _run_trade_preview_demo(data_dir)
            step3 = _step_run_preview_trade(preview_payload)
            overall_status = OrchestratorStatus.AWAITING_HUMAN_APPROVAL.value
        except Exception as exc:
            reason = f"交易预览失败，走 hold fallback：{exc}"
            warnings.append(reason)
            preview_payload = _make_hold_payload(request.intent, reason)
            step3 = _step_hold(reason)
            overall_status = OrchestratorStatus.HOLD.value
    else:
        reason = f"未识别的 intent: {request.intent}"
        preview_payload = _make_hold_payload(request.intent, reason)
        step3 = _step_unsupported_blocked(reason)
        overall_status = OrchestratorStatus.BLOCKED.value

    # Step 4: summarize
    is_blocked = overall_status == OrchestratorStatus.BLOCKED.value
    step4 = _step_summarize(preview_payload, is_blocked)

    # Step 5: human approval gate
    step5 = _step_human_approval(overall_status)

    steps = [step1, step2, step3, step4, step5]
    agent_trace = _build_trace(run_id, request.intent, overall_status, steps)

    return AgentOrchestratorResult(
        intent=request.intent,
        status=overall_status,
        requires_human_approval=True,
        preview_payload=preview_payload,
        agent_trace=agent_trace,
        warnings=warnings,
        limitations=limitations,
    )
