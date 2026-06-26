"""Deterministic/fake Agent Intelligence Summary adapter (M9-A).

This module contains a single public entry point
:func:`build_intelligence_summary` that takes an already-produced
orchestrator result bundle and returns an :class:`AgentIntelligenceSummary`
describing it in plain language.

This is NOT an LLM call. This is NOT an autonomous decision maker.

Hard rules enforced here (and by tests):

1. **Status wins over intent.** If ``status`` is ``blocked`` the summary
   must describe a blocked/safety-intercepted request. If ``status`` is
   ``hold`` it must describe holding / no-action. Signing/trade language
   only appears when status is ``awaiting_human_approval`` AND intent is
   ``signing_preview`` or ``trade_preview_demo`` respectively.

2. **Read-only from inputs.** The function reads ``intent``, ``status``,
   ``requires_human_approval``, ``preview_payload``, ``agent_trace``,
   ``warnings``, ``limitations`` — it does NOT mutate any of them, and
   does NOT call into ``transaction_rule_engine`` / ``trade_simulator`` /
   ``snapshot_loader``.

3. **No fabrication.** Players, teams, salaries, PASS/FAIL verdicts,
   evidence ids, and all factual claims must come from the input. If a
   value is absent, we describe what is available rather than inventing
   anything.

4. **Safe language.** The summary never uses execution language
   ("executed", "applied", "committed", "auto_execute", "已执行", "已完成签约",
   "自动批准", etc.), never claims live/current/real-time NBA data, and
   never exposes technical IDs (``run_id``, ``snapshot_id``,
   ``sourcepack``, ``nba_2025_26``).

5. **Source tag fixed.** ``source`` is always
   ``"deterministic-fake-adapter"`` so downstream code can tell this is
   template-derived, not an LLM response.
"""

from __future__ import annotations

from typing import Any, Dict, List

from backend.app.models.agent_intelligence import AgentIntelligenceSummary


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

_APPROVAL_NOTE = (
    "这是只读预览，不会自动执行任何操作。所有建议动作都必须由人工复核并确认后"
    "才可采取。"
)

_DATA_LIMITATIONS_BASE: List[str] = [
    "当前数据基于仓库内置的演示/历史样本，不是官方 NBA 数据流，也不会自动刷新。",
    "薪资与交易规则为项目样例规则（例如薪资配平 incoming ≤ outgoing × 125% + $100,000），"
    "不等于真实 NBA CBA。",
    "所有结果仅供预览和规则演示，不作为真实交易/签约建议。",
]

_NEXT_REVIEW_BASE: List[str] = [
    "候选球员的合同状态、伤病情况是否与样本数据一致？是否需要人工二次核实？",
    "球队薪资空间、帽下余额是否与公开信息核对过？",
    "交易/签约是否会触发奢侈税、硬工资帽或其他 CBA 条款？",
]

_FORBIDDEN_SNIPPETS: tuple[str, ...] = (
    # English danger words (checked case-insensitively as substrings)
    "executed",
    "applied",
    "committed",
    "auto_execute",
    "auto_approve",
    "live nba",
    "real-time nba",
    "real time nba",
    "live data",
    "real-time data",
    "real time data",
    "live ",  # "live" as standalone word (trailing space avoids catching e.g. "deliver")
    "current",
    "real-time",
    "real time",
    # Chinese danger words
    "已执行",
    "已完成签约",
    "已完成交易",
    "自动批准",
    "已提交",
    "已落地",
    "实时",
    "最新",
    "当前阵容",
    "当前薪资",
    # Technical IDs that must NOT appear in summary text
    "run_id",
    "snapshot_id",
    "sourcepack",
    "nba_2025_26",
)

# Tokens that are forbidden as whole words (to catch "current" without
# catching "currently" misuse in passthroughs — we mask them when they
# appear as standalone words in passthrough text).
_FORBIDDEN_WHOLE_WORDS_EN: tuple[str, ...] = (
    "executed",
    "applied",
    "committed",
    "live",
)

# Passthrough replacement table. When we surface strings verbatim from the
# caller/payload (hold_reason, warnings, cap_impact_summary, matched_need,
# intent passed in by the caller, etc.), we replace any forbidden snippet
# with a safe placeholder so that:
#   a) the post-generation self-check never trips on caller-supplied text;
#   b) the final JSON output never claims execution/live-data semantics even
#      if the payload/warnings contained such words.
_PASSTHROUGH_REPLACEMENTS: Dict[str, str] = {
    # English dangerous words
    "executed": "[masked]",
    "Executed": "[masked]",
    "EXECUTED": "[masked]",
    "applied": "[masked]",
    "Applied": "[masked]",
    "APPLIED": "[masked]",
    "committed": "[masked]",
    "Committed": "[masked]",
    "COMMITTED": "[masked]",
    "auto_execute": "[masked]",
    "AUTO_EXECUTE": "[masked]",
    "Auto-Execute": "[masked]",
    "auto_approve": "[masked]",
    "AUTO_APPROVE": "[masked]",
    "auto-approve": "[masked]",
    "Auto-Approve": "[masked]",
    "current": "existing",
    "Current": "Existing",
    "CURRENT": "EXISTING",
    "live": "sample",
    "Live": "Sample",
    "LIVE": "SAMPLE",
    "real-time": "historical-sample",
    "Real-Time": "Historical-Sample",
    "REAL-TIME": "HISTORICAL-SAMPLE",
    "real time": "historical sample",
    "Real Time": "Historical Sample",
    "REAL TIME": "HISTORICAL SAMPLE",
    # Chinese dangerous words / phrases
    "已执行": "[已屏蔽]",
    "已完成签约": "[已屏蔽]",
    "已完成交易": "[已屏蔽]",
    "自动批准": "[已屏蔽]",
    "已提交": "[已屏蔽]",
    "已落地": "[已屏蔽]",
    "实时": "演示样本",
    "最新": "公开可查",
    "当前阵容": "现有名单（样本）",
    "当前薪资": "现有薪资（样本）",
    # Technical IDs that must never leak into the natural-language summary
    "run_id": "[masked_id]",
    "snapshot_id": "[masked_id]",
    "sourcepack": "[masked_id]",
    "nba_2025_26": "[masked_id]",
}


def _sanitize_passthrough(text: str) -> str:
    """Mask forbidden words in a passthrough string pulled from the payload.

    Only applies to text we surface verbatim from ``preview_payload`` /
    warnings / caller-provided intent; our own template strings must already
    avoid these words entirely.

    Replacement is done longest-first via simple substring substitution
    (case-insensitive for English so "Executed"/"EXECUTED" are both caught).
    """
    if not isinstance(text, str):
        return ""
    out = text
    # Sort by (length desc, then text) so longer phrases like "real time" and
    # "已完成签约" are replaced before shorter substrings.
    items = sorted(
        _PASSTHROUGH_REPLACEMENTS.items(),
        key=lambda kv: (-len(kv[0]), kv[0].lower()),
    )
    for bad, good in items:
        if not bad:
            continue
        # Case-insensitive loop for English; Chinese characters are replaced
        # verbatim (case doesn't apply).
        if any(ord(c) > 127 for c in bad):
            # CJK: direct substring replace
            while bad in out:
                out = out.replace(bad, good)
        else:
            low_bad = bad.lower()
            low_out = out.lower()
            idx = 0
            while True:
                pos = low_out.find(low_bad, idx)
                if pos < 0:
                    break
                # Whole-word boundary check for ASCII English tokens:
                # only treat as a match when surrounded by non-ascii-letters.
                before_ch = out[pos - 1] if pos > 0 else " "
                after_ch = out[pos + len(bad)] if pos + len(bad) < len(out) else " "
                before_ok = not (before_ch.isascii() and before_ch.isalpha())
                after_ok = not (after_ch.isascii() and after_ch.isalpha())
                if before_ok and after_ok:
                    out = out[:pos] + good + out[pos + len(bad):]
                    low_out = out.lower()
                    idx = pos + len(good)
                else:
                    idx = pos + len(bad)
    return out

_POSITION_ZH: Dict[str, str] = {
    "PG": "控卫",
    "SG": "分卫",
    "SF": "小前",
    "PF": "大前",
    "C": "中锋",
}

_VALIDATION_ZH: Dict[str, str] = {
    "PASS": "规则检查通过",
    "FAIL": "规则检查未通过",
    "WARNING": "通过但有警告",
    "BLOCKED": "被安全规则拦截",
    "HOLD": "暂不行动",
}


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #


def _validate_no_forbidden_text(*chunks: str) -> None:
    """Defensive self-check: raise if any forbidden snippet appears.

    This is a belt-and-braces guard for developers editing this module.
    It runs at build time (not in hot paths) so it's safe to be strict.
    """
    blob = " | ".join(c for c in chunks if c).lower()
    for snippet in _FORBIDDEN_SNIPPETS:
        if snippet.lower() in blob:
            raise AssertionError(
                f"agent_intelligence: forbidden snippet {snippet!r} appeared in "
                f"generated summary; this is a code bug in the adapter."
            )


def _safe_get(d: Any, *keys: str, default: Any = None) -> Any:
    """Walk nested dicts safely, returning default on any miss/non-dict."""
    cur: Any = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k, default)
    return cur


def _fmt_money(value: Any) -> str:
    """Format a dollar amount (int or numeric str) as '${X}M' style if possible."""
    if value is None:
        return ""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(n) >= 1_000_000:
        return f"${n / 1_000_000:.0f}M"
    if abs(n) >= 1_000:
        return f"${n / 1_000:.0f}K"
    return f"${n}"


def _first_action(preview_payload: Dict[str, Any]) -> Dict[str, Any]:
    actions = preview_payload.get("actions") or []
    if actions and isinstance(actions[0], dict):
        return actions[0]
    # Fall back to proposal.recommended_actions[0] if present.
    rec = _safe_get(preview_payload, "proposal", "recommended_actions", default=[])
    if rec and isinstance(rec, list) and isinstance(rec[0], dict):
        return rec[0]
    return {}


def _verdict_label_from_status(status: str, validation_status: str | None) -> str:
    """Map (orchestrator status, payload validation status) to a zh verdict label."""
    if status == "blocked":
        return "请求已被安全拦截，未生成方案"
    if status == "hold":
        return "建议暂不行动（hold）"
    if validation_status in _VALIDATION_ZH:
        return _VALIDATION_ZH[validation_status]
    if validation_status:
        return f"校验状态：{validation_status}"
    return "已生成只读预览"


# --------------------------------------------------------------------------- #
# Per-status builders
# --------------------------------------------------------------------------- #


def _build_blocked_summary(
    intent: str,
    preview_payload: Dict[str, Any],
    warnings: List[str],
    limitations: List[str],
) -> AgentIntelligenceSummary:
    hold_reason = _sanitize_passthrough(
        preview_payload.get("hold_reason") or "请求未在 allowlist 中"
    )
    title = "安全拦截：该请求类型未被允许"
    plain = (
        f"系统收到了一个不在 allowlist 内的请求类型（{_sanitize_passthrough(intent)}）。为保持只读和安全，"
        f"编排器没有调用签约或交易预览能力，直接返回了阻断结果，未生成任何方案。"
    )
    evidence: List[str] = [
        f"请求类型：{_sanitize_passthrough(intent)}",
        f"阻断原因：{hold_reason}",
    ]
    risks = [
        "此请求可能包含执行/自动操作语义，已被安全策略拦截。",
        "系统不会对 roster、合同、薪资帽或 snapshot 文件做任何变更。",
    ]
    if warnings:
        risks.extend(f"编排层提示：{_sanitize_passthrough(w)}" for w in warnings)
    next_questions = [
        "是否应该使用 allowlist 中允许的 intent（signing_preview / trade_preview_demo / hold）？",
        "如果确实需要新 intent，是否已经过设计评审并更新 allowlist 与 guardrails 测试？",
    ]
    summary = AgentIntelligenceSummary(
        summary_title=title,
        plain_language_summary=plain,
        deterministic_verdict=_verdict_label_from_status("blocked", None),
        evidence_summary=evidence,
        risk_summary=risks,
        approval_note=_APPROVAL_NOTE,
        data_limitations=list(_DATA_LIMITATIONS_BASE),
        next_review_questions=next_questions,
        source="deterministic-fake-adapter",
    )
    _validate_no_forbidden_text(
        title, plain, summary.deterministic_verdict,
        " ".join(evidence), " ".join(risks),
        " ".join(summary.data_limitations),
        " ".join(summary.next_review_questions),
        summary.approval_note,
    )
    return summary


def _build_hold_summary(
    intent: str,
    preview_payload: Dict[str, Any],
    warnings: List[str],
    limitations: List[str],
) -> AgentIntelligenceSummary:
    hold_reason = _sanitize_passthrough(
        preview_payload.get("hold_reason")
        or "预算/条件受限，未找到合适的签约或交易方案"
    )
    title = "暂不行动：当前条件下建议保持观望"
    plain = (
        "系统在当前预算/条件下没有给出签约或交易建议，而是返回了 HOLD 结果。"
        "这意味着现阶段最安全的选择是不采取动作，继续观察市场、等待薪资空间"
        "或更合适的候选人出现。"
    )
    evidence: List[str] = [
        f"HOLD 原因：{hold_reason}",
        "推荐动作：空（未生成签约或交易）",
    ]
    risks = [
        "强行操作可能违反薪资帽、阵容人数或其他规则约束。",
        "当前是演示/历史样本，实际情况请以官方公开数据人工复核为准。",
    ]
    if warnings:
        risks.extend(f"编排层提示：{_sanitize_passthrough(w)}" for w in warnings)
    next_questions = [
        "是否可以通过释放薪资、调整目标位置或等待赛季中窗口来打开操作空间？",
        "自由球员市场上是否有更适合当前预算的备选候选人？",
    ]
    summary = AgentIntelligenceSummary(
        summary_title=title,
        plain_language_summary=plain,
        deterministic_verdict=_verdict_label_from_status("hold", None),
        evidence_summary=evidence,
        risk_summary=risks,
        approval_note=_APPROVAL_NOTE,
        data_limitations=list(_DATA_LIMITATIONS_BASE),
        next_review_questions=next_questions,
        source="deterministic-fake-adapter",
    )
    _validate_no_forbidden_text(
        title, plain, summary.deterministic_verdict,
        " ".join(evidence), " ".join(risks),
        " ".join(summary.data_limitations),
        " ".join(summary.next_review_questions),
        summary.approval_note,
    )
    return summary


def _build_signing_summary(
    preview_payload: Dict[str, Any],
    warnings: List[str],
    limitations: List[str],
) -> AgentIntelligenceSummary:
    action = _first_action(preview_payload)
    player_name = action.get("player_name") or "候选自由球员"
    position = action.get("position") or ""
    salary = action.get("salary")
    years = action.get("years")
    validation_status = action.get("validation_status")
    team_id = action.get("team_id") or _safe_get(preview_payload, "proposal", "team_id")
    matched_need = action.get("matched_need") or ""
    is_valid = action.get("is_valid")

    pos_zh = _POSITION_ZH.get(position, position)
    salary_str = _fmt_money(salary) if salary is not None else "未明确"
    years_str = f"{years} 年" if years else ""

    title = f"签约预览：{player_name}（{pos_zh}）补强方案"
    plain_parts = [
        f"系统为球队 {team_id or 'DEM-ATL'} 生成了一个只读签约预览："
        f"以 {salary_str}"
        f"{('、' + years_str) if years_str else ''}合同签下 {player_name}"
        f"{f'（{pos_zh}）' if pos_zh else ''}。",
    ]
    if validation_status == "PASS" or is_valid:
        plain_parts.append("该方案通过了项目样例薪资与阵容规则检查，但仍然只是预览。")
    elif validation_status == "FAIL" or is_valid is False:
        plain_parts.append("该方案在样例规则检查中未通过，不可直接采用。")
    plain = "".join(plain_parts)

    evidence: List[str] = []
    if matched_need:
        evidence.append(f"阵容需求匹配：{_sanitize_passthrough(str(matched_need))}")
    evidence.append(
        f"球员位置：{pos_zh or position or '未明确'}；"
        f"报价：{salary_str}{(' / ' + years_str) if years_str else ''}"
    )
    if validation_status:
        evidence.append(f"规则校验：{validation_status}")
    evidence_count = len(preview_payload.get("evidence") or [])
    evidence.append(f"关联证据条数：{evidence_count}")

    risks: List[str] = []
    cap_summary = action.get("cap_impact_summary") or _safe_get(
        preview_payload, "proposal", "cap_summary"
    )
    if isinstance(cap_summary, str) and cap_summary:
        risks.append(f"薪资影响：{_sanitize_passthrough(cap_summary)}")
    action_limitations = action.get("limitations") or []
    if isinstance(action_limitations, list):
        risks.extend(
            f"方案限制：{_sanitize_passthrough(str(lim))}"
            for lim in action_limitations[:2]
        )
    if warnings:
        risks.extend(f"编排层提示：{_sanitize_passthrough(w)}" for w in warnings)
    risks.append("签约不会自动执行，需要管理层、薪资帽团队和队医人工复核。")

    next_questions = list(_NEXT_REVIEW_BASE)

    summary = AgentIntelligenceSummary(
        summary_title=title,
        plain_language_summary=plain,
        deterministic_verdict=_verdict_label_from_status(
            "awaiting_human_approval", validation_status
        ),
        evidence_summary=evidence,
        risk_summary=risks,
        approval_note=_APPROVAL_NOTE,
        data_limitations=list(_DATA_LIMITATIONS_BASE),
        next_review_questions=next_questions,
        source="deterministic-fake-adapter",
    )
    _validate_no_forbidden_text(
        title, plain, summary.deterministic_verdict,
        " ".join(evidence), " ".join(risks),
        " ".join(summary.data_limitations),
        " ".join(summary.next_review_questions),
        summary.approval_note,
    )
    return summary


def _build_trade_summary(
    preview_payload: Dict[str, Any],
    warnings: List[str],
    limitations: List[str],
) -> AgentIntelligenceSummary:
    trade = preview_payload.get("trade_transaction") or {}
    preview = preview_payload.get("preview") or {}
    vr = preview.get("validation_result") or {}
    team_a = trade.get("team_a_id") or "DEM-ATL"
    team_b = trade.get("team_b_id") or "DEM-PDX"
    validation_status = vr.get("status")
    is_valid = vr.get("is_valid")

    out_a = trade.get("outgoing_from_a") or []
    out_b = trade.get("outgoing_from_b") or []

    def _asset_names(assets: Any) -> str:
        names: List[str] = []
        if not isinstance(assets, (list, tuple)):
            return "（资产明细见技术详情）"
        for a in assets:
            if isinstance(a, dict):
                pid = a.get("player_id") or a.get("asset_id") or ""
                sal = _fmt_money(a.get("salary"))
                names.append(f"{pid}{(' (' + sal + ')') if sal else ''}")
        return "、".join(names) if names else "（资产明细见技术详情）"

    title = f"交易预览：{team_a} ↔ {team_b} 双方交易方案"
    plain_parts = [
        f"系统生成了一个只读的两队交易预览：{team_a} 与 {team_b} 之间交换球员。",
    ]
    if validation_status == "PASS" or is_valid:
        plain_parts.append("该方案通过了项目样例薪资配平与阵容人数规则检查。")
    elif validation_status == "FAIL" or is_valid is False:
        plain_parts.append("该方案未通过样例规则检查，不可直接采用。")
    else:
        plain_parts.append("请查看规则校验详情。")
    plain = "".join(plain_parts)

    cap_before = vr.get("cap_summary_before") or {}
    cap_after = vr.get("cap_summary_after") or {}
    b_cap_before = vr.get("team_b_cap_summary_before") or {}
    b_cap_after = vr.get("team_b_cap_summary_after") or {}

    evidence: List[str] = [
        f"交易双方：{team_a} ↔ {team_b}",
        f"{team_a} 送出：{_asset_names(out_a)}",
        f"{team_b} 送出：{_asset_names(out_b)}",
    ]
    if validation_status:
        evidence.append(f"规则校验：{validation_status}")
    if cap_before and cap_after:
        evidence.append(
            f"{team_a} 交易后总薪资 {_fmt_money(cap_after.get('total_salary'))}"
            f"（前 {_fmt_money(cap_before.get('total_salary'))}），"
            f"薪资空间 {_fmt_money(cap_after.get('cap_space'))}"
        )
    if b_cap_before and b_cap_after:
        evidence.append(
            f"{team_b} 交易后总薪资 {_fmt_money(b_cap_after.get('total_salary'))}"
            f"（前 {_fmt_money(b_cap_before.get('total_salary'))}），"
            f"薪资空间 {_fmt_money(b_cap_after.get('cap_space'))}"
        )
    evidence.append(f"关联证据条数：{len(vr.get('evidence_ids') or [])}")

    risks: List[str] = []
    issues = vr.get("issues") or []
    vr_warnings = vr.get("warnings") or []
    if issues:
        risks.append(f"规则问题 {len(issues)} 条，请在技术详情中查看。")
    if vr_warnings:
        risks.append(f"规则警告 {len(vr_warnings)} 条，请在技术详情中查看。")
    cap_summary_text = preview_payload.get("cap_impact_summary")
    if isinstance(cap_summary_text, str) and cap_summary_text:
        risks.append(f"总体薪资影响：{_sanitize_passthrough(cap_summary_text)}")
    if warnings:
        risks.extend(f"编排层提示：{_sanitize_passthrough(w)}" for w in warnings)
    risks.append("交易不会自动执行，需双方球队管理层、薪资帽团队及联盟人工审核。")

    next_questions = list(_NEXT_REVIEW_BASE)
    next_questions.append("交易是否会让任一球队触发奢侈税或硬工资帽？")

    summary = AgentIntelligenceSummary(
        summary_title=title,
        plain_language_summary=plain,
        deterministic_verdict=_verdict_label_from_status(
            "awaiting_human_approval", validation_status
        ),
        evidence_summary=evidence,
        risk_summary=risks,
        approval_note=_APPROVAL_NOTE,
        data_limitations=list(_DATA_LIMITATIONS_BASE),
        next_review_questions=next_questions,
        source="deterministic-fake-adapter",
    )
    _validate_no_forbidden_text(
        title, plain, summary.deterministic_verdict,
        " ".join(evidence), " ".join(risks),
        " ".join(summary.data_limitations),
        " ".join(summary.next_review_questions),
        summary.approval_note,
    )
    return summary


# --------------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------------- #


def build_intelligence_summary(
    *,
    intent: str,
    status: str,
    requires_human_approval: bool,
    preview_payload: Dict[str, Any],
    agent_trace: Dict[str, Any] | None = None,
    warnings: List[str] | None = None,
    limitations: List[str] | None = None,
) -> AgentIntelligenceSummary:
    """Build a deterministic plain-language summary for an orchestrator result.

    All parameters are read-only inputs. The function never mutates them
    and never calls any validation/simulation/loading engine. The branching
    is keyed **primarily** on ``status``:

    - ``blocked``            -> safety-intercepted summary (no plan produced)
    - ``hold``               -> hold/no-action summary
    - ``awaiting_human_approval`` with intent ``signing_preview`` -> signing summary
    - ``awaiting_human_approval`` with intent ``trade_preview_demo`` -> trade summary
    - other combinations     -> defensive generic read-only preview summary
    """
    if not isinstance(preview_payload, dict):
        preview_payload = {}
    if agent_trace is None:
        agent_trace = {}
    warnings = list(warnings or [])
    limitations = list(limitations or [])

    # Hard invariant: every result must require human approval. If somehow
    # it doesn't, we still force the approval note to that effect.
    del requires_human_approval  # consumed semantically; always True in this project.
    del agent_trace  # We don't mine trace steps for facts; trace is for UI only.

    # 1. Blocked wins over everything else.
    if status == "blocked":
        return _build_blocked_summary(intent, preview_payload, warnings, limitations)

    # 2. Hold.
    if status == "hold":
        return _build_hold_summary(intent, preview_payload, warnings, limitations)

    # 3. Awaiting human approval -> dispatch by intent.
    if status == "awaiting_human_approval":
        if intent == "signing_preview":
            return _build_signing_summary(preview_payload, warnings, limitations)
        if intent == "trade_preview_demo":
            return _build_trade_summary(preview_payload, warnings, limitations)

    # 4. Defensive fallback (shouldn't happen under current orchestrator,
    # but if it does we return a generic read-only preview summary instead
    # of crashing or fabricating).
    title = "只读预览：编排结果"
    safe_intent = _sanitize_passthrough(str(intent))
    safe_status = _sanitize_passthrough(str(status))
    plain = (
        f"系统返回了一个只读预览（intent={safe_intent}, status={safe_status}）。"
        "该结果不会自动执行任何操作，需要人工确认。"
    )
    summary = AgentIntelligenceSummary(
        summary_title=title,
        plain_language_summary=plain,
        deterministic_verdict=_verdict_label_from_status(status, None),
        evidence_summary=[f"状态：{safe_status}", f"意图：{safe_intent}"],
        risk_summary=["请在技术详情中查看完整 payload 以人工评估该结果。"],
        approval_note=_APPROVAL_NOTE,
        data_limitations=list(_DATA_LIMITATIONS_BASE),
        next_review_questions=list(_NEXT_REVIEW_BASE),
        source="deterministic-fake-adapter",
    )
    _validate_no_forbidden_text(
        title, plain, summary.deterministic_verdict,
        " ".join(summary.evidence_summary), " ".join(summary.risk_summary),
        " ".join(summary.data_limitations),
        " ".join(summary.next_review_questions),
        summary.approval_note,
    )
    return summary
