"""Deterministic evidence retrieval service (M4-A).

This service is the **evidence foundation** for the future M4-B
offseason agent. It loads local DEMO/SAMPLE/SIMULATION evidence notes
from ``data/evidence_notes.json`` and returns structured
``EvidenceBundle`` objects that the agent can cite when explaining a
plan.

Guardrails:

- No LLM calls. No network. No disk writes.
- Never calls ``transaction_rule_engine``. Never generates proposals.
- Never mutates ``data/evidence_notes.json`` or any roster/cap/contract
  state. All returned objects are new frozen dataclass instances.
- When evidence is missing, returns an empty ``matched_notes`` tuple
  and a clear ``fallback_reason`` — it NEVER fabricates notes.
- ``sample_data`` is always ``True`` on returned notes/bundles; these
  are demo notes, not real news.

Retrieval rules (deterministic, no embeddings):

- ``evidence_ids`` exact match takes priority (used by
  ``get_evidence_by_ids``).
- ``team_id`` / ``player_id`` / ``topics`` matches add to the score.
- ``query`` is lowercased token-overlap against title / summary /
  topics / source.
- ``confidence`` is a light tiebreaker weight.
- Sort is deterministic: score desc, then ``evidence_id`` asc.
- ``limit`` is applied after sorting (0 = no limit).

Run tests:

    python -m pytest backend/app/tests/test_evidence_service.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

from ..models.evidence import (
    EvidenceBundle,
    EvidenceNote,
    EvidenceQuery,
    EvidenceType,
)
from .cap_sheet_service import _resolve_data_dir


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class EvidenceServiceError(Exception):
    """Base class for evidence_service errors."""


class EvidenceFileMissingError(EvidenceServiceError):
    """Raised when ``evidence_notes.json`` is missing or malformed."""


# --------------------------------------------------------------------------- #
# Constants / MVP limitations
# --------------------------------------------------------------------------- #

_MVP_LIMITATIONS: Tuple[str, ...] = (
    "M4-A demo evidence retrieval only.",
    "No external retrieval or live news.",
    "Evidence notes are local sample data.",
)

# Weights for the deterministic scoring. Tuned so that an exact
# evidence_id match dominates, then team/player/topic matches, then
# query token overlap, with confidence as a small tiebreaker.
_W_TEAM = 0.25
_W_PLAYER = 0.25
_W_TOPIC = 0.20  # per matched topic
_W_QUERY_TOKEN = 0.05  # per matched query token
_W_CONFIDENCE = 0.10

# Tokens ignored when computing query overlap (common English stopwords).
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "and", "or", "of", "to", "in", "for", "on",
        "is", "are", "be", "with", "that", "this", "it", "as", "at",
        "by", "from", "has", "have", "not", "but", "was", "were",
    }
)


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #


def load_evidence_notes(
    data_dir: Path | str = "data",
) -> Tuple[EvidenceNote, ...]:
    """Load all demo evidence notes from ``data/evidence_notes.json``.

    Raises:
        EvidenceFileMissingError: if the file is missing or malformed,
            or if any note has an invalid ``evidence_type``.
    """
    path = _resolve_data_dir(data_dir) / "evidence_notes.json"
    if not path.exists():
        raise EvidenceFileMissingError(f"evidence_notes.json not found at {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            payload = json.load(fh)
    except json.JSONDecodeError as exc:
        raise EvidenceFileMissingError(f"invalid JSON in {path}: {exc}") from exc

    raw_notes = payload.get("evidence_notes")
    if not isinstance(raw_notes, list):
        raise EvidenceFileMissingError(
            "evidence_notes.json must contain a list under 'evidence_notes'"
        )

    notes: List[EvidenceNote] = []
    for i, n in enumerate(raw_notes):
        if not isinstance(n, dict):
            raise EvidenceFileMissingError(
                f"evidence_notes.json entry #{i} is not an object: {n!r}"
            )
        notes.append(_parse_note(n, i))
    return tuple(notes)


def _parse_note(raw: dict, index: int) -> EvidenceNote:
    """Parse a raw dict into a frozen ``EvidenceNote``.

    Raises ``EvidenceFileMissingError`` on missing required fields or
    invalid ``evidence_type``.
    """
    eid = raw.get("evidence_id")
    if not eid or not isinstance(eid, str):
        raise EvidenceFileMissingError(
            f"evidence_notes.json entry #{index} missing evidence_id"
        )
    title = raw.get("title")
    if not isinstance(title, str):
        raise EvidenceFileMissingError(
            f"evidence_notes.json entry #{index} ({eid}) missing title"
        )
    summary = raw.get("summary")
    if not isinstance(summary, str):
        raise EvidenceFileMissingError(
            f"evidence_notes.json entry #{index} ({eid}) missing summary"
        )
    source = raw.get("source")
    if not isinstance(source, str):
        raise EvidenceFileMissingError(
            f"evidence_notes.json entry #{index} ({eid}) missing source"
        )
    source_type = raw.get("source_type")
    if not isinstance(source_type, str):
        raise EvidenceFileMissingError(
            f"evidence_notes.json entry #{index} ({eid}) missing source_type"
        )
    raw_type = raw.get("evidence_type")
    if not isinstance(raw_type, str):
        raise EvidenceFileMissingError(
            f"evidence_notes.json entry #{index} ({eid}) missing evidence_type"
        )
    try:
        evidence_type = EvidenceType(raw_type)
    except ValueError as exc:
        raise EvidenceFileMissingError(
            f"evidence_notes.json entry #{index} ({eid}) invalid "
            f"evidence_type: {raw_type!r}"
        ) from exc

    team_ids = tuple(str(t) for t in raw.get("team_ids", []) if isinstance(t, str))
    player_ids = tuple(
        str(p) for p in raw.get("player_ids", []) if isinstance(p, str)
    )
    topics = tuple(
        str(t).lower() for t in raw.get("topics", []) if isinstance(t, str)
    )
    confidence = float(raw.get("confidence", 0.5))
    if confidence < 0.0:
        confidence = 0.0
    elif confidence > 1.0:
        confidence = 1.0
    sample_data = bool(raw.get("sample_data", True))
    raw_meta = raw.get("metadata", {})
    metadata: Tuple[Tuple[str, str], ...] = ()
    if isinstance(raw_meta, dict):
        metadata = tuple(
            (str(k), str(v)) for k, v in raw_meta.items()
        )
    elif isinstance(raw_meta, list):
        metadata = tuple(
            (str(pair[0]), str(pair[1]))
            for pair in raw_meta
            if isinstance(pair, (list, tuple)) and len(pair) == 2
        )

    return EvidenceNote(
        evidence_id=eid,
        title=title,
        summary=summary,
        source=source,
        source_type=source_type,
        evidence_type=evidence_type,
        team_ids=team_ids,
        player_ids=player_ids,
        topics=topics,
        confidence=confidence,
        sample_data=sample_data,
        metadata=metadata,
    )


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


def _tokenize(text: str) -> set[str]:
    """Lowercase tokenization, dropping stopwords and short tokens."""
    tokens = set()
    for raw in text.lower().split():
        # Strip simple punctuation around tokens.
        cleaned = raw.strip(".,;:!?\"'()[]{}")
        if len(cleaned) < 2:
            continue
        if cleaned in _STOPWORDS:
            continue
        tokens.add(cleaned)
    return tokens


def _score_note(
    note: EvidenceNote,
    query: Optional[str],
    team_id: Optional[str],
    player_id: Optional[str],
    topics: Sequence[str],
) -> float:
    """Deterministic relevance score for a note against the query facets.

    Higher is better. Returns 0.0 when NO facet matched (so the caller
    can exclude notes that are irrelevant). ``confidence`` is only
    applied as a tiebreaker when at least one facet matched — it never
    alone causes a note to be included.
    """
    facet_score = 0.0
    matched_any_facet = False

    if team_id and team_id in note.team_ids:
        facet_score += _W_TEAM
        matched_any_facet = True
    if player_id and player_id in note.player_ids:
        facet_score += _W_PLAYER
        matched_any_facet = True

    if topics:
        note_topics = set(note.topics)
        for t in topics:
            if t.lower() in note_topics:
                facet_score += _W_TOPIC
                matched_any_facet = True

    if query:
        q_tokens = _tokenize(query)
        if q_tokens:
            note_text = " ".join(
                [note.title, note.summary, " ".join(note.topics), note.source]
            )
            note_tokens = _tokenize(note_text)
            overlap = q_tokens & note_tokens
            if overlap:
                facet_score += _W_QUERY_TOKEN * len(overlap)
                matched_any_facet = True

    if not matched_any_facet:
        return 0.0

    # Light confidence tiebreaker (only applied when something matched).
    return facet_score + _W_CONFIDENCE * note.confidence


# --------------------------------------------------------------------------- #
# Public retrieval API
# --------------------------------------------------------------------------- #


def get_evidence_by_ids(
    evidence_ids: Union[Tuple[str, ...], List[str]],
    data_dir: Path | str = "data",
) -> EvidenceBundle:
    """Fetch notes by exact ``evidence_id`` match.

    Notes that are not found are reported in ``missing_evidence_ids``.
    If any requested id is missing, ``fallback_reason`` is set to a
    clear message (the bundle is still returned with whatever was
    found). If NOTHING is found, ``matched_notes`` is empty and
    ``fallback_reason`` explains why.
    """
    ids_tuple = tuple(evidence_ids)
    query = EvidenceQuery(evidence_ids=ids_tuple, limit=0)
    all_notes = load_evidence_notes(data_dir)
    by_id: Dict[str, EvidenceNote] = {n.evidence_id: n for n in all_notes}

    matched: List[EvidenceNote] = []
    missing: List[str] = []
    for eid in ids_tuple:
        if eid in by_id:
            matched.append(by_id[eid])
        else:
            missing.append(eid)

    # Deterministic order: preserve requested order, then evidence_id asc.
    matched.sort(key=lambda n: n.evidence_id)

    fallback_reason: Optional[str] = None
    if missing and not matched:
        fallback_reason = (
            f"No evidence found for ids {missing}; matched_notes is empty."
        )
    elif missing:
        fallback_reason = (
            f"Missing evidence ids {missing}; partial bundle returned."
        )

    return EvidenceBundle(
        query=query,
        matched_notes=tuple(matched),
        missing_evidence_ids=tuple(missing),
        fallback_reason=fallback_reason,
        limitations=_MVP_LIMITATIONS,
        sample_data=True,
    )


def search_evidence(
    query: Optional[str] = None,
    team_id: Optional[str] = None,
    player_id: Optional[str] = None,
    topics: Sequence[str] = (),
    limit: int = 5,
    data_dir: Path | str = "data",
) -> EvidenceBundle:
    """Deterministic evidence search by query / team / player / topics.

    Returns an ``EvidenceBundle`` with ``matched_notes`` sorted by score
    desc then ``evidence_id`` asc, truncated to ``limit`` (0 = no limit).
    If nothing matches, ``matched_notes`` is empty and
    ``fallback_reason`` explains why.
    """
    eq = EvidenceQuery(
        query=query,
        team_id=team_id,
        player_id=player_id,
        topics=tuple(topics),
        limit=limit,
    )
    all_notes = load_evidence_notes(data_dir)

    scored: List[Tuple[float, EvidenceNote]] = []
    for note in all_notes:
        score = _score_note(note, query, team_id, player_id, topics)
        # Only include notes with a positive score (i.e. at least one
        # facet matched). A note with score 0 means nothing matched.
        if score > 0.0:
            scored.append((score, note))

    # Deterministic sort: score desc, then evidence_id asc.
    scored.sort(key=lambda pair: (-pair[0], pair[1].evidence_id))

    if limit and limit > 0:
        scored = scored[:limit]

    matched = tuple(n for _, n in scored)

    fallback_reason: Optional[str] = None
    if not matched:
        facets = []
        if query:
            facets.append(f"query={query!r}")
        if team_id:
            facets.append(f"team_id={team_id!r}")
        if player_id:
            facets.append(f"player_id={player_id!r}")
        if topics:
            facets.append(f"topics={tuple(topics)!r}")
        facet_str = ", ".join(facets) if facets else "(no facets)"
        fallback_reason = (
            f"No evidence matched ({facet_str}); matched_notes is empty."
        )

    return EvidenceBundle(
        query=eq,
        matched_notes=matched,
        missing_evidence_ids=(),
        fallback_reason=fallback_reason,
        limitations=_MVP_LIMITATIONS,
        sample_data=True,
    )


def build_evidence_bundle(
    query: Optional[EvidenceQuery] = None,
    *,
    evidence_ids: Union[Tuple[str, ...], List[str], None] = None,
    text_query: Optional[str] = None,
    team_id: Optional[str] = None,
    player_id: Optional[str] = None,
    topics: Sequence[str] = (),
    limit: int = 5,
    data_dir: Path | str = "data",
) -> EvidenceBundle:
    """Unified entry point that dispatches to ``get_evidence_by_ids`` or
    ``search_evidence`` based on the inputs.

    If ``evidence_ids`` (or ``query.evidence_ids``) is non-empty, exact
    id lookup is performed (search facets are ignored, matching the
    "exact match priority" rule). Otherwise a facet search is run.
    """
    if query is not None and query.evidence_ids:
        return get_evidence_by_ids(query.evidence_ids, data_dir)
    if evidence_ids:
        return get_evidence_by_ids(evidence_ids, data_dir)
    q = query or EvidenceQuery(
        query=text_query,
        team_id=team_id,
        player_id=player_id,
        topics=tuple(topics),
        limit=limit,
    )
    return search_evidence(
        query=q.query,
        team_id=q.team_id,
        player_id=q.player_id,
        topics=q.topics,
        limit=q.limit,
        data_dir=data_dir,
    )
