"""Tests for ``depth_chart_projector`` (M3-A).

Coverage:

1. ``project_current_depth_chart`` returns a ``ProjectedDepthChart``.
2. Every standard position (PG/SG/SF/PF/C) has a slot.
3. Starters/backups come from roster players, not hardcoded.
4. An empty position gets ``starter=None`` and ``need_level=high``.
5. A single-player position gets ``need_level=medium``.
6. A multi-player position gets ``need_level=low``.
7. Unknown ``team_id`` raises a clear exception.
8. The projector does not mutate ``data/players.json``.

Run:

    python -m pytest backend/app/tests/test_depth_chart_projector.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.models.roster import (
    DepthChartSlot,
    NeedLevel,
    Position,
    ProjectedDepthChart,
    RosterPlayer,
)
from backend.app.services.cap_sheet_service import TeamNotFoundError
from backend.app.services.depth_chart_projector import (
    build_depth_chart_from_players,
    project_current_depth_chart,
)
from backend.app.services.roster_need_service import load_roster_players

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


# --------------------------------------------------------------------------- #
# 1. project_current_depth_chart returns ProjectedDepthChart
# --------------------------------------------------------------------------- #


def test_project_current_depth_chart_returns_projected_depth_chart() -> None:
    chart = project_current_depth_chart("DEM-ATL", DATA_DIR)
    assert isinstance(chart, ProjectedDepthChart)
    assert chart.team_id == "DEM-ATL"
    assert chart.roster_count == 4  # ATL has 4 demo players
    assert isinstance(chart.slots, tuple)
    assert len(chart.limitations) > 0


# --------------------------------------------------------------------------- #
# 2. Every standard position has a slot
# --------------------------------------------------------------------------- #


def test_every_standard_position_has_slot() -> None:
    chart = project_current_depth_chart("DEM-ATL", DATA_DIR)
    slot_positions = [s.position for s in chart.slots]
    assert slot_positions == [Position.PG, Position.SG, Position.SF, Position.PF, Position.C]


# --------------------------------------------------------------------------- #
# 3. Starters/backups come from roster players, not hardcoded
# --------------------------------------------------------------------------- #


def test_starters_and_backups_come_from_roster_players() -> None:
    players = load_roster_players("DEM-ATL", DATA_DIR)
    chart = project_current_depth_chart("DEM-ATL", DATA_DIR)
    all_player_ids = {p.player_id for p in players}
    chart_player_ids: set[str] = set()
    for slot in chart.slots:
        if slot.starter is not None:
            chart_player_ids.add(slot.starter.player_id)
        for b in slot.backups:
            chart_player_ids.add(b.player_id)
    # Every player in the chart must come from the loaded roster.
    assert chart_player_ids.issubset(all_player_ids)
    # And every roster player must appear in the chart exactly once.
    assert chart_player_ids == all_player_ids
    # roster_count must match.
    assert chart.roster_count == len(players)


def test_roster_count_equals_sum_of_slot_players() -> None:
    chart = project_current_depth_chart("DEM-PDX", DATA_DIR)
    total = sum((1 if s.starter else 0) + len(s.backups) for s in chart.slots)
    assert chart.roster_count == total


# --------------------------------------------------------------------------- #
# 4. Empty position: starter=None, need_level=high
# --------------------------------------------------------------------------- #


def test_empty_position_has_no_starter_and_high_need() -> None:
    # ATL has no centers.
    chart = project_current_depth_chart("DEM-ATL", DATA_DIR)
    center_slot = next(s for s in chart.slots if s.position is Position.C)
    assert center_slot.starter is None
    assert center_slot.backups == ()
    assert center_slot.need_level is NeedLevel.HIGH


# --------------------------------------------------------------------------- #
# 5. Single-player position: need_level=medium
# --------------------------------------------------------------------------- #


def test_single_player_position_is_medium_need() -> None:
    # ATL has exactly 1 PG.
    chart = project_current_depth_chart("DEM-ATL", DATA_DIR)
    pg_slot = next(s for s in chart.slots if s.position is Position.PG)
    assert pg_slot.starter is not None
    assert pg_slot.backups == ()
    assert pg_slot.need_level is NeedLevel.MEDIUM


# --------------------------------------------------------------------------- #
# 6. Multi-player position: need_level=low
# --------------------------------------------------------------------------- #


def test_multi_player_position_is_low_need() -> None:
    # Build a synthetic roster with 2 PGs.
    players = (
        RosterPlayer("p1", "A", "T", Position.PG, "starter"),
        RosterPlayer("p2", "B", "T", Position.PG, "bench"),
    )
    chart = build_depth_chart_from_players("T", players)
    pg_slot = next(s for s in chart.slots if s.position is Position.PG)
    assert pg_slot.starter is not None
    assert pg_slot.starter.player_id == "p1"  # first in input order
    assert len(pg_slot.backups) == 1
    assert pg_slot.backups[0].player_id == "p2"
    assert pg_slot.need_level is NeedLevel.LOW


def test_first_player_in_input_order_is_starter() -> None:
    players = (
        RosterPlayer("p-late", "Late", "T", Position.SF, "bench"),
        RosterPlayer("p-early", "Early", "T", Position.SF, "starter"),
    )
    chart = build_depth_chart_from_players("T", players)
    sf_slot = next(s for s in chart.slots if s.position is Position.SF)
    # Starter is the FIRST in input order, regardless of role label.
    assert sf_slot.starter is not None
    assert sf_slot.starter.player_id == "p-late"
    assert len(sf_slot.backups) == 1


# --------------------------------------------------------------------------- #
# 7. Unknown team_id raises clear exception
# --------------------------------------------------------------------------- #


def test_project_current_depth_chart_raises_for_unknown_team() -> None:
    with pytest.raises(TeamNotFoundError) as exc_info:
        project_current_depth_chart("DOES-NOT-EXIST", DATA_DIR)
    msg = str(exc_info.value)
    assert "DOES-NOT-EXIST" in msg
    assert "DEM-ATL" in msg


# --------------------------------------------------------------------------- #
# 8. Projector does not mutate data/players.json
# --------------------------------------------------------------------------- #


def test_projector_does_not_mutate_players_json() -> None:
    path = DATA_DIR / "players.json"
    before = path.read_bytes()
    project_current_depth_chart("DEM-ATL", DATA_DIR)
    project_current_depth_chart("DEM-PDX", DATA_DIR)
    project_current_depth_chart("DEM-CHI", DATA_DIR)
    after = path.read_bytes()
    assert before == after


# --------------------------------------------------------------------------- #
# Bonus: determinism & immutability
# --------------------------------------------------------------------------- #


def test_depth_chart_is_deterministic() -> None:
    c1 = project_current_depth_chart("DEM-ATL", DATA_DIR)
    c2 = project_current_depth_chart("DEM-ATL", DATA_DIR)
    assert c1 == c2


def test_depth_chart_is_immutable() -> None:
    chart = project_current_depth_chart("DEM-ATL", DATA_DIR)
    with pytest.raises(Exception):
        chart.roster_count = 99  # type: ignore[misc]
    with pytest.raises(Exception):
        chart.slots = ()  # type: ignore[misc]


def test_all_three_demo_teams_project_successfully() -> None:
    for tid in ("DEM-ATL", "DEM-PDX", "DEM-CHI"):
        chart = project_current_depth_chart(tid, DATA_DIR)
        assert chart.team_id == tid
        assert len(chart.slots) == 5
        assert chart.roster_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
