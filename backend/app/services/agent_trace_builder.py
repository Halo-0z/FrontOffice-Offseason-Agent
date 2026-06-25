"""Agent trace builder (M8-E2).

Builds ``AgentTrace`` objects for ``proposal-preview`` and
``trade-preview-demo`` payloads. The trace is a **user-facing
projection** of the existing deterministic pipeline — it does NOT call
any LLM, does NOT execute transactions, and does NOT override any
deterministic verdict.

The builder reads from the already-serialized payload dicts (the same
dicts that ``build_demo_payload`` / ``build_trade_preview_payload``
return) plus the data-source resolver metadata, and assembles 8
plain-language steps per the M8-E1 contract.

Status mapping (the ONLY place verdict -> step status is performed):
- ``ValidationStatus.PASS``    -> step ``completed``
- ``ValidationStatus.WARNING`` -> step ``warning``
- ``ValidationStatus.FAIL``    -> step ``blocked``
- ``ToolCallStatus.SUCCESS``   -> step ``completed``
- ``ToolCallStatus.FALLBACK``  -> step ``warning``
- ``ToolCallStatus.FAILED``    -> step ``blocked`` (if not recoverable)

Guardrails:
- No LLM / MCP / network.
- ``final_message`` is always the read-only disclaimer.
- The salary-validation step status is derived strictly from the
  payload's ``validation_status`` field — the builder never invents a
  verdict.
- ``requires_human_review`` on the final approval step is always ``True``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.app.models.agent_trace import (
    AgentTrace,
    AgentTraceStep,
    ApprovalState,
    FINAL_MESSAGE_READ_ONLY,
    TraceIntentType,
    TraceOverallStatus,
    TraceStepStatus,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _now_iso() -> str:
    """Current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _data_source_label(metadata: Dict[str, Any]) -> str:
    """Map resolver metadata to a plain-language data source label.

    - snapshot mode (valid, no fallback) -> "历史数据样本"
    - snapshot mode with fallback / demo mode -> "演示数据"
    - anything else -> "演示数据"
    """
    data_mode = metadata.get("data_mode")
    fallback_reason = metadata.get("fallback_reason")
    if data_mode == "snapshot" and not fallback_reason:
        return "历史数据样本"
    # demo mode, or snapshot that fell back to demo
    return "演示数据"


def _validation_status_to_step_status(vstatus: Optional[str]) -> str:
    """Map a ``ValidationStatus`` string to a ``TraceStepStatus`` string.

    PASS -> completed, WARNING -> warning, FAIL -> blocked.
    Unknown / None -> warning (conservative).
    """
    if vstatus == "PASS":
        return TraceStepStatus.COMPLETED.value
    if vstatus == "WARNING":
        return TraceStepStatus.WARNING.value
    if vstatus == "FAIL":
        return TraceStepStatus.BLOCKED.value
    return TraceStepStatus.WARNING.value


def _tool_status_to_step_status(tool_status: Optional[str]) -> str:
    """Map a ``ToolCallStatus`` string to a ``TraceStepStatus`` string."""
    if tool_status == "SUCCESS":
        return TraceStepStatus.COMPLETED.value
    if tool_status == "FALLBACK":
        return TraceStepStatus.WARNING.value
    if tool_status == "FAILED":
        return TraceStepStatus.BLOCKED.value
    return TraceStepStatus.WARNING.value


def _has_warnings_in_trace(tool_trace: List[Dict[str, Any]]) -> bool:
    """Return True if any tool call in the trace is FALLBACK/FAILED."""
    for tc in tool_trace:
        if tc.get("status") in ("FALLBACK", "FAILED"):
            return True
    return False


def _extract_evidence_ids(payload: Dict[str, Any]) -> List[str]:
    """Pull evidence ids from a proposal payload's evidence_refs."""
    refs = payload.get("evidence") or payload.get("proposal", {}).get(
        "evidence_refs", []
    )
    ids: List[str] = []
    for ref in refs:
        eid = ref.get("evidence_id") if isinstance(ref, dict) else None
        if eid:
            ids.append(eid)
    return ids


# --------------------------------------------------------------------------- #
# Proposal trace (signing / hold path)
# --------------------------------------------------------------------------- #


def build_proposal_agent_trace(
    goal_team_id: str,
    goal_objective: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the ``agent_trace`` dict for a proposal-preview payload.

    Reads the already-built payload (from ``build_demo_payload``) and
    the data-source resolver metadata. Produces 8 steps:

    1. load_active_data_source  — 读取当前数据
    2. inspect_team_context     — 分析球队现状
    3. find_candidate_players   — 查找候选球员
    4. simulate_signing         — 模拟签约方案
    5. validate_salary_rules    — 检查薪资规则
    6. validate_roster_balance  — 检查阵容影响
    7. collect_evidence         — 整理支持证据
    8. request_human_approval   — 等待人工确认
    """
    from backend.app.services.data_source_resolver import (
        build_data_source_metadata,
    )

    metadata = build_data_source_metadata()
    ds_label = _data_source_label(metadata)

    proposal = payload.get("proposal", {}) or {}
    evaluation = payload.get("evaluation", {}) or {}
    actions = payload.get("actions", []) or proposal.get("recommended_actions", []) or []
    tool_trace = payload.get("tool_trace", []) or []
    evidence_ids = _extract_evidence_ids(payload)
    limitations = payload.get("limitations", []) or []

    proposal_id = proposal.get("proposal_id", "proposal-unknown")
    proposal_status = proposal.get("status", "NO_ACTION")
    eval_status = evaluation.get("status", "PASS")

    # The primary action's validation status drives the salary-rules step.
    primary_action: Dict[str, Any] = actions[0] if actions else {}
    primary_vstatus = primary_action.get("validation_status", "NOT_VALIDATED")
    primary_is_valid = primary_action.get("is_valid", False)

    # Derive the salary-rules step status strictly from the verdict.
    salary_step_status = _validation_status_to_step_status(primary_vstatus)

    # Determine whether the run is blocked.
    is_blocked = salary_step_status == TraceStepStatus.BLOCKED.value

    # Overall status: blocked wins; otherwise warning if any tool fell
    # back or evaluation is not PASS; otherwise completed -> awaiting approval.
    has_tool_warnings = _has_warnings_in_trace(tool_trace)
    if is_blocked:
        overall_status = TraceOverallStatus.BLOCKED.value
        current_state = "blocked"
        approval_state = ApprovalState.BLOCKED.value
    elif eval_status != "PASS" or has_tool_warnings or proposal_status == "NO_ACTION":
        overall_status = TraceOverallStatus.WARNING.value
        current_state = "awaiting_human_approval"
        approval_state = ApprovalState.REQUIRED.value
    else:
        overall_status = TraceOverallStatus.AWAITING_HUMAN_APPROVAL.value
        current_state = "awaiting_human_approval"
        approval_state = ApprovalState.REQUIRED.value

    intent_type = (
        TraceIntentType.HOLD.value
        if proposal_status == "NO_ACTION"
        else TraceIntentType.SIGNING.value
    )

    # -- Step 1: load_active_data_source --
    step1_warnings: List[str] = []
    ds_step_status = TraceStepStatus.COMPLETED.value
    if metadata.get("fallback_reason"):
        ds_step_status = TraceStepStatus.WARNING.value
        step1_warnings.append("数据源发生 fallback，当前使用演示数据。")
    if metadata.get("data_mode") == "snapshot" and metadata.get("snapshot_warnings"):
        ds_step_status = TraceStepStatus.WARNING.value
        step1_warnings.append("历史样本包含人工复核标记。")

    step1 = AgentTraceStep(
        step_id="step-1-load-data-source",
        sequence=1,
        status=ds_step_status,
        title="读取当前数据",
        plain_language_summary=f"确认当前使用{ds_label}。",
        tool_name="load_active_data_source",
        inputs_summary=None,
        outputs_summary={"data_source_label": ds_label},
        warnings=step1_warnings,
        requires_human_review=False,
        technical_details={
            "data_mode": metadata.get("data_mode"),
            "snapshot_id": metadata.get("snapshot_id"),
            "fallback_reason": metadata.get("fallback_reason"),
        },
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 2: inspect_team_context --
    cap_summary = proposal.get("cap_summary", "")
    roster_need_summary = proposal.get("roster_need_summary", "")
    step2 = AgentTraceStep(
        step_id="step-2-inspect-team",
        sequence=2,
        status=TraceStepStatus.COMPLETED.value,
        title="分析球队现状",
        plain_language_summary=f"读取球队 {goal_team_id} 的预算、位置需求和阵容上下文。",
        tool_name="inspect_team_context",
        inputs_summary={"team_id": goal_team_id},
        outputs_summary={
            "cap_summary": cap_summary,
            "roster_need_summary": roster_need_summary,
        },
        requires_human_review=False,
        technical_details={"team_id": goal_team_id},
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 3: find_candidate_players --
    candidate_count = len(actions)
    step3_status = TraceStepStatus.COMPLETED.value
    step3_warnings: List[str] = []
    if proposal_status == "NO_ACTION" or candidate_count == 0:
        step3_status = TraceStepStatus.WARNING.value
        step3_warnings.append("未找到满足条件的候选球员。")
    step3 = AgentTraceStep(
        step_id="step-3-find-candidates",
        sequence=3,
        status=step3_status,
        title="查找候选球员",
        plain_language_summary=(
            f"根据位置、预算和角色筛选候选人，共 {candidate_count} 个候选方案。"
        ),
        tool_name="find_candidate_players",
        inputs_summary={
            "objective": goal_objective,
            "target_positions": primary_action.get("position"),
        },
        outputs_summary={"candidate_count": candidate_count},
        warnings=step3_warnings,
        requires_human_review=False,
        technical_details={"action_count": candidate_count},
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 4: simulate_signing --
    step4_status = TraceStepStatus.COMPLETED.value
    step4_warnings: List[str] = []
    if proposal_status == "NO_ACTION":
        step4_status = TraceStepStatus.WARNING.value
        step4_warnings.append("无候选可模拟，跳过签约模拟。")
    step4 = AgentTraceStep(
        step_id="step-4-simulate-signing",
        sequence=4,
        status=step4_status,
        title="模拟签约方案",
        plain_language_summary="生成只读签约预览，不执行任何真实操作。",
        tool_name="simulate_signing",
        inputs_summary=(
            {
                "player_id": primary_action.get("player_id"),
                "salary": primary_action.get("salary"),
            }
            if primary_action
            else None
        ),
        outputs_summary=(
            {
                "action_type": primary_action.get("action_type"),
                "validation_status": primary_vstatus,
            }
            if primary_action
            else None
        ),
        warnings=step4_warnings,
        requires_human_review=False,
        technical_details={
            "proposal_id": proposal_id,
            "action_id": primary_action.get("action_id") if primary_action else None,
        },
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 5: validate_salary_rules (verdict from deterministic engine) --
    step5_warnings: List[str] = []
    if salary_step_status == TraceStepStatus.WARNING.value:
        step5_warnings.append("薪资规则校验产生警告，建议人工复核。")
    elif salary_step_status == TraceStepStatus.BLOCKED.value:
        step5_warnings.append("薪资规则校验未通过，方案被阻断。")
    step5 = AgentTraceStep(
        step_id="step-5-validate-salary",
        sequence=5,
        status=salary_step_status,
        title="检查薪资规则",
        plain_language_summary=(
            f"薪资规则裁决结果：{primary_vstatus}。"
            if primary_vstatus != "NOT_VALIDATED"
            else "无候选方案需要校验。"
        ),
        tool_name="validate_salary_rules",
        inputs_summary={"proposal_id": proposal_id},
        outputs_summary={
            "validation_status": primary_vstatus,
            "is_valid": primary_is_valid,
        },
        warnings=step5_warnings,
        requires_human_review=False,
        technical_details={
            "validation_status": primary_vstatus,
            "is_valid": primary_is_valid,
            "evaluation_status": eval_status,
        },
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 6: validate_roster_balance --
    depth_summary = proposal.get("depth_chart_summary", "")
    roster_impact = (
        primary_action.get("roster_impact_summary", "") if primary_action else ""
    )
    step6_status = TraceStepStatus.COMPLETED.value
    step6_warnings: List[str] = []
    if roster_impact and "risk" in str(roster_impact).lower():
        step6_status = TraceStepStatus.WARNING.value
        step6_warnings.append("阵容深度存在风险。")
    step6 = AgentTraceStep(
        step_id="step-6-validate-roster",
        sequence=6,
        status=step6_status,
        title="检查阵容影响",
        plain_language_summary="评估签约后的位置深度和阵容风险。",
        tool_name="validate_roster_balance",
        inputs_summary={"team_id": goal_team_id},
        outputs_summary={
            "depth_chart_summary": depth_summary,
            "roster_impact_summary": roster_impact,
        },
        warnings=step6_warnings,
        requires_human_review=False,
        technical_details={"depth_chart_summary": depth_summary},
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 7: collect_evidence --
    step7_status = TraceStepStatus.COMPLETED.value
    step7_warnings: List[str] = []
    if not evidence_ids:
        step7_status = TraceStepStatus.WARNING.value
        step7_warnings.append("未找到支持证据，建议人工复核。")
    step7 = AgentTraceStep(
        step_id="step-7-collect-evidence",
        sequence=7,
        status=step7_status,
        title="整理支持证据",
        plain_language_summary=(
            f"绑定 {len(evidence_ids)} 条证据记录。"
            if evidence_ids
            else "未找到支持证据。"
        ),
        tool_name="collect_evidence",
        inputs_summary={"team_id": goal_team_id, "evidence_query": goal_objective},
        outputs_summary={"evidence_ids": evidence_ids, "count": len(evidence_ids)},
        warnings=step7_warnings,
        evidence_ids=evidence_ids,
        requires_human_review=False,
        technical_details={"evidence_count": len(evidence_ids)},
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 8: request_human_approval (always requires review) --
    step8 = AgentTraceStep(
        step_id="step-8-human-approval",
        sequence=8,
        status=TraceStepStatus.COMPLETED.value,
        title="等待人工确认",
        plain_language_summary=FINAL_MESSAGE_READ_ONLY,
        tool_name="request_human_approval",
        inputs_summary={"proposal_id": proposal_id},
        outputs_summary={"approval_state": approval_state},
        warnings=[],
        requires_human_review=True,
        technical_details={
            "proposal_id": proposal_id,
            "proposal_status": proposal_status,
            "overall_status": overall_status,
        },
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    trace = AgentTrace(
        run_id=proposal_id,
        intent_type=intent_type,
        overall_status=overall_status,
        current_state=current_state,
        data_source_label=ds_label,
        steps=[step1, step2, step3, step4, step5, step6, step7, step8],
        requires_human_approval=True,
        approval_state=approval_state,
        final_message=FINAL_MESSAGE_READ_ONLY,
    )
    return trace.to_dict()


# --------------------------------------------------------------------------- #
# Trade trace
# --------------------------------------------------------------------------- #


def build_trade_agent_trace(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Build the ``agent_trace`` dict for a trade-preview-demo payload.

    Reads the already-built trade payload and the data-source resolver
    metadata. Produces 8 steps:

    1. load_active_data_source  — 读取当前数据
    2. inspect_team_context     — 分析两队交易上下文
    3. find_candidate_players   — 识别交易资产
    4. simulate_trade           — 模拟交易方案
    5. validate_salary_rules    — 检查薪资配平
    6. validate_roster_balance  — 检查交易后阵容影响
    7. collect_evidence         — 整理风险与证据
    8. request_human_approval   — 等待人工确认
    """
    from backend.app.services.data_source_resolver import (
        build_data_source_metadata,
    )

    metadata = build_data_source_metadata()
    ds_label = _data_source_label(metadata)

    tx = payload.get("trade_transaction", {}) or {}
    preview = payload.get("preview", {}) or {}
    vr = preview.get("validation_result", {}) or {}
    sm = payload.get("salary_matching", {}) or {}
    team_a_post = payload.get("team_a_post_trade", {}) or {}
    team_b_post = payload.get("team_b_post_trade", {}) or {}

    transaction_id = tx.get("transaction_id", "tx-unknown")
    team_a_id = tx.get("team_a_id", "")
    team_b_id = tx.get("team_b_id", "")
    vr_status = vr.get("status", "PASS")
    vr_is_valid = vr.get("is_valid", True)
    sm_a_passed = sm.get("team_a", {}).get("passed", True)
    sm_b_passed = sm.get("team_b", {}).get("passed", True)

    # Salary-matching step status from the trade validation verdict.
    salary_step_status = _validation_status_to_step_status(vr_status)
    is_blocked = (
        salary_step_status == TraceStepStatus.BLOCKED.value
        or not (sm_a_passed and sm_b_passed)
    )

    if is_blocked:
        overall_status = TraceOverallStatus.BLOCKED.value
        current_state = "blocked"
        approval_state = ApprovalState.BLOCKED.value
    elif vr_status == "WARNING":
        overall_status = TraceOverallStatus.WARNING.value
        current_state = "awaiting_human_approval"
        approval_state = ApprovalState.REQUIRED.value
    else:
        overall_status = TraceOverallStatus.AWAITING_HUMAN_APPROVAL.value
        current_state = "awaiting_human_approval"
        approval_state = ApprovalState.REQUIRED.value

    # -- Step 1: load_active_data_source --
    step1_warnings: List[str] = []
    ds_step_status = TraceStepStatus.COMPLETED.value
    if metadata.get("fallback_reason"):
        ds_step_status = TraceStepStatus.WARNING.value
        step1_warnings.append("数据源发生 fallback，当前使用演示数据。")
    step1 = AgentTraceStep(
        step_id="step-1-load-data-source",
        sequence=1,
        status=ds_step_status,
        title="读取当前数据",
        plain_language_summary=f"确认当前使用{ds_label}。",
        tool_name="load_active_data_source",
        outputs_summary={"data_source_label": ds_label},
        warnings=step1_warnings,
        requires_human_review=False,
        technical_details={
            "data_mode": metadata.get("data_mode"),
            "snapshot_id": metadata.get("snapshot_id"),
        },
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 2: inspect_team_context (both teams) --
    step2 = AgentTraceStep(
        step_id="step-2-inspect-teams",
        sequence=2,
        status=TraceStepStatus.COMPLETED.value,
        title="分析两队交易上下文",
        plain_language_summary=f"读取 {team_a_id} 与 {team_b_id} 的薪资和阵容上下文。",
        tool_name="inspect_team_context",
        inputs_summary={"team_a_id": team_a_id, "team_b_id": team_b_id},
        outputs_summary={
            "team_a_cap_before": team_a_post.get("cap_summary_before", ""),
            "team_b_cap_before": team_b_post.get("cap_summary_before", ""),
        },
        requires_human_review=False,
        technical_details={"team_a_id": team_a_id, "team_b_id": team_b_id},
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 3: identify trade assets --
    assets_a = tx.get("team_a_sends", []) or []
    assets_b = tx.get("team_b_sends", []) or []
    step3 = AgentTraceStep(
        step_id="step-3-identify-assets",
        sequence=3,
        status=TraceStepStatus.COMPLETED.value,
        title="识别交易资产",
        plain_language_summary=(
            f"{team_a_id} 送出 {len(assets_a)} 名球员，"
            f"{team_b_id} 送出 {len(assets_b)} 名球员。"
        ),
        tool_name="find_candidate_players",
        inputs_summary={"team_a_id": team_a_id, "team_b_id": team_b_id},
        outputs_summary={
            "team_a_sends_count": len(assets_a),
            "team_b_sends_count": len(assets_b),
        },
        requires_human_review=False,
        technical_details={
            "team_a_sends": assets_a,
            "team_b_sends": assets_b,
        },
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 4: simulate_trade --
    step4_status = TraceStepStatus.COMPLETED.value
    step4_warnings: List[str] = []
    if is_blocked:
        step4_status = TraceStepStatus.WARNING.value
        step4_warnings.append("交易模拟完成但校验未通过。")
    step4 = AgentTraceStep(
        step_id="step-4-simulate-trade",
        sequence=4,
        status=step4_status,
        title="模拟交易方案",
        plain_language_summary="生成只读交易预览，不执行任何真实操作。",
        tool_name="simulate_trade",
        inputs_summary={"transaction_id": transaction_id},
        outputs_summary={"validation_status": vr_status, "is_valid": vr_is_valid},
        warnings=step4_warnings,
        requires_human_review=False,
        technical_details={"transaction_id": transaction_id},
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 5: validate_salary_rules (salary matching) --
    step5_warnings: List[str] = []
    if not sm_a_passed:
        step5_warnings.append(f"{team_a_id} 薪资配平失败。")
    if not sm_b_passed:
        step5_warnings.append(f"{team_b_id} 薪资配平失败。")
    if salary_step_status == TraceStepStatus.BLOCKED.value:
        step5_warnings.append("薪资规则校验未通过，交易被阻断。")
    elif salary_step_status == TraceStepStatus.WARNING.value:
        step5_warnings.append("薪资规则校验产生警告。")
    step5 = AgentTraceStep(
        step_id="step-5-validate-salary",
        sequence=5,
        status=salary_step_status,
        title="检查薪资配平",
        plain_language_summary=(
            f"薪资配平裁决结果：{vr_status}。"
            if vr_status
            else "薪资配平检查完成。"
        ),
        tool_name="validate_salary_rules",
        inputs_summary={"transaction_id": transaction_id},
        outputs_summary={
            "validation_status": vr_status,
            "team_a_passed": sm_a_passed,
            "team_b_passed": sm_b_passed,
        },
        warnings=step5_warnings,
        requires_human_review=False,
        technical_details={
            "validation_status": vr_status,
            "is_valid": vr_is_valid,
            "salary_match_rule": sm.get("rule"),
        },
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 6: validate_roster_balance (post-trade) --
    step6_warnings: List[str] = []
    step6_status = TraceStepStatus.COMPLETED.value
    team_a_impact = team_a_post.get("roster_impact_summary", "")
    team_b_impact = team_b_post.get("roster_impact_summary", "")
    if "risk" in str(team_a_impact).lower() or "risk" in str(team_b_impact).lower():
        step6_status = TraceStepStatus.WARNING.value
        step6_warnings.append("交易后阵容深度存在风险。")
    step6 = AgentTraceStep(
        step_id="step-6-validate-roster",
        sequence=6,
        status=step6_status,
        title="检查交易后阵容影响",
        plain_language_summary="评估交易后两队的位置深度和阵容风险。",
        tool_name="validate_roster_balance",
        inputs_summary={"team_a_id": team_a_id, "team_b_id": team_b_id},
        outputs_summary={
            "team_a_roster_impact": team_a_impact,
            "team_b_roster_impact": team_b_impact,
        },
        warnings=step6_warnings,
        requires_human_review=False,
        technical_details={
            "team_a_depth_after": team_a_post.get("depth_chart_after", ""),
            "team_b_depth_after": team_b_post.get("depth_chart_after", ""),
        },
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 7: collect_evidence (risks) --
    step7_warnings: List[str] = []
    preview_limitations = preview.get("limitations", []) or []
    if preview_limitations:
        step7_warnings.extend(preview_limitations[:3])
    step7 = AgentTraceStep(
        step_id="step-7-collect-evidence",
        sequence=7,
        status=TraceStepStatus.COMPLETED.value,
        title="整理风险与证据",
        plain_language_summary="汇总交易风险、限制说明和证据标记。",
        tool_name="collect_evidence",
        inputs_summary={"transaction_id": transaction_id},
        outputs_summary={"limitations_count": len(preview_limitations)},
        warnings=step7_warnings,
        requires_human_review=False,
        technical_details={"limitations": preview_limitations},
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    # -- Step 8: request_human_approval --
    step8 = AgentTraceStep(
        step_id="step-8-human-approval",
        sequence=8,
        status=TraceStepStatus.COMPLETED.value,
        title="等待人工确认",
        plain_language_summary=FINAL_MESSAGE_READ_ONLY,
        tool_name="request_human_approval",
        inputs_summary={"transaction_id": transaction_id},
        outputs_summary={"approval_state": approval_state},
        warnings=[],
        requires_human_review=True,
        technical_details={
            "transaction_id": transaction_id,
            "validation_status": vr_status,
            "overall_status": overall_status,
        },
        started_at=_now_iso(),
        finished_at=_now_iso(),
    )

    trace = AgentTrace(
        run_id=transaction_id,
        intent_type=TraceIntentType.TRADE.value,
        overall_status=overall_status,
        current_state=current_state,
        data_source_label=ds_label,
        steps=[step1, step2, step3, step4, step5, step6, step7, step8],
        requires_human_approval=True,
        approval_state=approval_state,
        final_message=FINAL_MESSAGE_READ_ONLY,
    )
    return trace.to_dict()
