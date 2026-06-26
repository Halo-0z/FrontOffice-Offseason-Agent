"""Deterministic agent intelligence summary model (M9-A).

This module defines ``AgentIntelligenceSummary``, a small JSON-serializable
summary that sits additively on top of an ``AgentOrchestratorResult``. It
explains what the preview contains in plain language, but it is **not**
intelligence in the LLM sense:

- Every field is derived **only** from the orchestrator's already-produced
  ``intent``, ``status``, ``requires_human_approval``, ``preview_payload``,
  ``agent_trace``, ``warnings``, and ``limitations``.
- It never invents players, teams, dollar amounts, PASS/FAIL verdicts.
- It never overrides ``status``, ``requires_human_approval``, or any
  deterministic validation verdict in ``preview_payload``.
- It is frozen (immutable) and JSON-serializable.

Hard guardrails (enforced by tests in ``test_agent_intelligence_summary.py``
and ``test_agent_guardrails.py``):

- No LLM / MCP / network / scraping imports.
- No calls into ``transaction_rule_engine``, ``trade_simulator``, or
  ``snapshot_loader`` — the summary reads the payload; it does not
  re-run engines.
- No execution / commit / apply / mutate language.
- No claims of live / current / real-time NBA data.
- No exposure of internal technical IDs (``run_id``, ``snapshot_id``,
  ``sourcepack``, ``nba_2025_26``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class AgentIntelligenceSummary:
    """Plain-language summary of an orchestrator preview result.

    Attributes:
        summary_title: One-line human-readable title (e.g.
            "签约预览：中锋补强方案" / "Signing preview: center reinforcement").
        plain_language_summary: One-paragraph plain language description
            of what the preview contains, keyed off ``status`` first and
            ``intent`` second.
        deterministic_verdict: Human-readable rendering of the deterministic
            verdict ("规则检查通过 / 通过但有警告 / 暂不行动 / 请求已被安全拦截")
            — read from the payload, never invented.
        evidence_summary: List of short bullets summarizing evidence the
            preview considered (e.g. "阵容需求：C 位现有 0 人" / "薪资配平检查：
            通过"). Pulled from existing evidence/validation fields.
        risk_summary: List of short bullets describing risks / warnings /
            limitations surfaced by deterministic checks. Includes the
            inherent demo-data limitation.
        approval_note: A fixed statement that this is read-only and
            requires human approval (e.g. "这是只读预览，不会自动执行任何操作，
            需要人工确认后才可采取行动").
        data_limitations: List of data-limitation bullets (demo/historical
            data, not real-time NBA data, etc.).
        next_review_questions: List of open questions a human reviewer
            should ask before acting (e.g. "自由球员最新合同状态是否已人工核实？").
        source: Fixed provenance tag — always ``"deterministic-fake-adapter"``
            so downstream consumers can tell this is NOT an LLM output.
    """

    summary_title: str
    plain_language_summary: str
    deterministic_verdict: str
    evidence_summary: List[str] = field(default_factory=list)
    risk_summary: List[str] = field(default_factory=list)
    approval_note: str = ""
    data_limitations: List[str] = field(default_factory=list)
    next_review_questions: List[str] = field(default_factory=list)
    source: str = "deterministic-fake-adapter"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary_title": self.summary_title,
            "plain_language_summary": self.plain_language_summary,
            "deterministic_verdict": self.deterministic_verdict,
            "evidence_summary": list(self.evidence_summary),
            "risk_summary": list(self.risk_summary),
            "approval_note": self.approval_note,
            "data_limitations": list(self.data_limitations),
            "next_review_questions": list(self.next_review_questions),
            "source": self.source,
        }
