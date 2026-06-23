"""Depth chart projector (M3-A).

Deterministic, LLM-free projection of a team's *current* depth chart
from ``data/players.json``. This is the "current state" projector; a
future post-transaction projector (M3-B) will reuse this logic on a
preview roster.

Guardrails:

- No LLM calls. No network. No disk writes.
- The depth chart is always derived from roster players, never hardcoded.
- ``ProjectedDepthChart`` is immutable; this service only returns new
  instances.
- Does not call ``transaction_rule_engine`` and does not generate
  proposals.

Run tests:

    python -m pytest backend/app/tests/test_depth_chart_projector.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

from ..models.roster import (
    DepthChartSlot,
    NeedLevel,
    Position,
    ProjectedDepthChart,
    RosterPlayer,
)
from .roster_need_service import load_roster_players


_MVP_LIMITATIONS: Tuple[str, ...] = (
    "Demo depth chart: starter = first player at position, backups = rest.",
    "Does not consider player quality, minutes, or scheme fit.",
    "Does not project post-transaction depth charts (M3-B will).",
)


def _need_level_for_count(count: int) -> NeedLevel:
    """Map a position's player count to a ``NeedLevel``."""
    if count == 0:
        return NeedLevel.HIGH
    if count == 1:
        return NeedLevel.MEDIUM
    return NeedLevel.LOW


def _group_by_position(
    players: Tuple[RosterPlayer, ...],
) -> Dict[Position, List[RosterPlayer]]:
    """Group players by position, preserving input order within each group."""
    grouped: Dict[Position, List[RosterPlayer]] = {pos: [] for pos in Position}
    for p in players:
        grouped.setdefault(p.position, []).append(p)
    return grouped


def build_depth_chart_from_players(
    team_id: str, players: Tuple[RosterPlayer, ...]
) -> ProjectedDepthChart:
    """Build a ``ProjectedDepthChart`` from an explicit player tuple.

    This is the pure core: no data loading, no I/O. The first player at
    each position (in input order) becomes the starter; the rest become
    backups. Empty positions get ``starter=None`` and ``need_level=high``.
    """
    grouped = _group_by_position(players)
    slots: List[DepthChartSlot] = []
    for pos in Position:  # enum order: PG, SG, SF, PF, C
        bucket = grouped.get(pos, [])
        if bucket:
            starter = bucket[0]
            backups = tuple(bucket[1:])
        else:
            starter = None
            backups = ()
        slots.append(
            DepthChartSlot(
                position=pos,
                starter=starter,
                backups=backups,
                need_level=_need_level_for_count(len(bucket)),
            )
        )
    return ProjectedDepthChart(
        team_id=team_id,
        slots=tuple(slots),
        roster_count=len(players),
        limitations=_MVP_LIMITATIONS,
    )


def project_current_depth_chart(
    team_id: str, data_dir: Path | str = "data"
) -> ProjectedDepthChart:
    """Project the *current* depth chart for ``team_id`` from demo data.

    Raises:
        TeamNotFoundError: if ``team_id`` is not in ``teams.json``.
        PlayersFileMissingError: if ``players.json`` is missing/malformed.
    """
    players = load_roster_players(team_id, data_dir)
    return build_depth_chart_from_players(team_id, players)
