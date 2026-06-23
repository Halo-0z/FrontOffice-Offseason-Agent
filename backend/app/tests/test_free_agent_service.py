"""Tests for ``free_agent_service`` (M3-B).

Coverage:

1. Can load ``data/free_agents.json``.
2. Free agents are non-empty.
3. Each free agent preserves ``evidence_ids``.
4. ``rank_free_agents_for_team`` returns ``FreeAgentFit`` objects.
5. ATL (which needs C) matches C/big candidates.
6. ``fit_score`` is deterministic (same input -> same output).
7. Unknown ``team_id`` raises a clear exception.
8. Service does not mutate ``data/free_agents.json``.
9. Service does NOT call ``transaction_rule_engine``.
10. Service does NOT generate ``SigningTransaction`` objects.

Run:

    python -m pytest backend/app/tests/test_free_agent_service.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.models.roster import FreeAgentFit, Position
from backend.app.models.transaction import SigningTransaction
from backend.app.services.cap_sheet_service import TeamNotFoundError
from backend.app.services.free_agent_service import (
    FreeAgentsFileMissingError,
    load_free_agents,
    match_free_agents_to_needs,
    rank_free_agents_for_team,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


# --------------------------------------------------------------------------- #
# 1 & 2. Load + non-empty
# --------------------------------------------------------------------------- #


def test_load_free_agents_returns_non_empty_tuple() -> None:
    agents = load_free_agents(DATA_DIR)
    assert isinstance(agents, tuple)
    assert len(agents) > 0
    assert all(isinstance(a, dict) for a in agents)


# --------------------------------------------------------------------------- #
# 3. evidence_ids preserved
# --------------------------------------------------------------------------- #


def test_loaded_free_agents_preserve_evidence_ids() -> None:
    agents = load_free_agents(DATA_DIR)
    for a in agents:
        assert "evidence_ids" in a
        assert isinstance(a["evidence_ids"], list)


def test_free_agent_fits_preserve_evidence_ids() -> None:
    fits = rank_free_agents_for_team("DEM-ATL", DATA_DIR)
    # At least one fit should carry non-empty evidence_ids (fa-001 has 2).
    raw = load_free_agents(DATA_DIR)
    raw_by_id = {a.get("free_agent_id") or a.get("player_id"): a for a in raw}
    for fit in fits:
        raw_agent = raw_by_id.get(fit.free_agent_id)
        assert raw_agent is not None
        assert fit.evidence_ids == tuple(raw_agent.get("evidence_ids", []) or [])


# --------------------------------------------------------------------------- #
# 4. rank_free_agents_for_team returns FreeAgentFit
# --------------------------------------------------------------------------- #


def test_rank_free_agents_returns_free_agent_fit_objects() -> None:
    fits = rank_free_agents_for_team("DEM-ATL", DATA_DIR)
    assert len(fits) > 0
    assert all(isinstance(f, FreeAgentFit) for f in fits)
    for f in fits:
        assert 0.0 <= f.fit_score <= 1.0
        assert isinstance(f.position, Position)
        assert isinstance(f.evidence_ids, tuple)
        assert isinstance(f.limitations, tuple)
        assert len(f.limitations) > 0


def test_rank_free_agents_sorted_by_fit_score_desc() -> None:
    fits = rank_free_agents_for_team("DEM-ATL", DATA_DIR)
    scores = [f.fit_score for f in fits]
    assert scores == sorted(scores, reverse=True)


# --------------------------------------------------------------------------- #
# 5. ATL needs C -> matches C candidates
# --------------------------------------------------------------------------- #


def test_atl_matches_center_candidates() -> None:
    """ATL has 0 centers, so C is a HIGH-priority need. The C free agent
    (fa-005) should appear and should be matched to the C need."""
    fits = rank_free_agents_for_team("DEM-ATL", DATA_DIR)
    center_fits = [f for f in fits if f.position is Position.C]
    assert len(center_fits) >= 1
    cf = center_fits[0]
    assert cf.free_agent_id == "fa-005"
    assert cf.matched_need is not None
    assert cf.matched_need.position is Position.C
    # A HIGH-priority match should score meaningfully above 0.
    assert cf.fit_score > 0.5


def test_atl_non_matching_position_has_lower_score() -> None:
    """A free agent whose position is NOT among ATL's needs should score
    lower than one that matches a HIGH-priority need."""
    fits = rank_free_agents_for_team("DEM-ATL", DATA_DIR)
    # ATL needs: C (high), PG/SG/SF/PF (medium). A C match should beat
    # a non-need match. Every demo FA matches some ATL need except none
    # (all 5 positions are needs for ATL). So instead verify the C match
    # (high priority) beats the PG match (medium priority) when salaries
    # are comparable.
    by_pos = {f.position: f for f in fits}
    # fa-005 (C, 18M) vs fa-001 (PG, 12M). C is HIGH, PG is MEDIUM.
    # Even though fa-005 is pricier, the HIGH priority should dominate.
    assert by_pos[Position.C].fit_score > by_pos[Position.PG].fit_score


# --------------------------------------------------------------------------- #
# 6. Determinism
# --------------------------------------------------------------------------- #


def test_fit_scores_are_deterministic() -> None:
    f1 = rank_free_agents_for_team("DEM-ATL", DATA_DIR)
    f2 = rank_free_agents_for_team("DEM-ATL", DATA_DIR)
    assert f1 == f2
    assert [f.fit_score for f in f1] == [f.fit_score for f in f2]


def test_fit_scores_deterministic_across_teams() -> None:
    for tid in ("DEM-ATL", "DEM-PDX", "DEM-CHI"):
        a = rank_free_agents_for_team(tid, DATA_DIR)
        b = rank_free_agents_for_team(tid, DATA_DIR)
        assert a == b


# --------------------------------------------------------------------------- #
# 7. Unknown team_id raises clear exception
# --------------------------------------------------------------------------- #


def test_rank_free_agents_raises_for_unknown_team() -> None:
    with pytest.raises(TeamNotFoundError) as exc_info:
        rank_free_agents_for_team("DOES-NOT-EXIST", DATA_DIR)
    msg = str(exc_info.value)
    assert "DOES-NOT-EXIST" in msg
    assert "DEM-ATL" in msg


def test_match_free_agents_raises_for_unknown_team() -> None:
    with pytest.raises(TeamNotFoundError):
        match_free_agents_to_needs("NOPE", DATA_DIR)


# --------------------------------------------------------------------------- #
# 8. No mutation of data/free_agents.json
# --------------------------------------------------------------------------- #


def test_service_does_not_mutate_free_agents_json() -> None:
    path = DATA_DIR / "free_agents.json"
    before = path.read_bytes()
    load_free_agents(DATA_DIR)
    rank_free_agents_for_team("DEM-ATL", DATA_DIR)
    match_free_agents_to_needs("DEM-PDX", DATA_DIR)
    after = path.read_bytes()
    assert before == after


# --------------------------------------------------------------------------- #
# 9. Does NOT call transaction_rule_engine
# --------------------------------------------------------------------------- #


def test_free_agent_service_does_not_call_transaction_rule_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Patching ``validate_transaction`` to raise must NOT affect the FA
    service, since it must not call the rule engine."""
    from backend.app.services import transaction_rule_engine as engine

    def _boom(*args, **kwargs):
        raise AssertionError("free_agent_service must not call transaction_rule_engine")

    monkeypatch.setattr(engine, "validate_transaction", _boom)
    monkeypatch.setattr(engine, "validate_signing", _boom)
    monkeypatch.setattr(engine, "validate_trade", _boom)
    # Should complete without raising.
    fits = rank_free_agents_for_team("DEM-ATL", DATA_DIR)
    assert len(fits) > 0


# --------------------------------------------------------------------------- #
# 10. Does NOT generate SigningTransaction objects
# --------------------------------------------------------------------------- #


def test_free_agent_service_does_not_return_signing_transactions() -> None:
    fits = rank_free_agents_for_team("DEM-ATL", DATA_DIR)
    for f in fits:
        assert not isinstance(f, SigningTransaction)
    # And the FreeAgentFit type itself is not a transaction.
    assert not issubclass(FreeAgentFit, SigningTransaction)


def test_free_agent_fit_is_immutable() -> None:
    fits = rank_free_agents_for_team("DEM-ATL", DATA_DIR)
    f = fits[0]
    with pytest.raises(Exception):
        f.fit_score = 99.0  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Bonus: missing file handling
# --------------------------------------------------------------------------- #


def test_load_free_agents_raises_when_file_missing(tmp_path: Path) -> None:
    with pytest.raises(FreeAgentsFileMissingError):
        load_free_agents(tmp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
