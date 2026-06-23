"""Roster models for FrontOffice-Offseason-Agent (M3-A).

These are DEMO/SAMPLE/SIMULATION models. They represent a deliberately
simplified view of a basketball roster: five standard positions
(PG/SG/SF/PF/C), a starter + backups per position, and a heuristic
notion of "need" per position.

All dataclasses are frozen so callers (including the future agent layer)
cannot mutate roster state in place. The services in
``roster_need_service`` and ``depth_chart_projector`` return new
instances and never write to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple


class Position(str, Enum):
    """The five standard basketball positions used in the demo model."""

    PG = "PG"
    SG = "SG"
    SF = "SF"
    PF = "PF"
    C = "C"


class NeedLevel(str, Enum):
    """Heuristic need level for a depth chart slot.

    - ``high``: no player at the position.
    - ``medium``: exactly one player at the position.
    - ``low``: two or more players at the position.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class NeedPriority(str, Enum):
    """Priority of a ``PositionNeed`` in a ``RosterNeedReport``.

    - ``high``: the team is missing 2+ players vs the target count.
    - ``medium``: the team is missing exactly 1 player.
    - ``low``: the team meets or exceeds the target count.
    """

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class RosterPlayer:
    """A single player on a team's current roster.

    Attributes:
        player_id: Stable player identifier, e.g. ``"pl-001"``.
        name: Display name (demo/fictional).
        team_id: Team identifier, e.g. ``"DEM-ATL"``.
        position: Primary position (``Position``).
        role: Free-form role label, e.g. ``"starter"`` / ``"bench"``.
        contract_id: Optional contract identifier linking to ``contracts.json``.
        salary: Optional current-season salary (cap hit), in USD.
        sample_data: True if this is demo/sample/simulation data.
    """

    player_id: str
    name: str
    team_id: str
    position: Position
    role: str
    contract_id: Optional[str] = None
    salary: Optional[int] = None
    sample_data: bool = False


@dataclass(frozen=True)
class PositionNeed:
    """A single position need in a ``RosterNeedReport``.

    Attributes:
        position: The position this need applies to.
        current_count: How many players the team currently has at this position.
        target_count: The target number of players for this position.
        priority: ``NeedPriority`` derived from the gap.
        reason: Human-readable explanation.
    """

    position: Position
    current_count: int
    target_count: int
    priority: NeedPriority
    reason: str


@dataclass(frozen=True)
class RosterNeedReport:
    """A deterministic roster-need report for a team.

    Attributes:
        team_id: Team identifier.
        roster_count: Total players on the roster.
        needs: Positions where ``current_count < target_count``, sorted
            by priority (high first) then by position order.
        strengths: Positions where ``current_count >= target_count``.
        limitations: Notes about MVP simplifications.
    """

    team_id: str
    roster_count: int
    needs: Tuple[PositionNeed, ...] = field(default_factory=tuple)
    strengths: Tuple[Position, ...] = field(default_factory=tuple)
    limitations: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DepthChartSlot:
    """A single position slot in a ``ProjectedDepthChart``.

    Attributes:
        position: The position for this slot.
        starter: The starting player, or ``None`` if the position is empty.
        backups: Backup players at this position (excluding the starter).
        need_level: ``NeedLevel`` derived from the player count.
    """

    position: Position
    starter: Optional[RosterPlayer] = None
    backups: Tuple[RosterPlayer, ...] = field(default_factory=tuple)
    need_level: NeedLevel = NeedLevel.HIGH


@dataclass(frozen=True)
class ProjectedDepthChart:
    """A deterministic projected depth chart for a team.

    Attributes:
        team_id: Team identifier.
        slots: One ``DepthChartSlot`` per standard position, in
            ``Position`` enum order (PG, SG, SF, PF, C).
        roster_count: Total players represented in the chart.
        limitations: Notes about MVP simplifications.
    """

    team_id: str
    slots: Tuple[DepthChartSlot, ...] = field(default_factory=tuple)
    roster_count: int = 0
    limitations: Tuple[str, ...] = field(default_factory=tuple)
