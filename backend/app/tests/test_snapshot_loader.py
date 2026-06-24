"""Tests for ``snapshot_loader`` (M8-B Core).

Coverage:

1. Loader returns SnapshotBundle for valid fixture.
2. Loader raises on invalid fixture.
3. Loader raises on missing snapshot.
4. resolve_snapshot_dir finds the right directory.
5. load_normalized_json returns the expected top-level value.
6. SnapshotBundle.data_mode is always "snapshot".
7. SnapshotBundle has correct row counts from the valid fixture.

Run:

    python -m pytest backend/app/tests/test_snapshot_loader.py -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.services.snapshot_loader import (
    SnapshotBundle,
    SnapshotLoadError,
    SnapshotNotFoundError,
    SnapshotValidationError,
    load_normalized_json,
    load_snapshot,
    resolve_snapshot_dir,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "backend" / "app" / "tests" / "fixtures" / "snapshots"


# --------------------------------------------------------------------------- #
# Tests: load_snapshot
# --------------------------------------------------------------------------- #


def test_load_snapshot_returns_bundle_for_valid_fixture() -> None:
    """Loading the valid fixture must return a SnapshotBundle with all
    entities populated."""
    bundle = load_snapshot("valid_m8b_small", data_root=FIXTURES_DIR)
    assert isinstance(bundle, SnapshotBundle)
    assert bundle.snapshot_id == "valid_m8b_small"
    assert bundle.data_mode == "snapshot"
    assert len(bundle.teams) == 2
    assert len(bundle.players) == 4
    assert len(bundle.contracts) == 4
    assert len(bundle.free_agents) == 1
    assert isinstance(bundle.cap_config, dict)
    assert bundle.cap_config.get("season") == "2026-2027"
    assert len(bundle.evidence_notes) == 1
    assert bundle.validation_result.is_valid is True


def test_load_snapshot_raises_on_invalid_fixture() -> None:
    """Loading an invalid fixture must raise SnapshotValidationError."""
    with pytest.raises(SnapshotValidationError) as exc_info:
        load_snapshot("invalid_bad_salary", data_root=FIXTURES_DIR)
    assert exc_info.value.result.is_valid is False
    assert len(exc_info.value.result.errors) > 0


def test_load_snapshot_raises_on_missing_snapshot() -> None:
    """Loading a non-existent snapshot must raise SnapshotNotFoundError."""
    with pytest.raises(SnapshotNotFoundError):
        load_snapshot("does_not_exist", data_root=FIXTURES_DIR)


def test_load_snapshot_without_validation_skips_check() -> None:
    """When validate=False, an invalid fixture should still load
    (the loader trusts the caller)."""
    bundle = load_snapshot(
        "invalid_bad_salary", data_root=FIXTURES_DIR, validate=False
    )
    assert isinstance(bundle, SnapshotBundle)
    assert bundle.data_mode == "snapshot"
    # The bundle still has the (bad) data.
    assert len(bundle.contracts) == 1
    assert bundle.contracts[0]["salary"] == -5000000


# --------------------------------------------------------------------------- #
# Tests: resolve_snapshot_dir
# --------------------------------------------------------------------------- #


def test_resolve_snapshot_dir_finds_existing() -> None:
    """resolve_snapshot_dir must return the directory for a valid ID."""
    path = resolve_snapshot_dir("valid_m8b_small", data_root=FIXTURES_DIR)
    assert path.is_dir()
    assert path.name == "valid_m8b_small"


def test_resolve_snapshot_dir_raises_on_missing() -> None:
    """resolve_snapshot_dir must raise for a non-existent ID."""
    with pytest.raises(SnapshotNotFoundError):
        resolve_snapshot_dir("nope", data_root=FIXTURES_DIR)


# --------------------------------------------------------------------------- #
# Tests: load_normalized_json
# --------------------------------------------------------------------------- #


def test_load_normalized_json_returns_top_level_value() -> None:
    """load_normalized_json must return the value under the top-level key."""
    snapshot_dir = FIXTURES_DIR / "valid_m8b_small"
    teams = load_normalized_json(snapshot_dir, "teams.json", "teams")
    assert isinstance(teams, list)
    assert len(teams) == 2
    assert teams[0]["team_id"] == "SNAP-AAA"


def test_load_normalized_json_raises_on_missing_file() -> None:
    """load_normalized_json must raise SnapshotLoadError for a missing file."""
    snapshot_dir = FIXTURES_DIR / "valid_m8b_small"
    with pytest.raises(SnapshotLoadError):
        load_normalized_json(snapshot_dir, "nonexistent.json", "x")


def test_load_normalized_json_raises_on_missing_key() -> None:
    """load_normalized_json must raise SnapshotLoadError for a missing key."""
    snapshot_dir = FIXTURES_DIR / "valid_m8b_small"
    with pytest.raises(SnapshotLoadError):
        load_normalized_json(snapshot_dir, "teams.json", "wrong_key")


# --------------------------------------------------------------------------- #
# Tests: bundle structure
# --------------------------------------------------------------------------- #


def test_bundle_manifest_is_dict() -> None:
    """The bundle's manifest must be a dict with snapshot_id."""
    bundle = load_snapshot("valid_m8b_small", data_root=FIXTURES_DIR)
    assert isinstance(bundle.manifest, dict)
    assert bundle.manifest["snapshot_id"] == "valid_m8b_small"
    assert bundle.manifest["snapshot_type"] == "test_fixture"


def test_bundle_validation_result_has_row_counts() -> None:
    """The bundle's validation_result must have row_counts."""
    bundle = load_snapshot("valid_m8b_small", data_root=FIXTURES_DIR)
    assert bundle.validation_result.row_counts["teams"] == 2
    assert bundle.validation_result.row_counts["players"] == 4
    assert bundle.validation_result.row_counts["contracts"] == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
