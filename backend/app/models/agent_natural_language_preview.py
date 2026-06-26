"""Natural-language preview flow models (M9-C).

This module defines the request / response dataclasses for the
classify-to-preview backend flow. The flow:

    natural-language utterance
        -> M9-B deterministic rule-based classifier
        -> M9-C safety gate
        -> (only if resolved signing/trade + high confidence + clean
           safety flags) orchestrator preview
        -> otherwise: gate-level response without touching the
           orchestrator.

Hard guardrails enforced by tests:

- Frozen dataclasses (immutable after construction).
- ``flow_status`` is one of ``preview_generated`` /
  ``needs_clarification`` / ``blocked`` / ``preview_not_generated``
  (four distinct states).
- ``classification`` is a *safe projection* of the M9-B intent plan:
  only ``classification_status`` / ``resolved_intent`` / ``confidence``
  / ``needs_clarification`` / ``safety_flags`` / ``blocked_reason``
  / ``clarification_questions`` / ``approval_note`` / ``source`` are
  exposed. ``objective`` / ``constraints`` / raw user text are
  deliberately excluded to avoid echoing caller-supplied entities.
- ``preview_result`` is either the orchestrator's
  ``AgentOrchestratorResult.to_dict()`` verbatim (no reshape, no
  field add/remove, no verdict rewrite) or ``None``.
- ``requires_human_approval`` is ``True`` only when
  ``flow_status == "preview_generated"``.
- ``source`` is fixed to ``"deterministic-classify-to-preview-flow"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


FLOW_STATUS_PREVIEW_GENERATED = "preview_generated"
FLOW_STATUS_NEEDS_CLARIFICATION = "needs_clarification"
FLOW_STATUS_BLOCKED = "blocked"
FLOW_STATUS_PREVIEW_NOT_GENERATED = "preview_not_generated"

_PREVIEW_ALLOWED_INTENTS = frozenset({"signing_preview", "trade_preview_demo"})


@dataclass(frozen=True)
class AgentNaturalLanguagePreviewRequest:
    """Input to the classify-to-preview flow.

    Mirrors the M9-B classify-intent request shape; validation and
    forbidden-key scanning happen at the API layer (reused from M9-B).
    """

    user_text: str
    team_id: Optional[str] = None
    locale: Optional[str] = None
    constraints: Union[Dict[str, Any], List[Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClassificationProjection:
    """Safe projection of :class:`AgentIntentPlan`.

    Deliberately omits ``objective`` and ``constraints`` so caller-
    supplied strings / entities are not echoed back.
    """

    classification_status: str
    resolved_intent: Optional[str]
    confidence: float
    needs_clarification: bool
    safety_flags: List[str] = field(default_factory=list)
    blocked_reason: Optional[str] = None
    clarification_questions: List[str] = field(default_factory=list)
    approval_note: str = ""
    source: str = "deterministic-rule-classifier"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "classification_status": self.classification_status,
            "resolved_intent": self.resolved_intent,
            "confidence": self.confidence,
            "needs_clarification": self.needs_clarification,
            "safety_flags": list(self.safety_flags),
            "blocked_reason": self.blocked_reason,
            "clarification_questions": list(self.clarification_questions),
            "approval_note": self.approval_note,
            "source": self.source,
        }


@dataclass(frozen=True)
class AgentNaturalLanguagePreviewResult:
    """Result of the classify-to-preview flow.

    Invariants:

    - If ``flow_status == "preview_generated"``:
        - ``classification.resolved_intent`` is in
          ``{"signing_preview", "trade_preview_demo"}``
        - ``preview_result`` is a dict equal to the orchestrator
          result's ``to_dict()`` (deep equal; no reshape)
        - ``requires_human_approval`` is ``True``
    - If ``flow_status == "needs_clarification"``:
        - ``preview_result is None``
        - ``requires_human_approval is False``
        - ``classification.needs_clarification is True``
    - If ``flow_status == "blocked"``:
        - ``preview_result is None``
        - ``requires_human_approval is False``
        - ``classification.blocked_reason`` is non-empty
    - If ``flow_status == "preview_not_generated"``:
        - ``preview_result is None``
        - ``requires_human_approval is False``
        - covers resolved/hold, low-confidence, invalid invariants,
          and safety-flag denials
    """

    flow_status: str
    classification: ClassificationProjection
    preview_result: Optional[Dict[str, Any]]
    requires_human_approval: bool
    safety_notes: List[str] = field(default_factory=list)
    source: str = "deterministic-classify-to-preview-flow"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "flow_status": self.flow_status,
            "classification": self.classification.to_dict(),
            "preview_result": self.preview_result,
            "requires_human_approval": self.requires_human_approval,
            "safety_notes": list(self.safety_notes),
            "source": self.source,
        }


# ---------------------------------------------------------------------------
# Default safety notes (stable, generic; do not contain user text).
# ---------------------------------------------------------------------------

_DEFAULT_SAFETY_NOTES: List[str] = [
    "Only resolved signing/trade plans may generate preview.",
    "Needs-clarification, blocked, hold, and low-confidence plans do not call the orchestrator.",
    "Preview results are read-only and require human approval.",
]
