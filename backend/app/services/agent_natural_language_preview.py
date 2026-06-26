"""Classify-to-preview backend flow (M9-C).

This is the only module that composes M9-B (intent classification) with
M8-E (preview orchestration). It imports and calls ONLY:

- ``backend.app.services.agent_intent_classifier.classify_user_intent``
- ``backend.app.services.agent_orchestrator.orchestrate_preview``

It does NOT directly import or call any deterministic engine
(``trade_simulator``, ``transaction_rule_engine``, ``proposal_builder``,
``proposal_viewer``, ``snapshot_loader``) or the M9-A/B adapter/trace
modules (``agent_intelligence``, ``agent_trace_builder``). Those are
reached through ``orchestrate_preview`` only, which remains the single
choke-point for preview generation.

Gate rules (strict four-state):

1. ``preview_generated`` — ALL of:
   - ``classification_status == "resolved"``
   - ``resolved_intent in {"signing_preview", "trade_preview_demo"}``
   - ``needs_clarification is False``
   - ``blocked_reason is None``
   - ``confidence >= 0.7``
   - no safety flag indicating danger / block / unsafe
2. ``needs_clarification`` — ``classification_status == "needs_clarification"``
3. ``blocked`` — ``classification_status == "blocked"``
4. ``preview_not_generated`` — everything else, including:
   - resolved/hold (GLM review: hold must NOT call the orchestrator)
   - invalid invariant combos (e.g. resolved + resolved_intent=None)
   - low confidence
   - dangerous/blocked/unsafe safety flags

In all non-generated states the orchestrator is NEVER called.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from backend.app.models.agent_natural_language_preview import (
    FLOW_STATUS_BLOCKED,
    FLOW_STATUS_NEEDS_CLARIFICATION,
    FLOW_STATUS_PREVIEW_GENERATED,
    FLOW_STATUS_PREVIEW_NOT_GENERATED,
    AgentNaturalLanguagePreviewRequest,
    AgentNaturalLanguagePreviewResult,
    ClassificationProjection,
)
from backend.app.models.agent_natural_language_preview import (
    _DEFAULT_SAFETY_NOTES,
    _PREVIEW_ALLOWED_INTENTS,
)
from backend.app.models.agent_intent_classifier import (
    AgentIntentClassificationRequest,
)

_SAFETY_FLAG_BLOCK_TOKENS = ("dangerous", "blocked", "unsafe")


def _project_classification(plan: Any) -> ClassificationProjection:
    """Return a safe projection of the M9-B intent plan.

    Intentionally omits ``objective`` and ``constraints`` so caller-
    supplied entities / user text is not echoed in the M9-C response.
    """
    return ClassificationProjection(
        classification_status=plan.classification_status,
        resolved_intent=plan.resolved_intent,
        confidence=plan.confidence,
        needs_clarification=plan.needs_clarification,
        safety_flags=list(plan.safety_flags),
        blocked_reason=plan.blocked_reason,
        clarification_questions=list(plan.clarification_questions),
        approval_note=plan.approval_note,
        source=plan.source,
    )


def _safety_flag_denies_preview(flags: List[str]) -> bool:
    lowered = [f.lower() for f in (flags or [])]
    for tok in _SAFETY_FLAG_BLOCK_TOKENS:
        for f in lowered:
            if tok in f:
                return True
    return False


def run_natural_language_preview(
    request: AgentNaturalLanguagePreviewRequest,
    data_dir: Optional[Union[str, Path]] = None,
) -> AgentNaturalLanguagePreviewResult:
    """Run the classify-to-preview flow.

    Pure read-only flow. When the gate allows preview, imports and calls
    :func:`orchestrate_preview` and returns ``orchestrator_result.to_dict()``
    verbatim as ``preview_result`` (no reshape, no add/remove fields, no
    verdict rewrite).

    Args:
        request: M9-C request (user_text + team/locale/constraints/metadata).
        data_dir: Optional override for the demo data directory; default
            uses the orchestrator's own default (``<repo>/data``).
    """
    from backend.app.services.agent_intent_classifier import classify_user_intent

    cls_req = AgentIntentClassificationRequest(
        user_text=request.user_text,
        team_id=request.team_id,
        locale=request.locale,
        constraints=_copy_constraints(request.constraints),
        metadata=dict(request.metadata),
    )
    plan = classify_user_intent(cls_req)

    classification = _project_classification(plan)

    # Decide flow_status based on the plan + defensive invariants.
    flow_status, preview_result, requires_human_approval, extra_notes = _gate(
        plan, request, data_dir
    )

    safety_notes = list(_DEFAULT_SAFETY_NOTES) + list(extra_notes)

    return AgentNaturalLanguagePreviewResult(
        flow_status=flow_status,
        classification=classification,
        preview_result=preview_result,
        requires_human_approval=requires_human_approval,
        safety_notes=safety_notes,
    )


def _copy_constraints(c: Union[Dict[str, Any], List[Any]]):
    if isinstance(c, dict):
        return dict(c)
    if isinstance(c, list):
        return list(c)
    return c


def _gate(
    plan: Any,
    request: AgentNaturalLanguagePreviewRequest,
    data_dir: Optional[Union[str, Path]],
):
    """Apply the M9-C gate.

    Returns (flow_status, preview_result_or_None, requires_human_approval, extra_notes).
    """
    status = plan.classification_status
    intent = plan.resolved_intent
    conf = plan.confidence

    # 1. needs_clarification / blocked short-circuit first (never call orchestrator)
    if status == "needs_clarification":
        return FLOW_STATUS_NEEDS_CLARIFICATION, None, False, []
    if status == "blocked":
        return FLOW_STATUS_BLOCKED, None, False, []

    # 2. Defensive invariant checks — anything that falls through but isn't
    #    a clean resolved + allowed-intent + high-confidence + safe-flagged
    #    plan must produce preview_not_generated without touching the
    #    orchestrator.
    invalid = False
    invalid_reason: Optional[str] = None

    if status != "resolved":
        invalid = True
        invalid_reason = "unrecognised_classification_status"
    elif intent is None:
        invalid = True
        invalid_reason = "resolved_without_intent"
    elif not isinstance(conf, (int, float)) or conf < 0.7:
        invalid = True
        invalid_reason = "low_confidence"
    elif _safety_flag_denies_preview(plan.safety_flags):
        invalid = True
        invalid_reason = "unsafe_safety_flags"
    elif intent == "hold":
        # Resolved hold: explicit user request not to act. Gate-level hold,
        # do not call orchestrator (per GLM review; avoids conflicting with
        # the M8-F frontend hold → old proposal-preview behaviour).
        extra = [
            "User intent is hold: no signing/trade preview was generated.",
        ]
        return FLOW_STATUS_PREVIEW_NOT_GENERATED, None, False, extra
    elif intent not in _PREVIEW_ALLOWED_INTENTS:
        invalid = True
        invalid_reason = "unsupported_resolved_intent"

    if invalid:
        extra = []
        if invalid_reason:
            extra.append(f"Gate denied preview: {invalid_reason}.")
        return FLOW_STATUS_PREVIEW_NOT_GENERATED, None, False, extra

    # 3. Allowed resolved signing/trade — call orchestrator and return verbatim.
    from backend.app.models.agent_orchestrator import AgentOrchestratorRequest
    from backend.app.services.agent_orchestrator import orchestrate_preview

    # We deliberately do NOT forward the raw user_text as objective, since
    # the objective field flows into signing preview builders and may be
    # surfaced verbatim. Use a generic objective that matches the intent.
    objective = _generic_objective_for(intent)

    orch_req = AgentOrchestratorRequest(
        intent=intent,
        team_id=request.team_id,
        locale=request.locale,
        objective=objective,
        metadata=dict(request.metadata),
    )

    if data_dir is not None:
        orch_result = orchestrate_preview(orch_req, data_dir)
    else:
        orch_result = orchestrate_preview(orch_req)

    return (
        FLOW_STATUS_PREVIEW_GENERATED,
        orch_result.to_dict(),
        True,
        [],
    )


def _generic_objective_for(intent: str) -> str:
    if intent == "signing_preview":
        return "generate a read-only free-agent signing preview"
    if intent == "trade_preview_demo":
        return "generate a read-only demo trade preview"
    return "generate a read-only preview"
