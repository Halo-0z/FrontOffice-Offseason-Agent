"""Deterministic rule-based natural-language intent classifier (M9-B).

This is a **pure**, **side-effect-free** classifier that maps a single
user utterance to a broad intent category. It sits upstream of the
preview-only orchestrator and must never:

- call the orchestrator or any deterministic engine (rule_engine,
  trade_simulator, snapshot_loader, proposal_builder, proposal_viewer,
  agent_intelligence, agent_trace_builder);
- import LLM / network / scraping libraries;
- generate preview payloads, pick specific players, pick teams, or
  construct trade packages;
- mutate any input object or any file on disk;
- echo the raw user text or surface specific players / teams / dollar
  amounts in its output.

Output states:

- ``resolved`` — high-confidence classification into one of
  ``signing_preview`` / ``trade_preview_demo`` / ``hold``.
- ``needs_clarification`` — ambiguous / low-confidence / mixed-intent /
  empty / too-short input. ``resolved_intent`` is ``None`` in this state.
- ``blocked`` — dangerous / execution / bypass language detected.
  ``resolved_intent`` is ``None`` and ``blocked_reason`` is a generic
  string that does NOT echo the user text.

The classifier supports both Chinese and English keywords.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from backend.app.models.agent_intent_classifier import (
    CLASSIFICATION_STATUS_BLOCKED,
    CLASSIFICATION_STATUS_NEEDS_CLARIFICATION,
    CLASSIFICATION_STATUS_RESOLVED,
    AgentIntentClassificationRequest,
    AgentIntentPlan,
)


# --------------------------------------------------------------------------- #
# Keyword sets
# --------------------------------------------------------------------------- #

_SIGNING_ZH = (
    "签", "签下", "签约", "补强", "自由球员", "自由市场",
    "底薪",
    "加入", "招人", "找个", "补一个", "补强位置", "自由人",
    "签人", "签个", "签一",
)
_SIGNING_EN = (
    "sign", "signs", "signed", "signing",
    "add a", "pick up",
    "free agent", "free-agent", "free agents", "free agents",
    "frontcourt help", "frontcourt depth", "backcourt help", "backcourt depth",
    "low-cost", "low cost", "minimum", "veteran minimum",
    "add depth", "add help",
)

_TRADE_ZH = (
    "交易", "换", "换取", "换来", "交易市场", "模拟交易",
    "交易包", "交易方案", "交易方向", "做一笔交易", "一笔交易",
    "换个", "换一", "换来",
)
_TRADE_EN = (
    "trade for", "trade", "trades", "trading",
    "deal", "deals",
    "swap", "exchange", "package",
    "explore trade", "explore a trade", "explore trades",
    "simulate a trade", "simulate trade", "simulate trades",
    "trade market", "trade target", "trade targets",
    "trade scenario", "trade preview",
    "low-risk deal", "low risk deal", "low-risk trades", "low risk trades",
    "explore the trade market",
)

_HOLD_ZH = (
    "别动", "别乱动", "观望", "暂不行动", "保留", "保持灵活",
    "保持弹性", "等", "等等", "不做", "不动", "稳住", "等待",
    "先不", "暂时不", "按兵不动", "原地观望", "保留薪资空间",
    "保留空间", "不交易", "不签约",
)
_HOLD_EN = (
    "hold", "stand pat", "sit tight", "stay flexible",
    "preserve flexibility", "preserve cap", "wait and", "wait on",
    "don't move", "do not move", "don't do", "do not do",
    "hold for now", "hold off", "stay put",
)

_BLOCKED_ZH = (
    "绕过审批", "跳过审批", "不用审批", "不要审批", "无需审批",
    "不要人工确认", "不用人工确认", "跳过人工", "绕过人工",
    "忽略薪资", "忽略规则", "忽略校验", "忽略验证", "无视规则", "无视薪资",
    "忽略 salary", "忽略validation", "忽略 validation",
    "直接签", "直接执行", "马上执行", "立刻执行", "立即执行",
    "马上交", "立即交", "立刻交",
    "写入", "写到",
    "修改合同", "改合同", "改薪资", "修改薪资",
    "修改contract", "修改 contract", "修改contracts", "修改 contracts",
    "改contract", "改 contract", "改snapshot", "改 snapshot",
    "更新snapshot", "更新快照", "更新数据", "写入阵容", "改阵容",
    "更新 snapshot",
    "提交签约", "提交交易",
    "批准交易", "批准签约", "自动批", "自动执行",
    "强制通过", "强制执", "绕过验证", "跳过校验",
)
_BLOCKED_EN = (
    "execute now", "execute a trade", "execute trade", "execute the",
    "sign him now", "sign him immediately",
    "skip approval", "bypass approval", "without approval",
    "no approval", "no human", "skip human", "bypass human",
    "ignore salary", "ignore validation", "ignore rule", "ignore rules",
    "override", "bypass validation", "bypass rule", "bypass rules",
    "salary validation",
    "commit the", "commit transaction", "commit trade", "commit signing",
    "apply trade", "apply the trade", "apply signing",
    "write to", "write roster",
    "modify contract", "modify contracts",
    "update snapshot", "update roster", "update contracts",
    "auto-execute", "auto execute", "auto-approve", "auto approve",
    "force through", "right now", "immediately",
    "contracts", "roster", "snapshot", "snapshots",
)

_VAGUE_ZH = (
    "帮我看看", "你觉得呢", "做点什么", "想想办法", "随便看看",
    "看看", "看看吧", "你怎么看", "建议一下", "有什么建议",
    "怎么办", "咋整", "来一下", "搞一下", "整一下",
)
_VAGUE_EN = (
    "help me", "what do you think", "do something", "improve team",
    "improve the team", "make us better", "what should i do",
    "thoughts", "any ideas", "ideas", "take a look", "look at",
)

# --------------------------------------------------------------------------- #
# Constants for output
# --------------------------------------------------------------------------- #

_APPROVAL_NOTE = (
    "本分类结果仅为只读意图识别，不会自动执行任何操作，"
    "也不会生成签约或交易方案；后续预览同样需要人工确认。"
)

_DATA_LIMITATIONS_GENERIC = (
    "分类基于规则关键词匹配，演示数据环境；不构成任何执行建议。"
)

_BLOCKED_REASON = "请求包含不安全的执行或绕审语义，已被安全拦截。"

# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def classify_user_intent(
    request: AgentIntentClassificationRequest,
) -> AgentIntentPlan:
    """Classify a user utterance into a broad intent category.

    Pure function: does not touch the filesystem, does not import
    engines, does not mutate ``request`` or any nested object.
    """
    raw = request.user_text or ""
    text = _normalize(raw)

    constraints_out = _constraints_to_safe_dict(request.constraints)

    # 1. Blocked first — safety overrides everything.
    blocked_flag = _match_any(text, _BLOCKED_ZH) or _match_any(text, _BLOCKED_EN)
    if blocked_flag:
        return AgentIntentPlan(
            classification_status=CLASSIFICATION_STATUS_BLOCKED,
            resolved_intent=None,
            confidence=0.0,
            needs_clarification=False,
            objective=None,
            constraints=constraints_out,
            safety_flags=["dangerous_language_blocked"],
            blocked_reason=_BLOCKED_REASON,
            clarification_questions=[],
            approval_note=_APPROVAL_NOTE,
            source="deterministic-rule-classifier",
        )

    # 2. Empty / too short / control-only text -> needs_clarification.
    stripped = text.strip()
    if len(stripped) < 2:
        return _clarification(
            reason="empty_or_short",
            objective=None,
            constraints=constraints_out,
            questions=_DEFAULT_CLARIFY_QUESTIONS,
        )

    signing_hits = _match_any(text, _SIGNING_ZH) or _match_any(text, _SIGNING_EN)
    trade_hits = _match_any(text, _TRADE_ZH) or _match_any(text, _TRADE_EN)
    hold_hits = _match_any(text, _HOLD_ZH) or _match_any(text, _HOLD_EN)
    vague_hits = _match_any(text, _VAGUE_ZH) or _match_any(text, _VAGUE_EN)

    # 3. Mixed intent (signing + trade) — never guess.
    if signing_hits and trade_hits:
        return _clarification(
            reason="mixed_signing_trade",
            objective=None,
            constraints=constraints_out,
            questions=[
                "你想先看签约预览，还是先看交易预览？",
                "请说明主要方向：补强自由球员，还是通过交易调整阵容？",
            ],
        )

    # 4. Vague text with no strong signal -> needs_clarification.
    if vague_hits and not (signing_hits or trade_hits or hold_hits):
        return _clarification(
            reason="vague_low_confidence",
            objective=None,
            constraints=constraints_out,
            questions=_DEFAULT_CLARIFY_QUESTIONS,
        )

    # 5. If no signal at all (no signing, no trade, no hold, no vague)
    #    treat as low-confidence -> needs_clarification (never hold).
    if not (signing_hits or trade_hits or hold_hits):
        return _clarification(
            reason="no_signal",
            objective=None,
            constraints=constraints_out,
            questions=_DEFAULT_CLARIFY_QUESTIONS,
        )

    # 6. Resolve to the strongest single intent. Hold is resolved only
    #    when explicitly signalled; signing/trade take precedence when
    #    mixed with hold (since "补个中锋然后保持灵活" implies signing
    #    with a flexibility constraint, not pure hold).
    if signing_hits and not trade_hits:
        objective = _build_objective("signing")
        return AgentIntentPlan(
            classification_status=CLASSIFICATION_STATUS_RESOLVED,
            resolved_intent="signing_preview",
            confidence=0.85,
            needs_clarification=False,
            objective=objective,
            constraints=constraints_out,
            safety_flags=["preview_only"],
            blocked_reason=None,
            clarification_questions=[],
            approval_note=_APPROVAL_NOTE,
        )

    if trade_hits and not signing_hits:
        objective = _build_objective("trade")
        return AgentIntentPlan(
            classification_status=CLASSIFICATION_STATUS_RESOLVED,
            resolved_intent="trade_preview_demo",
            confidence=0.8,
            needs_clarification=False,
            objective=objective,
            constraints=constraints_out,
            safety_flags=["preview_only", "demo_trade"],
            blocked_reason=None,
            clarification_questions=[],
            approval_note=_APPROVAL_NOTE,
        )

    if hold_hits and not (signing_hits or trade_hits):
        objective = "保持阵容弹性与薪资空间，暂不进行签约或交易。"
        return AgentIntentPlan(
            classification_status=CLASSIFICATION_STATUS_RESOLVED,
            resolved_intent="hold",
            confidence=0.85,
            needs_clarification=False,
            objective=objective,
            constraints=constraints_out,
            safety_flags=["preview_only"],
            blocked_reason=None,
            clarification_questions=[],
            approval_note=_APPROVAL_NOTE,
        )

    # Fallback — should not reach here, but stay safe.
    return _clarification(
        reason="ambiguous",
        objective=None,
        constraints=constraints_out,
        questions=_DEFAULT_CLARIFY_QUESTIONS,
    )


# --------------------------------------------------------------------------- #
# Internal helpers
# --------------------------------------------------------------------------- #

_DEFAULT_CLARIFY_QUESTIONS: List[str] = [
    "你想了解哪一类操作？可选方向：签约自由球员预览、交易模拟预览、或暂时观望。",
    "请补充你的主要目标（例如补强哪个位置、是否希望通过交易调整、或先保持灵活性）。",
]


def _normalize(text: str) -> str:
    """Normalize user text for keyword matching.

    - Lowercase.
    - Collapse whitespace.
    - Strip common punctuation only (keep CJK characters intact).
    - Does NOT echo or return the raw text anywhere outside this module.
    """
    if not isinstance(text, str):
        return ""
    t = text.lower()
    # Replace common punctuation with spaces so word matching works
    # even if the user writes "trade,brief" or "签个中锋。".
    t = re.sub(r"[\s,.!?;:，。！？；：、~`@#$%^&*()+={}\[\]|\\\"<>/\-]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _match_any(text: str, keywords: Tuple[str, ...]) -> bool:
    """Return True if any keyword matches ``text``.

    - Keywords that contain only ASCII letters use word-boundary matching
      (so short words like ``sign`` / ``trade`` / ``hold`` / ``wait`` do
      not false-match inside longer words like ``design`` / ``persuade``
      / ``household`` / ``await``).
    - Keywords containing spaces, digits, CJK characters, or hyphens use
      plain substring matching (covers multi-word English phrases and all
      Chinese keywords).
    """
    for kw in keywords:
        if _is_ascii_word(kw):
            if re.search(rf"(?<![a-z]){re.escape(kw)}(?![a-z])", text):
                return True
        else:
            if kw in text:
                return True
    return False


def _is_ascii_word(s: str) -> bool:
    return bool(s) and all(ord("a") <= ord(c) <= ord("z") for c in s)


def _clarification(
    *,
    reason: str,
    objective: Optional[str],
    constraints: Dict[str, Any],
    questions: List[str],
) -> AgentIntentPlan:
    """Build a ``needs_clarification`` result."""
    return AgentIntentPlan(
        classification_status=CLASSIFICATION_STATUS_NEEDS_CLARIFICATION,
        resolved_intent=None,
        confidence=0.4,
        needs_clarification=True,
        objective=objective,
        constraints=constraints,
        safety_flags=["needs_clarification", reason],
        blocked_reason=None,
        clarification_questions=list(questions),
        approval_note=_APPROVAL_NOTE,
    )


def _build_objective(kind: str) -> str:
    """Return an abstract objective string.

    Crucially this never contains specific player names, team names,
    or dollar amounts — those are never present in the classifier's
    input processing anyway, and we never invent them here.
    """
    if kind == "signing":
        return "探索自由球员补强方向，查看符合薪资与阵容规则的签约预览。"
    if kind == "trade":
        return "探索交易方向，查看符合薪资配平与阵容规则的交易预览。"
    return "保持观望。"


def _constraints_to_safe_dict(constraints: List[Any]) -> Dict[str, Any]:
    """Convert the incoming constraints list to a small sanitized dict
    for the response.

    The classifier never forwards raw constraint strings verbatim (to
    avoid leaking specific names/amounts the caller may have passed);
    instead it records only:
      - ``user_provided``: how many constraint items the caller sent
      - ``preserve_cap_flexibility`` heuristic: True if any item looks
        like a cap-flexibility request
      - ``low_risk_only`` heuristic: True if any item looks like a
        low-risk preference
    """
    preserve_cap = False
    low_risk = False
    for c in constraints or []:
        if not isinstance(c, str):
            continue
        cl = c.lower()
        if any(t in cl for t in (
            "cap", "flex", "space", "薪资空间", "灵活", "弹性", "保留空间",
        )):
            preserve_cap = True
        if any(t in cl for t in (
            "low risk", "low-risk", "低风险", "保守", "稳妥", "稳健",
        )):
            low_risk = True
    out: Dict[str, Any] = {
        "user_provided_count": len(constraints or []),
        "preserve_cap_flexibility": preserve_cap,
        "low_risk_only": low_risk,
    }
    return out
