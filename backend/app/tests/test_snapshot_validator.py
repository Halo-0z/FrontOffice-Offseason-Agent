"""Tests for ``snapshot_validator`` (M8-B Core).

Coverage:

1. Valid snapshot passes validation.
2. Missing manifest fails.
3. Missing required file fails.
4. Invalid JSON fails.
5. Duplicate team ID fails.
6. Duplicate player ID fails.
7. Duplicate contract ID fails.
8. Contract references missing player fails.
9. Contract references missing team fails.
10. Player references missing team fails.
11. Negative salary fails.
12. Invalid cap_config ordering fails.
13. sample_data=true fails.
14. Missing source_name fails.
15. Missing as_of_date fails.
16. Invalid position fails.
17. manual_review_required produces warning but not failure.
18. Roster player without contract produces warning but not failure.

Run:

    python -m pytest backend/app/tests/test_snapshot_validator.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend.app.services.snapshot_validator import (
    SnapshotValidationResult,
    validate_snapshot,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "backend" / "app" / "tests" / "fixtures" / "snapshots"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_snapshot_dir(
    tmp_path: Path,
    name: str,
    manifest: Dict[str, Any],
    files: Dict[str, Any],
) -> Path:
    """Build a minimal snapshot directory under tmp_path."""
    snapshot_dir = tmp_path / name
    normalized = snapshot_dir / "normalized"
    normalized.mkdir(parents=True, exist_ok=True)

    (snapshot_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    for filename, content in files.items():
        (normalized / filename).write_text(
            json.dumps(content, indent=2), encoding="utf-8"
        )
    return snapshot_dir


def _valid_manifest(snapshot_id: str = "test-snap") -> Dict[str, Any]:
    return {
        "snapshot_id": snapshot_id,
        "snapshot_type": "test_fixture",
        "source_name": "m8b_test_fixture",
        "source_url": "https://example.com/m8b-test",
        "as_of_date": "2026-07-01",
        "sample_data": False,
    }


def _valid_teams() -> Dict[str, Any]:
    return {
        "sample_data": False,
        "teams": [
            {
                "team_id": "SNAP-AAA",
                "name": "Team A",
                "abbreviation": "TA",
                "market": "A",
                "sample_data": False,
                "source_name": "m8b_test_fixture",
                "source_url": "https://example.com/m8b-test",
                "as_of_date": "2026-07-01",
            }
        ],
    }


def _valid_players() -> Dict[str, Any]:
    return {
        "sample_data": False,
        "players": [
            {
                "player_id": "sp-001",
                "name": "Player A",
                "team_id": "SNAP-AAA",
                "position": "PG",
                "role": "starter",
                "sample_data": False,
                "source_name": "m8b_test_fixture",
                "source_url": "https://example.com/m8b-test",
                "as_of_date": "2026-07-01",
            }
        ],
    }


def _valid_contracts() -> Dict[str, Any]:
    return {
        "sample_data": False,
        "contracts": [
            {
                "contract_id": "sct-001",
                "player_id": "sp-001",
                "team_id": "SNAP-AAA",
                "salary": 25000000,
                "years_remaining": 2,
                "guaranteed": True,
                "sample_data": False,
                "source_name": "m8b_test_fixture",
                "source_url": "https://example.com/m8b-test",
                "as_of_date": "2026-07-01",
            }
        ],
    }


def _valid_free_agents() -> Dict[str, Any]:
    return {"sample_data": False, "free_agents": []}


def _valid_cap_config() -> Dict[str, Any]:
    return {
        "sample_data": False,
        "cap_config": {
            "season": "2026-2027",
            "salary_cap": 140000000,
            "luxury_tax": 170000000,
            "first_apron": 178000000,
            "second_apron": 189000000,
            "roster_min": 14,
            "roster_max": 15,
            "minimum_salary": 1200000,
            "mid_level_exception": 12800000,
            "sample_data": False,
            "source_name": "m8b_test_fixture",
            "source_url": "https://example.com/m8b-test",
            "as_of_date": "2026-07-01",
        },
    }


def _valid_evidence_notes() -> Dict[str, Any]:
    return {"sample_data": False, "evidence_notes": []}


def _all_valid_files() -> Dict[str, Any]:
    return {
        "teams.json": _valid_teams(),
        "players.json": _valid_players(),
        "contracts.json": _valid_contracts(),
        "free_agents.json": _valid_free_agents(),
        "cap_config.json": _valid_cap_config(),
        "evidence_notes.json": _valid_evidence_notes(),
    }


# --------------------------------------------------------------------------- #
# Tests: valid fixture
# --------------------------------------------------------------------------- #


def test_valid_snapshot_fixture_passes_validation() -> None:
    """The bundled valid_m8b_small fixture must pass cleanly."""
    result = validate_snapshot(FIXTURES_DIR / "valid_m8b_small")
    assert result.is_valid is True
    assert result.errors == ()
    assert result.snapshot_id == "valid_m8b_small"
    assert result.manifest_status == "ok"
    assert result.row_counts["teams"] == 2
    assert result.row_counts["players"] == 4
    assert result.row_counts["contracts"] == 4


def test_valid_snapshot_built_in_memory_passes(tmp_path: Path) -> None:
    """A valid snapshot built in-memory must also pass."""
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "valid_inline", _valid_manifest(), _all_valid_files()
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is True
    assert result.errors == ()


# --------------------------------------------------------------------------- #
# Tests: manifest failures
# --------------------------------------------------------------------------- #


def test_missing_manifest_fails(tmp_path: Path) -> None:
    """Missing manifest.json must fail with manifest_status='missing'."""
    snapshot_dir = tmp_path / "no_manifest"
    (snapshot_dir / "normalized").mkdir(parents=True)
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert result.manifest_status == "missing"
    assert any("manifest" in e for e in result.errors)


def test_invalid_manifest_json_fails(tmp_path: Path) -> None:
    """Corrupt manifest.json must fail with manifest_status='invalid'."""
    snapshot_dir = tmp_path / "bad_manifest"
    (snapshot_dir / "normalized").mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text("{not json", encoding="utf-8")
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert result.manifest_status == "invalid"


def test_missing_source_name_fails(tmp_path: Path) -> None:
    """Manifest without source_name must fail."""
    manifest = _valid_manifest()
    del manifest["source_name"]
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "no_source", manifest, _all_valid_files()
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("source_name" in e for e in result.errors)


def test_missing_as_of_date_fails(tmp_path: Path) -> None:
    """Manifest without as_of_date must fail."""
    manifest = _valid_manifest()
    del manifest["as_of_date"]
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "no_date", manifest, _all_valid_files()
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("as_of_date" in e for e in result.errors)


# --------------------------------------------------------------------------- #
# Tests: required file failures
# --------------------------------------------------------------------------- #


def test_missing_required_file_fails(tmp_path: Path) -> None:
    """Missing contracts.json must fail."""
    files = _all_valid_files()
    del files["contracts.json"]
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "no_contracts", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("contracts.json" in e for e in result.errors)


def test_invalid_json_fails(tmp_path: Path) -> None:
    """Corrupt JSON in a normalized file must fail."""
    snapshot_dir = tmp_path / "bad_json"
    normalized = snapshot_dir / "normalized"
    normalized.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text(
        json.dumps(_valid_manifest()), encoding="utf-8"
    )
    for filename, content in _all_valid_files().items():
        if filename == "players.json":
            (normalized / filename).write_text("{not json", encoding="utf-8")
        else:
            (normalized / filename).write_text(
                json.dumps(content), encoding="utf-8"
            )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("not valid JSON" in e for e in result.errors)


def test_missing_top_level_key_fails(tmp_path: Path) -> None:
    """A file with the wrong top-level key must fail."""
    files = _all_valid_files()
    files["teams.json"] = {"sample_data": False, "wrong_key": []}
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "bad_key", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("top-level key" in e for e in result.errors)


# --------------------------------------------------------------------------- #
# Tests: duplicate IDs
# --------------------------------------------------------------------------- #


def test_duplicate_team_id_fails(tmp_path: Path) -> None:
    """Duplicate team_id must fail."""
    files = _all_valid_files()
    teams = files["teams.json"]["teams"]
    teams.append({**teams[0], "name": "Dup"})
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "dup_team", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("duplicate team_id" in e for e in result.errors)


def test_duplicate_player_id_fails(tmp_path: Path) -> None:
    """Duplicate player_id must fail."""
    files = _all_valid_files()
    players = files["players.json"]["players"]
    players.append({**players[0], "name": "Dup"})
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "dup_player", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("duplicate player_id" in e for e in result.errors)


def test_duplicate_contract_id_fails(tmp_path: Path) -> None:
    """Duplicate contract_id must fail."""
    files = _all_valid_files()
    contracts = files["contracts.json"]["contracts"]
    contracts.append({**contracts[0]})
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "dup_contract", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("duplicate contract_id" in e for e in result.errors)


# --------------------------------------------------------------------------- #
# Tests: reference failures
# --------------------------------------------------------------------------- #


def test_contract_references_missing_player_fails(tmp_path: Path) -> None:
    """Contract referencing a non-existent player must fail."""
    files = _all_valid_files()
    files["contracts.json"]["contracts"][0]["player_id"] = "sp-999"
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "bad_ref_player", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("references missing player" in e for e in result.errors)


def test_contract_references_missing_team_fails(tmp_path: Path) -> None:
    """Contract referencing a non-existent team must fail."""
    files = _all_valid_files()
    files["contracts.json"]["contracts"][0]["team_id"] = "SNAP-ZZZ"
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "bad_ref_team", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("references missing team" in e for e in result.errors)


def test_player_references_missing_team_fails(tmp_path: Path) -> None:
    """Player referencing a non-existent team must fail."""
    files = _all_valid_files()
    files["players.json"]["players"][0]["team_id"] = "SNAP-ZZZ"
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "bad_player_team", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("references missing team" in e for e in result.errors)


# --------------------------------------------------------------------------- #
# Tests: value failures
# --------------------------------------------------------------------------- #


def test_negative_salary_fails(tmp_path: Path) -> None:
    """Negative salary in a contract must fail."""
    files = _all_valid_files()
    files["contracts.json"]["contracts"][0]["salary"] = -5000000
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "neg_salary", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("negative salary" in e for e in result.errors)


def test_invalid_position_fails(tmp_path: Path) -> None:
    """Invalid position must fail."""
    files = _all_valid_files()
    files["players.json"]["players"][0]["position"] = "GK"
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "bad_pos", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("invalid position" in e for e in result.errors)


def test_invalid_cap_config_ordering_fails(tmp_path: Path) -> None:
    """cap_config where luxury_tax < salary_cap must fail."""
    files = _all_valid_files()
    files["cap_config.json"]["cap_config"]["luxury_tax"] = 100000000
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "bad_cap_order", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("ordering invalid" in e for e in result.errors)


# --------------------------------------------------------------------------- #
# Tests: sample_data flag
# --------------------------------------------------------------------------- #


def test_sample_data_true_fails(tmp_path: Path) -> None:
    """A row with sample_data=true must fail."""
    files = _all_valid_files()
    files["teams.json"]["teams"][0]["sample_data"] = True
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "sample_true", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is False
    assert any("sample_data=true" in e for e in result.errors)


# --------------------------------------------------------------------------- #
# Tests: warnings (non-fatal)
# --------------------------------------------------------------------------- #


def test_manual_review_required_produces_warning(tmp_path: Path) -> None:
    """manual_review_required=true must warn, not fail."""
    files = _all_valid_files()
    files["teams.json"]["teams"][0]["manual_review_required"] = True
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "manual_review", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is True
    assert any("manual_review_required" in w for w in result.warnings)


def test_roster_player_without_contract_produces_warning(
    tmp_path: Path,
) -> None:
    """A player with no contract must warn, not fail."""
    files = _all_valid_files()
    # Add a second player with no contract.
    files["players.json"]["players"].append(
        {
            "player_id": "sp-002",
            "name": "Player B",
            "team_id": "SNAP-AAA",
            "position": "SG",
            "role": "bench",
            "sample_data": False,
            "source_name": "m8b_test_fixture",
            "source_url": "https://example.com/m8b-test",
            "as_of_date": "2026-07-01",
        }
    )
    snapshot_dir = _make_snapshot_dir(
        tmp_path, "no_contract", _valid_manifest(), files
    )
    result = validate_snapshot(snapshot_dir)
    assert result.is_valid is True
    assert any("no contract" in w for w in result.warnings)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
