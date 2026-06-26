"""Natural-language intent classifier models (M9-B).

This module defines the request / response dataclasses for the deterministic
rule-based intent classifier. The classifier sits **upstream** of the
preview-only orchestrator: it decides which broad category a natural-language
user utterance falls into (signing preview / trade preview / hold / needs
clarification / blocked), but it does **not** build previews, pick players,
simulate trades, or call the orchestrator in any way.

Hard guardrails (enforced by tests in ``test_agent_intent_classifier.py``,
``test_agent_intent_classifier_api.py`` and ``test_agent_guardrails.py``):

- Frozen dataclass (immutable after construction).
- Pure-Python rule-based classification — no LLM, no network.
- No imports from the orchestrator or deterministic engines
  (``agent_orchestrator``, ``transaction_rule_engine``, ``trade_simulator``,
  ``snapshot_loader``, ``proposal_builder``, ``proposal_viewer``,
  ``agent_intelligence``, ``agent_trace_builder``).
- ``classification_status`` is one of ``resolved`` / ``needs_clarification``
  / ``blocked`` — three distinct states; low-confidence inputs MUST return
  ``needs_clarification`` (never ``hold``).
- When status is ``needs_clarification`` or ``blocked``, ``resolved_intent``
  MUST be ``None`` (so downstream consumers cannot mistake ambiguity for a
  concrete hold recommendation).
- When status is ``resolved``, ``resolved_intent`` is one of
  ``signing_preview`` / ``trade_preview_demo`` / ``hold``.
- ``source`` is fixed to ``"deterministic-rule-classifier"``.
- Output never echoes the raw user text, never names specific players /
  teams / dollar amounts, never contains execution-semantic words or
  live-data claims.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


CLASSIFICATION_STATUS_RESOLVED = "resolved"
CLASSIFICATION_STATUS_NEEDS_CLARIFICATION = "needs_clarification"
CLASSIFICATION_STATUS_BLOCKED = "blocked"

VALID_RESOLVED_INTENTS = frozenset({
    "signing_preview",
    "trade_preview_demo",
    "hold",
})


@dataclass(frozen=True)
class AgentIntentClassificationRequest:
    """Input to the intent classifier.

    Attributes:
        user_text: Free-form natural-language utterance from the user.
            Required; max 500 characters; no control characters or
            zero-width characters (validated at the API layer).
        team_id: Optional team identifier. The classifier does not
            resolve specific teams; this is passed through for logging
            / future use only and MUST NOT influence classification.
        locale: Optional locale hint (``zh-CN`` / ``en-US`` / ...).
        constraints: Caller-provided constraint strings / objects.
            Recursively scanned for forbidden mutation keys by the API
            layer before reaching the classifier.
        metadata: Optional caller metadata. Recursively scanned for
            forbidden mutation keys by the API layer.
    """

    user_text: str
    team_id: Optional[str] = None
    locale: Optional[str] = None
    constraints: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentIntentPlan:
    """Deterministic intent classification result.

    Invariants (enforced by builder + tests):

    - If ``classification_status == "resolved"`` then
      ``resolved_intent`` is in ``{signing_preview, trade_preview_demo, hold}``,
      ``needs_clarification is False``, ``blocked_reason is None``.
    - If ``classification_status == "needs_clarification"`` then
      ``resolved_intent is None``, ``needs_clarification is True``,
      ``blocked_reason is None``, and ``clarification_questions`` is
      non-empty.
    - If ``classification_status == "blocked"`` then
      ``resolved_intent is None``, ``needs_clarification is False``,
      ``blocked_reason`` is a non-empty generic string that does NOT
      echo the raw user text, and ``confidence == 0.0``.

    ``confidence`` is always in ``[0.0, 1.0]``:
      - blocked: 0.0
      - needs_clarification: < 0.7
      - resolved: >= 0.7
    """

    classification_status: str
    resolved_intent: Optional[str]
    confidence: float
    needs_clarification: bool
    objective: Optional[str]
    constraints: Dict[str, Any]
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
            "objective": self.objective,
            "constraints": _safe_dict_copy(self.constraints),
            "safety_flags": list(self.safety_flags),
            "blocked_reason": self.blocked_reason,
            "clarification_questions": list(self.clarification_questions),
            "approval_note": self.approval_note,
            "source": self.source,
        }


def _safe_dict_copy(d: Dict[str, Any]) -> Dict[str, Any]:
    """Return a shallow-but-safe copy that won't alias the caller's dict.

    Values that are lists or dicts are shallow-copied; primitives are
    returned as-is. This is enough to guarantee the classifier never
    mutates the caller's input.
    """
    out: Dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, list):
            out[k] = list(v)
        elif isinstance(v, dict):
            out[k] = dict(v)
        else:
            out[k] = v
    return out
