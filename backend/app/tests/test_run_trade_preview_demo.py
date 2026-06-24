"""Tests for the trade preview CLI demo script (M6-D).

These tests verify that:

- The script runs successfully with default args (exit code 0).
- ``--format text`` output contains recognizable trade preview headers.
- ``--format json`` output is valid JSON with the expected keys.
- The trade preview has ``requires_human_approval=True``.
- The trade preview has ``sample_data=True``.
- The trade preview validation status is ``PASS`` (salary matching ok).
- The trade preview has a non-empty ``trade_transaction`` with both teams.
- The trade preview has salary matching info for both teams.
- The trade preview has roster need / depth chart after data (validation passed).
- The script does not mutate any data file.
- The script does not call LLM / MCP.

Run tests:

    python -m pytest backend/app/tests/test_run_trade_preview_demo.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "run_trade_preview_demo.py"
PYTHON = sys.executable


def _run_script(*args: str) -> subprocess.CompletedProcess:
    """Run the trade preview CLI demo script with the given args."""
    cmd = [PYTHON, str(SCRIPT_PATH), *args]
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def _data_file_hashes() -> dict:
    """Return a dict of {filename: sha256} for all data files."""
    import hashlib

    hashes = {}
    for name in (
        "cap_config.json",
        "contracts.json",
        "evidence_notes.json",
        "free_agents.json",
        "players.json",
        "teams.json",
    ):
        p = DATA_DIR / name
        if p.exists():
            hashes[name] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashes


# --------------------------------------------------------------------------- #
# Success path tests
# --------------------------------------------------------------------------- #


def test_script_default_run_succeeds() -> None:
    """The script must run successfully with default args (exit 0)."""
    result = _run_script()
    assert result.returncode == 0, (
        f"script failed: stdout={result.stdout!r}, stderr={result.stderr!r}"
    )
    assert len(result.stdout) > 0


def test_script_text_format_contains_headers() -> None:
    """``--format text`` output must contain recognizable trade headers."""
    result = _run_script("--format", "text")
    assert result.returncode == 0
    assert "TRADE PREVIEW" in result.stdout
    assert "DEM-ATL" in result.stdout
    assert "DEM-PDX" in result.stdout
    assert "Salary Matching" in result.stdout
    assert "requires human approval" in result.stdout.lower()


def test_script_json_format_is_valid_json() -> None:
    """``--format json`` output must be valid JSON."""
    result = _run_script("--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict)


def test_script_json_contains_expected_top_level_keys() -> None:
    """JSON output must contain the expected top-level keys."""
    result = _run_script("--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    for key in (
        "trade_transaction",
        "preview",
        "salary_matching",
        "requires_human_approval",
        "sample_data",
    ):
        assert key in payload, f"missing top-level key: {key}"


def test_script_json_requires_human_approval_is_true() -> None:
    """``requires_human_approval`` must be True at every level."""
    result = _run_script("--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["requires_human_approval"] is True
    assert payload["preview"]["requires_human_approval"] is True
    assert payload["trade_transaction"]["requires_human_approval"] is True
    assert payload["preview"]["validation_result"]["requires_human_approval"] is True


def test_script_json_sample_data_is_true() -> None:
    """``sample_data`` must be True."""
    result = _run_script("--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["sample_data"] is True
    assert payload["trade_transaction"]["sample_data"] is True


def test_script_json_validation_status_is_pass() -> None:
    """The demo trade must PASS validation (salary matching ok for both teams)."""
    result = _run_script("--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    vr = payload["preview"]["validation_result"]
    assert vr["status"] == "PASS"
    assert vr["is_valid"] is True
    assert vr["transaction_type"] == "TWO_TEAM_TRADE"


def test_script_json_has_both_teams() -> None:
    """The trade transaction must reference both DEM-ATL and DEM-PDX."""
    result = _run_script("--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    tx = payload["trade_transaction"]
    assert tx["team_a_id"] == "DEM-ATL"
    assert tx["team_b_id"] == "DEM-PDX"
    assert len(tx["outgoing_from_a"]) > 0
    assert len(tx["outgoing_from_b"]) > 0


def test_script_json_salary_matching_both_teams_pass() -> None:
    """Salary matching must pass for both teams."""
    result = _run_script("--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    sm = payload["salary_matching"]
    assert sm["team_a"]["passed"] is True
    assert sm["team_b"]["passed"] is True


def test_script_json_has_roster_need_and_depth_chart_after() -> None:
    """Because validation passed, roster_need_after and depth_chart_after must be present."""
    result = _run_script("--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    pv = payload["preview"]
    assert pv["roster_need_after"] is not None
    assert pv["depth_chart_after"] is not None
    assert pv["roster_need_after"]["team_id"] == "DEM-ATL"
    assert pv["depth_chart_after"]["team_id"] == "DEM-ATL"
    # Depth chart must have 5 slots (PG, SG, SF, PF, C).
    assert len(pv["depth_chart_after"]["slots"]) == 5


def test_script_json_has_cap_summary_before_and_after() -> None:
    """The validation result must include cap_summary_before and cap_summary_after."""
    result = _run_script("--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    vr = payload["preview"]["validation_result"]
    assert vr["cap_summary_before"] is not None
    assert vr["cap_summary_after"] is not None
    assert vr["cap_summary_before"]["team_id"] == "DEM-ATL"
    assert vr["cap_summary_after"]["team_id"] == "DEM-ATL"


def test_script_json_has_limitations() -> None:
    """The preview must include MVP limitations."""
    result = _run_script("--format", "json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    pv = payload["preview"]
    assert len(pv["limitations"]) > 0
    # Must mention human approval.
    assert any(
        "human approval" in lim.lower() for lim in pv["limitations"]
    )


# --------------------------------------------------------------------------- #
# Data integrity tests
# --------------------------------------------------------------------------- #


def test_script_does_not_mutate_data_files() -> None:
    """The script must not mutate any file under data/."""
    before = _data_file_hashes()
    result = _run_script("--format", "json")
    assert result.returncode == 0
    after = _data_file_hashes()
    assert before == after, "data files were mutated by the script"


# --------------------------------------------------------------------------- #
# Programmatic API tests
# --------------------------------------------------------------------------- #


def test_build_trade_preview_payload_returns_dict() -> None:
    """``build_trade_preview_payload`` must return a dict with expected keys."""
    from backend.scripts.run_trade_preview_demo import build_trade_preview_payload

    payload = build_trade_preview_payload(DATA_DIR)
    assert isinstance(payload, dict)
    assert "trade_transaction" in payload
    assert "preview" in payload
    assert "salary_matching" in payload
    assert payload["requires_human_approval"] is True
    assert payload["sample_data"] is True


def test_build_trade_preview_brief_returns_str() -> None:
    """``build_trade_preview_brief`` must return a non-empty string."""
    from backend.scripts.run_trade_preview_demo import build_trade_preview_brief

    brief = build_trade_preview_brief(DATA_DIR)
    assert isinstance(brief, str)
    assert "TRADE PREVIEW" in brief
    assert "DEM-ATL" in brief
