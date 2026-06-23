"""Roster need service (M3-A).

Deterministic, LLM-free analysis of a team's current roster needs.
Loads demo players from ``data/players.json``, joins optional contract
info from ``data/contracts.json``, and produces a ``RosterNeedReport``
that lists which positions are under-staffed vs a simple target count.

Guardrails:

- No LLM calls. No network. No disk writes.
- Never calls ``transaction_rule_engine``. Never generates proposals.
- Position targets are heuristic constants, kept here (not mixed into
  ``cap_config``). They are a demo roster-planning rule, not a salary
  rule.
- ``RosterPlayer`` / ``RosterNeedReport`` are immutable; this service
  only returns new instances.

Run tests:

    python -m pytest backend/app/tests/test_roster_need_service.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple

from ..models.roster import (
    NeedPriority,
    Position,
    PositionNeed,
    RosterNeedReport,
    RosterPlayer,
)
from .cap_sheet_service import (
    CapSheetError,
    TeamNotFoundError,
    _load_team_ids,
    _resolve_data_dir,
)


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #


class RosterNeedError(Exception):
    """Base class for roster_need_service errors."""


class PlayersFileMissingError(RosterNeedError):
    """Raised when ``players.json`` is missing or malformed."""


# --------------------------------------------------------------------------- #
# Heuristic position targets
# --------------------------------------------------------------------------- #

# Demo roster-planning target: how many players each team should carry
# per position. This is NOT a salary/CBA rule and is deliberately kept
# in this service module, separate from ``cap_config``.
POSITION_TARGET_COUNTS: Dict[Position, int] = {
    Position.PG: 2,
    Position.SG: 2,
    Position.SF: 2,
    Position.PF: 2,
    Position.C: 2,
}

_MVP_LIMITATIONS: Tuple[str, ...] = (
    "Demo roster-need heuristic: target=2 per position. Not a scouting model.",
    "Does not consider player quality, injuries, or scheme fit.",
    "Does not call transaction_rule_engine or generate proposals.",
)


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #


def _load_players_raw(data_dir: Path | str) -> list[dict]:
    """Load the raw ``players`` list from ``players.json``."""
    path = _resolve_data_dir(data_dir) / "players.json"
    if not path.exists():
        raise PlayersFileMissingError(f"players.json not found at {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            payload = json.load(fh)
    except json.JSONDecodeError as exc:
        raise PlayersFileMissingError(f"invalid JSON in {path}: {exc}") from exc
    players = payload.get("players")
    if not isinstance(players, list):
        raise PlayersFileMissingError(
            "players.json must contain a list under 'players'"
        )
    return players


def _load_contracts_map(data_dir: Path | str) -> Dict[str, dict]:
    """Load ``contracts.json`` as a ``player_id -> contract dict`` map.

    Used to enrich ``RosterPlayer`` with ``contract_id`` and ``salary``.
    Missing or malformed contracts file yields an empty map (non-fatal).
    """
    path = _resolve_data_dir(data_dir) / "contracts.json"
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            payload = json.load(fh)
    except json.JSONDecodeError:
        return {}
    contracts = payload.get("contracts")
    if not isinstance(contracts, list):
        return {}
    return {str(c["player_id"]): c for c in contracts if isinstance(c, dict) and "player_id" in c}


def load_roster_players(
    team_id: str, data_dir: Path | str = "data"
) -> Tuple[RosterPlayer, ...]:
    """Load the current roster players for ``team_id``.

    Raises:
        TeamNotFoundError: if ``team_id`` is not in ``teams.json``.
        PlayersFileMissingError: if ``players.json`` is missing/malformed.
    """
    team_ids = _load_team_ids(data_dir)
    if team_id not in team_ids:
        raise TeamNotFoundError(
            f"team_id {team_id!r} not found in teams.json; known: {sorted(team_ids)}"
        )
    raw_players = _load_players_raw(data_dir)
    contracts_map = _load_contracts_map(data_dir)

    players: list[RosterPlayer] = []
    for i, p in enumerate(raw_players):
        if not isinstance(p, dict):
            raise PlayersFileMissingError(
                f"players.json entry #{i} is not an object: {p!r}"
            )
        if str(p.get("team_id")) != team_id:
            continue
        try:
            position = Position(str(p["position"]))
        except (KeyError, ValueError) as exc:
            raise PlayersFileMissingError(
                f"players.json entry #{i} has invalid position: {p.get('position')!r}"
            ) from exc
        contract = contracts_map.get(str(p.get("player_id")))
        players.append(
            RosterPlayer(
                player_id=str(p["player_id"]),
                name=str(p.get("name", "")),
                team_id=team_id,
                position=position,
                role=str(p.get("role", "bench")),
                contract_id=str(contract["contract_id"]) if contract else None,
                salary=int(contract["salary"]) if contract and "salary" in contract else None,
                sample_data=bool(p.get("sample_data", False)),
            )
        )
    return tuple(players)


# --------------------------------------------------------------------------- #
# Analysis
# --------------------------------------------------------------------------- #


def summarize_position_counts(
    players: Tuple[RosterPlayer, ...] | list[RosterPlayer],
) -> Dict[Position, int]:
    """Return a ``{Position: count}`` dict for the given players.

    Every standard position is present in the result (0 if no players).
    """
    counts: Dict[Position, int] = {pos: 0 for pos in Position}
    for p in players:
        counts[p.position] = counts.get(p.position, 0) + 1
    return counts


def _priority_for_gap(gap: int) -> NeedPriority:
    """Map a shortfall gap to a priority. ``gap`` = target - current."""
    if gap >= 2:
        return NeedPriority.HIGH
    if gap == 1:
        return NeedPriority.MEDIUM
    return NeedPriority.LOW


def evaluate_roster_needs(
    team_id: str, data_dir: Path | str = "data"
) -> RosterNeedReport:
    """Produce a deterministic ``RosterNeedReport`` for ``team_id``."""
    players = load_roster_players(team_id, data_dir)
    counts = summarize_position_counts(players)

    needs: list[PositionNeed] = []
    strengths: list[Position] = []
    for pos in Position:  # enum order: PG, SG, SF, PF, C
        current = counts.get(pos, 0)
        target = POSITION_TARGET_COUNTS[pos]
        gap = target - current
        if gap > 0:
            priority = _priority_for_gap(gap)
            needs.append(
                PositionNeed(
                    position=pos,
                    current_count=current,
                    target_count=target,
                    priority=priority,
                    reason=(
                        f"{pos.value}: have {current}, target {target}, "
                        f"short {gap} (priority={priority.value})."
                    ),
                )
            )
        else:
            strengths.append(pos)

    # Sort needs: high priority first, then by position enum order.
    priority_order = {NeedPriority.HIGH: 0, NeedPriority.MEDIUM: 1, NeedPriority.LOW: 2}
    needs.sort(key=lambda n: (priority_order[n.priority], list(Position).index(n.position)))

    return RosterNeedReport(
        team_id=team_id,
        roster_count=len(players),
        needs=tuple(needs),
        strengths=tuple(strengths),
        limitations=_MVP_LIMITATIONS,
    )
