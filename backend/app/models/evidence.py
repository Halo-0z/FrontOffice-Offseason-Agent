"""Evidence models for FrontOffice-Offseason-Agent (M4-A).

These are DEMO/SAMPLE/SIMULATION models. They represent local analyst
notes used by the future M4-B offseason agent to cite supporting
evidence for each plan. They are **not** real news, real reporting, or
real NBA media citations.

All dataclasses are frozen so callers (including the future agent
layer) cannot mutate evidence state in place. The
``evidence_service`` returns new instances and never writes to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class EvidenceType(str, Enum):
    """The kind of context an ``EvidenceNote`` provides.

    - ``TEAM_CONTEXT``        : notes about a team's situation/goals.
    - ``PLAYER_CONTEXT``      : notes about a specific player.
    - ``CAP_CONTEXT``         : notes about cap space / aprons / exceptions.
    - ``ROSTER_CONTEXT``      : notes about roster composition / needs.
    - ``MARKET_CONTEXT``      : notes about the free-agent / trade market.
    - ``TRANSACTION_CONTEXT`` : notes about a specific transaction idea.
    - ``GENERAL_NOTE``        : anything that does not fit above.
    """

    TEAM_CONTEXT = "team_context"
    PLAYER_CONTEXT = "player_context"
    CAP_CONTEXT = "cap_context"
    ROSTER_CONTEXT = "roster_context"
    MARKET_CONTEXT = "market_context"
    TRANSACTION_CONTEXT = "transaction_context"
    GENERAL_NOTE = "general_note"


@dataclass(frozen=True)
class EvidenceNote:
    """A single local demo evidence note.

    Attributes:
        evidence_id: Stable identifier, e.g. ``"ev-demo-001"``.
        title: Short human-readable title.
        summary: One- or two-sentence summary (demo/fictional).
        source: Free-form source label, e.g.
            ``"demo-scouting-note"`` / ``"demo-cap-note"``. Never a real
            media name.
        source_type: Coarse source category, e.g.
            ``"internal_simulation"`` / ``"demo-front-office-note"``.
        evidence_type: ``EvidenceType`` for filtering.
        team_ids: Team ids this note is relevant to (may be empty).
        player_ids: Player ids this note is relevant to (may be empty).
        topics: Free-form topic tags, e.g. ``("cap", "pg_need")``.
        confidence: Heuristic confidence in ``[0.0, 1.0]``.
        sample_data: Always ``True`` for demo notes.
        metadata: Optional free-form metadata dict.
    """

    evidence_id: str
    title: str
    summary: str
    source: str
    source_type: str
    evidence_type: EvidenceType
    team_ids: Tuple[str, ...] = field(default_factory=tuple)
    player_ids: Tuple[str, ...] = field(default_factory=tuple)
    topics: Tuple[str, ...] = field(default_factory=tuple)
    confidence: float = 0.5
    sample_data: bool = True
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EvidenceQuery:
    """A deterministic evidence retrieval query.

    Attributes:
        query: Optional free-text query (lowercased token overlap is
            used; no LLM, no embeddings).
        team_id: Optional team filter.
        player_id: Optional player filter.
        topics: Optional topic tags to match.
        evidence_ids: Optional explicit evidence ids to fetch directly.
        limit: Max number of matched notes to return (0 = no limit).
    """

    query: Optional[str] = None
    team_id: Optional[str] = None
    player_id: Optional[str] = None
    topics: Tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: Tuple[str, ...] = field(default_factory=tuple)
    limit: int = 5


@dataclass(frozen=True)
class EvidenceBundle:
    """A structured evidence retrieval result.

    Attributes:
        query: The ``EvidenceQuery`` that produced this bundle.
        matched_notes: Notes matched by the query, sorted by score desc
            then ``evidence_id`` asc. Empty if nothing matched.
        missing_evidence_ids: Subset of ``query.evidence_ids`` that were
            not found in the demo data.
        fallback_reason: ``None`` when retrieval succeeded; a clear
            string when no notes matched or some requested ids were
            missing.
        limitations: Notes about MVP simplifications.
        sample_data: Always ``True`` for demo bundles.
    """

    query: EvidenceQuery
    matched_notes: Tuple[EvidenceNote, ...] = field(default_factory=tuple)
    missing_evidence_ids: Tuple[str, ...] = field(default_factory=tuple)
    fallback_reason: Optional[str] = None
    limitations: Tuple[str, ...] = field(default_factory=tuple)
    sample_data: bool = True
