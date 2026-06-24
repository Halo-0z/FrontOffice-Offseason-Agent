"""Tests for the ``validate_snapshot.py`` CLI (M8-B Core).

Coverage:

1. Valid fixture exits 0.
2. Invalid fixture exits nonzero (1).
3. Missing snapshot directory exits nonzero.
4. --snapshot-id resolves via data-root.

Run:

    python -m pytest backend/app/tests/test_validate_snapshot_cli.py -v
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES_DIR = REPO_ROOT / "backend" / "app" / "tests" / "fixtures" / "snapshots"
CLI_PATH = REPO_ROOT / "backend" / "scripts" / "validate_snapshot.py"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run the CLI with the given args and capture output."""
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_cli_valid_fixture_exits_zero() -> None:
    """The CLI must exit 0 for a valid snapshot."""
    result = _run_cli("--path", str(FIXTURES_DIR / "valid_m8b_small"))
    assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
    body = json.loads(result.stdout)
    assert body["is_valid"] is True
    assert body["snapshot_id"] == "valid_m8b_small"
    assert body["manifest_status"] == "ok"
    assert body["row_counts"]["teams"] == 2


def test_cli_invalid_fixture_exits_nonzero() -> None:
    """The CLI must exit 1 for an invalid snapshot."""
    result = _run_cli("--path", str(FIXTURES_DIR / "invalid_bad_salary"))
    assert result.returncode == 1
    body = json.loads(result.stdout)
    assert body["is_valid"] is False
    assert len(body["errors"]) > 0
    assert any("negative salary" in e for e in body["errors"])


def test_cli_missing_snapshot_exits_nonzero() -> None:
    """The CLI must exit 1 for a non-existent snapshot directory."""
    result = _run_cli("--path", str(FIXTURES_DIR / "does_not_exist"))
    assert result.returncode == 1


def test_cli_snapshot_id_resolves_via_data_root() -> None:
    """The CLI must resolve --snapshot-id via --data-root."""
    result = _run_cli(
        "--snapshot-id", "valid_m8b_small",
        "--data-root", str(FIXTURES_DIR),
    )
    assert result.returncode == 0
    body = json.loads(result.stdout)
    assert body["is_valid"] is True


def test_cli_invalid_duplicate_id_exits_nonzero() -> None:
    """The CLI must exit 1 for the duplicate_id fixture."""
    result = _run_cli("--path", str(FIXTURES_DIR / "invalid_duplicate_id"))
    assert result.returncode == 1
    body = json.loads(result.stdout)
    assert body["is_valid"] is False
    assert any("duplicate" in e for e in body["errors"])


def test_cli_invalid_missing_file_exits_nonzero() -> None:
    """The CLI must exit 1 for the missing_file fixture."""
    result = _run_cli("--path", str(FIXTURES_DIR / "invalid_missing_file"))
    assert result.returncode == 1
    body = json.loads(result.stdout)
    assert body["is_valid"] is False


def test_cli_invalid_sample_data_true_exits_nonzero() -> None:
    """The CLI must exit 1 for the sample_data_true fixture."""
    result = _run_cli("--path", str(FIXTURES_DIR / "invalid_sample_data_true"))
    assert result.returncode == 1
    body = json.loads(result.stdout)
    assert body["is_valid"] is False
    assert any("sample_data=true" in e for e in body["errors"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
