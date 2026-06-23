"""Free agent matching service (M3-B).

Deterministic, LLM-free matching of demo free agents to a team's roster
needs. Reads ``data/free_agents.json``, calls
``roster_need_service.evaluate_roster_needs`` to get the team's
``PositionNeed`` list, and scores each free agent against those needs.

Guardrails:

- No LLM calls. No network. No disk writes.
- Does NOT call ``transaction_rule_engine``. Does NOT generate
  ``SigningTransaction`` objects. This service only *suggests*
  candidates; turning a candidate into a proposal is the agent's (M4)
  job, and validating it is the rule engine's (M2) job.
- ``FreeAgentFit`` is immutable; this service only returns new instances.

Run tests:

    python -m pytest backend/app/tests/test_free_agent_service.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from ..models.roster import (
    FreeAgentFit,
    NeedPriority,
    Position,
    PositionNeed,
)
from .cap_sheet_service import (
    TeamNotFoundError,
    _load_team_ids,
    _resolve_data_dir,
    load_cap_config,
)
from .roster_need_service import evaluate_roster_needs


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class FreeAgentServiceError(Exception):
    """Base class for free_agent_service errors."""


class FreeAgentsFileMissingError(FreeAgentServiceError):
    """Raised when ``free_agents.json`` is missing or malformed."""


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# Lightweight role-keyword buckets used as a small fit-score booster.
# This is NOT a scouting model; it just gives a tiny bonus when a free
# agent's role text aligns with a positional archetype.
_ROLE_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "guard": ("PG", "SG"),
    "wing": ("SF", "SG"),
    "forward": ("SF", "PF"),
    "big": ("PF", "C"),
    "center": ("C",),
}

# Salary affordability: if expected_salary exceeds this multiple of the
# mid-level exception, we penalize the fit score.
_SALARY_PENALTY_THRESHOLD_FACTOR = 1.5

_MVP_LIMITATIONS: Tuple[str, ...] = (
    "Demo free-agent matching: position + role keyword + salary affordability heuristic.",
    "Not a scouting model; does not consider player quality, age, or injury history.",
    "Does not call transaction_rule_engine or generate signing transactions.",
)


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #


def load_free_agents(data_dir: Path | str = "data") -> tuple:
    """Load all demo free agents from ``free_agents.json``.

    Returns a tuple of plain dicts (one per free agent) so callers can
    inspect raw fields. Use ``rank_free_agents_for_team`` for scored
    ``FreeAgentFit`` objects.

    Raises:
        FreeAgentsFileMissingError: if the file is missing/malformed.
    """
    path = _resolve_data_dir(data_dir) / "free_agents.json"
    if not path.exists():
        raise FreeAgentsFileMissingError(f"free_agents.json not found at {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            payload = json.load(fh)
    except json.JSONDecodeError as exc:
        raise FreeAgentsFileMissingError(f"invalid JSON in {path}: {exc}") from exc
    agents = payload.get("free_agents")
    if not isinstance(agents, list):
        raise FreeAgentsFileMissingError(
            "free_agents.json must contain a list under 'free_agents'"
        )
    return tuple(agents)


def get_free_agent_by_id(
    free_agent_id: str, data_dir: Path | str = "data"
) -> dict | None:
    """Return the raw free-agent dict for ``free_agent_id``, or ``None``.

    Looks up by both ``free_agent_id`` and ``player_id`` fields (the demo
    data uses both; some entries share the same value). Returns the raw
    dict so callers (e.g. ``trade_simulator``) can read ``position``,
    ``name``, and ``role`` without re-parsing the file.

    Returns ``None`` if no free agent matches. ``FreeAgentsFileMissingError``
    is propagated if ``free_agents.json`` itself is missing/malformed.
    """
    agents = load_free_agents(data_dir)
    for a in agents:
        if not isinstance(a, dict):
            continue
        if str(a.get("free_agent_id")) == free_agent_id or str(
            a.get("player_id")
        ) == free_agent_id:
            return a
    return None


# --------------------------------------------------------------------------- #
# Scoring
# --------------------------------------------------------------------------- #


def _role_bonus(position: Position, role_text: str) -> float:
    """Small bonus (0.0-0.1) if the role text matches the position archetype."""
    role_lower = (role_text or "").lower()
    bonus = 0.0
    for keyword, positions in _ROLE_KEYWORDS.items():
        if keyword in role_lower and position.value in positions:
            bonus = max(bonus, 0.1)
    return bonus


def _salary_affordability_score(
    expected_salary: int, mid_level_exception: int
) -> float:
    """Return a 0.0-1.0 affordability score.

    - expected_salary <= mid_level_exception: full 1.0
    - expected_salary <= mid_level_exception * 1.5: linear decay to 0.5
    - expected_salary > mid_level_exception * 1.5: linear decay toward 0.0
    """
    if expected_salary <= 0:
        return 1.0
    if mid_level_exception <= 0:
        return 0.0
    if expected_salary <= mid_level_exception:
        return 1.0
    over = expected_salary - mid_level_exception
    threshold = mid_level_exception * _SALARY_PENALTY_THRESHOLD_FACTOR
    if expected_salary <= threshold:
        # Linear from 1.0 down to 0.5 across [MLE, MLE*1.5].
        return 1.0 - 0.5 * (over / (threshold - mid_level_exception))
    # Beyond threshold: continue decaying toward 0.
    excess = expected_salary - threshold
    return max(0.0, 0.5 - 0.5 * (excess / mid_level_exception))


def _priority_weight(priority: NeedPriority) -> float:
    """Higher weight for higher-priority needs."""
    if priority is NeedPriority.HIGH:
        return 1.0
    if priority is NeedPriority.MEDIUM:
        return 0.6
    return 0.2  # LOW


def _score_free_agent(
    agent: dict,
    needs: Tuple[PositionNeed, ...],
    mid_level_exception: int,
) -> Tuple[float, PositionNeed | None]:
    """Compute a deterministic fit score in [0.0, 1.0] for one agent.

    Returns ``(score, matched_need)``. ``matched_need`` is the need the
    agent best matches (by position), or ``None`` if the team has no
    needs or the agent's position is not among the needs.
    """
    try:
        position = Position(str(agent.get("position", "")))
    except ValueError:
        return 0.0, None

    # Find the matching need (if any) by position.
    matched_need: PositionNeed | None = None
    for n in needs:
        if n.position is position:
            matched_need = n
            break

    # Base score: position match against a need is the dominant signal.
    if matched_need is not None:
        base = 0.6 * _priority_weight(matched_need.priority)
    elif not needs:
        # No needs at all: small generic score so we still return
        # candidates, but flagged as low-priority suggestions.
        base = 0.1
    else:
        # Has needs but this agent doesn't match any of them.
        base = 0.05

    # Role keyword bonus (0.0 - 0.1).
    role_bonus = _role_bonus(position, str(agent.get("role", "")))

    # Salary affordability (0.0 - 1.0), weighted at 0.3.
    expected_salary = int(agent.get("expected_salary", 0) or 0)
    affordability = _salary_affordability_score(expected_salary, mid_level_exception)
    salary_component = 0.3 * affordability

    score = base + role_bonus + salary_component
    # Clamp to [0, 1].
    return (max(0.0, min(1.0, score)), matched_need)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def match_free_agents_to_needs(
    team_id: str, data_dir: Path | str = "data"
) -> Tuple[FreeAgentFit, ...]:
    """Match free agents to ``team_id``'s roster needs.

    Returns a tuple of ``FreeAgentFit`` sorted by ``fit_score`` descending,
    then by ``free_agent_id`` ascending for determinism.

    Raises:
        TeamNotFoundError: if ``team_id`` is not in ``teams.json``.
        FreeAgentsFileMissingError: if ``free_agents.json`` is missing/malformed.
    """
    team_ids = _load_team_ids(data_dir)
    if team_id not in team_ids:
        raise TeamNotFoundError(
            f"team_id {team_id!r} not found in teams.json; known: {sorted(team_ids)}"
        )

    report = evaluate_roster_needs(team_id, data_dir)
    needs = report.needs
    cap_config = load_cap_config(data_dir)
    agents = load_free_agents(data_dir)

    fits: List[FreeAgentFit] = []
    for agent in agents:
        score, matched_need = _score_free_agent(
            agent, needs, cap_config.mid_level_exception
        )
        try:
            position = Position(str(agent.get("position", "")))
        except ValueError:
            # Skip agents with invalid positions rather than crashing.
            continue
        fits.append(
            FreeAgentFit(
                free_agent_id=str(agent.get("free_agent_id") or agent.get("player_id", "")),
                name=str(agent.get("name", "")),
                position=position,
                role=str(agent.get("role", "")),
                expected_salary=int(agent.get("expected_salary", 0) or 0),
                matched_need=matched_need,
                fit_score=round(score, 4),
                evidence_ids=tuple(str(e) for e in agent.get("evidence_ids", []) or []),
                limitations=_MVP_LIMITATIONS,
            )
        )

    # Sort: fit_score desc, then free_agent_id asc for determinism.
    fits.sort(key=lambda f: (-f.fit_score, f.free_agent_id))
    return tuple(fits)


def rank_free_agents_for_team(
    team_id: str, data_dir: Path | str = "data"
) -> Tuple[FreeAgentFit, ...]:
    """Alias for ``match_free_agents_to_needs``.

    Returns free agents ranked by fit score (best first).
    """
    return match_free_agents_to_needs(team_id, data_dir)
