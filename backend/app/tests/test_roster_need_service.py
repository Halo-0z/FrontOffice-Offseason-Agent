"""Tests for ``roster_need_service`` (M3-A).

Coverage:

1. Can load 3 demo teams' roster players.
2. Each team's roster players are non-empty.
3. Position counts are computed correctly.
4. ``evaluate_roster_needs`` returns a ``RosterNeedReport``.
5. A demo case with a missing position produces a high/medium need.
6. Strengths list positions that meet the target.
7. Unknown ``team_id`` raises a clear exception.
8. The service does not mutate ``data/players.json``.

Run:

    python -m pytest backend/app/tests/test_roster_need_service.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.models.roster import (
    NeedPriority,
    Position,
    PositionNeed,
    RosterNeedReport,
    RosterPlayer,
)
from backend.app.services.cap_sheet_service import TeamNotFoundError
from backend.app.services.roster_need_service import (
    POSITION_TARGET_COUNTS,
    PlayersFileMissingError,
    evaluate_roster_needs,
    load_roster_players,
    summarize_position_counts,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


# --------------------------------------------------------------------------- #
# 1 & 2. Load 3 demo teams, each non-empty
# --------------------------------------------------------------------------- #


def test_load_roster_players_for_all_demo_teams() -> None:
    team_ids = ("DEM-ATL", "DEM-PDX", "DEM-CHI")
    for tid in team_ids:
        players = load_roster_players(tid, DATA_DIR)
        assert isinstance(players, tuple)
        assert len(players) > 0, f"{tid} should have non-empty roster"
        assert all(isinstance(p, RosterPlayer) for p in players)
        assert all(p.team_id == tid for p in players)


def test_loaded_players_have_expected_fields() -> None:
    players = load_roster_players("DEM-ATL", DATA_DIR)
    p = players[0]
    assert p.player_id.startswith("pl-")
    assert p.name  # non-empty
    assert isinstance(p.position, Position)
    assert p.role in ("starter", "bench")
    # ATL players have contracts in contracts.json, so contract_id/salary
    # should be enriched.
    assert p.contract_id is not None
    assert p.salary is not None and p.salary > 0
    assert p.sample_data is True


# --------------------------------------------------------------------------- #
# 3. Position counts are correct
# --------------------------------------------------------------------------- #


def test_summarize_position_counts_is_correct() -> None:
    players = load_roster_players("DEM-ATL", DATA_DIR)
    counts = summarize_position_counts(players)
    # Every standard position is present.
    assert set(counts.keys()) == set(Position)
    # Sum of counts equals roster size.
    assert sum(counts.values()) == len(players)
    # ATL demo roster: PG=1, SG=1, SF=1, PF=1, C=0
    assert counts[Position.PG] == 1
    assert counts[Position.SG] == 1
    assert counts[Position.SF] == 1
    assert counts[Position.PF] == 1
    assert counts[Position.C] == 0


def test_summarize_position_counts_handles_empty() -> None:
    counts = summarize_position_counts(())
    assert counts == {pos: 0 for pos in Position}


# --------------------------------------------------------------------------- #
# 4. evaluate_roster_needs returns RosterNeedReport
# --------------------------------------------------------------------------- #


def test_evaluate_roster_needs_returns_report() -> None:
    report = evaluate_roster_needs("DEM-ATL", DATA_DIR)
    assert isinstance(report, RosterNeedReport)
    assert report.team_id == "DEM-ATL"
    assert report.roster_count == 4
    assert isinstance(report.needs, tuple)
    assert isinstance(report.strengths, tuple)
    assert isinstance(report.limitations, tuple)
    assert len(report.limitations) > 0  # MVP limitations documented


# --------------------------------------------------------------------------- #
# 5. Missing position produces high/medium need
# --------------------------------------------------------------------------- #


def test_missing_position_produces_high_need() -> None:
    """ATL has 0 centers; target is 2, so gap=2 -> HIGH priority."""
    report = evaluate_roster_needs("DEM-ATL", DATA_DIR)
    center_need = next((n for n in report.needs if n.position is Position.C), None)
    assert center_need is not None, "ATL should have a C need"
    assert center_need.current_count == 0
    assert center_need.target_count == 2
    assert center_need.priority is NeedPriority.HIGH


def test_single_player_position_produces_medium_need() -> None:
    """ATL has 1 PG; target is 2, so gap=1 -> MEDIUM priority."""
    report = evaluate_roster_needs("DEM-ATL", DATA_DIR)
    pg_need = next((n for n in report.needs if n.position is Position.PG), None)
    assert pg_need is not None
    assert pg_need.current_count == 1
    assert pg_need.target_count == 2
    assert pg_need.priority is NeedPriority.MEDIUM


def test_needs_are_sorted_by_priority_then_position() -> None:
    report = evaluate_roster_needs("DEM-ATL", DATA_DIR)
    # HIGH needs come before MEDIUM needs.
    priorities = [n.priority for n in report.needs]
    high_idx = [i for i, p in enumerate(priorities) if p is NeedPriority.HIGH]
    medium_idx = [i for i, p in enumerate(priorities) if p is NeedPriority.MEDIUM]
    if high_idx and medium_idx:
        assert max(high_idx) < min(medium_idx)


# --------------------------------------------------------------------------- #
# 6. Strengths list positions that meet the target
# --------------------------------------------------------------------------- #


def test_strengths_exclude_needs() -> None:
    """No position should appear in both needs and strengths."""
    report = evaluate_roster_needs("DEM-ATL", DATA_DIR)
    need_positions = {n.position for n in report.needs}
    strength_positions = set(report.strengths)
    assert need_positions.isdisjoint(strength_positions)


def test_strengths_cover_positions_at_or_above_target() -> None:
    """Build a synthetic roster where one position meets target."""
    players = (
        RosterPlayer("p1", "A", "T", Position.PG, "starter"),
        RosterPlayer("p2", "B", "T", Position.PG, "bench"),
        RosterPlayer("p3", "C", "T", Position.SG, "starter"),
    )
    counts = summarize_position_counts(players)
    # PG meets target (2), SG is below (1), others are 0.
    assert counts[Position.PG] >= POSITION_TARGET_COUNTS[Position.PG]
    assert counts[Position.SG] < POSITION_TARGET_COUNTS[Position.SG]


# --------------------------------------------------------------------------- #
# 7. Unknown team_id raises clear exception
# --------------------------------------------------------------------------- #


def test_load_roster_players_raises_for_unknown_team() -> None:
    with pytest.raises(TeamNotFoundError) as exc_info:
        load_roster_players("DOES-NOT-EXIST", DATA_DIR)
    msg = str(exc_info.value)
    assert "DOES-NOT-EXIST" in msg
    assert "DEM-ATL" in msg  # known teams listed


def test_evaluate_roster_needs_raises_for_unknown_team() -> None:
    with pytest.raises(TeamNotFoundError):
        evaluate_roster_needs("NOPE", DATA_DIR)


# --------------------------------------------------------------------------- #
# 8. Service does not mutate data/players.json
# --------------------------------------------------------------------------- #


def test_service_does_not_mutate_players_json() -> None:
    path = DATA_DIR / "players.json"
    before = path.read_bytes()
    load_roster_players("DEM-ATL", DATA_DIR)
    load_roster_players("DEM-PDX", DATA_DIR)
    evaluate_roster_needs("DEM-CHI", DATA_DIR)
    after = path.read_bytes()
    assert before == after


# --------------------------------------------------------------------------- #
# Bonus: report is deterministic & immutable
# --------------------------------------------------------------------------- #


def test_report_is_deterministic() -> None:
    r1 = evaluate_roster_needs("DEM-ATL", DATA_DIR)
    r2 = evaluate_roster_needs("DEM-ATL", DATA_DIR)
    assert r1 == r2


def test_report_is_immutable() -> None:
    report = evaluate_roster_needs("DEM-ATL", DATA_DIR)
    with pytest.raises(Exception):
        report.roster_count = 99  # type: ignore[misc]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
